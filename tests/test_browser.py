import unittest
from unittest.mock import Mock,patch

from desktop_agent.browser import Browser,same_destination
from desktop_agent.client import AgentError


class DestinationTests(unittest.TestCase):
    def test_live_browser_session_is_reused(self):
        browser=Browser()
        browser.socket=Mock()
        browser.process=Mock()
        browser.process.poll.return_value=None
        browser.call=Mock(return_value=['window'])
        browser.start()
        browser.call.assert_called_once_with('WebDriver:GetWindowHandles')

    @patch('desktop_agent.browser.shutil.which',return_value=None)
    def test_dead_browser_socket_is_discarded_before_relaunch(self,which):
        browser=Browser()
        connection=Mock()
        browser.socket=connection
        browser.process=Mock()
        browser.process.poll.return_value=0
        browser.targets={'old':'stale'}
        browser.call=Mock()
        with self.assertRaisesRegex(AgentError,'APPLICATION_NOT_INSTALLED'):
            browser.start()
        self.assertIsNone(browser.socket)
        self.assertEqual(browser.targets,{})
        connection.close.assert_called_once()

    def test_disconnect_retries_navigation_once_but_not_other_actions(self):
        browser=Browser()
        browser.start=Mock()
        browser.close=Mock()
        browser.call=Mock(side_effect=[AgentError('BROWSER_CONNECTION_FAILED'),{},'https://example.com/'])
        self.assertTrue(browser.navigate('https://example.com/')['verified'])
        browser.close.assert_called_once_with(terminate=True)
        self.assertEqual(browser.start.call_count,2)

    def test_host_path_and_requested_search_query_are_verified(self):
        self.assertTrue(same_destination('https://www.youtube.com/results?search_query=cats+and+dogs',
                                         'https://youtube.com/results?search_query=cats%20and%20dogs&extra=1'))

    def test_other_host_or_path_is_not_verified(self):
        for actual in ['https://consent.youtube.com/results?q=music',
                       'https://youtube.com/', 'https://example.com/results?q=music']:
            self.assertFalse(same_destination('https://youtube.com/results?q=music',actual))

    def test_different_search_query_is_not_verified(self):
        self.assertFalse(same_destination('https://youtube.com/results?q=music',
                                          'https://youtube.com/results?q=sports'))

    def test_https_upgrade_and_trailing_slash_are_allowed(self):
        self.assertTrue(same_destination('http://example.com','https://www.example.com/'))

    def test_different_port_and_invalid_address_are_not_verified(self):
        self.assertFalse(same_destination('http://localhost:1234/','http://localhost:4321/'))
        self.assertFalse(same_destination('https://example.com/','about:blank'))
