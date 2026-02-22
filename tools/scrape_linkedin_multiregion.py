"""
LinkedIn Multi-Region Job Scraper
Searches multiple countries/cities and aggregates results up to a target count.

Usage:
    python tools/scrape_linkedin_multiregion.py --keyword "AI" --target 50 --regions apac
    python tools/scrape_linkedin_multiregion.py --keyword "Sales" --target 100 --regions apac
"""

import argparse
import os
import random
import re
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Force UTF-8 output on Windows (avoids UnicodeEncodeError with special chars in job titles)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

OUTPUT_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR.mkdir(exist_ok=True)

SMTP_USER     = os.getenv("SMTP_USER") or os.getenv("GMAIL_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL  = os.getenv("NOTIFY_EMAIL", "")


def send_completion_email(job_count: int, keyword: str, region: str, filename: str):
    """Send a Gmail notification when the scrape finishes."""
    if not (SMTP_USER and SMTP_PASSWORD and NOTIFY_EMAIL):
        print("  (Email notification skipped — SMTP_USER / SMTP_PASSWORD / NOTIFY_EMAIL not configured)")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ LinkedIn Scrape Done: {job_count} '{keyword}' jobs in {region.upper()}"
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_EMAIL
        body = (
            f"Your LinkedIn scrape has completed!\n\n"
            f"  Keyword : {keyword}\n"
            f"  Region  : {region.upper()}\n"
            f"  Jobs    : {job_count}\n"
            f"  File    : {Path(filename).name}\n\n"
            f"Log in to the app to view and download your results."
        )
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
        print(f"  Email notification sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  Email notification failed: {e}")

REGIONS = {
    "apac": [
        "Singapore",
        "Australia",
        "Japan",
        "India",
        "Hong Kong",
        "South Korea",
        "China",
        "Malaysia",
        "New Zealand",
        "Philippines",
        "Indonesia",
        "Thailand",
    ],
    "sea": [
        "Singapore",
        "Malaysia",
        "Philippines",
        "Indonesia",
        "Thailand",
        "Vietnam",
        "Myanmar",
    ],
}


def human_delay(min_s=1.5, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))


def build_search_url(keyword: str, location: str, start: int = 0,
                     exp_levels: str = "", industries: str = "", min_salary: str = "") -> str:
    import urllib.parse
    params = {
        "keywords": keyword,
        "location": location,
        "f_TPR": "",
        "position": 1,
        "pageNum": 0,
        "start": start,
    }
    if exp_levels:
        params["f_E"] = exp_levels
    if industries:
        params["f_I"] = industries
    if min_salary:
        params["f_SB2"] = min_salary
    return "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)


def dismiss_signin_modal(page):
    try:
        close_btn = page.locator("button.modal__dismiss, [aria-label='Dismiss'], .modal__dismiss")
        if close_btn.count() > 0:
            close_btn.first.click()
            human_delay(0.5, 1)
    except Exception:
        pass


def extract_jobs_from_page(page, location: str) -> list[dict]:
    jobs = []
    try:
        page.wait_for_selector(
            ".job-search-card, .base-card, ul.jobs-search__results-list",
            timeout=12000,
        )
    except PlaywrightTimeoutError:
        return jobs

    dismiss_signin_modal(page)

    # Scroll to trigger lazy-loaded cards
    for _ in range(3):
        page.keyboard.press("End")
        human_delay(0.8, 1.5)

    # Use the selectors confirmed working via debug
    cards = page.locator(".job-search-card").all()
    if not cards:
        cards = page.locator(".base-card").all()
    if not cards:
        cards = page.locator("ul.jobs-search__results-list > li").all()

    for card in cards:
        try:
            title = card.locator("h3.base-search-card__title, h3").first.inner_text(timeout=2000).strip()
        except Exception:
            title = ""

        try:
            company = card.locator("h4.base-search-card__subtitle, h4").first.inner_text(timeout=2000).strip()
        except Exception:
            company = ""

        try:
            loc = card.locator(".job-search-card__location, .base-search-card__metadata").first.inner_text(timeout=2000).strip()
        except Exception:
            loc = location  # fallback to search location

        try:
            posted = card.locator("time, .job-search-card__listdate").first.inner_text(timeout=2000).strip()
        except Exception:
            posted = ""

        try:
            href = card.locator("a.base-card__full-link, a[href*='/jobs/view/']").first.get_attribute("href", timeout=2000) or ""
            job_url = href.split("?")[0]
            if job_url and not job_url.startswith("http"):
                job_url = "https://www.linkedin.com" + job_url
        except Exception:
            job_url = ""

        if title or company:
            jobs.append({
                "Job Title": title,
                "Company": company,
                "Location": loc,
                "Posted": posted,
                "Job URL": job_url,
                "Search Region": location,
                "Seniority": "",
                "Employment Type": "",
            })

    return jobs


