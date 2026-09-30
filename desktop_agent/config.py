import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    directory = Path(os.environ.get("DESKTOP_AGENT_CONFIG", ROOT / "config"))
    with (directory / name).open() as file:
        return json.load(file)
