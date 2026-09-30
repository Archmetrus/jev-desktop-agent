import re

SECRET = re.compile(r"\b(password|passphrase|api\s*key|access\s*token|secret\s*key)\b", re.I)
RISK = re.compile(r"\b(delete|remove|erase|trash|format|shutdown|reboot|send|publish|purchase|buy|checkout|pay|install|uninstall|sudo|sil|gönder|satın)\b", re.I)


def display_command(command):
    return "[Hassas komut gizlendi]" if SECRET.search(command) else command


def requires_confirmation(action, command):
    if action["action"] in ("open_app", "focus_window", "navigate", "wait", "scroll"):
        return False
    if action["action"] == "press_key" and action["key"] in ("enter", "save"):
        return True
    return bool(RISK.search(command) or RISK.search(action.get("label", "")))
