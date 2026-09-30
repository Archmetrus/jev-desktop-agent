"""Private JSON-line inference worker; never downloads models at runtime."""
import contextlib
import json
import re
import sys
from laya_policy import request_text,operation_question,needed_heads


def reply(value):
    print(json.dumps(value),file=sys.__stdout__,flush=True)


try:
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from laya import load
        from laya import cached_embed_fn,embed_fn_from_agent,shortlist_choice
        torch.set_num_threads(4)
        device=sys.argv[2] if len(sys.argv)>2 else 'cpu'
        if device=='cuda' and not torch.cuda.is_available():
            reply({'ready':False,'error':'LAYA_GPU_UNAVAILABLE'})
            raise SystemExit(1)
        agent=load(sys.argv[1],device=device)
        embed=cached_embed_fn(embed_fn_from_agent(agent,max_length=128,batch_size=8),maxsize=512)
    reply({'ready':True,'device':torch.device(agent.device).type})
except Exception:
    reply({'ready':False})
    raise SystemExit(1)

for line in sys.stdin:
    try:
        request=json.loads(line)
        state=request['state']
        rendered=request_text(state)
        rendered=rendered if isinstance(rendered,str) else json.dumps(rendered,ensure_ascii=False)
        if len(agent.tok.encode(rendered,add_special_tokens=False))>1400:
            reply({'error':'LAYA_CONTEXT_LIMIT'})
            continue
        questions=request['questions']
        answers={}
        shortlist_meta={}
        fallbacks_before=getattr(agent,'cpu_fallback_count',0)
        with contextlib.redirect_stdout(sys.stderr):
            if 'operation' in questions:
                result=agent.system_one(rendered,{'operation':operation_question(questions['operation'])},
                    lang='en',max_len=2048,head_max_len=512)
                answers.update(result['answers'])
                operation=answers['operation']['choice']
                # Do not spend time ranking controls for a rejected/low-confidence operation.
                remaining=needed_heads(operation) if answers['operation']['answer_confidence']>=request['threshold'] else []
            else:
                operation=None
                remaining=list(questions)
            for head in remaining:
                original=questions[head]
                question=dict(original)
                if head=='click':
                    question['instructions']='Select the visible control named in the user request. Choose none if no control matches.'
                criteria=original.get('criteria',{})
                if original['type']=='choice' and len(criteria)>12:
                    ranked=shortlist_choice(request_text(state,operation),
                        {k:v for k,v in criteria.items() if k!='none'},embed,k=11)
                    # Keep exact named controls even when the coarse encoder misses them.
                    goal=(state.get('goal','') if isinstance(state,dict) else str(state)).casefold()
                    words=set(re.findall(r'\w+',goal))-{'click','play','press','the','and','in','on','button','link'}
                    scores={k:len(words.intersection(re.findall(r'\w+',str(v).casefold())))
                            for k,v in criteria.items() if k!='none'}
                    exact=sorted((k for k in scores if scores[k]),key=lambda k:-scores[k])
                    labels=list(dict.fromkeys(exact+ranked))[:11]
                    if 'none' in criteria:labels.append('none')
                    question['criteria']={k:criteria[k] for k in labels}
                    shortlist_meta[head]={'original':len(criteria),'kept':len(labels)}
                aliases={}
                if head in ('click','type_text','option','window'):
                    aliases={('none' if key=='none' else 'candidate_'+str(i)):key
                             for i,key in enumerate(question['criteria'])}
                    question['criteria']={alias:question['criteria'][key] for alias,key in aliases.items()}
                result=agent.system_one(request_text(state,operation),{head:question},lang='en',max_len=2048,head_max_len=512)
                if result.get('usage',{}).get('options'):
                    raise ValueError('indistinguishable options')
                answer=result['answers'][head]
                if aliases:
                    answer['choice']=aliases[answer['choice']]
                    answer['probabilities']={aliases[key]:value for key,value in answer['probabilities'].items()}
                if head in shortlist_meta:
                    # Probabilities are conditional on retrieval, not a calibrated full-screen distribution.
                    answer['probabilities']={key:answer['probabilities'].get(key,0.0) for key in criteria}
                    answer['shortlisted']=True
                answers[head]=answer
        if device=='cuda' and getattr(agent,'cpu_fallback_count',0)>fallbacks_before:
            reply({'error':'LAYA_GPU_FALLBACK'})
        else:
            reply({'answers':answers,'shortlist':shortlist_meta})
    except Exception:
        reply({'error':'LAYA_INFERENCE_FAILED'})
