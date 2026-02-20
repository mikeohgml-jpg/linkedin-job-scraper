"""
LinkedIn Job Scraper — Web Interface
Run with: streamlit run app.py
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from subprocess import PIPE, STDOUT

import io
import re

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent
TOOLS_DIR = BASE_DIR / "tools"
OUTPUT_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR.mkdir(exist_ok=True)

PYTHON = sys.executable
IN_CLOUD = os.environ.get("RUNNING_IN_CLOUD") == "true"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LinkedIn Job Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔍 LinkedIn Job Scraper")
st.caption("Scrape LinkedIn job listings and export to Excel.")

# ── Sidebar — Controls ────────────────────────────────────────────────────────

with st.sidebar:
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

# ── Build command ─────────────────────────────────────────────────────────────

def build_command() -> list[str]:
    # Resolve filter values
    exp_codes     = ",".join(EXP_LEVEL_MAP[s] for s in exp_levels_sel)
    industry_codes = ",".join(INDUSTRY_MAP[s] for s in industries_sel)
    salary_code   = SALARY_MAP[salary_sel]

    if mode == "Single Region":
        cmd = [
            PYTHON, str(TOOLS_DIR / "scrape_linkedin_jobs.py"),
            "--keyword", keyword,
            "--location", location,
            "--max-pages", str(max_pages),
        ]
        if fetch_details:
            cmd.append("--fetch-details")
    else:
        cmd = [
            PYTHON, str(TOOLS_DIR / "scrape_linkedin_multiregion.py"),
            "--keyword", keyword,
            "--target", str(target),
            "--regions", region,
        ]

    if exp_codes:
        cmd += ["--exp-levels", exp_codes]
    if industry_codes:
        cmd += ["--industries", industry_codes]
    if salary_code:
        cmd += ["--min-salary", salary_code]
    if headless:
        cmd.append("--headless")
    return cmd


def latest_output_file() -> Path | None:
    files = sorted(OUTPUT_DIR.glob("linkedin_*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_run, tab_results, tab_history = st.tabs(["▶ Run", "📊 Results", "🗂 History"])

# ── Tab 1: Run ────────────────────────────────────────────────────────────────

with tab_run:
    if not keyword.strip():
        st.warning("Enter a keyword before running.")
    elif run_btn:
        cmd = build_command()

        st.subheader("Progress")
        st.code(" ".join(cmd), language="bash")

        # Progress bar + status line sit above the log
        progress_bar  = st.progress(0, text="Starting...")
        status_line   = st.empty()
        log_box       = st.empty()
        status_box    = st.empty()
        lines: list[str] = []

        # Determine the progress denominator upfront
        if mode == "Single Region":
            total_steps = max_pages          # Page X / max_pages
            progress_unit = "pages"
        else:
            total_steps = target             # Total: N / target
            progress_unit = "jobs"

        current_step = 0

        proc_env = os.environ.copy()
        proc_env["PYTHONIOENCODING"] = "utf-8"
        proc_env["PYTHONUTF8"] = "1"

        process = subprocess.Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            cwd=str(BASE_DIR),
            encoding="utf-8",
            errors="replace",
            env=proc_env,
        )

        for line in process.stdout:
            lines.append(line)
            log_box.code("".join(lines[-60:]))

            # ── Parse progress from stdout ──────────────────────────────
            # Single mode: "Page 2/5 — start=25"
            m_page = re.search(r"Page\s+(\d+)/(\d+)", line)
            if m_page:
                current_step = int(m_page.group(1))
                total_steps  = int(m_page.group(2))
                pct = min(current_step / total_steps, 1.0)
                progress_bar.progress(
                    pct,
                    text=f"Scraping page {current_step} of {total_steps}..."
                )
                status_line.caption(line.strip())
                continue

            # Multi mode: "+12 new unique jobs | Total: 34"
            m_total = re.search(r"Total:\s*(\d+)", line)
            if m_total:
                current_step = int(m_total.group(1))
                pct = min(current_step / total_steps, 1.0)
                progress_bar.progress(
                    pct,
                    text=f"Collected {current_step} / {total_steps} jobs..."
                )
                status_line.caption(line.strip())
                continue

            # Country header: "--- Singapore (need 40 more) ---"
            m_country = re.search(r"---\s*(.+?)\s*\(need", line)
            if m_country:
                status_line.caption(f"Searching: {m_country.group(1).strip()}")

        process.wait()

        if process.returncode == 0:
            progress_bar.progress(1.0, text="Done!")
            status_line.empty()
            status_box.success("Scrape completed successfully!")
            out_file = latest_output_file()
            if out_file:
                file_bytes = out_file.read_bytes()
                st.info(f"Output: `{out_file.name}`")
                st.download_button(
                    label="⬇ Download Excel",
                    data=file_bytes,
                    file_name=out_file.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
        else:
            progress_bar.progress(1.0, text="Failed")
            status_box.error("Scraper exited with errors. Check the log above.")
    else:
        st.info("Configure your search in the sidebar and click **Run Scraper**.")

# ── Tab 2: Results ────────────────────────────────────────────────────────────

with tab_results:
    out_file = latest_output_file()

    if out_file is None:
        st.info("No results yet. Run the scraper first.")
    else:
        st.subheader(f"Latest: `{out_file.name}`")

        # Read bytes first — avoids PermissionError when file is open in Excel
        try:
            file_bytes = out_file.read_bytes()
            df = pd.read_excel(io.BytesIO(file_bytes))
            # Replace NaN with empty string for display (NaN appears in optional columns
            # like Seniority, Employment Type, Description when fetch-details wasn't used)
            df = df.fillna("")
        except PermissionError:
            st.error(
                f"**Permission denied** — close `{out_file.name}` in Excel first, then refresh this page."
            )
            st.stop()
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Jobs", len(df))
        col2.metric("Companies", df["Company"].nunique() if "Company" in df.columns else "—")
        col3.metric(
            "File size",
            f"{out_file.stat().st_size / 1024:.1f} KB",
        )

        # Make URLs clickable
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
        st.info("No previous scrape files found in `.tmp/`.")
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
