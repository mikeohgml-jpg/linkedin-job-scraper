import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest import TestCase, mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"


class StopCalled(Exception):
    pass


class _ContextBlock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeStreamlit:
    def __init__(self, *, is_logged_in: bool, email: str):
        self.user = types.SimpleNamespace(is_logged_in=is_logged_in, email=email)
        self.markdown_calls = []
        self.events = []
        self.sidebar = _ContextBlock()

    def set_page_config(self, **kwargs):
        self.events.append(("set_page_config", kwargs))

    def columns(self, spec):
        self.events.append(("columns", spec))
        return _ContextBlock(), _ContextBlock()

    def title(self, value):
        self.events.append(("title", value))

    def caption(self, value):
        self.events.append(("caption", value))

    def info(self, value):
        self.events.append(("info", value))

    def error(self, value):
        self.events.append(("error", value))

    def button(self, label, **kwargs):
        self.events.append(("button", label, kwargs))

    def markdown(self, body, unsafe_allow_html=False):
        self.markdown_calls.append((body, unsafe_allow_html))
        self.events.append(("markdown", body, unsafe_allow_html))

    def login(self):
        self.events.append(("login", None))

    def logout(self):
        self.events.append(("logout", None))

    def stop(self):
        self.events.append(("stop", None))
        raise StopCalled()


def load_app(streamlit_module, env):
    spec = importlib.util.spec_from_file_location("app_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    fake_pandas = types.SimpleNamespace()
    with mock.patch.dict(sys.modules, {"streamlit": streamlit_module, "pandas": fake_pandas}):
        with mock.patch.dict(os.environ, env, clear=False):
            try:
                spec.loader.exec_module(module)
            except StopCalled:
                pass

    return streamlit_module


class AppHeaderTests(TestCase):
    def test_login_screen_renders_escaped_build_badge_before_stop(self):
        fake_st = FakeStreamlit(is_logged_in=False, email="")

        load_app(
            fake_st,
            {
                "GOOGLE_CLIENT_ID": "client-id",
                "APP_VERSION": "<b>feature</b>",
                "APP_GIT_SHA": "abcdef1",
                "APP_BUILD_DATE": "2026-07-21",
            },
        )

        self.assertTrue(fake_st.markdown_calls, "expected build badge to render before st.stop()")
        badge_html, unsafe = fake_st.markdown_calls[0]
        self.assertTrue(unsafe)
        self.assertIn("&lt;b&gt;feature&lt;/b&gt; | abcdef1 | 2026-07-21", badge_html)
        self.assertNotIn("<b>feature</b>", badge_html)
        self.assertLess(
            fake_st.events.index(("markdown", badge_html, unsafe)),
            fake_st.events.index(("stop", None)),
        )

    def test_access_denied_screen_renders_build_badge_before_stop(self):
        fake_st = FakeStreamlit(is_logged_in=True, email="blocked@example.com")

        load_app(
            fake_st,
            {
                "GOOGLE_CLIENT_ID": "client-id",
                "ALLOWED_EMAILS": "allowed@example.com",
                "APP_VERSION": "master",
                "APP_GIT_SHA": "abcdef1",
                "APP_BUILD_DATE": "2026-07-21",
            },
        )

        self.assertTrue(fake_st.markdown_calls, "expected build badge to render before st.stop()")
        badge_html, unsafe = fake_st.markdown_calls[0]
        self.assertIn("master | abcdef1 | 2026-07-21", badge_html)
        self.assertLess(
            fake_st.events.index(("markdown", badge_html, unsafe)),
            fake_st.events.index(("stop", None)),
        )
