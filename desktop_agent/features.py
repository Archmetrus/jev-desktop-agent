"""Explicit local commands. No model-generated programs or shell expansion."""
import json
import os
import re
import shlex
import time
from pathlib import Path

from .client import AgentError
from .config import ROOT
from .safety import SECRET, requires_confirmation

HELP = '''Media: Play music · Pause music · Next track · Previous track · Stop music
Tabs (task Firefox): List tabs · New tab · Close tab · Switch tab to "title"
Routines: /routine add work = Open Firefox ; Open Konsole · /routine list · Run routine work
Teach: /teach hello = Open Firefox · /aliases · /forget hello
Files: Open file "path" · Find files "name" in "folder" · Create folder "path"
Rename file "path" to "new name" · Move file "path" to "destination" · Trash file "path"
Windows: Maximize window · Minimize window · Tile window left/right · Move window to desktop 2
Targets: Show targets · Click number 2 · /targets
History: /history · Undo last action · /undo
Panel: /panel · Emergency stop: Ctrl+Alt+X while listening · /stop
Audio: Set volume to 40 · Mute audio · Unmute audio · List audio outputs · Use audio output 2'''


def words(value):
    try:
        return shlex.split(value)
    except ValueError:
        raise AgentError('INVALID_COMMAND') from None


