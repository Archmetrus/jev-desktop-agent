import unittest
from unittest.mock import Mock
from desktop_agent.shortcuts import GlobalShortcut


class ShortcutTests(unittest.TestCase):
    def test_stop_fires_only_on_press_and_matching_session(self):
        shortcut=GlobalShortcut.__new__(GlobalShortcut)
        shortcut.dbus=Mock();shortcut.dbus.Dictionary.side_effect=lambda values,**kwargs:values
        shortcut.dbus.Array.side_effect=lambda values,**kwargs:values
        shortcut.dbus.ObjectPath.side_effect=lambda value:value
        shortcut.signals=[];shortcut.bus=Mock()
        shortcut.request=Mock(side_effect=[{'session_handle':'session'},
            {'shortcuts':[('talk',{'trigger_description':'Ctrl+Alt+V'}),('stop',{})]}])
        press,release,stop=Mock(),Mock(),Mock()
        shortcut.bind('CTRL+ALT+v',press,release,stop)
        callbacks={call.kwargs['signal_name']:call.args[0] for call in shortcut.bus.add_signal_receiver.call_args_list}
        callbacks['Activated']('wrong','stop',0,{})
        callbacks['Deactivated']('session','stop',0,{})
        stop.assert_not_called()
        callbacks['Activated']('session','stop',0,{})
        stop.assert_called_once()
        callbacks['Activated']('session','talk',0,{})
        callbacks['Deactivated']('session','talk',0,{})
        press.assert_called_once();release.assert_called_once()
