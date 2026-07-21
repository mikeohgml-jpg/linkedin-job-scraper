import contextlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from unittest import TestCase, mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "email_notifications.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"Missing module: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("email_notifications", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeHttpError(urllib.error.HTTPError):
    def __init__(self, url, code, body):
        super().__init__(url, code, "Bad Request", hdrs=None, fp=io.BytesIO(body.encode("utf-8")))


class SendCompletionEmailTests(TestCase):
    def _call(self, module, **overrides):
        defaults = dict(
            job_count=40,
            keyword="Sales",
            scope_label="Location",
            scope_value="Singapore",
            filename="C:\\tmp\\linkedin_sales.xlsx",
            api_key="brevo_test_key",
            notify_email="user@example.com",
            from_email="noreply@example.com",
        )
        defaults.update(overrides)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            module.send_completion_email(**defaults)
        return buffer.getvalue()

    def test_posts_brevo_request(self):
        module = load_module()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(201)

        with mock.patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
            output = self._call(module)

        self.assertEqual(captured["url"], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(captured["headers"]["Api-key"], "brevo_test_key")
        self.assertEqual(captured["payload"]["sender"]["email"], "noreply@example.com")
        self.assertEqual(captured["payload"]["to"], [{"email": "user@example.com"}])
        self.assertIn("Sales", captured["payload"]["subject"])
        self.assertIn("linkedin_sales.xlsx", captured["payload"]["textContent"])
        self.assertIn("Email notification sent to user@example.com", output)

    def test_skips_when_config_missing(self):
        module = load_module()
        with mock.patch.object(module.urllib.request, "urlopen") as urlopen:
            output = self._call(module, api_key="")
        urlopen.assert_not_called()
        self.assertIn("BREVO_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured", output)

    def test_logs_http_error_response_body(self):
        module = load_module()
        with mock.patch.object(
            module.urllib.request,
            "urlopen",
            side_effect=FakeHttpError(
                "https://api.brevo.com/v3/smtp/email",
                401,
                '{"message":"Key not found","code":"unauthorized"}',
            ),
        ):
            output = self._call(module)

        self.assertIn("HTTP Error 401", output)
        self.assertIn('"code":"unauthorized"', output)
