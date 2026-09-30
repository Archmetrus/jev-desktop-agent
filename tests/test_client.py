import json
import io
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import MagicMock, Mock, patch

from desktop_agent.client import AgentError, JevClient, NoRedirect


class ClientTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_does_not_access_network(self):
        client = JevClient()
        client.opener = Mock()
        with self.assertRaisesRegex(AgentError, "MISSING_API_KEY"):
            client.evaluate({}, {})
        client.opener.open.assert_not_called()

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-only-key"})
    def test_official_request_and_response_contract(self):
        client = JevClient()
        reply = Mock()
        reply.read.return_value = json.dumps({"answers": {"launch": {"type": "choice"}}}).encode()
        client.opener = MagicMock()
        client.opener.open.return_value.__enter__.return_value = reply
        self.assertEqual(client.evaluate({"command": "Open browser"}, {"launch": {"type": "choice"}}),
                         {"launch": {"type": "choice"}})
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, JevClient.ENDPOINT)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only-key")
        self.assertEqual(json.loads(request.data)["model"], "jev-latest")

    def test_redirect_does_not_forward_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "router-test-key", "TYPESAFE_API_KEY": "other-key"}, clear=True)
    def test_openrouter_decisions_contract_and_provider_key(self):
        client = JevClient(provider="openrouter",model="typesafe/jev-1.13")
        client.opener = MagicMock()
        client.opener.open.return_value.__enter__.return_value.read.return_value = b'{"answers": {}}'
        self.assertEqual(client.evaluate({"command": "Open Firefox"}, {"launch": {"type": "choice"}}), {})
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/alpha/decisions")
        self.assertEqual(request.get_header("Authorization"), "Bearer router-test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "typesafe/jev-1.13")
        self.assertEqual(payload["state"], {"command": "Open Firefox"})
        self.assertIn("launch", payload["questions"])

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "other-provider-key"}, clear=True)
    def test_openrouter_never_falls_back_to_typesafe_key(self):
        client = JevClient(provider="openrouter",model="typesafe/jev-1.13")
        client.opener = Mock()
        with self.assertRaisesRegex(AgentError, "MISSING_API_KEY"):
            client.evaluate({}, {})
        client.opener.open.assert_not_called()

    def test_http_errors_expose_only_status_codes(self):
        for status, code in ((400, "API_BAD_REQUEST"), (404, "API_NOT_FOUND"),
                             (503, "API_UNAVAILABLE"), (500, "API_HTTP_500")):
            with self.subTest(status=status):
                client = JevClient(api_key="test-key", provider="openrouter",model="typesafe/jev-1.13")
                client.opener = Mock()
                client.opener.open.side_effect = HTTPError(client.endpoint, status, "private response", {}, None)
                with self.assertRaisesRegex(AgentError, "^" + code + "$"):
                    client.evaluate({}, {})

    def test_free_model_under_openrouter_stops_before_network(self):
        client=JevClient(provider='openrouter',api_key='test-only-key')
        client.opener=Mock()
        with self.assertRaisesRegex(AgentError,'PROVIDER_MODEL_MISMATCH'):
            client.evaluate({}, {})
        client.opener.open.assert_not_called()

    @patch.dict(os.environ, {'OPENCODE_API_KEY':'zen-test-key','OPENROUTER_API_KEY':'router-test-key'},clear=True)
    def test_opencode_free_model_uses_own_endpoint_and_key(self):
        client=JevClient(provider='opencode')
        client.opener=MagicMock()
        client.opener.open.return_value.__enter__.return_value.read.return_value=b'{"answers":{}}'
        client.evaluate({}, {})
        request=client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://opencode.ai/zen/v1/systemone')
        self.assertEqual(request.get_header('Authorization'),'Bearer zen-test-key')
        self.assertEqual(request.get_header('User-agent'),JevClient.USER_AGENT)
        self.assertEqual(json.loads(request.data)['model'],'jev-1.13-free')

    @patch.dict(os.environ, {'OPENROUTER_API_KEY':'router-test-key'},clear=True)
    def test_opencode_never_reuses_openrouter_key(self):
        client=JevClient(provider='opencode')
        client.opener=Mock()
        with self.assertRaisesRegex(AgentError,'MISSING_API_KEY'):
            client.evaluate({}, {})
        client.opener.open.assert_not_called()

    def test_free_tier_denial_is_classified_without_exposing_provider_message(self):
        client=JevClient(provider='opencode',api_key='private-test-key')
        client.opener=Mock()
        body={'type':'error','error':{'type':'FreeTierError',
              'message':'Free tier can only be used from within OpenCode private-test-key'}}
        client.opener.open.side_effect=HTTPError(client.endpoint,403,'denied',{},
                                                  io.BytesIO(json.dumps(body).encode()))
        with self.assertRaises(AgentError) as caught:
            client.evaluate({}, {})
        self.assertEqual(caught.exception.code,'ACCESS_DENIED')
        self.assertEqual(caught.exception.reason,'FREE_TIER_RESTRICTED')
        self.assertNotIn('private-test-key',str(caught.exception))

    def test_unknown_denial_does_not_return_raw_error_text(self):
        client=JevClient(provider='opencode',api_key='private-test-key')
        client.opener=Mock()
        client.opener.open.side_effect=HTTPError(client.endpoint,403,'denied',{},
                            io.BytesIO(b'{"message":"private-test-key"}'))
        with self.assertRaises(AgentError) as caught:
            client.evaluate({}, {})
        self.assertEqual(caught.exception.reason,'ACCESS_POLICY_UNKNOWN')

    def test_plaintext_client_signature_denial_is_identified(self):
        client=JevClient(provider='opencode',api_key='test-only-key')
        client.opener=Mock()
        client.opener.open.side_effect=HTTPError(client.endpoint,403,'denied',{},io.BytesIO(b'error code: 1010\n'))
        with self.assertRaises(AgentError) as caught:
            client.evaluate({}, {})
        self.assertEqual(caught.exception.reason,'CLIENT_SIGNATURE_BLOCKED')
