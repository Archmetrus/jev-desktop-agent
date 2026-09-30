"""An on-demand, offline English model in its own project-local interpreter."""
import json
import os
import select
import subprocess
import time

from .client import AgentError
from .config import ROOT


class LayaClient:
    provider = 'laya'
    model = 'laya-english'
    api_key = None

    def __init__(self, timeout=60,device='cpu',threshold=.65):
        if device not in ('cpu','cuda') or not 0<=threshold<=1:
            raise ValueError('INVALID_LAYA_SETTINGS')
        self.device=device
        self.threshold=threshold
        self.timeout = max(timeout, 60)
        self.process = None
        self.poll_callback = None

    def read(self, timeout):
        deadline = time.monotonic() + timeout
        raw = bytearray()
        while time.monotonic() < deadline:
            if self.poll_callback:
                self.poll_callback()
            if not select.select([self.process.stdout], [], [], min(.1, max(0, deadline-time.monotonic())))[0]:
                continue
            part = os.read(self.process.stdout.fileno(), 65536)
            if not part:
                raise AgentError('LAYA_WORKER_STOPPED')
            raw.extend(part)
            if len(raw) > 1_000_000:
                raise AgentError('INVALID_RESPONSE')
            if raw.endswith(b'\n'):
                return json.loads(raw)
        raise AgentError('LAYA_TIMEOUT')

    def start(self):
        if self.process and self.process.poll() is None:
            return
        python = ROOT / '.local/laya/venv/bin/python'
        model = ROOT / '.local/laya/model'
        if not python.exists() or not (model/'model.safetensors').exists():
            raise AgentError('LAYA_NOT_INSTALLED')
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                   HF_HOME=str(ROOT/'.local/laya/hf-cache'), TOKENIZERS_PARALLELISM='false')
        gpu_packages=ROOT/'.local/laya/gpu-packages'
        if self.device=='cuda' and (gpu_packages/'torch').exists():
            # Reuse only linked GPU runtime packages; keep Laya's other dependencies isolated.
            env['PYTHONPATH']=str(gpu_packages)
        # No API keys are needed or passed to the local inference worker.
        for key in ('OPENCODE_API_KEY','OPENROUTER_API_KEY','TYPESAFE_API_KEY','HF_TOKEN'):
            env.pop(key, None)
        self.process = subprocess.Popen([str(python), str(ROOT/'desktop_agent/laya_worker.py'),str(model),self.device],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=ROOT)
        try:
            result = self.read(120)
            if not result.get('ready'):
                raise AgentError('LAYA_GPU_UNAVAILABLE' if result.get('error')=='LAYA_GPU_UNAVAILABLE' else 'LAYA_LOAD_FAILED')
            if result.get('device')!=self.device:
                raise AgentError('LAYA_DEVICE_MISMATCH')
        except BaseException:
            self.close()
            raise

    def evaluate(self, state, questions):
        # Retain the goal and action history before UI text. Long DOM dumps are not prompts.
        if isinstance(state,dict) and 'goal' in state:
            screen = state.get('screen',{})
            state = {'goal':state['goal'], 'history':state.get('history',[])[-3:],
                     'screen':{'title':screen.get('title',''), 'url':screen.get('url',''),
                               'text':screen.get('text','')[:500]},
                     'payloads':state.get('payloads',{}), 'destinations':state.get('destinations',{})}
        try:
            self.start()
            self.process.stdin.write(json.dumps({'state':state,'questions':questions,'threshold':self.threshold}).encode()+b'\n')
            self.process.stdin.flush()
            result = self.read(self.timeout)
            if result.get('error'):
                code=result['error']
                raise AgentError(code if code in ('LAYA_CONTEXT_LIMIT','LAYA_OPTION_LIMIT','LAYA_INFERENCE_FAILED','LAYA_GPU_FALLBACK')
                                 else 'LAYA_INFERENCE_FAILED')
            answers=result['answers']
            self.last_shortlist=result.get('shortlist',{})
            for answer in answers.values():
                if answer.get('type')=='choice':
                    # Laya's entropy confidence is not Jev's confidence scale.
                    answer['confidence']=answer['answer_confidence']
            return answers
        except (OSError, ValueError, KeyError, TypeError):
            self.close()
            raise AgentError('LAYA_INFERENCE_FAILED') from None
        except AgentError as error:
            if error.code in ('LAYA_TIMEOUT','LAYA_WORKER_STOPPED','TASK_CANCELLED'):
                self.close()
            raise

    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            for stream in (self.process.stdin,self.process.stdout):
                stream.close()
            self.process=None
