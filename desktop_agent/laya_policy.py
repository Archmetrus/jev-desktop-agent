"""Small, explicit classification inputs for the English decision checkpoint."""
import json
import re

OPERATIONS={
    'click':'Click a visible control, link, or Play button.',
    'type_text':'Type the supplied text into an editable field.',
    'navigate':'Open a website or web search URL.',
    'open_app':'Launch an installed application.',
    'focus_window':'Switch to an existing application window.',
    'select':'Select a dropdown option.',
    'press_key':'Press a named keyboard key or shortcut.',
    'scroll_up':'Scroll upward.', 'scroll_down':'Scroll downward.',
    'wait':'Wait for loading after a previous action.',
    'done':'The requested actions have already been completed.',
    'blocked':'The request has no matching supported action.'}


def request_text(state, operation=None):
    if not isinstance(state,dict) or 'goal' not in state:
        return state
    text='User request: '+state['goal']
    if state.get('history'):
        text+='\nAlready executed actions: '+json.dumps(state['history'][-3:],ensure_ascii=False)
    if operation:
        text+='\nNext action: '+operation
    return text


def operation_question(question):
    return {'type':'choice','instructions':'Select the next action in the user request. '
            'Read already executed actions to choose the remaining step. '
            'Choose done only if the entire request has already been executed.',
            'criteria':{key:OPERATIONS.get(key,value) for key,value in question['criteria'].items()}}


def needed_heads(operation):
    return {'click':['click'], 'type_text':['type_text','text'], 'navigate':['url'],
            'open_app':['app'], 'focus_window':['window'], 'select':['option'],
            'press_key':['key']}.get(operation,[])


def single_click_request(command):
    # A one-click request needs one execution, not a second model decision to stop.
    return bool(re.fullmatch(r'\s*(?:please\s+)?(?:click|tap|play)\s+[^;\n]+',command,re.I)
        and not re.search(r'\b(?:then|and(?: then)?)\s+(?:click|tap|play|type|write|press|open|search|scroll|select)\b',command,re.I))


def action_budget(command):
    unquoted=re.sub(r'"[^"]*"|“[^”]*”|\x27[^\x27]*\x27',' payload ',command)
    extra=re.findall(r'(?:\b(?:and(?:\s+then)?|then)\s+|;\s*)'
        r'(?:click|tap|play|type|write|input|press|open|launch|start|go|navigate|visit|search|'
        r'select|scroll|focus|switch|bring|copy|undo|save)\b',unquoted,re.I)
    return min(8,1+len(extra))


def action_signature(action):
    # Target IDs change every snapshot; compare label and actual payload instead.
    return tuple(action.get(key) for key in ('action','label','application','window','url','text','value','key','direction'))
