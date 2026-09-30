"""KDE/Wayland GlobalShortcuts portal: press records, release transcribes."""
import json
import queue
import threading
import time
import uuid

from .client import AgentError
from .safety import display_command


class GlobalShortcut:
    SERVICE = "org.freedesktop.portal.Desktop"
    PATH = "/org/freedesktop/portal/desktop"
    INTERFACE = "org.freedesktop.portal.GlobalShortcuts"

    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop, threads_init
        from gi.repository import GLib
        threads_init()
        DBusGMainLoop(set_as_default=True)
        self.dbus = dbus
        self.bus = dbus.SessionBus()
        self.context = GLib.MainContext.default()
        self.portal = dbus.Interface(self.bus.get_object(self.SERVICE, self.PATH), self.INTERFACE)
        self.session = None
        self.signals = []

    def pump(self):
        while self.context.pending():
            self.context.iteration(False)

    def request(self, method, *args, **options):
        token = "jev_" + uuid.uuid4().hex
        sender = self.bus.get_unique_name()[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        response = []
        match = self.bus.add_signal_receiver(lambda code, values: response.append((int(code), values)),
            signal_name="Response", dbus_interface="org.freedesktop.portal.Request",
            bus_name=self.SERVICE, path=path)
        options["handle_token"] = token
        try:
            actual = str(getattr(self.portal, method)(*args, self.dbus.Dictionary(options, signature="sv")))
            if actual != path:
                raise AgentError("SHORTCUT_REQUEST_FAILED")
            deadline = time.monotonic() + 120
            while not response:
                self.pump()
                if time.monotonic() >= deadline:
                    raise AgentError("SHORTCUT_PERMISSION_TIMEOUT")
                time.sleep(0.02)
            code, values = response[0]
            if code != 0:
                raise AgentError("SHORTCUT_PERMISSION_DENIED")
            return values
        finally:
            match.remove()
            if not response:
                try:
                    self.dbus.Interface(self.bus.get_object(self.SERVICE, path),
                                        "org.freedesktop.portal.Request").Close()
                except self.dbus.DBusException:
                    pass

    def bind(self, trigger, activated, deactivated, emergency=None):
        values = self.request("CreateSession", session_handle_token="jev_" + uuid.uuid4().hex)
        self.session = str(values["session_handle"])
        for name, callback in (("Activated", activated), ("Deactivated", deactivated)):
            def receive(session, identifier, timestamp, options, callback=callback, name=name):
                if str(session) == self.session:
                    if str(identifier) == "talk":
                        callback()
                    elif str(identifier) == "stop" and name == "Activated" and emergency:
                        emergency()
            self.signals.append(self.bus.add_signal_receiver(receive, signal_name=name,
                dbus_interface=self.INTERFACE, bus_name=self.SERVICE, path=self.PATH))
        bindings = [("talk", self.dbus.Dictionary({
            "description": "Jev: basılı tutarak konuş", "preferred_trigger": trigger}, signature="sv"))]
        if emergency:
            bindings.append(("stop", self.dbus.Dictionary({"description":"Jev: görevi durdur",
                "preferred_trigger":"CTRL+ALT+x"}, signature="sv")))
        shortcuts = self.dbus.Array(bindings, signature="(sa{sv})")
        print("[SHORTCUT] KDE izin penceresi açılırsa kısayolu onaylayın.", flush=True)
        result = self.request("BindShortcuts", self.dbus.ObjectPath(self.session), shortcuts, "")
        bindings = {str(identifier): details for identifier,details in result.get('shortcuts',[])}
        if 'talk' not in bindings: raise AgentError('SHORTCUT_NOT_BOUND')
        if emergency and 'stop' not in bindings: raise AgentError('STOP_SHORTCUT_NOT_BOUND')
        return str(bindings['talk'].get('trigger_description',trigger))

    def close(self):
        for match in self.signals:
            match.remove()
        self.signals.clear()
        if self.session:
            try:
                self.dbus.Interface(self.bus.get_object(self.SERVICE, self.session),
                                    "org.freedesktop.portal.Session").Close()
            except self.dbus.DBusException:
                pass
            self.session = None


def hold_to_talk(speech, on_result, trigger="CTRL+ALT+v", agent=None, stop_listening=None):
    speech.check()
    portal = GlobalShortcut()
    results = queue.Queue()
    stop, cancel = threading.Event(), threading.Event()
    worker = None
    busy = False
    application = indicator = None
    if speech.config.get("indicator", True):
        try:
            from .indicator import create_indicator
            application, indicator = create_indicator()
        except ImportError:
            print("[VOICE] Ekran göstergesi kullanılamıyor; terminal durumu gösteriyor.")

    def status(title, details):
        if indicator:
            indicator.changed.emit(title, details)

    def speech_status(message):
        print(message, flush=True)
        if message.startswith("[STT]"):
            status("Çözümleniyor", "Kayıt tamamlandı; İngilizce konuşma çözümleniyor.")

    def record():
        try:
            text = speech.recognize(on_status=speech_status, stop_event=stop, cancel_event=cancel)
            results.put((text, None))
        except AgentError as error:
            results.put((None, error.code))
        except Exception:
            results.put((None, "SPEECH_FAILED"))

    def press():
        nonlocal worker, busy
        if busy:
            return
        busy = True
        stop.clear()
        cancel.clear()
        if agent: agent.cancel.clear()
        print("[MIC] Kısayol basılı: kayıt başlıyor.", flush=True)
        status("Kayıt", "Konuş; Ctrl+Alt+V tuşlarını bırakınca kayıt bitecek.")
        worker = threading.Thread(target=record, daemon=True)
        worker.start()

    def release():
        if busy and not stop.is_set():
            stop.set()
            print("[MIC] Kısayol bırakıldı: kayıt duruyor.", flush=True)
            status("Çözümleniyor", "Kayıt durdu; konuşma çözümlenecek.")

    def emergency():
        cancel.set(); stop.set()
        if agent:
            agent.cancel.set()
        print('[STOP] Bekleyen adımlar iptal edildi.',flush=True)
        status('Beklemede','Görev durduruldu; mikrofon kapalı.')

    def pump():
        if application:
            application.processEvents()
        else:
            try:
                from PySide6.QtWidgets import QApplication
                if QApplication.instance(): QApplication.instance().processEvents()
            except ImportError:
                pass
        portal.pump()

    previous_pump = getattr(agent,'pump',None) if agent else None
    if agent:
        if not hasattr(agent,'cancel'):
            agent.cancel=threading.Event()
        agent.pump=pump
        agent.voice_running=True
    try:
        status("Beklemede", "KDE izin penceresini onaylayın; mikrofon kapalı.")
        description = portal.bind(trigger, press, release, emergency)
        print(f"[SHORTCUT] {description} basılıyken konuş, bırakınca uygula.\n"
              "[MIC] Beklemede: mikrofon kapalı. Ctrl+C ile durdur.", flush=True)
        status("Beklemede", description + " basılı tutarak konuş. Mikrofon kapalı.")
        print('[SHORTCUT] Ctrl+Alt+X: görevi durdur.',flush=True)
        while not (stop_listening and stop_listening.is_set()):
            pump()
            if agent and agent.cancel.is_set() and busy:
                cancel.set();stop.set()
            try:
                text, error = results.get_nowait()
            except queue.Empty:
                time.sleep(0.02)
                continue
            try:
                if error:
                    print("[VOICE] Hata: " + error, flush=True)
                    status("Hata", error + " · Yeni kayıt için kısayolu basılı tut.")
                elif cancel.is_set():
                    status('Beklemede','Kayıt iptal edildi; mikrofon kapalı.')
                else:
                    shown = display_command(text)
                    print("[STT] " + json.dumps(shown, ensure_ascii=False), flush=True)
                    status("Uygulanıyor", shown)
                    if application:
                        application.processEvents()
                    result = on_result(text)
                    if isinstance(result, dict) and not result.get("success"):
                        status("Hata", result.get("error", "EXECUTION_FAILED"))
                    else:
                        status("Beklemede", "Duyulan: " + shown + " · Mikrofon kapalı.")
            finally:
                busy = False
                print("[MIC] Beklemede: mikrofon kapalı.", flush=True)
    except KeyboardInterrupt:
        print("\n[VOICE] Kısayol dinlemesi durdu.")
    except portal.dbus.DBusException:
        raise AgentError("SHORTCUT_PORTAL_FAILED") from None
    finally:
        cancel.set()
        stop.set()
        if worker:
            worker.join(timeout=3)
        portal.close()
        if agent:
            agent.pump=previous_pump
            agent.voice_running=False
        if indicator:
            indicator.close()
            application.processEvents()
