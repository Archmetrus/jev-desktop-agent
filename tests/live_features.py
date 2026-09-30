"""Local fixture only; no model/API request and no downloads."""
import json
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from http.server import HTTPServer
from threading import Thread
from unittest.mock import Mock

from tests.live_browser import Handler
from desktop_agent.config import load
from desktop_agent.task_agent import TaskAgent
from desktop_agent.tools import Tools
from desktop_agent.features import Features


def main():
    server=HTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    tools=Tools(load('apps.json'))
    client=Mock(provider='offline')
    agent=TaskAgent(client,load('apps.json'),tools,load('config.json'),load('sites.json'))
    with tempfile.TemporaryDirectory(dir='/tmp') as directory:
        agent.features=Features(agent,Path(directory)/'state',[directory])
        def command(text):
            result=agent.process(text)
            print(text,json.dumps(result,ensure_ascii=False),flush=True)
            assert result['success'],result
            return result
        try:
            command(f'Open http://127.0.0.1:{server.server_port}/')
            assert len(command('List tabs')['tabs'])==1
            command('New tab')
            assert len(command('List tabs')['tabs'])==2
            command('Switch tab to "Jev integration fixture"')
            command('Show targets')
            assert agent.features.targets['numbered']
            command('Click number one')
            command('Maximize window');command('/undo')
            command('Tile window left');command('/undo')
            command('Minimize window');command('/undo')
            command('Close tab')
            assert len(command('List tabs')['tabs'])==1
            command('List audio outputs')
            # A separate native fixture, never any existing user application.
            native=subprocess.Popen([sys.executable,'-m','tests.live_fixture'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+10
                window=None
                while time.monotonic()<deadline:
                    window=next((w for w in tools.desktop.windows() if w['pid']==native.pid),None)
                    if window: break
                    time.sleep(.1)
                assert window,'Native fixture window missing'
                tools.desktop.focus_window(window['id'])
                command('Show targets')
                assert agent.features.targets['numbered'],'Native target missing'
                command('Click number one')
            finally:
                native.terminate();native.wait(timeout=5)
            client.evaluate.assert_not_called()
            print('PASS: tabs, numbered targets, maximize/tile/minimize and undo, output listing; no model calls.',flush=True)
        finally:
            if agent.features.overlay: agent.features.overlay.close()
            tools.browser.close(terminate=True);tools.close();server.shutdown()


if __name__=='__main__': main()
