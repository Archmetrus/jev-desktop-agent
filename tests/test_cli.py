import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from desktop_agent.cli import interactive, check_connection, main
from desktop_agent.client import AgentError, JevClient


class InteractiveTests(unittest.TestCase):
    def setUp(self):
        for name, value in [('lookup',None),('save',True),('forget',True)]:
            patcher=patch('desktop_agent.cli.credentials.'+name,return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_connection_check_makes_real_client_call_with_synthetic_text(self):
        client=JevClient(provider='opencode')
        client.evaluate=Mock(return_value={'connection':{'type':'noul','noul':0.99}})
        result=check_connection(client)
        self.assertTrue(result['api_response_valid'])
        self.assertFalse(result['desktop_action_executed'])
        self.assertEqual(result['model'],'jev-1.13-free')
        state,questions=client.evaluate.call_args.args
        self.assertEqual(state,'This is a connection test.')
        self.assertEqual(questions['connection']['type'],'noul')

    @patch('desktop_agent.cli.sys.stdin.isatty',return_value=True)
    @patch('desktop_agent.cli.credentials.lookup',return_value='remembered-test-key')
    @patch('desktop_agent.cli.credentials.save')
    @patch('desktop_agent.cli.check_connection',return_value={'success':True})
    @patch('desktop_agent.cli.read_key')
    @patch('builtins.input',side_effect=['/quit'])
    def test_remembered_key_skips_prompt_and_is_not_printed(self,input_mock,key_mock,check_mock,save_mock,lookup_mock,tty_mock):
        agent=Mock()
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(interactive(agent,'opencode'),0)
        lookup_mock.assert_called_once_with('opencode')
        key_mock.assert_not_called()
        save_mock.assert_not_called()
        check_mock.assert_called_once_with(agent.client)
        self.assertNotIn('remembered-test-key',output.getvalue())
        self.assertIsNone(agent.client.api_key)

    def test_connection_check_rejects_malformed_response(self):
        client=JevClient(provider='opencode')
        client.evaluate=Mock(return_value={'connection':{'type':'noul','noul':float('nan')}})
        self.assertEqual(check_connection(client)['error'],'INVALID_RESPONSE')

    def test_connection_check_does_not_claim_success_after_api_rejection(self):
        client=JevClient(provider='opencode')
        client.evaluate=Mock(side_effect=AgentError('API_BAD_REQUEST'))
        result=check_connection(client)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'],'API_BAD_REQUEST')

    @patch("desktop_agent.cli.sys.stdin.isatty", return_value=True)
    @patch("desktop_agent.cli.check_connection", return_value={'success':True})
    @patch("desktop_agent.cli.read_key", return_value="zen-private-key")
    @patch("builtins.input", side_effect=["", "/quit"])
    def test_default_selection_is_opencode(self, input_mock, key_mock, check_mock, tty_mock):
        agent = Mock()
        agent.client = JevClient()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(interactive(agent), 0)
        self.assertEqual(agent.client.provider, "opencode")
        self.assertEqual(agent.client.model, "jev-1.13-free")
        self.assertIsNone(agent.client.api_key)
        key_mock.assert_called_once_with("opencode")
        check_mock.assert_called_once_with(agent.client)
        agent.process.assert_not_called()

    @patch('desktop_agent.cli.interactive',return_value=0)
    @patch('desktop_agent.cli.Tools')
    @patch('sys.argv',['desktop-agent'])
    def test_launcher_uses_configured_opencode_provider_without_flags(self,tools_mock,interactive_mock):
        self.assertEqual(main(),0)
        agent,provider,*_=interactive_mock.call_args.args
        self.assertEqual(provider,'opencode')
        self.assertEqual(agent.client.endpoint,'https://opencode.ai/zen/v1/systemone')
        self.assertEqual(agent.client.model,'jev-1.13-free')

    @patch('desktop_agent.cli.sys.stdin.isatty',return_value=True)
    @patch('desktop_agent.cli.check_connection',return_value={'success':False,'error':'AUTHENTICATION_FAILED'})
    @patch('desktop_agent.cli.read_key',return_value='invalid-test-key')
    @patch('builtins.input',side_effect=['/quit'])
    @patch('desktop_agent.cli.hold_to_talk')
    def test_failed_startup_check_does_not_start_voice(self,hold_mock,input_mock,key_mock,check_mock,tty_mock):
        agent=Mock()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(interactive(agent,'opencode',speech=Mock(),start_listening=True),0)
        hold_mock.assert_not_called()
        agent.process.assert_not_called()
        self.assertIsNone(agent.client.api_key)

    @patch("desktop_agent.cli.sys.stdin.isatty", return_value=True)
    @patch("desktop_agent.cli.read_key", side_effect=["private-key", "replacement-key"])
    @patch("builtins.input", side_effect=["Open Firefox", "/key", "Open Konsole", "/quit"])
    def test_errors_continue_key_replacement_and_cleanup(self, input_mock, key_mock, tty_mock):
        agent = Mock()
        agent.apps = {"firefox": {}, "konsole": {}}
        used_keys = []

        def process(command, on_event, confirm=None):
            used_keys.append(agent.client.api_key)
            if command == "Open Firefox":
                return {"success": False, "error": "AUTHENTICATION_FAILED"}
            on_event("evaluating", {})
            on_event("selected", {"application": "konsole", "confidence": 0.95})
            on_event("executing", {"application": "konsole"})
            return {"success": True, "application": "konsole", "verified": True}

        agent.process.side_effect = process
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(interactive(agent, "typesafe"), 0)
        self.assertEqual(used_keys, ["private-key", "replacement-key"])
        self.assertIsNone(agent.client.api_key)
        self.assertIn("AUTHENTICATION_FAILED", output.getvalue())
        self.assertIn("konsole penceresi doğrulandı", output.getvalue())
        self.assertIn('Komut: "Open Firefox"', output.getvalue())
        self.assertNotIn("private-key", output.getvalue())
        self.assertNotIn("replacement-key", output.getvalue())

    @patch("desktop_agent.cli.sys.stdin.isatty", return_value=True)
    @patch("desktop_agent.cli.read_key", side_effect=KeyboardInterrupt)
    def test_interrupt_clears_session_key(self, key_mock, tty_mock):
        agent = Mock()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(interactive(agent, "typesafe"), 0)
        self.assertIsNone(agent.client.api_key)

    @patch("desktop_agent.cli.sys.stdin.isatty", return_value=False)
    @patch("desktop_agent.cli.read_key")
    def test_pipe_does_not_prompt_for_secret(self, key_mock, tty_mock):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(interactive(Mock()), 1)
        key_mock.assert_not_called()
