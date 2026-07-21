import contextlib
import importlib.util
import io
import json
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


class SendCompletionEmailTests(TestCase):
    def test_posts_resend_request(self):
        module = load_module()
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(200)

        with mock.patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                module.send_completion_email(
                    job_count=40,
                    keyword="Sales",
                    scope_label="Location",
                    scope_value="Singapore",
                    filename="C:\\tmp\\linkedin_sales.xlsx",
                    api_key="re_test_key",
                    notify_email="user@example.com",
                    from_email="noreply@example.com",
                )

        self.assertEqual(captured["url"], "https://api.resend.com/emails")
        self.assertEqual(captured["timeout"], 15)
        self.assertEqual(captured["headers"]["Authorization"], "Bearer re_test_key")
        self.assertEqual(captured["payload"]["from"], "noreply@example.com")
        self.assertEqual(captured["payload"]["to"], ["user@example.com"])
        self.assertEqual(captured["payload"]["subject"], "LinkedIn Scrape Done: 40 'Sales' jobs in Singapore")
        self.assertIn("Keyword : Sales", captured["payload"]["text"])
        self.assertIn("Location: Singapore", captured["payload"]["text"])
        self.assertIn("linkedin_sales.xlsx", captured["payload"]["text"])
        self.assertIn("Email notification sent to user@example.com", buffer.getvalue())

    def test_skips_when_config_missing(self):
        module = load_module()

        with mock.patch.object(module.urllib.request, "urlopen") as urlopen:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                module.send_completion_email(
                    job_count=10,
                    keyword="AI",
                    scope_label="Region",
                    scope_value="APAC",
                    filename="linkedin_ai.xlsx",
                    api_key="",
                    notify_email="user@example.com",
                    from_email="noreply@example.com",
                )

        urlopen.assert_not_called()
        self.assertIn("RESEND_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured", buffer.getvalue())
