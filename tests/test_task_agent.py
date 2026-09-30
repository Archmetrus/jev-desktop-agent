import unittest
import tempfile
from unittest.mock import Mock,patch

from desktop_agent.task_agent import TaskAgent, text_candidates, url_candidates


def answer(question, choice):
    return {"type":"choice","choice":choice,"confidence":0.99,
            "probabilities":{key:1.0 if key==choice else 0.0 for key in question['criteria']}}


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tools = Mock()
        self.client = Mock()
        self.config = {'confidence_threshold':0.8,'probability_threshold':0.8,'max_steps':6,'max_no_progress':3}
        self.agent = TaskAgent(self.client, {'firefox':{'aliases':['browser'],'command':['firefox']}},
                               self.tools, self.config, {'youtube':{'url':'https://www.youtube.com',
                               'search':'https://www.youtube.com/results?search_query={query}'}})
        from desktop_agent.features import Features
        state=tempfile.TemporaryDirectory(dir='/tmp');self.addCleanup(state.cleanup)
        self.agent.features=Features(self.agent,state.name)
        self.screen = {'source':'browser','fingerprint':'one','window':{'id':'w1','application':'firefox'},
                       'windows':[],'elements':[{'id':'observed-1','role':'input','label':'Search',
                        'operations':['type_text']},{'id':'observed-2','role':'button','label':'Search',
                        'operations':['click']}]}

    def test_payload_preserves_normal_conjunctions(self):
        self.assertIn('rock and roll',text_candidates('Type "rock and roll" and click Search').values())
        self.assertEqual(list(text_candidates('Search YouTube for Interstellar soundtrack').values()),
                         ['Interstellar soundtrack'])

    def test_only_http_urls_and_encoded_search_values(self):
        candidates = url_candidates('search youtube for cats & dogs',{'t0':'cats & dogs'},self.agent.sites)
        self.assertTrue(any('cats+%26+dogs' in value['url'] for value in candidates.values()))
        self.assertEqual(url_candidates('javascript:alert(1)',{},{}),{})

    def test_search_field_label_does_not_create_google_navigation(self):
        command='Type "hello world" in Search and click Apply'
        sites={**self.agent.sites,'google':{'url':'https://www.google.com','search':'https://www.google.com/search?q={query}'}}
        self.assertEqual(url_candidates(command,text_candidates(command),sites), {})

    def test_youtube_search_has_one_destination_not_home_or_google(self):
        sites={**self.agent.sites,'google':{'url':'https://www.google.com',
                                         'search':'https://www.google.com/search?q={query}'}}
        command='Search YouTube for interstellar soundtrack'
        urls=url_candidates(command,text_candidates(command),sites)
        self.assertEqual([item['url'] for item in urls.values()],
                         ['https://www.youtube.com/results?search_query=interstellar+soundtrack'])
        questions,_=self.agent.choices(self.screen,text_candidates(command),urls,command)
        self.assertEqual(set(questions['operation']['criteria']),{'navigate','blocked'})
        self.assertEqual(set(questions),{'operation','url'})

    def test_browser_and_type_named_site_has_site_destination(self):
        command='Open browser and type YouTube'
        urls=url_candidates(command,text_candidates(command),self.agent.sites)
        self.assertEqual([item['url'] for item in urls.values()],['https://www.youtube.com'])

    def test_completed_url_not_offered_again(self):
        command='Search YouTube for soundtrack'
        urls=url_candidates(command,text_candidates(command),self.agent.sites)
        questions,_=self.agent.choices(self.screen,text_candidates(command),urls,command,
                                      [{'action':'navigate','url_id':'u0'}])
        self.assertNotIn('navigate',questions['operation']['criteria'])
        self.assertIn('done',questions['operation']['criteria'])

    def test_low_confidence_reports_question_and_numbers_without_executing(self):
        self.tools.observe.return_value=self.screen
        def evaluate(state,questions):
            result=answer(questions['operation'],'navigate')
            result['confidence']=0.6
            return {'operation':result}
        self.client.evaluate.side_effect=evaluate
        events=[]
        result=self.agent.process('Search YouTube for soundtrack and scroll down',
                                  on_event=lambda name,data:events.append((name,data)))
        self.assertEqual(result['error'],'LOW_CONFIDENCE')
        diagnostic=next(data for name,data in events if name=='uncertain')
        self.assertEqual(diagnostic['question'],'operation')
        self.assertEqual(diagnostic['confidence'],0.6)
        self.assertEqual(diagnostic['probability'],1.0)
        self.tools.execute.assert_not_called()

    def test_explicit_browser_launch_uses_unique_configured_alias_without_api(self):
        self.tools.execute.return_value={'success':True,'verified':True,'application':'firefox'}
        result=self.agent.process('Open browser')
        self.assertTrue(result['success'])
        self.tools.execute.assert_called_once_with({'action':'open_app','application':'firefox'})
        self.client.evaluate.assert_not_called()

    def test_explicit_web_search_uses_encoded_configured_url_without_api(self):
        self.tools.execute.return_value={'success':True,'verified':True,'action':'navigate'}
        result=self.agent.process('Search YouTube for Interstellar Soundtrack')
        self.assertTrue(result['success'])
        self.assertEqual(self.tools.execute.call_args.args[0],{
            'action':'navigate','url':'https://www.youtube.com/results?search_query=Interstellar+Soundtrack'})
        self.client.evaluate.assert_not_called()

    def test_explicit_site_and_browser_site_use_registered_destination(self):
        for command in ['Open YouTube','Open browser and type YouTube']:
            with self.subTest(command=command):
                self.assertEqual(self.agent.direct_action(command),{
                    'action':'navigate','url':'https://www.youtube.com'})

    def test_compound_goal_is_not_silently_shortened_to_direct_search(self):
        self.assertIsNone(self.agent.direct_action('Search YouTube for music and click Play'))

    def test_direct_navigation_redirect_does_not_claim_verification(self):
        self.tools.execute.return_value={'success':True,'verified':False,'action':'navigate'}
        self.assertEqual(self.agent.process('Open YouTube')['error'],'NAVIGATION_NOT_VERIFIED')

    def test_general_operation_question_gets_actual_destinations_and_tool_capability(self):
        self.tools.observe.return_value=self.screen
        def evaluate(state,questions):
            self.assertIn('https://www.youtube.com/results?search_query=soundtrack',
                          state['destinations']['u0']['url'])
            self.assertIn('starts Firefox itself',questions['operation']['criteria']['navigate'])
            self.assertIn('youtube.com',questions['operation']['criteria']['navigate'])
            return {'operation':answer(questions['operation'],'blocked')}
        self.client.evaluate.side_effect=evaluate
        self.assertEqual(self.agent.process('Search YouTube for soundtrack and scroll down')['error'],'TASK_BLOCKED')

    def test_terminal_controls_never_offered(self):
        screen={**self.screen,'window':{'application':'org.kde.konsole'}}
        questions,_=self.agent.choices(screen,{'t0':'hello'},{},'Type hello')
        self.assertNotIn('type_text',questions['operation']['criteria'])
        self.assertNotIn('click',questions['operation']['criteria'])

    def test_observe_choose_execute_observe_uses_current_targets(self):
        self.tools.observe.side_effect = [self.screen,{**self.screen,'fingerprint':'two','elements':[]}]
        self.tools.execute.return_value = {'success':True,'action':'type_text','verified':True}
        def evaluate(state, questions):
            if state['history']:
                return {'operation':answer(questions['operation'],'done')}
            return {'operation':answer(questions['operation'],'type_text'),
                    'type_text':answer(questions['type_text'],'observed-1'),
                    'text':answer(questions['text'],'t0')}
        self.client.evaluate.side_effect = evaluate
        result=self.agent.process('Type "hello world" in the Search field')
        self.assertTrue(result['success'])
        self.assertFalse(result['goal_verified'])
        action=self.tools.execute.call_args.args[0]
        self.assertEqual(action['target'],'observed-1')
        self.assertEqual(action['text'],'hello world')
        self.assertEqual(self.tools.observe.call_count,2)

    def test_invented_target_never_executes(self):
        self.tools.observe.return_value = self.screen
        def evaluate(state,questions):
            return {'operation':answer(questions['operation'],'click'),
                    'click':answer(questions['click'],'invented')}
        self.client.evaluate.side_effect=evaluate
        self.assertEqual(self.agent.process('Click Search')['error'],'INVALID_RESPONSE')
        self.tools.execute.assert_not_called()

    @patch('desktop_agent.task_agent.time.sleep')
    def test_laya_single_type_stops_without_done_decision(self,sleep):
        self.client.provider='laya'
        self.client.threshold=.65
        self.tools.observe.return_value=self.screen
        self.tools.execute.return_value={'success':True,'verified':True}
        def evaluate(state,questions):
            return {'operation':answer(questions['operation'],'type_text'),
                    'type_text':answer(questions['type_text'],'observed-1'),
                    'text':answer(questions['text'],'t0')}
        self.client.evaluate.side_effect=evaluate
        result=self.agent.process('Type "hello" in Search')
        self.assertTrue(result['success'])
        self.assertEqual(result['action_limit'],1)
        self.tools.execute.assert_called_once()
        self.client.evaluate.assert_called_once()

    @patch('desktop_agent.task_agent.time.sleep')
    def test_laya_duplicate_action_is_blocked_even_when_screen_changes(self,sleep):
        self.client.provider='laya'
        self.client.threshold=.65
        self.tools.observe.side_effect=[self.screen,{**self.screen,'fingerprint':'two'}]
        self.tools.execute.return_value={'success':True,'verified':True}
        def evaluate(state,questions):
            return {'operation':answer(questions['operation'],'click'),
                    'click':answer(questions['click'],'observed-2')}
        self.client.evaluate.side_effect=evaluate
        result=self.agent.process('Click Search and scroll down')
        self.assertEqual(result['error'],'REPEATED_ACTION_BLOCKED')
        self.tools.execute.assert_called_once()

    @patch('desktop_agent.task_agent.time.sleep')
    def test_laya_two_explicit_actions_stop_without_third_decision(self,sleep):
        self.client.provider='laya'
        self.client.threshold=.65
        self.tools.observe.side_effect=[self.screen,{**self.screen,'fingerprint':'two'},
                                       {**self.screen,'fingerprint':'three'}]
        self.tools.execute.return_value={'success':True,'verified':True}
        def evaluate(state,questions):
            if state['history']:
                return {'operation':answer(questions['operation'],'scroll_down')}
            return {'operation':answer(questions['operation'],'click'),
                    'click':answer(questions['click'],'observed-2')}
        self.client.evaluate.side_effect=evaluate
        result=self.agent.process('Click Search and scroll down')
        self.assertTrue(result['success'])
        self.assertEqual(result['action_limit'],2)
        self.assertEqual(self.tools.execute.call_count,2)
        self.assertEqual(self.client.evaluate.call_count,2)

    def test_send_button_requires_confirmation(self):
        self.tools.observe.return_value={**self.screen,'elements':[{'id':'send','role':'button','label':'Send',
                                                                 'operations':['click']}]}
        def evaluate(state,questions):
            return {'operation':answer(questions['operation'],'click'),'click':answer(questions['click'],'send')}
        self.client.evaluate.side_effect=evaluate
        self.assertEqual(self.agent.process('Click Send')['error'],'CONFIRMATION_REQUIRED')
        self.tools.execute.assert_not_called()

    def test_secret_command_never_leaves_machine(self):
        result=self.agent.process('Type password secret123')
        self.assertEqual(result['error'],'SENSITIVE_COMMAND_BLOCKED')
        self.client.evaluate.assert_not_called()
        self.tools.execute.assert_not_called()

    def test_no_progress_stops_repeating_actions(self):
        self.tools.observe.return_value=self.screen
        self.tools.execute.return_value={'success':True,'verified':False}
        def evaluate(state,questions):
            return {'operation':answer(questions['operation'],'wait')}
        self.client.evaluate.side_effect=evaluate
        self.assertEqual(self.agent.process('Wait for results')['error'],'NO_PROGRESS')
        self.assertEqual(self.tools.execute.call_count,3)

    def test_history_preserves_selected_option_and_scroll_direction(self):
        screen={**self.screen,'elements':[{'id':'category','role':'select','label':'Category',
                'operations':['select'],'options':[{'label':'Two','value':'two'}]}]}
        self.tools.observe.side_effect=[screen,{**screen,'fingerprint':'two'},
                                       {**screen,'fingerprint':'three'}]
        self.tools.execute.return_value={'success':True,'verified':True}
        def evaluate(state,questions):
            if not state['history']:
                return {'operation':answer(questions['operation'],'select'),
                        'option':answer(questions['option'],'category_0')}
            self.assertEqual(state['history'][0]['target'],'Category')
            self.assertEqual(state['history'][0]['option_label'],'Two')
            if len(state['history'])==1:
                return {'operation':answer(questions['operation'],'scroll_down')}
            self.assertEqual(state['history'][1]['direction'],'down')
            return {'operation':answer(questions['operation'],'done')}
        self.client.evaluate.side_effect=evaluate
        self.assertTrue(self.agent.process('Select Two in Category and scroll down')['success'])
