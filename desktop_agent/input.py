"""Allowlisted keyboard and scroll events through the Wayland portal."""
from .client import AgentError
from .shortcuts import GlobalShortcut

KEYS = {"enter": [0xff0d], "escape": [0xff1b], "tab": [0xff09],
        "up": [0xff52], "down": [0xff54], "left": [0xff51], "right": [0xff53],
        "address_bar": [0xffe3, ord('l')], "new_tab": [0xffe3, ord('t')],
        "select_all": [0xffe3, ord('a')], "find": [0xffe3, ord('f')],
        "copy": [0xffe3, ord('c')], "undo": [0xffe3, ord('z')],
        "save": [0xffe3, ord('s')], "back": [0xffe9, 0xff51]}


class Input(GlobalShortcut):
    INTERFACE = "org.freedesktop.portal.RemoteDesktop"

    def ensure(self):
        if self.session:
            return
        import uuid
        result = self.request("CreateSession", session_handle_token="jev_input_" + uuid.uuid4().hex)
        self.session = str(result["session_handle"])
        self.request("SelectDevices", self.dbus.ObjectPath(self.session), types=self.dbus.UInt32(3))
        print("[INPUT] KDE klavye/fare izin penceresi açılırsa onaylayın.", flush=True)
        result = self.request("Start", self.dbus.ObjectPath(self.session), "")
        if int(result.get("devices", 0)) & 3 != 3:
            self.close()
            raise AgentError("INPUT_PERMISSION_DENIED")

    def key(self, name):
        if name not in KEYS:
            raise AgentError("UNKNOWN_KEY")
        self.ensure()
        pressed = []
        try:
            for symbol in KEYS[name]:
                self.portal.NotifyKeyboardKeysym(self.dbus.ObjectPath(self.session), {}, symbol, self.dbus.UInt32(1))
                pressed.append(symbol)
        finally:
            for symbol in reversed(pressed):
                self.portal.NotifyKeyboardKeysym(self.dbus.ObjectPath(self.session), {}, symbol, self.dbus.UInt32(0))
        return {"success": True, "action": "press_key", "verified": False, "key": name}

    def scroll(self, direction, window, cursor):
        self.ensure()
        geometry = window["geometry"]
        self.portal.NotifyPointerMotion(self.dbus.ObjectPath(self.session), {},
            geometry["x"] + geometry["width"] / 2 - cursor["x"],
            geometry["y"] + geometry["height"] / 2 - cursor["y"])
        self.portal.NotifyPointerAxisDiscrete(self.dbus.ObjectPath(self.session), {}, self.dbus.UInt32(0), direction * 3)
        return {"success": True, "action": "scroll", "verified": False}
