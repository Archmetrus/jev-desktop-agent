import unittest
from unittest.mock import Mock
from desktop_agent.browser import Browser
from desktop_agent.client import AgentError


class TabsTests(unittest.TestCase):
    def browser(self):
        browser=Browser();browser.socket=Mock();browser.process=Mock();browser.process.poll.return_value=None
        return browser

    def test_listing_restores_original_tab_even_on_failure(self):
        browser=self.browser()
        calls=[]
        def call(name,params=None):
            calls.append((name,params))
            if name=='WebDriver:GetWindowHandle':return 'original'
            if name=='WebDriver:GetWindowHandles':return ['original','second']
            if name=='WebDriver:GetTitle':raise AgentError('BROWSER_OPERATION_FAILED')
        browser.call=call
        with self.assertRaises(AgentError): browser.tabs()
        self.assertEqual(calls[-1],('WebDriver:SwitchToWindow',{'handle':'original'}))

    def test_ambiguous_title_never_switches(self):
        browser=self.browser();browser.call=Mock()
        browser.tabs=Mock(return_value=[{'handle':'1','title':'Music one'},{'handle':'2','title':'Music two'}])
        with self.assertRaises(AgentError) as error:browser.tab('switch','Music')
        self.assertEqual(error.exception.code,'AMBIGUOUS_TAB');browser.call.assert_not_called()

    def test_last_tab_closes_without_switching_to_invalid_handle(self):
        browser=self.browser();browser.tabs=Mock(return_value=[{'handle':'1'}]);browser.call=Mock(return_value=[])
        self.assertTrue(browser.tab('close')['success'])
        browser.call.assert_called_once_with('WebDriver:CloseWindow')
