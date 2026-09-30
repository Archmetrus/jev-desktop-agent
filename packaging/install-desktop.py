#!/usr/bin/env python3
"""Install this clone's desktop shortcut for the current Linux user."""
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent

def quote(value):
    # Exec quoting first, then desktop-entry string escaping.
    value = str(value)
    if any(c in value for c in '\n\r\x00'):
        raise ValueError('Unsupported newline in launcher path')
    value = value.replace('%', '%%')
    value = ''.join('\\' + c if c in '\\"`$' else c for c in value)
    return ('"' + value + '"').replace('\\', '\\\\')

def main():
    template = ROOT / 'packaging/org.local.Jev.desktop'
    entry = template.read_text().replace('@PROJECT_ROOT@', str(ROOT))
    entry = '\n'.join('Exec=' + quote(shutil.which('konsole') or 'konsole') + ' --workdir ' + quote(ROOT) + ' -e ' + quote(ROOT/'desktop-agent') + ' listen --choose-provider' if line.startswith('Exec=') else line for line in entry.splitlines()) + '\n'
    directory = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'applications'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / template.name
    destination.write_text(entry)
    print(destination)

if __name__ == '__main__':
    main()
