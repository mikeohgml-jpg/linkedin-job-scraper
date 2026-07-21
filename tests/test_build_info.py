import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "build_info.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_info", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuildInfoTests(TestCase):
    def test_resolves_dynamic_railway_metadata(self):
        module = load_module()

        metadata = module.resolve_build_metadata(
            {
                "RAILWAY_GIT_BRANCH": "master",
                "RAILWAY_GIT_COMMIT_SHA": "d6a4d55179f19a2246199053749c0eaa593df96e",
            },
            today_provider=Mock(return_value="2026-07-21"),
        )

        self.assertEqual(
            metadata,
            {
                "version": "master",
                "git_sha": "d6a4d55",
                "build_date": "2026-07-21",
            },
        )

    def test_prefers_explicit_app_metadata(self):
        module = load_module()

        metadata = module.resolve_build_metadata(
            {
                "APP_VERSION": "v1.2.0",
                "APP_GIT_SHA": "abcdef123456",
                "APP_BUILD_DATE": "2026-07-20",
                "RAILWAY_GIT_BRANCH": "master",
                "RAILWAY_GIT_COMMIT_SHA": "d6a4d55179f19a2246199053749c0eaa593df96e",
            },
            today_provider=Mock(return_value="2026-07-21"),
        )

        self.assertEqual(
            metadata,
            {
                "version": "v1.2.0",
                "git_sha": "abcdef1",
                "build_date": "2026-07-20",
            },
        )

    def test_formats_full_build_label(self):
        module = load_module()
        self.assertEqual(
            module.format_build_label("v1.2.0", "d6a4d55", "2026-07-21"),
            "v1.2.0 | d6a4d55 | 2026-07-21",
        )

    def test_omits_missing_parts(self):
        module = load_module()
        self.assertEqual(module.format_build_label("", "d6a4d55", ""), "d6a4d55")
