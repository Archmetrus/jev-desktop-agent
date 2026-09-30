import unittest
from unittest.mock import Mock,patch
from desktop_agent.tools import Tools


class BrowserFocusTests(unittest.TestCase):
    @patch('desktop_agent.tools.time.sleep')
    def test_navigation_waits_for_window_before_focusing(self,sleep):
        tools=Tools({})
        tools.browser=Mock()
        tools.browser.process.pid=1234
        tools.browser.navigate.return_value={'success':True,'verified':True}
        tools.desktop=Mock(timeout=1)
        tools.desktop.windows.side_effect=[[],[{'id':'owned','pid':1234}]]
        result=tools.execute({'action':'navigate','url':'https://example.com/'})
        tools.desktop.focus_window.assert_called_once_with('owned')
        self.assertTrue(result['focused'])

    def test_other_active_application_is_not_silently_replaced(self):
        tools=Tools({})
        tools.browser=Mock()
        tools.browser.process.pid=1234
        tools.browser.socket=True
        tools.desktop=Mock()
        tools.desktop.windows.return_value=[{'active':True,'id':'other','pid':555}]
        tools.accessibility=Mock()
        tools.accessibility.observe.return_value={'source':'desktop'}
        self.assertEqual(tools.observe()['source'],'desktop')
        tools.browser.observe.assert_not_called()
        tools.desktop.focus_window.assert_not_called()
