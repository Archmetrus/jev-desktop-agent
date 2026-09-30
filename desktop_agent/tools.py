"""Code-owned desktop/browser adapters, with current-window checks."""
import time

from .accessibility import Accessibility
from .browser import Browser
from .client import AgentError
from .desktop import Desktop
from .input import Input

TERMINALS = ("konsole", "terminal", "kitty", "alacritty", "wezterm", "foot", "xterm")


class Tools:
    def __init__(self, apps, timeout=10):
        self.desktop = Desktop(apps, timeout)
        self.browser = Browser()
        self.accessibility = None
        self.input = None
        self.last = None

    def open_app(self, app):
        return self.desktop.open_app(app)

    def observe(self):
        windows = self.desktop.windows()
        window = next((w for w in windows if w["active"]), None)
        if self.browser.socket and window and window["pid"] == self.browser.process.pid:
            screen = self.browser.observe()
            screen["window"] = window
        else:
            if self.accessibility is None:
                self.accessibility = Accessibility()
            screen = self.accessibility.observe(window)
        screen["windows"] = windows
        self.last = screen
        return screen

    def guard_window(self):
        expected = (self.last or {}).get("window")
        current = next((w for w in self.desktop.windows() if w["active"]), None)
        if not current or not expected or current["id"] != expected["id"]:
            raise AgentError("ACTIVE_WINDOW_CHANGED")
        if any(name in current["application"].lower() for name in TERMINALS):
            raise AgentError("TERMINAL_INPUT_BLOCKED")
        return current

    def execute(self, action):
        kind = action["action"]
        if kind == "open_app":
            return self.open_app(action["application"])
        if kind == "focus_window":
            if action["window"] not in {w["id"] for w in self.last["windows"]}:
                raise AgentError("STALE_TARGET")
            return self.desktop.focus_window(action["window"])
        if kind == "navigate":
            result = self.browser.navigate(action["url"])
            # Marionette can be ready before KWin has registered the new window.
            deadline=time.monotonic()+self.desktop.timeout
            own=None
            while time.monotonic()<deadline:
                own=next((w for w in self.desktop.windows() if w['pid']==self.browser.process.pid),None)
                if own:
                    break
                time.sleep(.1)
            if not own:
                raise AgentError('BROWSER_WINDOW_NOT_FOUND')
            self.desktop.focus_window(own["id"])
            result['focused']=True
            return result
        if kind == "wait":
            time.sleep(0.5)
            return {"success": True, "action": "wait", "verified": False}
        window = self.guard_window()
        adapter = self.browser if self.last["source"] == "browser" else self.accessibility
        if kind == "click":
            return adapter.click(action["target"])
        if kind == "type_text":
            return adapter.type_text(action["target"], action["text"])
        if kind == "select" and adapter is self.browser:
            return adapter.select(action["target"], action["value"])
        if kind == "press_key":
            if adapter is self.browser:
                return self.browser.key(action["key"])
            if self.input is None:
                self.input = Input()
            self.input.ensure()
            self.guard_window()  # Permission dialogs must not redirect input.
            return self.input.key(action["key"])
        if kind == "scroll":
            if adapter is self.browser:
                return self.browser.scroll(action["direction"])
            if self.input is None:
                self.input = Input()
            self.input.ensure()
            current = self.guard_window()
            return self.input.scroll(action["direction"], current, self.desktop.cursor())
        raise AgentError("UNSUPPORTED_ACTION")

    def close(self):
        self.browser.close()
        if self.input:
            self.input.close()
