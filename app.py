"""
LinkedIn Job Scraper — Web Interface
Run with: streamlit run app.py
"""

import io
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent
TOOLS_DIR = BASE_DIR / "tools"

PYTHON = sys.executable
IN_CLOUD = os.environ.get("RUNNING_IN_CLOUD") == "true"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LinkedIn Job Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate ──────────────────────────────────────────────────────────────────
# Only enforce login when Google OAuth env vars are configured
GOOGLE_AUTH_ENABLED = bool(os.environ.get("GOOGLE_CLIENT_ID"))

# Allowlist: comma-separated emails in ALLOWED_EMAILS env var
# e.g. ALLOWED_EMAILS=alice@gmail.com,bob@company.com
# If not set, any authenticated Google account is allowed
_raw_allowed = os.environ.get("ALLOWED_EMAILS", "")
ALLOWED_EMAILS = {e.strip().lower() for e in _raw_allowed.split(",") if e.strip()}

if GOOGLE_AUTH_ENABLED:
    if not st.user.is_logged_in:
        st.title("🔍 LinkedIn Job Scraper")
        st.info("Sign in with your Google account to continue.")
        st.button("Sign in with Google", on_click=st.login, type="primary")
        st.stop()

    # Check allowlist (only if one is configured)
    if ALLOWED_EMAILS and st.user.email.lower() not in ALLOWED_EMAILS:
        st.error(f"Access denied. **{st.user.email}** is not authorised to use this app.")
        st.button("Sign out", on_click=st.logout)
        st.stop()

    # Per-user output folder: .tmp/<sanitized_email>/
    _safe_email = re.sub(r"[^\w]", "_", st.user.email)
    OUTPUT_DIR = BASE_DIR / ".tmp" / _safe_email
else:
    OUTPUT_DIR = BASE_DIR / ".tmp"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.title("🔍 LinkedIn Job Scraper")
st.caption("Scrape LinkedIn job listings and export to Excel.")

# ── Sidebar — Controls ────────────────────────────────────────────────────────

with st.sidebar:
    if GOOGLE_AUTH_ENABLED and st.user.is_logged_in:
        st.caption(f"Signed in as **{st.user.email}**")
        st.button("Sign out", on_click=st.logout)
        st.divider()

    st.header("Search Settings")

    mode = st.radio(
        "Scrape mode",
        ["Single Region", "Multi-Region (APAC / SEA)"],
        index=0,
    )

    keyword = st.text_input("Keyword", value="Sales", placeholder="e.g. Sales, AI, Data Engineer")

    if mode == "Single Region":
        location = st.text_input("Location", value="Singapore", placeholder="e.g. Singapore, Tokyo")
        max_pages = st.slider("Max pages", min_value=1, max_value=20, value=5,
                              help="25 jobs per page (~58 unique without login)")
    else:
        region = st.selectbox("Region", ["apac", "sea"],
                              format_func=lambda r: {"apac": "Asia-Pacific (12 countries)", "sea": "Southeast Asia (7 countries)"}[r])
        target = st.number_input("Target jobs", min_value=10, max_value=500, value=50, step=10)

    st.divider()
    st.subheader("Filters")

    EXP_LEVEL_MAP = {
        "Internship":      "1",
        "Entry Level":     "2",
        "Associate":       "3",
        "Mid-Senior Level":"4",
        "Director":        "5",
        "Executive":       "6",
    }
    exp_levels_sel = st.multiselect(
        "Position / Level",
        list(EXP_LEVEL_MAP.keys()),
        placeholder="Any level",
    )

    INDUSTRY_MAP = {
        "Technology (Software)":    "4",
        "Technology (Internet)":    "6",
        "Technology (Hardware)":    "96",
        "Financial Services":       "43",
        "Banking":                  "41",
        "Healthcare":               "14",
        "Management Consulting":    "78",
        "Marketing & Advertising":  "80",
        "Real Estate":              "44",
        "Retail":                   "27",
        "Education":                "69",
        "Manufacturing":            "22",
    }
    industries_sel = st.multiselect(
        "Industry",
        list(INDUSTRY_MAP.keys()),
        placeholder="Any industry",
    )

    SALARY_MAP = {
        "Any":        "",
        "SGD 40K+":  "1",
        "SGD 60K+":  "2",
        "SGD 80K+":  "3",
        "SGD 100K+": "4",
        "SGD 120K+": "5",
        "SGD 140K+": "6",
        "SGD 160K+": "7",
        "SGD 180K+": "8",
        "SGD 200K+": "9",
    }
    salary_sel = st.selectbox("Minimum Salary", list(SALARY_MAP.keys()))

    st.divider()
    st.subheader("Options")
    fetch_details = st.toggle("Fetch full descriptions", value=False,
                              help="Visits each job page — much slower but adds description text")
    if IN_CLOUD:
        headless = True
        st.caption("🌐 Cloud mode: browser runs headless automatically.")
    else:
        headless = st.toggle("Headless browser", value=False,
                             help="Hide the browser window (faster but slightly more detectable)")

    st.divider()
    run_btn = st.button("▶ Run Scraper", type="primary", use_container_width=True)

