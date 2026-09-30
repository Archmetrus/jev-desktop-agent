"""Offline Laya + real Firefox: 61 targets, a named click, exactly one action."""
import json
import tempfile
from http.server import HTTPServer,BaseHTTPRequestHandler
from threading import Thread

from desktop_agent.config import load
from desktop_agent.laya_client import LayaClient
from desktop_agent.task_agent import TaskAgent
from desktop_agent.tools import Tools
from desktop_agent.features import Features


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        page='<title>Laya target test</title><p id="result">Waiting</p>'
        page+=''.join(f'<button>{i} other control</button>' for i in range(60))
        page+='<button onclick="document.getElementById(\'result\').textContent=\'Shorts clicked\'">Shorts</button>'
        if self.path=='/custom':
            page='<title>Custom widget test</title><p id="result">Waiting</p><div tabindex="0" onclick="document.getElementById(\'result\').textContent=\'Continue clicked\'">Continue</div>'
        if self.path=='/shadow':
            page='<title>Shadow widget test</title><p id="result">Waiting</p><div id="host"></div><script>document.getElementById("host").attachShadow({mode:"open"}).innerHTML=`<button onclick="document.getElementById(\'result\').textContent=\'Next clicked\'">Next</button>`;</script>'
        self.wfile.write(page.encode())

    def log_message(self,*args):
        pass


def main(device='cpu'):
    server=HTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    client=LayaClient(device=device)
    tools=Tools(load('apps.json'))
    state=tempfile.TemporaryDirectory(dir='/tmp')
    executed=[]
    try:
        navigation=tools.execute({'action':'navigate','url':f'http://127.0.0.1:{server.server_port}/'})
        screen=tools.observe()
        assert navigation['focused'] and screen['source']=='browser'
        assert len(screen['elements'])==61
        agent=TaskAgent(client,load('apps.json'),tools,load('config.json'),load('sites.json'))
        agent.features=Features(agent,state.name)
        def event(name,data):
            if name=='executing':executed.append(data)
            if name in ('observing','uncertain','shortlist'):print(name,json.dumps(data),flush=True)
        result=agent.process('Click Shorts',on_event=event)
        assert result['success'] and result['steps']==1,result
        assert result['action_effect_verified'],result
        assert len(executed)==1 and executed[0]['label']=='Shorts'
        assert 'Shorts clicked' in tools.browser.observe()['text']
        for path,label in [('/custom','Continue'),('/shadow','Next')]:
            tools.execute({'action':'navigate','url':f'http://127.0.0.1:{server.server_port}{path}'})
            result=agent.process('Click '+label,on_event=event)
            assert result['success'] and result['steps']==1,result
            assert label+' clicked' in tools.browser.observe()['text']
        print(json.dumps({'real_laya_named_click':True,'targets':61,'executed_once':True,
                          'custom_onclick':True,'open_shadow_dom':True,'device':client.device,
                          'threshold':client.threshold}),flush=True)
    finally:
        client.close()
        tools.browser.close(terminate=True)
        tools.close()
        server.shutdown()
        state.cleanup()


if __name__=='__main__':
    main()
