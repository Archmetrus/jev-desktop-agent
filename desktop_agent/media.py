"""MPRIS media and PipeWire output controls; never changes microphone gain."""
import json
import subprocess
from .client import AgentError


def run(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise AgentError('SYSTEM_CONTROL_FAILED') from None


def players():
    import dbus
    bus = dbus.SessionBus()
    result = []
    for name in bus.list_names():
        if str(name).startswith('org.mpris.MediaPlayer2.'):
            obj = bus.get_object(name, '/org/mpris/MediaPlayer2')
            props = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
            state = props.GetAll('org.mpris.MediaPlayer2.Player')
            result.append((str(name), obj, state))
    return result


def media(operation):
    import dbus
    available = players()
    playing = [p for p in available if p[2].get('PlaybackStatus') == 'Playing']
    candidates = playing or available
    if not candidates:
        raise AgentError('NO_MEDIA_PLAYER')
    if len(candidates) != 1:
        raise AgentError('AMBIGUOUS_MEDIA_PLAYER')
    name, obj, state = candidates[0]
    methods = {'play':'Play', 'pause':'Pause', 'toggle':'PlayPause', 'next':'Next',
               'previous':'Previous', 'stop':'Stop'}
    capabilities = {'play':'CanPlay','pause':'CanPause','next':'CanGoNext','previous':'CanGoPrevious'}
    if not state.get('CanControl') or (operation in capabilities and not state.get(capabilities[operation])):
        raise AgentError('MEDIA_OPERATION_UNAVAILABLE')
    getattr(dbus.Interface(obj, 'org.mpris.MediaPlayer2.Player'), methods[operation])()
    following = dbus.Interface(obj, 'org.freedesktop.DBus.Properties').GetAll('org.mpris.MediaPlayer2.Player')
    expected = {'play':'Playing','pause':'Paused','stop':'Stopped'}.get(operation)
    return {'success':True,'action':'media','operation':operation,'player':name,
            'verified': bool(expected and following.get('PlaybackStatus') == expected)}


def outputs():
    sinks = json.loads(run('pactl','--format=json','list','sinks'))
    return [{'number':i+1,'name':s['name'],'description':s.get('description',s['name'])}
            for i,s in enumerate(sinks)]


def audio(operation, value=None):
    if operation == 'outputs':
        return {'success':True,'action':'audio_outputs','outputs':outputs()}
    if operation == 'output':
        sinks = outputs()
        if not 1 <= value <= len(sinks):
            raise AgentError('OUTPUT_UNAVAILABLE')
        name = sinks[value-1]['name']
        run('pactl','set-default-sink',name)
        return {'success':True,'action':'audio_output','name':name,
                'verified':run('pactl','get-default-sink') == name}
    if operation == 'volume':
        if not 0 <= value <= 100:
            raise AgentError('INVALID_VOLUME')
        run('wpctl','set-volume','@DEFAULT_AUDIO_SINK@',str(value/100))
    elif operation in ('mute','unmute'):
        run('wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1' if operation=='mute' else '0')
    else:
        raise AgentError('UNSUPPORTED_ACTION')
    state = run('wpctl','get-volume','@DEFAULT_AUDIO_SINK@')
    verified = (abs(float(state.split()[1])-value/100)<.015 if operation=='volume'
                else ('MUTED' in state) == (operation=='mute'))
    return {'success':True,'action':'audio','operation':operation,'state':state,'verified':verified}
