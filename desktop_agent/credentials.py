"""Provider-scoped keys in the desktop Secret Service (KWallet on KDE)."""
import shutil
import subprocess

from .client import JevClient


def command(operation, provider):
    if provider not in JevClient.PROVIDERS or not shutil.which('secret-tool'):
        return None
    args=['secret-tool',operation]
    if operation=='store':
        args+=['--label=Jev desktop API key ('+provider+')']
    return args+['application','jev-desktop','provider',provider]


def lookup(provider):
    args=command('lookup',provider)
    if not args:
        return None
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=20)
        return (result.stdout.strip() or None) if result.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):
        return None


def save(provider,key):
    args=command('store',provider)
    if not args or not key:
        return False
    try:
        result=subprocess.run(args,input=key,capture_output=True,text=True,timeout=30)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


def forget(provider):
    args=command('clear',provider)
    if not args:
        return False
    try:
        return subprocess.run(args,capture_output=True,timeout=20).returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False
