import subprocess
import unittest
from unittest.mock import Mock,patch
from desktop_agent import credentials

@patch('desktop_agent.credentials.shutil.which',return_value='/usr/bin/secret-tool')
class CredentialTests(unittest.TestCase):
    @patch('desktop_agent.credentials.subprocess.run')
    def test_key_is_passed_only_via_stdin(self,run,which):
        run.return_value=Mock(returncode=0)
        self.assertTrue(credentials.save('opencode','test-secret'))
        self.assertNotIn('test-secret',run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['input'],'test-secret')
        self.assertEqual(run.call_args.args[0][-2:],['provider','opencode'])

    @patch('desktop_agent.credentials.subprocess.run')
    def test_lookup_is_scoped_to_provider(self,run,which):
        run.return_value=Mock(returncode=0,stdout='test-secret\n')
        self.assertEqual(credentials.lookup('opencode'),'test-secret')
        self.assertEqual(run.call_args.args[0][-2:],['provider','opencode'])

    @patch('desktop_agent.credentials.subprocess.run')
    def test_locked_unavailable_wallet_has_no_plaintext_fallback(self,run,which):
        run.side_effect=subprocess.TimeoutExpired('secret-tool',20)
        self.assertIsNone(credentials.lookup('opencode'))
        self.assertFalse(credentials.save('opencode','test-secret'))

    @patch('desktop_agent.credentials.subprocess.run')
    def test_unknown_provider_never_accesses_wallet(self,run,which):
        self.assertIsNone(credentials.lookup('unconfigured'))
        run.assert_not_called()
