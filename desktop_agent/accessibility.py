"""AT-SPI observations and actions bound to the current application's nodes."""
import hashlib
import json
import re
import time
import uuid

from .client import AgentError


class Accessibility:
    def __init__(self):
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        self.api = Atspi
        self.targets = {}

    @staticmethod
    def enable():
        import dbus
        bus = dbus.SessionBus()
        props = dbus.Interface(bus.get_object("org.a11y.Bus", "/org/a11y/bus"),
                               "org.freedesktop.DBus.Properties")
        if not props.Get("org.a11y.Status", "IsEnabled"):
            props.Set("org.a11y.Status", "IsEnabled", dbus.Boolean(True))

    def describe(self, node):
        states = node.get_state_set()
        role = node.get_role_name()
        name = (node.get_name() or "")[:140]
        if "password" in role.lower() or re.search(r"password|secret|token|api.?key", name, re.I):
            return None
        if not states.contains(self.api.StateType.SHOWING) or not states.contains(self.api.StateType.ENABLED):
            return None
        interfaces = node.get_interfaces()
        operations = []
        actions = []
        if "Action" in interfaces:
            action = node.get_action_iface()
            for index in range(action.get_n_actions()):
                verb = (action.get_action_name(index) or '').lower()
                if verb in ("click", "press", "activate", "toggle", "jump", "open"):
                    actions.append(index)
            if actions:
                operations.append("click")
        value = ""
        if "EditableText" in interfaces and states.contains(self.api.StateType.EDITABLE):
            operations.append("type_text")
            if "Text" in interfaces:
                text = node.get_text_iface()
                value = self.api.Text.get_text(text, 0, min(self.api.Text.get_character_count(text), 250))
        if not operations:
            return None
        return {"role": role, "label": name, "value": value,
                "operations": operations, "actions": actions}

    def observe(self, window):
        self.enable()
        self.targets = {}
        elements = []
        if not window:
            return {"source": "desktop", "elements": [], "fingerprint": "no-window"}
        desktop = self.api.get_desktop(0)
        apps = []
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            try:
                if app.get_process_id() == window["pid"]:
                    apps.append(app)
            except Exception:
                continue
        token = uuid.uuid4().hex[:8]
        visited = 0
        started = time.monotonic()
        queue = []
        for app in apps:
            frames = [app.get_child_at_index(i) for i in range(app.get_child_count())]
            active = [frame for frame in frames if frame.get_state_set().contains(self.api.StateType.ACTIVE)]
            exact = [frame for frame in frames if frame.get_name() == window['title']]
            queue.extend(active or exact)
        visible_text = []
        while queue and visited < 700 and len(elements) < 100 and time.monotonic() - started < 2:
            node = queue.pop(0)
            visited += 1
            try:
                description = self.describe(node)
                states = node.get_state_set()
                name = node.get_name() or ''
                role = node.get_role_name().lower()
                if states.contains(self.api.StateType.SHOWING) and name and 'password' not in role and not re.search(r'password|secret|token|api.?key',name,re.I):
                    visible_text.append(name[:140])
                if description:
                    identifier = "a_" + token + "_" + str(len(elements))
                    self.targets[identifier] = {"node": node, "description": description}
                    elements.append({"id": identifier, **{k:v for k,v in description.items() if k != "actions"}})
                if "password" not in node.get_role_name().lower():
                    queue.extend(node.get_child_at_index(i) for i in range(min(node.get_child_count(), 100)))
            except Exception:
                continue
        stable = [{k:v for k,v in item.items() if k != "id"} for item in elements]
        text = '\n'.join(visible_text)[:1800]
        fingerprint = hashlib.sha256(json.dumps([window["id"], stable, text], sort_keys=True).encode()).hexdigest()
        return {"source": "desktop", "window": window, "elements": elements, "fingerprint": fingerprint,
                "accessibility_available": bool(apps), "text": text}

    def target(self, identifier, operation):
        item = self.targets.get(identifier)
        if not item or operation not in item["description"]["operations"]:
            raise AgentError("STALE_TARGET")
        current = self.describe(item["node"])
        if current != item["description"]:
            raise AgentError("STALE_TARGET")
        return item

    def type_text(self, identifier, text):
        item = self.target(identifier, "type_text")
        node = item["node"]
        if not node.get_component_iface().grab_focus():
            raise AgentError("TARGET_FOCUS_FAILED")
        if not node.get_editable_text_iface().set_text_contents(text):
            raise AgentError("TEXT_NOT_VERIFIED")
        current = node.get_text_iface()
        if self.api.Text.get_text(current, 0, self.api.Text.get_character_count(current)) != text:
            raise AgentError("TEXT_NOT_VERIFIED")
        return {"success": True, "action": "type_text", "verified": True, "characters": len(text)}

    def click(self, identifier):
        item = self.target(identifier, "click")
        if not item["node"].get_action_iface().do_action(item["description"]["actions"][0]):
            raise AgentError("CLICK_FAILED")
        return {"success": True, "action": "click", "verified": False}
