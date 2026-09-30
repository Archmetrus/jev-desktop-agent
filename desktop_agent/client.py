import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class AgentError(Exception):
    def __init__(self, code, reason=None):
        super().__init__(code)
        self.code = code
        self.reason = reason


def denial_reason(raw):
    """Classify provider errors without returning their text or credentials."""
    if isinstance(raw,bytes) and raw.strip()==b'error code: 1010':
        return 'CLIENT_SIGNATURE_BLOCKED'
    try:
        data=json.loads(raw)
        if not isinstance(data,dict):
            return 'ACCESS_POLICY_UNKNOWN'
        error=data.get('error',data)
        if not isinstance(error,dict):
            return 'ACCESS_POLICY_UNKNOWN'
        kind=error.get('type')
        message=str(error.get('message','')).lower()
        if kind=='FreeTierError' or 'free tier can only be used' in message:
            return 'FREE_TIER_RESTRICTED'
        if 'billing' in message or 'payment required' in message:
            return 'BILLING_REQUIRED'
        if 'model' in message and any(word in message for word in ('permission','access','disabled','allowed')):
            return 'MODEL_ACCESS_RESTRICTED'
        if 'account' in message and any(word in message for word in ('suspended','disabled','blocked','permission')):
            return 'ACCOUNT_ACCESS_RESTRICTED'
    except (ValueError,TypeError,UnicodeError):
        pass
    return 'ACCESS_POLICY_UNKNOWN'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class JevClient:
    USER_AGENT = 'JevDesktopAgent/2026.09 (Python urllib)'
    ENDPOINT = "https://api.typesafe.ai/v1/systemone"
    PROVIDERS = {
        "typesafe": {"endpoint": ENDPOINT, "model": "jev-latest", "key_env": "TYPESAFE_API_KEY"},
        "openrouter": {"endpoint": "https://openrouter.ai/api/alpha/decisions",
                       "model": "jev-1.13-free", "key_env": "OPENROUTER_API_KEY"},
        "opencode": {"endpoint": "https://opencode.ai/zen/v1/systemone",
                     "model": "jev-1.13-free", "key_env": "OPENCODE_API_KEY"},
    }

    def __init__(self, model=None, timeout=15, api_key=None, provider="typesafe"):
        if provider not in self.PROVIDERS:
            raise ValueError("UNKNOWN_PROVIDER")
        settings = self.PROVIDERS[provider]
        self.provider = provider
        self.endpoint = settings["endpoint"]
        self.key_env = settings["key_env"]
        self.model = model or settings["model"]
        self.timeout = timeout
        self.api_key = api_key
        self.opener = build_opener(NoRedirect())

    def evaluate(self, state, questions):
        if self.provider == 'openrouter' and self.model == 'jev-1.13-free':
            raise AgentError('PROVIDER_MODEL_MISMATCH')
        key = self.api_key if self.api_key is not None else os.environ.get(self.key_env)
        if not key:
            raise AgentError("MISSING_API_KEY")
        payload = {"model": self.model, "state": state, "questions": questions}
        request = Request(self.endpoint, json.dumps(payload).encode(),
            {"Authorization": "Bearer " + key, "Content-Type": "application/json",
             "User-Agent": self.USER_AGENT}, method="POST")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise AgentError("INVALID_RESPONSE")
            result = json.loads(raw)
            if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
                raise AgentError("INVALID_RESPONSE")
            return result["answers"]
        except HTTPError as error:
            reason=None
            try:
                if error.code==403:
                    reason=denial_reason(error.read(65536))
            except (OSError,AttributeError,ValueError,TypeError):
                reason='ACCESS_POLICY_UNKNOWN'
            finally:
                error.close()
            raise AgentError({400: "API_BAD_REQUEST", 401: "AUTHENTICATION_FAILED",
                402: "INSUFFICIENT_CREDITS", 403: "ACCESS_DENIED", 404: "API_NOT_FOUND",
                422: "API_INVALID_REQUEST", 429: "RATE_LIMITED", 502: "API_UNAVAILABLE",
                503: "API_UNAVAILABLE"}.get(error.code, "API_HTTP_" + str(error.code)),reason) from None
        except (URLError, TimeoutError, OSError):
            raise AgentError("API_CONNECTION_FAILED") from None
        except (ValueError, UnicodeError):
            raise AgentError("INVALID_RESPONSE") from None