class Features:
    def __init__(self, agent, directory=None, roots=None):
        self.agent = agent
        self.directory = Path(directory or ROOT/'.state/features')
        self.roots = [Path(p).resolve() for p in (roots or [ROOT, Path.home()/'Documents',
                        Path.home()/'Downloads', Path.home()/'Music', Path.home()/'Videos',
                        Path.home()/'Pictures', Path.home()/'Desktop'])]
        self.settings = {'aliases':{},'routines':{}}
        self.journal = []
        self.undo_stack = []
        self.targets = None
        self.overlay = None
        self.panel = None
        self.expanding = []
        if (self.directory/'settings.json').exists():
            self.settings = json.loads((self.directory/'settings.json').read_text())
        if (self.directory/'history.json').exists():
            self.journal = json.loads((self.directory/'history.json').read_text())[-200:]

    def save(self, name, value):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory/name
        temporary = path.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
        temporary.replace(path)

    def remember(self, action, result):
        # No dictated text, URLs, API keys or raw screen content in action history.
        record = {'time':time.time(),'action':action,'success':bool(result.get('success')),
                  'verified':bool(result.get('verified'))}
        if result.get('error'):
            record['error'] = result['error']
        self.journal.append(record)
        self.journal = self.journal[-200:]
        self.save('history.json',self.journal)

    def path(self, raw, existing=False, allow_root=False):
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT/path
        path = path.resolve()
        if not any(path.is_relative_to(root) and (allow_root or path != root) for root in self.roots):
            raise AgentError('FILE_PATH_OUTSIDE_ROOTS')
        protected = [ROOT/'.local',ROOT/'.state',ROOT/'.git',ROOT/'.codex',ROOT/'.agents']
        if any(path == p or path.is_relative_to(p) for p in protected) or any(part.startswith('.') for part in path.relative_to(next(r for r in self.roots if path.is_relative_to(r))).parts):
            raise AgentError('PROTECTED_FILE_PATH')
        if existing and not path.exists():
            raise AgentError('FILE_NOT_FOUND')
        return path

    def file(self, args, confirm):
        operation, raw, *rest = args
        from .files import move_no_replace
        raw_path=Path(raw).expanduser()
        if not raw_path.is_absolute(): raw_path=ROOT/raw_path
        if operation in ('rename','move','trash') and raw_path.is_symlink():
            raise AgentError('FILE_SYMLINK_BLOCKED')
        source = self.path(raw, operation != 'mkdir')
        undo = None
        if operation == 'open':
            if source.suffix.casefold() in ('.desktop','.sh','.bash','.py','.exe','.appimage') or (source.is_file() and os.access(source,os.X_OK)):
                raise AgentError('EXECUTABLE_FILE_BLOCKED')
            from .media import run
            run('gio','open',str(source))
        elif operation == 'mkdir':
            try:
                source.mkdir()  # Single folder; never overwrite or create parents implicitly.
            except FileExistsError:
                raise AgentError('DESTINATION_EXISTS') from None
            except PermissionError:
                raise AgentError('FILE_PERMISSION_DENIED') from None
            undo = {'kind':'rmdir','source':str(source),'identity':self.identity(source)}
        elif operation in ('rename','move'):
            if operation == 'rename':
                name = rest[0]
                if name in ('','.', '..') or '/' in name:
                    raise AgentError('INVALID_FILE_NAME')
                target = self.path(str(source.parent/name))
            else:
                target = self.path(rest[0])
            if target.exists() or target.is_symlink():
                raise AgentError('DESTINATION_EXISTS')
            # rename is atomic on one filesystem; cross-filesystem move fails safely.
            move_no_replace(source,target)
            undo = {'kind':'move','source':str(target),'target':str(source),'identity':self.identity(target)}
        elif operation == 'trash':
            if confirm is None or not confirm({'action':'trash_file','path':str(source)}):
                raise AgentError('CONFIRMATION_REQUIRED')
            from .media import run
            self.agent.check_cancel()
            run('gio','trash',str(source))
        if undo:
            self.undo_stack.append(undo)
        return {'success':True,'action':'file_'+operation,'verified':operation!='open',
                'undo_available':bool(undo)}

    @staticmethod
    def identity(path):
        stat = path.stat()
        return (stat.st_dev,stat.st_ino,stat.st_mtime_ns,stat.st_size)

    def undo(self):
        from .files import move_no_replace
        if not self.undo_stack:
            raise AgentError('UNDO_UNAVAILABLE')
        step = self.undo_stack[-1]
        if step['kind'] == 'window':
            result = self.agent.desktop.desktop.restore_window(step['state'],step['after'])
        else:
            source = self.path(step['source'],True)
            if str(source)!=step['source'] or Path(step['source']).is_symlink():
                raise AgentError('UNDO_CONFLICT')
            if self.identity(source) != step['identity']:
                raise AgentError('UNDO_CONFLICT')
            if step['kind']=='rmdir':
                if any(source.iterdir()):
                    raise AgentError('UNDO_CONFLICT')
                source.rmdir()
            else:
                target = self.path(step['target'])
                if target.exists() or target.is_symlink():
                    raise AgentError('UNDO_CONFLICT')
                move_no_replace(source,target)
            result = {'success':True,'action':'undo','verified':True}
        self.undo_stack.pop()
        return result

    def dispatch(self, command, dry_run=False, event=None, confirm=None):
        command = command.strip()
        lower = command.casefold()
        action = None
        if lower in ('/features','/tools'):
            return {'success':True,'action':'help','commands':HELP}
        if lower in ('/stop','stop task','cancel task'):
            if dry_run: return {'success':True,'dry_run':True,'executed':False,'action':'stop'}
            self.agent.cancel.set()
            return {'success':True,'action':'stop','verified':True}
        if lower in ('/history','show action history'):
            return {'success':True,'action':'history','history':self.journal[-30:]}
        if lower in ('/undo','undo last action'):
            action = ('undo',None)
        media_commands = {'play music':'play','resume music':'play','pause music':'pause',
                          'pause video':'pause','resume video':'play','next track':'next',
                          'previous track':'previous','stop music':'stop','toggle playback':'toggle'}
        if lower in media_commands:
            action = ('media',media_commands[lower])
        tabs = {'list tabs':'list','/tabs':'list','new tab':'new','close tab':'close'}
        if lower in tabs:
            action = ('tab',(tabs[lower],None))
        match = re.fullmatch(r'switch tab to (.+)',command,re.I)
        if match:
            parsed = words(match[1]); action = ('tab',('switch',' '.join(parsed)))
        if lower.startswith('/routine add '):
            name,sep,value = command[13:].partition('=')
            name = name.strip().casefold()
            steps = [s.strip() for s in value.split(';') if s.strip()]
            if not sep or not re.fullmatch(r'[a-z0-9 _-]{1,60}',name) or not 1<=len(steps)<=8:
                raise AgentError('INVALID_ROUTINE')
            if any(s.startswith('/') or s.casefold().startswith('run routine ') or SECRET.search(s) for s in steps):
                raise AgentError('INVALID_ROUTINE')
            if dry_run: return {'success':True,'dry_run':True,'executed':False}
            self.settings['routines'][name] = steps
            self.save('settings.json',self.settings)
            return {'success':True,'action':'routine_saved','name':name,'steps':len(steps)}
        if lower in ('/routine list','/routines'):
            return {'success':True,'action':'routines','routines':self.settings['routines']}
        match = re.fullmatch(r'/routine delete (.+)',lower)
        if match:
            if dry_run: return {'success':True,'dry_run':True,'executed':False}
            self.settings['routines'].pop(match[1],None); self.save('settings.json',self.settings)
            return {'success':True,'action':'routine_deleted'}
        if lower.startswith('run routine '):
            action = ('routine',lower[12:].strip())
        if lower.startswith('/teach '):
            name,sep,value = command[7:].partition('='); name=name.strip().casefold(); value=value.strip()
            if not sep or not name or len(name)>100 or not value or value.startswith('/') or SECRET.search(value):
                raise AgentError('INVALID_ALIAS')
            if dry_run: return {'success':True,'dry_run':True,'executed':False}
            self.settings['aliases'][name]=value; self.save('settings.json',self.settings)
            return {'success':True,'action':'alias_saved','name':name}
        if lower=='/aliases':
            return {'success':True,'action':'aliases','aliases':self.settings['aliases']}
        if lower.startswith('/forget '):
            if dry_run: return {'success':True,'dry_run':True,'executed':False}
            self.settings['aliases'].pop(lower[8:].strip(),None);self.save('settings.json',self.settings)
            return {'success':True,'action':'alias_deleted'}
        if lower in self.settings['aliases']:
            action = ('alias',self.settings['aliases'][lower])
        file_patterns = [(r'open file (.+)','open'),(r'create folder (.+)','mkdir'),
                         (r'trash file (.+)','trash'),(r'rename file (.+) to (.+)','rename'),
                         (r'move file (.+) to (.+)','move')]
        for pattern,operation in file_patterns:
            match = re.fullmatch(pattern,command,re.I)
            if match:
                parsed=[words(group) for group in match.groups()]
                if any(len(group)!=1 for group in parsed): raise AgentError('QUOTE_FILE_PATHS')
                action=('file',(operation,*[p[0] for p in parsed]));break
        match = re.fullmatch(r'find files (.+) in (.+)',command,re.I)
        if match:
            parts=[words(g) for g in match.groups()]
            if any(len(p)!=1 for p in parts): raise AgentError('QUOTE_FILE_PATHS')
            action=('find',(parts[0][0],parts[1][0]))
        window_commands={'maximize window':'maximize','minimize window':'minimize',
                         'tile window left':'left','tile window right':'right','restore window':'restore'}
        if lower in window_commands:
            action=('window',(window_commands[lower],None))
        match = re.fullmatch(r'move window to desktop (\d+)',lower)
        if match: action=('window',('desktop',int(match[1])))
        if lower in ('show targets','/targets'):
            action=('targets',None)
        match=re.fullmatch(r'click (?:number|target) (\d+|one|two|three|four|five|six|seven|eight|nine|ten)',lower)
        if match:
            value=match[1];numbers=['one','two','three','four','five','six','seven','eight','nine','ten']
            action=('number',int(value) if value.isdigit() else numbers.index(value)+1)
        if lower in ('/panel','open control panel'): action=('panel',None)
        match = re.fullmatch(r'(?:set )volume(?: to)? (\d+)(?: percent|%)?',lower)
        if match: action=('audio',('volume',int(match[1])))
        if lower in ('mute audio','unmute audio','list audio outputs','/outputs'):
            action=('audio',({'mute audio':'mute','unmute audio':'unmute','list audio outputs':'outputs','/outputs':'outputs'}[lower],None))
        match=re.fullmatch(r'use audio output (\d+)',lower)
        if match: action=('audio',('output',int(match[1])))
        if action is None: return None
        kind,value=action
        if dry_run:
            return {'success':True,'dry_run':True,'executed':False,'network_used':False,'action':kind}
        self.agent.check_cancel()
        if event: event('executing',{'action':kind})
        if kind=='media':
            from .media import media
            return media(value)
        if kind=='tab':
            return self.agent.desktop.browser.tab(*value)
        if kind in ('routine','alias'):
            if (kind,value) in self.expanding or len(self.expanding)>=8 or (kind=='routine' and any(k=='routine' for k,v in self.expanding)):
                raise AgentError('RECURSIVE_COMMAND_BLOCKED')
            steps = self.settings['routines'].get(value) if kind=='routine' else [value]
            if not steps: raise AgentError('ROUTINE_NOT_FOUND')
            self.expanding.append((kind,value))
            results=[]
            try:
                for step in steps:
                    self.agent.check_cancel()
                    result=self.agent._process(step,on_event=event,confirm=confirm)
                    results.append(result)
                    if not result.get('success'): return {**result,'completed_steps':len(results)-1}
            finally: self.expanding.pop()
            return {'success':True,'action':kind,'steps':len(results),'verified':all(r.get('verified') for r in results)}
        if kind=='file': return self.file(value,confirm)
        if kind=='find':
            name,raw=value;folder=self.path(raw,True,allow_root=True)
            matches=[]; scanned=0
            for parent,dirs,files in os.walk(folder,followlinks=False):
                self.agent.check_cancel()
                dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(parent)/d).is_symlink()]
                for item in dirs+files:
                    scanned+=1
                    if name.casefold() in item.casefold(): matches.append(str(Path(parent)/item))
                    if scanned>=10000 or len(matches)>=100: break
                if scanned>=10000 or len(matches)>=100: break
            return {'success':True,'action':'find_files','matches':matches,'truncated':scanned>=10000 or len(matches)>=100}
        if kind=='window':
            result=self.agent.desktop.desktop.manage_window(*value)
            self.undo_stack.append({'kind':'window','state':result.pop('before'),'after':result.pop('after')})
            return result
        if kind=='targets':
            self.targets=self.agent.desktop.observe()
            items=[e for e in self.targets.get('elements',[]) if 'click' in e['operations']]
            self.targets={**self.targets,'numbered':items}
            if self.overlay: self.overlay.close();self.overlay=None
            if self.targets['source']=='browser':
                self.agent.desktop.browser.show_numbers([item['id'] for item in items])
            else:
                from .target_overlay import show_targets
                self.overlay=show_targets(items)
            return {'success':True,'action':'targets','targets':[{'number':i+1,'label':e.get('label','')} for i,e in enumerate(items)]}
        if kind=='number':
            if not self.targets or not 1<=value<=len(self.targets['numbered']): raise AgentError('TARGET_UNAVAILABLE')
            old=self.targets;item=old['numbered'][value-1]
            if self.overlay: self.overlay.close();self.overlay=None
            if old.get('source')=='browser': self.agent.desktop.browser.hide_numbers()
            current=self.agent.desktop.observe()
            if current['fingerprint']!=old['fingerprint'] or (current.get('window') or {}).get('id')!=(old.get('window') or {}).get('id'):
                raise AgentError('STALE_TARGET')
            # Fresh observation regenerates IDs; map by stable order only after fingerprint equality.
            items=[e for e in current.get('elements',[]) if 'click' in e['operations']]
            target=items[value-1]
            descriptor={'action':'click','target':target['id'],'label':target.get('label','')}
            if requires_confirmation(descriptor,command) and (not confirm or not confirm(descriptor)):
                raise AgentError('CONFIRMATION_REQUIRED')
            if self.overlay: self.overlay.close();self.overlay=None
            self.targets=None
            self.agent.check_cancel()
            return self.agent.desktop.execute(descriptor)
        if kind=='undo': return self.undo()
        if kind=='panel':
            if self.panel and self.panel.isVisible():
                self.panel.raise_()
                return {'success':True,'action':'panel_opened'}
            from .panel import show_panel
            self.panel=show_panel(self.agent,self)
            return {'success':True,'action':'panel_opened'}
        if kind=='audio':
            from .media import audio
            return audio(*value)
