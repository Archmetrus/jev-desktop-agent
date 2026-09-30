import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from desktop_agent.features import Features
from desktop_agent.task_agent import TaskAgent
from desktop_agent.client import AgentError


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        client=Mock(provider='laya',threshold=.65)
        self.agent=TaskAgent(client,{'firefox':{'aliases':['browser']}},Mock(),{}, {})
        self.agent.cancel=threading.Event()
        self.agent.features=self.features=Features(self.agent,self.root/'state',[self.root])
        self.agent.desktop.execute.return_value={'success':True,'action':'open_app','verified':True}

    def command(self,text,**kwargs): return self.agent.process(text,**kwargs)

    def test_media_bypasses_model_and_dry_run_has_no_side_effect(self):
        with patch('desktop_agent.media.media',return_value={'success':True,'action':'media'}) as media:
            self.assertTrue(self.command('Pause music')['success'])
            media.assert_called_once_with('pause')
            self.agent.client.evaluate.assert_not_called()
            self.command('Next track',dry_run=True)
            media.assert_called_once()

    def test_alias_persisted_and_expands_without_model(self):
        self.assertTrue(self.command('/teach browser time = Open Firefox')['success'])
        self.assertTrue(self.command('browser time')['success'])
        self.agent.desktop.execute.assert_called_once()
        self.assertEqual(Features(self.agent,self.root/'state',[self.root]).settings['aliases']['browser time'],'Open Firefox')

    def test_alias_recursion_is_bounded(self):
        self.command('/teach first = second');self.command('/teach second = first')
        self.assertEqual(self.command('first')['error'],'RECURSIVE_COMMAND_BLOCKED')
        self.agent.client.evaluate.assert_not_called()

    def test_routine_stops_at_failure(self):
        self.command('/routine add work = Open Firefox ; Open Firefox ; Open Firefox')
        self.agent.desktop.execute.side_effect=[{'success':True},AgentError('WINDOW_NOT_FOUND')]
        result=self.command('Run routine work')
        self.assertEqual(result['completed_steps'],1)
        self.assertEqual(self.agent.desktop.execute.call_count,2)

    def test_routine_rejects_nested_and_long_or_sensitive_commands(self):
        for definition in ('run routine work','Open Firefox;'*9,'api key hello'):
            self.assertFalse(self.command('/routine add work = '+definition)['success'])

    def test_file_move_and_undo_never_overwrite(self):
        source=self.root/'a.txt';source.write_text('hello')
        dest=self.root/'b.txt'
        result=self.command(f'Move file "{source}" to "{dest}"')
        self.assertTrue(result['verified']);self.assertFalse(source.exists())
        self.assertTrue(self.command('/undo')['success']);self.assertEqual(source.read_text(),'hello')
        dest.write_text('existing')
        self.assertEqual(self.command(f'Move file "{source}" to "{dest}"')['error'],'DESTINATION_EXISTS')
        self.assertEqual(dest.read_text(),'existing')

    def test_undo_conflict_retains_data(self):
        source=self.root/'a.txt';source.write_text('hello');dest=self.root/'b.txt'
        self.command(f'Move file "{source}" to "{dest}"');dest.write_text('changed')
        self.assertEqual(self.command('/undo')['error'],'UNDO_CONFLICT')
        self.assertEqual(dest.read_text(),'changed')

    def test_folder_undo_refuses_nonempty(self):
        folder=self.root/'new';self.command(f'Create folder "{folder}"');(folder/'keep').write_text('x')
        self.assertEqual(self.command('/undo')['error'],'UNDO_CONFLICT')

    def test_symlink_escape_and_hidden_files_blocked(self):
        (self.root/'outside').symlink_to('/etc')
        for raw in (self.root/'outside/passwd',self.root/'.key','/etc/passwd'):
            self.assertFalse(self.command(f'Open file "{raw}"')['success'])

    def test_trash_requires_explicit_confirmation(self):
        source=self.root/'a.txt';source.write_text('x')
        with patch('desktop_agent.media.run') as run:
            self.assertEqual(self.command(f'Trash file "{source}"')['error'],'CONFIRMATION_REQUIRED')
            run.assert_not_called()
            self.assertTrue(self.command(f'Trash file "{source}"',confirm=lambda _:True)['success'])
            run.assert_called_once_with('gio','trash',str(source))

    def test_cancel_between_routine_steps(self):
        self.command('/routine add work = Open Firefox ; Open Firefox')
        def execute(action):
            self.agent.cancel.set();return {'success':True}
        self.agent.desktop.execute.side_effect=execute
        self.assertEqual(self.command('Run routine work')['error'],'TASK_CANCELLED')
        self.agent.desktop.execute.assert_called_once()

    def test_history_omits_command_and_secret_text(self):
        self.command('api key sensitivevalue')
        raw=(self.root/'state/history.json').read_text()
        self.assertNotIn('sensitivevalue',raw)
        self.assertEqual((self.root/'state/history.json').stat().st_mode&0o777,0o600)

    def test_dry_run_does_not_save_alias_or_run_file_operation(self):
        self.command('/teach x = Open Firefox',dry_run=True)
        self.assertFalse(self.features.settings['aliases'])
        self.command(f'Create folder "{self.root}/new"',dry_run=True)
        self.assertFalse((self.root/'new').exists())

    def test_stale_number_does_not_click(self):
        self.features.targets={'fingerprint':'old','numbered':[{'id':'old','operations':['click']}], 'window':{'id':'one'}}
        self.agent.desktop.observe.return_value={'fingerprint':'new','window':{'id':'one'}}
        self.assertEqual(self.command('Click number one')['error'],'STALE_TARGET')
        self.agent.desktop.execute.assert_not_called()

    def test_fresh_number_maps_to_new_target_id(self):
        self.features.targets={'fingerprint':'same','numbered':[{'id':'old','operations':['click']}], 'window':{'id':'one'}}
        self.agent.desktop.observe.return_value={'fingerprint':'same','window':{'id':'one'},
            'elements':[{'id':'fresh','operations':['click'],'label':'Continue'}]}
        self.assertTrue(self.command('Click number one')['success'])
        self.assertEqual(self.agent.desktop.execute.call_args.args[0]['target'],'fresh')

    def test_destructive_number_requires_confirmation(self):
        self.features.targets={'fingerprint':'same','numbered':[{'id':'old'}],'window':{'id':'one'}}
        self.agent.desktop.observe.return_value={'fingerprint':'same','window':{'id':'one'},
            'elements':[{'id':'fresh','operations':['click'],'label':'Delete account'}]}
        self.assertEqual(self.command('Click number one')['error'],'CONFIRMATION_REQUIRED')

    def test_audio_volume_uses_output_only_and_bounds(self):
        from desktop_agent.media import audio
        with patch('desktop_agent.media.run',side_effect=['','Volume: 0.40']) as run:
            self.assertTrue(audio('volume',40)['verified'])
            self.assertIn('@DEFAULT_AUDIO_SINK@',run.call_args_list[0].args)
        with self.assertRaises(AgentError): audio('volume',101)

    def test_routine_can_use_a_taught_alias(self):
        self.command('/teach browser time = Open Firefox')
        self.command('/routine add work = browser time ; Open Firefox')
        self.assertTrue(self.command('Run routine work')['success'])
        self.assertEqual(self.agent.desktop.execute.call_count,2)

    def test_find_can_search_allowed_root_without_mutating_it(self):
        (self.root/'sample.txt').write_text('x')
        result=self.command(f'Find files "sample" in "{self.root}"')
        self.assertEqual(result['matches'],[str(self.root/'sample.txt')])

    def test_stop_after_model_response_prevents_physical_action(self):
        self.agent.desktop.observe.return_value={'source':'desktop','fingerprint':'x','window':None,'windows':[], 'elements':[]}
        self.agent.choices=Mock(return_value=({'operation':{'criteria':{'wait':'wait'}}},{}))
        def evaluate(*args):
            self.agent.cancel.set()
            return {}
        self.agent.client.evaluate.side_effect=evaluate
        self.assertEqual(self.command('Please inspect screen')['error'],'TASK_CANCELLED')
        self.agent.desktop.execute.assert_not_called()

    def test_executable_file_is_not_launched(self):
        source=self.root/'payload.sh';source.write_text('echo hello')
        with patch('desktop_agent.media.run') as run:
            self.assertEqual(self.command(f'Open file "{source}"')['error'],'EXECUTABLE_FILE_BLOCKED')
            run.assert_not_called()

    def test_history_failure_does_not_misreport_successful_action(self):
        with patch.object(self.features,'remember',side_effect=OSError('disk full')):
            result=self.command('Open Firefox')
            self.assertTrue(result['success']);self.assertFalse(result['history_saved'])

    def test_reentrant_command_cannot_reset_cancel_or_execute(self):
        self.agent._task_active=True;self.agent.cancel.set()
        self.assertEqual(self.command('Open Firefox')['error'],'TASK_BUSY')
        self.assertTrue(self.agent.cancel.is_set());self.agent.desktop.execute.assert_not_called()
        self.assertTrue(self.command('/stop')['success'])

    def test_ambiguous_media_player_does_not_receive_commands(self):
        from desktop_agent.media import media
        with patch('desktop_agent.media.players',return_value=[('a',Mock(),{'PlaybackStatus':'Playing'}),
                                                              ('b',Mock(),{'PlaybackStatus':'Playing'})]):
            with self.assertRaises(AgentError) as error: media('pause')
            self.assertEqual(error.exception.code,'AMBIGUOUS_MEDIA_PLAYER')

    def test_media_capability_must_be_supported(self):
        from desktop_agent.media import media
        with patch('desktop_agent.media.players',return_value=[('a',Mock(),{'CanControl':True,'CanGoNext':False})]):
            with self.assertRaises(AgentError) as error: media('next')
            self.assertEqual(error.exception.code,'MEDIA_OPERATION_UNAVAILABLE')

    def test_audio_output_accepts_only_enumerated_index(self):
        from desktop_agent.media import audio
        with patch('desktop_agent.media.outputs',return_value=[{'name':'known-sink'}]),patch('desktop_agent.media.run',side_effect=['','known-sink']) as run:
            self.assertTrue(audio('output',1)['verified'])
            self.assertEqual(run.call_args_list[0].args,('pactl','set-default-sink','known-sink'))
        with patch('desktop_agent.media.outputs',return_value=[]):
            with self.assertRaises(AgentError): audio('output',1)

    def test_window_undo_passes_expected_state(self):
        before={'id':'owned'};after={'id':'owned','x':50}
        self.agent.desktop.desktop.manage_window.return_value={'success':True,'action':'window_left','verified':True,'before':before,'after':after}
        self.agent.desktop.desktop.restore_window.return_value={'success':True,'action':'undo_window','verified':True}
        self.command('Tile window left');self.assertTrue(self.command('/undo')['verified'])
        self.agent.desktop.desktop.restore_window.assert_called_once_with(before,after)

    def test_remote_request_cancel_is_responsive_and_result_is_discarded(self):
        from desktop_agent.client import JevClient
        client=JevClient(provider='opencode');release=threading.Event();started=threading.Event()
        def evaluate(*args):
            started.set();release.wait(2);return {'unused':True}
        client.evaluate=Mock(side_effect=evaluate);self.agent.client=client
        def pump():
            if started.is_set():self.agent.cancel.set()
        self.agent.pump=pump
        try:
            with self.assertRaises(AgentError) as error:self.agent.evaluate({}, {})
            self.assertEqual(error.exception.code,'TASK_CANCELLED')
            self.agent.cancel.clear();self.agent.pump=None
            with self.assertRaises(AgentError) as error:self.agent.evaluate({}, {})
            self.assertEqual(error.exception.code,'API_REQUEST_PENDING')
        finally:
            release.set();self.agent._request_thread.join(2)

    def test_atomic_move_rejects_existing_destination_even_without_precheck(self):
        from desktop_agent.files import move_no_replace
        a=self.root/'a';b=self.root/'b';a.write_text('source');b.write_text('keep')
        with self.assertRaises(AgentError) as error:move_no_replace(a,b)
        self.assertEqual(error.exception.code,'DESTINATION_EXISTS')
        self.assertEqual(b.read_text(),'keep');self.assertEqual(a.read_text(),'source')

    def test_cancellation_during_trash_confirmation_prevents_mutation(self):
        source=self.root/'a.txt';source.write_text('keep')
        def confirm(action):
            self.agent.cancel.set();return True
        with patch('desktop_agent.media.run') as run:
            self.assertEqual(self.command(f'Trash file "{source}"',confirm=confirm)['error'],'TASK_CANCELLED')
            run.assert_not_called();self.assertTrue(source.exists())

    def test_explicit_tab_command_works_from_terminal_without_native_input(self):
        self.agent.desktop.browser.tab.return_value={'success':True,'action':'tab_close','verified':True}
        self.assertTrue(self.command('Close tab')['success'])
        self.agent.desktop.observe.assert_not_called()
        self.agent.desktop.browser.tab.assert_called_once_with('close',None)