# ── Background process helpers ────────────────────────────────────────────────

LOG_FILE = OUTPUT_DIR / "current.log"
PID_FILE = OUTPUT_DIR / "current.pid"


def is_process_running(pid: int) -> bool:
    """Check if a process is still alive by PID."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def launch_scraper(cmd: list[str]) -> int:
    """Start scraper as a detached process; returns PID.
    Uses start_new_session=True so it survives browser disconnects."""
    proc_env = os.environ.copy()
    proc_env.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8":       "1",
        "PYTHONUNBUFFERED": "1",
    })
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8", errors="replace") as log_f:
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,   # detach — survives browser disconnect
            cwd=str(BASE_DIR),
            env=proc_env,
        )
    PID_FILE.write_text(str(proc.pid))
    return proc.pid


def stop_scraper():
    """Terminate the running scraper process."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)
    st.session_state.is_scraping = False


def read_log() -> str:
    try:
        return LOG_FILE.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_progress(log_content: str, total_steps: int, scrape_mode: str, still_running: bool):
    """Return (progress_fraction, progress_text) by scanning the log.
    Never returns 1.0 while the process is still alive — avoids premature
    100% when e.g. a single-page scrape shows 'Page 1/1' early on."""
    pct, text = 0.0, "Running..."
    for line in log_content.splitlines():
        # Detail-fetch lines: "    [3/25] Job Title @ Company"
        m_detail = re.search(r"\[(\d+)/(\d+)\]", line)
        if m_detail:
            cur, tot = int(m_detail.group(1)), int(m_detail.group(2))
            if tot > 0:
                pct = cur / tot
                text = f"Fetching details {cur} of {tot}..."
            continue
        # Page progress: "Page 2/5"
        m = re.search(r"Page\s+(\d+)/(\d+)", line)
        if m:
            cur, tot = int(m.group(1)), int(m.group(2))
            pct = cur / max(tot, 1)
            text = f"Scraping page {cur} of {tot}..."
        # Multi-region total: "Total: 34"
        m2 = re.search(r"Total:\s*(\d+)", line)
        if m2 and scrape_mode != "Single Region":
            cur = int(m2.group(1))
            pct = cur / max(total_steps, 1)
            text = f"Collected {cur} / {total_steps} jobs..."
        # Final collection summary: "Collected 57 unique jobs (from 66 total)."
        m3 = re.search(r"Collected\s+(\d+)\s+unique jobs \(from\s+(\d+)\s+total\)", line)
        if m3:
            unique, total = int(m3.group(1)), int(m3.group(2))
            pct = 0.98
            text = f"Collected {unique} / {total} unique jobs"
    # While still running, cap at 0.95 so bar never falsely hits 100%
    if still_running:
        pct = min(pct, 0.95)
    return min(pct, 1.0), text


# ── Build command ─────────────────────────────────────────────────────────────

def build_command() -> list[str]:
    exp_codes      = ",".join(EXP_LEVEL_MAP[s] for s in exp_levels_sel)
    industry_codes = ",".join(INDUSTRY_MAP[s] for s in industries_sel)
    salary_code    = SALARY_MAP[salary_sel]

    if mode == "Single Region":
        cmd = [
            PYTHON, "-u", str(TOOLS_DIR / "scrape_linkedin_jobs.py"),
            "--keyword", keyword,
            "--location", location,
            "--max-pages", str(max_pages),
        ]
        if fetch_details:
            cmd.append("--fetch-details")
    else:
        cmd = [
            PYTHON, "-u", str(TOOLS_DIR / "scrape_linkedin_multiregion.py"),
            "--keyword", keyword,
            "--target", str(target),
            "--regions", region,
        ]

    if exp_codes:      cmd += ["--exp-levels",  exp_codes]
    if industry_codes: cmd += ["--industries",   industry_codes]
    if salary_code:    cmd += ["--min-salary",   salary_code]
    if headless:       cmd.append("--headless")
    cmd += ["--output-dir", str(OUTPUT_DIR)]
    # Send notification to the logged-in user's email (falls back to NOTIFY_EMAIL env var)
    if GOOGLE_AUTH_ENABLED and st.user.is_logged_in:
        cmd += ["--notify-email", st.user.email]
    return cmd


