import contextlib
import importlib.util
import io
import smtplib
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


class SendCompletionEmailTests(TestCase):
    def _call(self, module, **overrides):
        defaults = dict(
            job_count=40,
            keyword="Sales",
            scope_label="Location",
            scope_value="Singapore",
            filename="C:\\tmp\\linkedin_sales.xlsx",
            api_key="re_test_key",
            notify_email="user@example.com",
            from_email="noreply@example.com",
        )
        defaults.update(overrides)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            module.send_completion_email(**defaults)
        return buffer.getvalue()

    def test_sends_via_resend_smtp(self):
        module = load_module()
        mock_server = mock.MagicMock()
        mock_smtp_ssl = mock.MagicMock()
        mock_smtp_ssl.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_ssl.__exit__ = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl) as smtp_cls:
            output = self._call(module)

        smtp_cls.assert_called_once_with("smtp.resend.com", 465, timeout=15)
        mock_server.login.assert_called_once_with("resend", "re_test_key")
        mock_server.send_message.assert_called_once()
        sent_msg = mock_server.send_message.call_args[0][0]
        self.assertEqual(sent_msg["From"], "noreply@example.com")
        self.assertEqual(sent_msg["To"], "user@example.com")
        self.assertIn("Sales", sent_msg["Subject"])
        self.assertIn("Email notification sent to user@example.com", output)

    def test_skips_when_config_missing(self):
        module = load_module()
        with mock.patch("smtplib.SMTP_SSL") as smtp_cls:
            output = self._call(module, api_key="")
        smtp_cls.assert_not_called()
        self.assertIn("RESEND_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured", output)

    def test_logs_auth_error(self):
        module = load_module()
        mock_server = mock.MagicMock()
        mock_smtp_ssl = mock.MagicMock()
        mock_smtp_ssl.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_ssl.__exit__ = mock.Mock(return_value=False)
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl):
            output = self._call(module)

        self.assertIn("auth error", output)
