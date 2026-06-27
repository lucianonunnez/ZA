"""Health-check logic (offline, with a stub HTTP client)."""

from copilot.healthcheck import _summary, check_openrouter, check_telegram


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Client:
    """Minimal stub: returns a queued response for the next get()."""

    def __init__(self, resp):
        self._resp = resp

    async def get(self, url, headers=None):
        return self._resp


async def test_telegram_ok():
    client = _Client(_Resp(payload={"ok": True, "result": {"username": "FLY_009Bot"}}))
    c = await check_telegram(client, "tok")
    assert c.ok and "FLY_009Bot" in c.detail


async def test_telegram_bad_token():
    client = _Client(_Resp(payload={"ok": False, "description": "Unauthorized"}))
    c = await check_telegram(client, "tok")
    assert not c.ok and c.required and "Unauthorized" in c.detail


async def test_telegram_missing_token_is_required_fail():
    c = await check_telegram(_Client(_Resp()), "")
    assert not c.ok and c.required


async def test_openrouter_missing_key_is_warning_not_required():
    c = await check_openrouter(_Client(_Resp()), "")
    assert not c.ok and not c.required   # mock provider still works → not required


async def test_openrouter_valid_key():
    client = _Client(_Resp(status_code=200, payload={"data": {"limit": 5}}))
    c = await check_openrouter(client, "sk-or-x")
    assert c.ok and "valid" in c.detail


def test_summary_is_markdown_table():
    from copilot.healthcheck import Check
    md = _summary([Check("Telegram", True, True, "ok"), Check("OpenRouter", False, False, "no key")])
    assert "| Connection |" in md and "✅" in md and "⚠️" in md
