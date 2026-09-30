"""A bounded Firefox DOM adapter using its built-in Marionette server."""
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .client import AgentError
from .config import ROOT

DOM = Path(__file__).with_name("dom.js").read_text()


def valid_url(url):
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def same_destination(requested, observed):
    """Check the requested host/path/query, allowing www and HTTPS upgrades."""
    if not valid_url(requested) or not valid_url(observed):
        return False
    expected,actual=urlsplit(requested),urlsplit(observed)
    try:
        hosts=expected.hostname.removeprefix('www.')==actual.hostname.removeprefix('www.')
        ports=(expected.port or (443 if expected.scheme=='https' else 80)) == (actual.port or (443 if actual.scheme=='https' else 80))
        upgrade=expected.scheme=='http' and actual.scheme=='https' and expected.port is None and actual.port is None
        return (hosts and (ports or upgrade) and expected.path.rstrip('/')==actual.path.rstrip('/')
                and all(pair in parse_qsl(actual.query,keep_blank_values=True)
                        for pair in parse_qsl(expected.query,keep_blank_values=True)))
    except ValueError:
        return False


class Browser:
    def __init__(self):
        self.socket = None
        self.process = None
        self.targets = {}
        self.message_id = 0
        self.last = None

    def receive(self):
        prefix = bytearray()
        while True:
            byte = self.socket.recv(1)
            if not byte:
                raise AgentError("BROWSER_DISCONNECTED")
            if byte == b":":
                break
            prefix.extend(byte)
            if len(prefix) > 10 or not byte.isdigit():
                raise AgentError("BROWSER_PROTOCOL_ERROR")
        size = int(prefix)
        if not 0 < size <= 2_000_000:
            raise AgentError("BROWSER_PROTOCOL_ERROR")
        raw = bytearray()
        while len(raw) < size:
            chunk = self.socket.recv(size - len(raw))
            if not chunk:
                raise AgentError("BROWSER_DISCONNECTED")
            raw.extend(chunk)
        return json.loads(raw)

    def call(self, name, parameters=None):
        try:
            self.message_id += 1
            data = json.dumps([0, self.message_id, name, parameters or {}]).encode()
            self.socket.sendall(str(len(data)).encode() + b":" + data)
            reply = self.receive()
            if not isinstance(reply, list) or len(reply) != 4 or reply[:2] != [1, self.message_id]:
                raise AgentError("BROWSER_PROTOCOL_ERROR")
            if reply[2]:
                code = reply[2].get("error", "")
                raise AgentError({"stale element reference": "STALE_TARGET",
                                  "element click intercepted": "TARGET_COVERED",
                                  "timeout": "BROWSER_TIMEOUT"}.get(code, "BROWSER_ACTION_FAILED"))
            value = reply[3]
            return value.get("value", value) if isinstance(value, dict) else value
        except (OSError, ValueError, TypeError):
            raise AgentError("BROWSER_CONNECTION_FAILED") from None

    def start(self):
        if self.socket is not None:
            try:
                if self.process and self.process.poll() is None and self.call('WebDriver:GetWindowHandles'):
                    return
            except AgentError as error:
                if error.code not in ('BROWSER_DISCONNECTED','BROWSER_CONNECTION_FAILED','BROWSER_ACTION_FAILED'):
                    raise
            self.close(terminate=True)
        if not shutil.which("firefox"):
            raise AgentError("APPLICATION_NOT_INSTALLED")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        directory = ROOT / ".state" / "browsers"
        directory.mkdir(parents=True, exist_ok=True)
        self.profile = Path(tempfile.mkdtemp(prefix="task-", dir=directory))
        self.profile.chmod(0o700)
        prefs = {"marionette.port": port, "marionette.enabled": True,
                 "browser.shell.checkDefaultBrowser": False,
                 "browser.startup.homepage_override.mstone": "ignore", "browser.startup.page": 0,
                 "accessibility.force_disabled": -1}
        (self.profile / "user.js").write_text("\n".join(
            f"user_pref({json.dumps(key)}, {json.dumps(value)});" for key, value in prefs.items()))
        self.process = subprocess.Popen(["firefox", "--no-remote", "--profile", str(self.profile),
                                         "--marionette", "about:blank"],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 12
        try:
            while time.monotonic() < deadline:
                try:
                    self.socket = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    if self.process.poll() is not None:
                        raise AgentError("BROWSER_LAUNCH_FAILED")
                    time.sleep(0.1)
            if self.socket is None:
                raise AgentError("BROWSER_LAUNCH_FAILED")
            self.socket.settimeout(20)
            hello = self.receive()
            if hello.get("applicationType") != "gecko" or hello.get("marionetteProtocol") != 3:
                raise AgentError("BROWSER_PROTOCOL_ERROR")
            session = self.call("WebDriver:NewSession", {"acceptInsecureCerts": False})
            if session.get("capabilities", {}).get("moz:processID") != self.process.pid:
                raise AgentError("BROWSER_IDENTITY_FAILED")
            self.call("WebDriver:SetTimeouts", {"pageLoad": 15000, "script": 5000, "implicit": 0})
        except Exception:
            self.close(terminate=True)
            raise

    def script(self, source, args=None):
        return self.call("WebDriver:ExecuteScript", {"script": source, "args": args or [],
            "newSandbox": False, "sandbox": "jev", "line": 1, "filename": "jev-owned"})

    def observe(self):
        data = self.script(DOM, ["snapshot"])
        token = uuid.uuid4().hex[:8]
        self.targets = {}
        elements = []
        for index, item in enumerate(data.pop("elements")):
            native = item.pop("node")
            identifier = "b_" + token + "_" + str(index)
            self.targets[identifier] = {"native": native, "description": dict(item)}
            elements.append({"id": identifier, **item})
        fingerprint_data = {**data, "elements": [{k:v for k,v in e.items() if k != "id"} for e in elements]}
        data["fingerprint"] = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
        data["elements"] = elements
        data["source"] = "browser"
        self.last = data
        return data

    def target(self, identifier, operation):
        item = self.targets.get(identifier)
        if item is None or operation not in item["description"]["operations"]:
            raise AgentError("STALE_TARGET")
        current = self.script(DOM, ["target", item["native"]])
        expected = item["description"]
        if current is None or current.get("sensitive") or not current.get("enabled"):
            raise AgentError("STALE_TARGET")
        if current.get("covered"):
            raise AgentError("TARGET_COVERED")
        for key in ("role", "label", "value", "selected"):
            if current.get(key) != expected.get(key):
                raise AgentError("STALE_TARGET")
        return next(value for key, value in item["native"].items() if key.startswith("element-"))

    def navigate(self, url):
        if not valid_url(url):
            raise AgentError("INVALID_URL")
        for attempt in range(2):
            self.start()
            try:
                self.call("WebDriver:Navigate", {"url": url})
                break
            except AgentError as error:
                if attempt or error.code not in ('BROWSER_DISCONNECTED','BROWSER_CONNECTION_FAILED'):
                    raise
                self.close(terminate=True)
        observed = self.call("WebDriver:GetCurrentURL")
        if not valid_url(observed):
            raise AgentError("NAVIGATION_NOT_VERIFIED")
        return {"success": True, "action": "navigate", "verified": same_destination(url,observed),
                "destination_host": urlsplit(observed).hostname}

    def click(self, identifier):
        native = self.target(identifier, "click")
        before = self.last["fingerprint"]
        self.call("WebDriver:ElementClick", {"id": native})
        time.sleep(0.2)
        after = self.observe()
        return {"success": True, "action": "click", "verified": before != after["fingerprint"]}

    def type_text(self, identifier, text):
        native = self.target(identifier, "type_text")
        self.call("WebDriver:ElementClear", {"id": native})
        self.call("WebDriver:ElementSendKeys", {"id": native, "text": text, "value": list(text)})
        observed = self.script("return String(arguments[0].value ?? arguments[0].innerText ?? '');",
                               [self.targets[identifier]["native"]])
        if observed != text:
            raise AgentError("TEXT_NOT_VERIFIED")
        return {"success": True, "action": "type_text", "verified": True, "characters": len(text)}

    def scroll(self, direction):
        before = self.script("return Math.round(scrollY);")
        self.script("window.scrollBy(0, arguments[0] * Math.round(innerHeight * 0.7));", [direction])
        time.sleep(0.1)
        after = self.script("return Math.round(scrollY);")
        return {"success": True, "action": "scroll", "verified": before != after}

    def select(self, identifier, value):
        self.target(identifier, "select")
        item = self.targets[identifier]
        if value not in [option["value"] for option in item["description"]["options"]]:
            raise AgentError("UNKNOWN_OPTION")
        changed = self.script("""
const e=arguments[0], value=arguments[1];
if (e.tagName !== 'SELECT' || !Array.from(e.options).some(o => o.value === value && !o.disabled)) return false;
e.value=value; e.dispatchEvent(new Event('input',{bubbles:true}));
e.dispatchEvent(new Event('change',{bubbles:true})); return e.value === value;
""", [item["native"], value])
        if not changed:
            raise AgentError("SELECT_NOT_VERIFIED")
        return {"success": True, "action": "select", "verified": True}

    def key(self, name):
        from .input import KEYS
        if name not in KEYS:
            raise AgentError("UNKNOWN_KEY")
        if name == "new_tab":
            tab = self.call("WebDriver:NewWindow", {"type": "tab"})
            self.call("WebDriver:SwitchToWindow", {"handle": tab["handle"]})
            return {"success": True, "action": "press_key", "key": name, "verified": True}
        if name == "back":
            self.call("WebDriver:Back")
            return {"success": True, "action": "press_key", "key": name, "verified": False}
        symbols = {0xff0d:'\ue007',0xff1b:'\ue00c',0xff09:'\ue004',0xff52:'\ue013',
                   0xff54:'\ue015',0xff51:'\ue012',0xff53:'\ue014',0xffe3:'\ue009',0xffe9:'\ue00a'}
        actions = [{"type":"keyDown","value":symbols.get(key, chr(key))} for key in KEYS[name]]
        actions += [{"type":"keyUp","value":symbols.get(key, chr(key))} for key in reversed(KEYS[name])]
        try:
            self.call("WebDriver:PerformActions", {"actions":[{"type":"key","id":"jev-key","actions":actions}]})
        finally:
            self.call("WebDriver:ReleaseActions")
        return {"success": True, "action": "press_key", "key": name, "verified": False}

    def show_numbers(self, identifiers):
        nodes=[self.targets[i]['native'] for i in identifiers]
        self.script("""
for(const e of document.querySelectorAll('[data-jev-overlay]')) e.remove();
const box=document.createElement('div');box.dataset.jevOverlay='true';
box.setAttribute('aria-hidden','true');
box.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:2147483647';
arguments[0].forEach((node,i)=>{
 const rect=node.getBoundingClientRect(),badge=document.createElement('span');
 badge.textContent=String(i+1);
 badge.style.cssText='position:absolute;background:#164b87;color:white;font:bold 14px sans-serif;padding:3px 6px;border-radius:3px;pointer-events:none';
 badge.style.left=Math.max(0,rect.left)+'px';badge.style.top=Math.max(0,rect.top)+'px';
 box.appendChild(badge);
});
document.documentElement.appendChild(box);
setTimeout(()=>box.remove(),30000);
""",[nodes])

    def hide_numbers(self):
        if self.socket:
            self.script("for(const e of document.querySelectorAll('[data-jev-overlay]')) e.remove();")

    def tabs(self):
        if not self.socket or not self.process or self.process.poll() is not None:
            raise AgentError('NO_TASK_BROWSER')
        original = self.call('WebDriver:GetWindowHandle')
        result = []
        try:
            for handle in self.call('WebDriver:GetWindowHandles'):
                self.call('WebDriver:SwitchToWindow', {'handle':handle})
                result.append({'handle':handle,'title':self.call('WebDriver:GetTitle'),
                               'url':self.call('WebDriver:GetCurrentURL'),'active':handle==original})
        finally:
            self.call('WebDriver:SwitchToWindow', {'handle':original})
        return result

    def tab(self, operation, title=None):
        if operation == 'list':
            return {'success':True,'action':'tabs','tabs':self.tabs()}
        self.tabs()  # Require an existing, owned browser, never capture unrelated tabs.
        if operation == 'new':
            opened = self.call('WebDriver:NewWindow', {'type':'tab'})
            self.call('WebDriver:SwitchToWindow', {'handle':opened['handle']})
        elif operation == 'switch':
            tabs = self.tabs()
            matches = [t for t in tabs if t['title'].casefold()==title.casefold()]
            if not matches:
                matches = [t for t in tabs if title.casefold() in t['title'].casefold()]
            if len(matches)!=1:
                raise AgentError('AMBIGUOUS_TAB' if matches else 'TAB_NOT_FOUND')
            self.call('WebDriver:SwitchToWindow', {'handle':matches[0]['handle']})
        elif operation == 'close':
            remaining = self.call('WebDriver:CloseWindow')
            if remaining:
                self.call('WebDriver:SwitchToWindow', {'handle':remaining[0]})
        else:
            raise AgentError('UNSUPPORTED_ACTION')
        self.targets = {}
        return {'success':True,'action':'tab_'+operation,'verified':True}

    def close(self, terminate=False):
        if self.socket:
            try:
                self.call("WebDriver:DeleteSession")
            except Exception:
                pass
            self.socket.close()
            self.socket = None
        self.targets.clear()
        self.last = None
        if terminate and self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