def latest_output_file() -> Path | None:
    files = sorted(OUTPUT_DIR.glob("linkedin_*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


# ── Session state init ────────────────────────────────────────────────────────

if "is_scraping"       not in st.session_state: st.session_state.is_scraping       = False
if "scrape_pid"        not in st.session_state: st.session_state.scrape_pid        = None
if "total_steps"       not in st.session_state: st.session_state.total_steps       = 5
if "scrape_mode_s"     not in st.session_state: st.session_state.scrape_mode_s     = "Single Region"
if "scrape_completed"  not in st.session_state: st.session_state.scrape_completed  = False

# Reconcile: process may have finished between page loads.
# Set a flag so the Run tab can still show the Done! state + download button.
if st.session_state.is_scraping and not is_process_running(st.session_state.scrape_pid):
    st.session_state.is_scraping = False
    log_snap = read_log()
    st.session_state.scrape_completed = "Saved" in log_snap or ".xlsx" in log_snap

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_run, tab_results, tab_history = st.tabs(["▶ Run", "📊 Results", "🗂 History"])

# ── Tab 1: Run ────────────────────────────────────────────────────────────────

with tab_run:

    # ── Launch new scrape ──────────────────────────────────────────────────────
    if run_btn and not st.session_state.is_scraping:
        if not keyword.strip():
            st.warning("Enter a keyword before running.")
        else:
            cmd = build_command()
            st.session_state.scrape_pid    = launch_scraper(cmd)
            st.session_state.is_scraping   = True
            st.session_state.total_steps   = max_pages if mode == "Single Region" else int(target)
            st.session_state.scrape_mode_s = mode
            st.rerun()

    # ── Show progress while running ────────────────────────────────────────────
    if st.session_state.is_scraping:
        still_running = is_process_running(st.session_state.scrape_pid)

        st.subheader("Scraping in progress...")
        if st.button("⏹ Stop", type="secondary"):
            stop_scraper()
            st.warning("Scrape stopped.")
            st.rerun()

        log_content = read_log()
        pct, prog_text = parse_progress(
            log_content,
            st.session_state.total_steps,
            st.session_state.scrape_mode_s,
            still_running,
        )
        st.progress(pct, text=prog_text)
        st.code(log_content[-4000:] if log_content else "Starting...", language=None)

        if still_running:
            time.sleep(3)
            st.rerun()
        else:
            # Process just finished — set flag so the display block below shows Done!
            st.session_state.is_scraping = False
            log_content = read_log()
            st.session_state.scrape_completed = "Saved" in log_content or ".xlsx" in log_content
            st.rerun()

    # ── Done state (process just finished) ─────────────────────────────────────
    elif st.session_state.scrape_completed:
        st.session_state.scrape_completed = False   # clear flag after first render
        log_content = read_log()
        _, final_text = parse_progress(log_content, st.session_state.total_steps,
                                       st.session_state.scrape_mode_s, still_running=False)
        st.progress(1.0, text=f"Done! — {final_text}")
        st.success("Scrape completed! Results are in the **Results** tab.")
        st.code(log_content[-4000:] if log_content else "", language=None)
        out_file = latest_output_file()
        if out_file:
            st.download_button(
                label="⬇ Download Excel",
                data=out_file.read_bytes(),
                file_name=out_file.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        elif log_content:
            st.error("Scraper exited with errors. Check the log above.")

    # ── Idle state ─────────────────────────────────────────────────────────────
    elif not run_btn:
        st.info("Configure your search in the sidebar and click **Run Scraper**.")
        st.caption("💡 The scraper runs on the server — closing your browser or letting your laptop sleep won't interrupt it.")

# ── Tab 2: Results ────────────────────────────────────────────────────────────

with tab_results:
    out_file = latest_output_file()

    if out_file is None:
        st.info("No results yet. Run the scraper first.")
    else:
        st.subheader(f"Latest: `{out_file.name}`")

        try:
            file_bytes = out_file.read_bytes()
            df = pd.read_excel(io.BytesIO(file_bytes))
            df = df.fillna("")
        except PermissionError:
            st.error(f"**Permission denied** — close `{out_file.name}` in Excel first, then refresh.")
            st.stop()
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Jobs", len(df))
        col2.metric("Companies", df["Company"].nunique() if "Company" in df.columns else "—")
        col3.metric("File size", f"{out_file.stat().st_size / 1024:.1f} KB")

        if "Job URL" in df.columns:
            df["Job URL"] = df["Job URL"].apply(
                lambda u: f'<a href="{u}" target="_blank">Link</a>' if pd.notna(u) and u else ""
            )
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.dataframe(df, use_container_width=True)

        st.divider()
        st.download_button(
            label="⬇ Download Excel",
            data=file_bytes,
            file_name=out_file.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ── Tab 3: History ────────────────────────────────────────────────────────────

with tab_history:
    xlsx_files = sorted(OUTPUT_DIR.glob("linkedin_*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not xlsx_files:
        st.info("No previous scrape files found.")
    else:
        st.subheader(f"{len(xlsx_files)} scrape file(s) found")

        for f in xlsx_files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size_kb = f.stat().st_size / 1024

            try:
                f_bytes = f.read_bytes()
                row_count = len(pd.read_excel(io.BytesIO(f_bytes)))
            except Exception:
                f_bytes = None
                row_count = "?"

            col_name, col_meta, col_dl = st.columns([4, 3, 2])
            col_name.markdown(f"**{f.name}**")
            col_meta.caption(f"{mtime} · {row_count} rows · {size_kb:.1f} KB")
            if f_bytes:
                col_dl.download_button(
                    label="⬇ Download",
                    data=f_bytes,
                    file_name=f.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{f.name}",
                )
            else:
                col_dl.caption("File locked")