def scrape_location(page, keyword: str, location: str, target: int,
                    exp_levels: str = "", industries: str = "", min_salary: str = "") -> list[dict]:
    """Scrape jobs for a single location, stopping when target is reached."""
    collected = []

    for page_num in range(5):  # max 5 pages per location
        start = page_num * 25
        url = build_search_url(keyword, location, start, exp_levels, industries, min_salary)
        print(f"    Page {page_num + 1} | start={start} | {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            human_delay(2, 4)
        except PlaywrightTimeoutError:
            print(f"    Timeout — skipping page.")
            break

        if "captcha" in page.url.lower():
            print("    CAPTCHA — waiting 30s...")
            time.sleep(30)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                human_delay(3, 5)
            except Exception:
                break

        jobs = extract_jobs_from_page(page, location)
        print(f"    Found {len(jobs)} cards.")

        if not jobs:
            break

        collected.extend(jobs)

        if len(jobs) < 20:
            break  # last page for this location

        if len(collected) >= target:
            break

        human_delay(2, 4)

    return collected


def save_to_excel(jobs: list[dict], keyword: str, region: str, target: int) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = re.sub(r"[^\w]", "_", keyword)
    safe_region = re.sub(r"[^\w]", "_", region)
    filename = OUTPUT_DIR / f"linkedin_{safe_kw}_{safe_region}_{timestamp}.xlsx"

    df = pd.DataFrame(jobs, columns=[
        "Job Title", "Company", "Location", "Posted",
        "Job URL", "Search Region", "Seniority", "Employment Type",
    ])
    df = df.fillna("")  # replace NaN with blank so Excel shows empty cells, not "NaN"

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jobs")
        ws = writer.sheets["Jobs"]

        col_widths = {
            "A": 40, "B": 30, "C": 25, "D": 15,
            "E": 55, "F": 18, "G": 20, "H": 20,
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"

    return filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", default="AI", help="Job search keyword")
    parser.add_argument("--target", type=int, default=50, help="Target number of unique jobs")
    parser.add_argument("--regions", default="apac", choices=list(REGIONS.keys()), help="Region preset")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--exp-levels", default="", help="Experience level codes e.g. '2,3,4'")
    parser.add_argument("--industries", default="", help="Industry codes e.g. '4,6,96'")
    parser.add_argument("--min-salary", default="", help="Minimum salary code (1–9)")
    parser.add_argument("--output-dir", default="", help="Override output directory for Excel files")
    args = parser.parse_args()

    # Per-user output directory (passed from app.py when auth is enabled)
    global OUTPUT_DIR
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    locations = REGIONS[args.regions]

    print("=" * 60)
    print(f"LinkedIn Multi-Region Job Scraper")
    print(f"  Keyword : {args.keyword}")
    print(f"  Region  : {args.regions} ({len(locations)} locations)")
    print(f"  Target  : {args.target} unique jobs")
    if args.exp_levels:  print(f"  Exp levels: {args.exp_levels}")
    if args.industries:  print(f"  Industries: {args.industries}")
    if args.min_salary:  print(f"  Min salary: {args.min_salary}")
    print("=" * 60)

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",   # prevents Chromium crash in Docker (limited /dev/shm)
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for loc in locations:
            remaining = args.target - len(all_jobs)
            if remaining <= 0:
                print(f"\nTarget of {args.target} reached — stopping.")
                break

            print(f"\n--- {loc} (need {remaining} more) ---")
            raw_jobs = scrape_location(page, args.keyword, loc, remaining,
                                       args.exp_levels, args.industries, args.min_salary)

            # Deduplicate globally by URL
            new_count = 0
            for job in raw_jobs:
                key = job["Job URL"] or f"{job['Job Title']}|{job['Company']}"
                if key not in seen_urls:
                    seen_urls.add(key)
                    all_jobs.append(job)
                    new_count += 1

            print(f"  +{new_count} new unique jobs | Total: {len(all_jobs)}")
            human_delay(2, 4)

        browser.close()

    if not all_jobs:
        print("\nNo jobs collected.")
        sys.exit(1)

    # Trim to target
    final_jobs = all_jobs[:args.target]
    output_path = save_to_excel(final_jobs, args.keyword, args.regions, args.target)

    print(f"\nCollected {len(final_jobs)} unique jobs.")
    print(f"Saved to: {output_path}")
    send_completion_email(len(final_jobs), args.keyword, args.regions, str(output_path))
    print("Done.")


if __name__ == "__main__":
    main()
