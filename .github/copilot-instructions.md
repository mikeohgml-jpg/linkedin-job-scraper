# Copilot Instructions

## Build, run, and verification commands

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m streamlit run app.py
python -m unittest discover -v
python -m unittest tests.test_email_notifications
python tools/scrape_linkedin_jobs.py --keyword "Sales" --location "Singapore" --max-pages 1
python tools/scrape_linkedin_multiregion.py --keyword "AI" --target 20 --regions apac --headless
docker build -t linkedin-job-scraper .
docker run --env-file .env -p 8501:8501 linkedin-job-scraper
```

This repository does **not** define a linter or formatter config. The automated tests are a small `unittest` regression slice around the shared email helper, and the closest end-to-end verification is running one scraper directly with a small page/target count.

## High-level architecture

- `app.py` is the Streamlit control plane. It handles Google login/allowlisting, builds scraper CLI arguments, launches the selected scraper as a detached subprocess, tails `.tmp/.../current.log`, parses progress from scraper stdout, and renders/downloads the latest Excel output.
- `build_info.py` owns the header build badge metadata and HTML formatting. Keep badge fallback logic there so `app.py` only passes environment data into `resolve_build_metadata()` and renders the helper output.
- `tools/scrape_linkedin_jobs.py` is the single-region scraper. `tools/scrape_linkedin_multiregion.py` is the multi-region aggregator across preset location lists. Both use Playwright for LinkedIn page automation, pandas/openpyxl for Excel export, and the shared `tools/email_notifications.py` helper for Resend-based completion emails when env vars are configured.
- `entrypoint.sh` and `Dockerfile` are the cloud path. The container installs Chromium dependencies, sets `RUNNING_IN_CLOUD=true`, and generates `.streamlit/secrets.toml` from environment variables so `st.login()` can use Google OAuth without committing secrets.
- This repo follows the WAT pattern documented in `CLAUDE.md`: `workflows/` contains SOP-style instructions, and `tools/` contains the deterministic Python executors. When changing scraper behavior, read the relevant workflow first and prefer updating scripts over pushing execution logic into the agent/session.

## Key repository conventions

- Keep the UI and CLI in sync. `app.py` depends on scraper flags such as `--fetch-details`, `--output-dir`, and `--notify-email`; if scraper arguments change, update `build_command()` in `app.py` at the same time.
- Treat `APP_VERSION` as the managed product release number. Only change it for user-visible releases; when it is unset, the build badge must fall back automatically to Railway branch/SHA metadata, and only include a date when an explicit immutable build date is available.
- Preserve scraper log phrases unless you also update `app.py::parse_progress()`. The UI progress bar currently infers state from stdout lines like `Page X/Y`, `Total: N`, and `Collected ... unique jobs`.
- Output is intentionally disposable and local to `.tmp/`. When auth is enabled, `app.py` writes per-user artifacts under `.tmp/<sanitized_email>/`; do not hardcode shared output paths for authenticated runs.
- Preserve the anti-detection/browser setup already shared across the scrapers: custom user agent, `navigator.webdriver` masking, random delays, modal dismissal, and headful-by-default local runs. Cloud runs are forced headless through `RUNNING_IN_CLOUD`.
- Excel output shape is part of the app contract. The Results and History tabs expect stable filenames (`linkedin_<...>_<timestamp>.xlsx`) and columns such as `Company` and `Job URL`.
- Follow the repo’s secret handling from `.gitignore` and `CLAUDE.md`: keep credentials in `.env` or generated `.streamlit/secrets.toml`, never in source, and treat `.tmp/` as regenerable.
