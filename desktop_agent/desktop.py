import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .client import AgentError


class Desktop:
    def __init__(self, apps, timeout=10):
        self.apps, self.timeout = apps, timeout

    def kwin(self, body, arguments=None):
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib

        DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()

        class Reply(dbus.service.Object):
            result = None

            @dbus.service.method("org.local.JevDesktop", in_signature="s", out_signature="")
            def Receive(self, value):
                self.result = json.loads(str(value))

        token = uuid.uuid4().hex
        reply = Reply(bus, "/reply_" + token)
        name = "jev-desktop-" + token
        scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting", introspect=False),
                                   "org.kde.kwin.Scripting")
        script = ("const ARGS=" + json.dumps(arguments or {}) + "; const SERVICE="
                  + json.dumps(bus.get_unique_name()) + "; const REPLY="
                  + json.dumps(reply.__dbus_object_path__) + ";\nconst result = (() => {\n" + body +
                  "\n})();\ncallDBus(SERVICE, REPLY, 'org.local.JevDesktop', 'Receive', JSON.stringify(result));")
        loaded = False
        with tempfile.TemporaryDirectory(prefix="jev-desktop-") as directory:
            path = Path(directory) / "main.js"
            path.write_text(script)
            try:
                identifier = int(scripting.loadScript(str(path), name, signature="ss"))
                if identifier < 0:
                    raise AgentError("WINDOW_VERIFICATION_FAILED")
                loaded = True
                dbus.Interface(bus.get_object("org.kde.KWin", f"/Scripting/Script{identifier}"),
                               "org.kde.kwin.Script").run()
                deadline = time.monotonic() + 3
                context = GLib.MainContext.default()
                while reply.result is None:
                    while context.pending():
                        context.iteration(False)
                    if time.monotonic() >= deadline:
                        raise AgentError("WINDOW_VERIFICATION_FAILED")
                    time.sleep(0.01)
                return reply.result
            finally:
                if loaded:
                    scripting.unloadScript(name, signature="s")
                reply.remove_from_connection()

    def find_window(self, application, activate=False):
        result = self.kwin("""
const match = workspace.windowList().find(w =>
    w.normalWindow && String(w.resourceClass).toLowerCase() === ARGS.expected);
if (match && ARGS.activate) { match.minimized = false; workspace.activeWindow = match; }
return match ? {id:String(match.internalId), active:workspace.activeWindow === match} : {};
""", {"expected": self.apps[application]["window_class"].casefold(), "activate": activate})
        if activate and result.get("id") and not result.get("active"):
            self.focus_window(result['id'])
        return result.get("id")

    def windows(self):
        return self.kwin("""
return {windows: workspace.windowList().filter(w => w.normalWindow).map(w => ({
 id:String(w.internalId), application:String(w.resourceClass), pid:Number(w.pid),
 title:String(w.caption).slice(0,160), active:workspace.activeWindow === w,
 geometry:{x:w.frameGeometry.x,y:w.frameGeometry.y,width:w.frameGeometry.width,height:w.frameGeometry.height}
}))};
""")["windows"]

    def focus_window(self, identifier):
        deadline = time.monotonic() + 2
        while True:
            result = self.kwin("""
const w = workspace.windowList().find(w => String(w.internalId) === ARGS.id && w.normalWindow);
if (!w) return {};
w.minimized = false; workspace.activeWindow = w;
return {active:workspace.activeWindow === w};
""", {"id": identifier})
            if result.get('active'):
                break
            if time.monotonic() >= deadline:
                raise AgentError("WINDOW_FOCUS_FAILED")
            time.sleep(0.1)
        return {"success": True, "action": "focus_window", "verified": True}

    def cursor(self):
        return self.kwin("return {x:workspace.cursorPos.x,y:workspace.cursorPos.y};")

    def open_app(self, application):
        if application not in self.apps:
            raise AgentError("UNKNOWN_APPLICATION")
        argv = self.apps[application]["command"]
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
            raise AgentError("INVALID_APPLICATION_CONFIG")
        if not shutil.which(argv[0]):
            raise AgentError("APPLICATION_NOT_INSTALLED")
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            window = self.find_window(application, activate=True)
            if window:
                return {"success": True, "action": "open_app", "application": application,
                        "verified": True, "focused": True, "window": window}
            if process.poll() not in (None, 0):
                raise AgentError("APPLICATION_LAUNCH_FAILED")
            time.sleep(0.2)
        raise AgentError("WINDOW_NOT_FOUND")

    def manage_window(self, operation, number=None):
        if operation not in ('maximize','minimize','left','right','restore','desktop'):
            raise AgentError('UNSUPPORTED_ACTION')
        result = self.kwin("""
const w=workspace.activeWindow;
if (!w || !w.normalWindow) return {error:'NO_ACTIVE_WINDOW'};
const g=w.frameGeometry;
const before={id:String(w.internalId), active:workspace.activeWindow===w, minimized:w.minimized,
 maximizedH:Boolean(Number(w.maximizeMode)&2), maximizedV:Boolean(Number(w.maximizeMode)&1),
 geometry:{x:g.x,y:g.y,width:g.width,height:g.height}, desktops:w.desktops.map(d=>d.id)};
if (ARGS.operation==='desktop') {
 const d=workspace.desktops[ARGS.number-1];
 if (!d) return {error:'DESKTOP_UNAVAILABLE'};
 w.desktops=[d];
} else if (ARGS.operation==='minimize') w.minimized=true;
else if (ARGS.operation==='maximize') {w.minimized=false;w.setMaximize(true,true);}
else if (ARGS.operation==='restore') {w.minimized=false;w.setMaximize(false,false);}
else {
 w.setMaximize(false,false);
 const area=workspace.clientArea(KWin.MaximizeArea,w);
 const half=Math.floor(area.width/2);
 w.frameGeometry={x:area.x+(ARGS.operation==='right'?half:0),y:area.y,
 width:ARGS.operation==='right'?area.width-half:half,height:area.height};
}
return {id:before.id,before:before};
""", {'operation':operation,'number':number})
        if result.get('error'): raise AgentError(result['error'])
        identifier=result['id']
        deadline=time.monotonic()+2
        while True:
            state=self.kwin("""
const w=workspace.windowList().find(w=>String(w.internalId)===ARGS.id);
if(!w) return {verified:false};
let ok=false;
if(ARGS.operation==='minimize') ok=w.minimized;
else if(ARGS.operation==='maximize') ok=Number(w.maximizeMode)===3;
else if(ARGS.operation==='restore') ok=!w.minimized && Number(w.maximizeMode)===0;
else if(ARGS.operation==='desktop') ok=w.desktops.includes(workspace.desktops[ARGS.number-1]);
else {
 const a=workspace.clientArea(KWin.MaximizeArea,w), g=w.frameGeometry, half=Math.floor(a.width/2);
 ok=Math.abs(g.x-(a.x+(ARGS.operation==='right'?half:0)))<4 && Math.abs(g.width-(ARGS.operation==='right'?a.width-half:half))<4;
}
return {verified:Boolean(ok)};
""",{'id':identifier,'operation':operation,'number':number})
            if state['verified']: break
            if time.monotonic()>=deadline: raise AgentError('WINDOW_ACTION_NOT_VERIFIED')
            time.sleep(.05)
        return {'success':True,'action':'window_'+operation,'verified':True,'before':result['before'],
                'after':self.window_state(identifier)}

    def window_state(self, identifier):
        result=self.kwin("""
const w=workspace.windowList().find(w=>String(w.internalId)===ARGS.id);
if (!w) return {error:'WINDOW_NOT_FOUND'};
const g=w.frameGeometry;
return {id:String(w.internalId),active:workspace.activeWindow===w,minimized:w.minimized,
 maximizedH:Boolean(Number(w.maximizeMode)&2),maximizedV:Boolean(Number(w.maximizeMode)&1),
 geometry:{x:g.x,y:g.y,width:g.width,height:g.height},desktops:w.desktops.map(d=>d.id)};
""",{'id':identifier})
        if result.get('error'): raise AgentError(result['error'])
        return result

    def restore_window(self, state, expected=None):
        if expected and self.window_state(state['id'])!=expected:
            raise AgentError('UNDO_CONFLICT')
        result=self.kwin("""
const w=workspace.windowList().find(w=>String(w.internalId)===ARGS.state.id);
if(!w) return {error:'WINDOW_NOT_FOUND'};
const s=ARGS.state;
w.setMaximize(false,false);w.frameGeometry=s.geometry;
w.desktops=workspace.desktops.filter(d=>s.desktops.includes(d.id));
w.setMaximize(s.maximizedV,s.maximizedH);w.minimized=s.minimized;
if(s.active && !s.minimized) workspace.activeWindow=w;
return {success:true};
""",{'state':state})
        if result.get('error'): raise AgentError(result['error'])
        deadline=time.monotonic()+2
        while self.window_state(state['id'])!=state:
            if time.monotonic()>=deadline: raise AgentError('WINDOW_ACTION_NOT_VERIFIED')
            time.sleep(.05)
        return {'success':True,'action':'undo_window','verified':True}
