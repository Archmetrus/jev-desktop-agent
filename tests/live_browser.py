"""Real Firefox/tool-loop checks using an offline policy, not a paid Jev call."""
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import Mock

from desktop_agent.client import AgentError
from desktop_agent.config import load
from desktop_agent.task_agent import TaskAgent
from desktop_agent.tools import Tools
from desktop_agent.features import Features

PAGE = b'''<!doctype html><title>Jev integration fixture</title>
<label>Search<input id="query"></label>
<button onclick="document.getElementById('result').textContent=document.getElementById('query').value">Apply</button>
<p id="result"></p><label>Category<select><option value="one">One</option><option value="two">Two</option></select></label>
<input type="password" aria-label="Password"><div style="height:1600px"></div>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *args):
        pass


def answer(question, selected):
    assert selected in question['criteria']
    return {'type':'choice','choice':selected,'confidence':0.99,
            'probabilities':{key:float(key==selected) for key in question['criteria']}}


def main(client=None):
    server=HTTPServer(('127.0.0.1',0), Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    tools=Tools(load('apps.json'))
    offline = client is None
    client = client or Mock()
    agent=TaskAgent(client,load('apps.json'),tools,load('config.json'),load('sites.json'))
    state=tempfile.TemporaryDirectory(dir='/tmp')
    agent.features=Features(agent,state.name)
    goal=f'Go to http://127.0.0.1:{server.server_port}/ and type "hello world" in Search and click Apply and select Two and scroll down'

    def evaluate(state,questions):
        step=len(state['history'])
        operation=['navigate','type_text','click','select','scroll_down','done'][step]
        result={'operation':answer(questions['operation'],operation)}
        if operation=='navigate':
            result['url']=answer(questions['url'],'u0')
        elif operation=='type_text':
            result['type_text']=answer(questions['type_text'],next(iter(k for k in questions['type_text']['criteria'] if k!='none')))
            result['text']=answer(questions['text'],'t0')
        elif operation=='click':
            result['click']=answer(questions['click'],next(k for k,v in questions['click']['criteria'].items() if 'Apply' in v))
        elif operation=='select':
            result['option']=answer(questions['option'],next(k for k,v in questions['option']['criteria'].items() if v.endswith(': Two')))
        return result

    if offline:
        client.evaluate.side_effect=evaluate
    try:
        result=agent.process(goal,on_event=lambda event,data:print(event,data,flush=True))
        assert result['success'], result
        assert result['steps']==5, result
        page=tools.browser.last
        assert 'hello world' in page['text']
        # Scroll moved controls offscreen; use a fresh observed control for guard checks.
        tools.browser.scroll(-1)
        screen=tools.browser.observe()
        assert not any(e['label']=='Password' for e in screen['elements'])
        assert next(e['value'] for e in screen['elements'] if e['role']=='select')=='two'
        old=next(e['id'] for e in screen['elements'] if 'type_text' in e['operations'])
        tools.browser.observe()
        try:
            tools.browser.type_text(old,'stale')
        except AgentError as error:
            assert error.code=='STALE_TARGET'
        else:
            raise AssertionError('Old observation target was accepted')
        print('PASS: real navigation/type/click/select/scroll; current targets; password excluded.',flush=True)
    finally:
        tools.browser.close(terminate=True)
        tools.close()
        server.shutdown()
        state.cleanup()


if __name__=='__main__':
    main()
