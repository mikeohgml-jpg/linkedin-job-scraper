"""
LinkedIn Sales Jobs Scraper — Singapore
Tool in the WAT framework.

Usage:
    python tools/scrape_linkedin_jobs.py
    python tools/scrape_linkedin_jobs.py --keyword "Sales" --max-pages 5 --headless
"""

import argparse
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows (avoids UnicodeEncodeError with special chars in job titles)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

OUTPUT_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def slow_type(page, selector, text, delay_ms=80):
    """Type like a human."""
    page.click(selector)
    for char in text:
        page.keyboard.press(char)
        time.sleep(random.uniform(0.05, 0.15))


def human_delay(min_s=1.5, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))


def build_search_url(keyword: str, location: str, start: int = 0,
                     exp_levels: str = "", industries: str = "", min_salary: str = "") -> str:
    import urllib.parse
    params = {
        "keywords": keyword,
        "location": location,
        "f_TPR": "",          # time filter — empty = all time
        "position": 1,
        "pageNum": 0,
        "start": start,
    }
    if exp_levels:
        params["f_E"] = exp_levels        # e.g. "2,3,4"
    if industries:
        params["f_I"] = industries        # e.g. "4,6,96"
    if min_salary:
        params["f_SB2"] = min_salary      # e.g. "3" = SGD 80K+
    return "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)


# ── Login ─────────────────────────────────────────────────────────────────────

def login(page) -> bool:
    """Log in to LinkedIn. Returns True on success."""
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        return False

    print("  Logging in to LinkedIn...")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    human_delay(1, 2)

    try:
        slow_type(page, "#username", LINKEDIN_EMAIL)
        human_delay(0.3, 0.8)
        slow_type(page, "#password", LINKEDIN_PASSWORD)
        human_delay(0.3, 0.8)
        page.click("button[type='submit']")
        page.wait_for_url("**/feed/**", timeout=15000)
        print("  Logged in successfully.")
        return True
    except PlaywrightTimeoutError:
        print("  Login failed or CAPTCHA detected — continuing as guest.")
        return False


# ── Scraping ──────────────────────────────────────────────────────────────────

def dismiss_signin_modal(page):
    """Close the 'Sign in to see more' modal if it appears."""
    try:
        close_btn = page.locator("button.modal__dismiss, [aria-label='Dismiss'], .modal__dismiss")
        if close_btn.count() > 0:
            close_btn.first.click()
            human_delay(0.5, 1)
    except Exception:
        pass


def extract_jobs_from_page(page) -> list[dict]:
    """Parse job cards from the current search results page."""
    jobs = []

    # Wait for job list to load
    try:
        page.wait_for_selector("ul.jobs-search__results-list, .jobs-search-results-list", timeout=10000)
    except PlaywrightTimeoutError:
        print("  No job list found on page.")
        return jobs

    dismiss_signin_modal(page)

    # Scroll to load all cards on page
    for _ in range(4):
        page.keyboard.press("End")
        human_delay(0.8, 1.5)

    cards = page.locator("li.jobs-search__results-list > div, .job-search-card").all()

    # Fallback selector for public (non-logged-in) view
    if not cards:
        cards = page.locator("ul.jobs-search__results-list > li").all()

    print(f"  Found {len(cards)} cards on page.")

    for card in cards:
        try:
            title = card.locator("h3.base-search-card__title, .job-card-list__title, h3").first.inner_text(timeout=2000).strip()
        except Exception:
            title = ""

        try:
            company = card.locator("h4.base-search-card__subtitle, .job-card-container__company-name, h4").first.inner_text(timeout=2000).strip()
        except Exception:
            company = ""

        try:
            location = card.locator(".job-search-card__location, .job-card-container__metadata-item").first.inner_text(timeout=2000).strip()
        except Exception:
            location = ""

        try:
            posted = card.locator("time, .job-search-card__listdate").first.inner_text(timeout=2000).strip()
        except Exception:
            posted = ""

        try:
            href = card.locator("a[href*='/jobs/view/'], a.base-card__full-link").first.get_attribute("href", timeout=2000) or ""
            # Strip tracking params — keep clean URL
            job_url = re.sub(r"\?.*", "", href.split("?")[0])
            if job_url and not job_url.startswith("http"):
                job_url = "https://www.linkedin.com" + job_url
        except Exception:
            job_url = ""

        if title or company:
            jobs.append({
                "Job Title": title,
                "Company": company,
                "Location": location,
                "Posted": posted,
                "Job URL": job_url,
                "Seniority": "",
                "Employment Type": "",
                "Description": "",
            })

    return jobs


def fetch_job_details(page, job: dict) -> dict:
    """Visit individual job page to get seniority, type, and description."""
    if not job["Job URL"]:
        return job

    try:
        page.goto(job["Job URL"], wait_until="domcontentloaded", timeout=15000)
        human_delay(1.5, 3)
        dismiss_signin_modal(page)

        try:
            desc = page.locator(".description__text, .show-more-less-html__markup").first.inner_text(timeout=5000).strip()
            job["Description"] = desc[:3000]  # cap at 3k chars
        except Exception:
            pass

        try:
            criteria = page.locator(".description__job-criteria-item").all()
            for item in criteria:
                label = item.locator("h3").first.inner_text(timeout=1000).strip().lower()
                value = item.locator("span").first.inner_text(timeout=1000).strip()
                if "seniority" in label:
                    job["Seniority"] = value
                elif "employment" in label:
                    job["Employment Type"] = value
        except Exception:
            pass

    except PlaywrightTimeoutError:
        print(f"    Timeout fetching: {job['Job URL']}")

    return job


# ── Main ──────────────────────────────────────────────────────────────────────

def scrape(keyword: str, location: str, max_pages: int, headless: bool, fetch_details: bool,
           exp_levels: str = "", industries: str = "", min_salary: str = ""):
    all_jobs: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
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

        # Mask webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Login if credentials available
        logged_in = login(page)
        if logged_in:
            human_delay(2, 3)

        for page_num in range(max_pages):
            start = page_num * 25
            url = build_search_url(keyword, location, start, exp_levels, industries, min_salary)
            print(f"\nPage {page_num + 1}/{max_pages} — start={start}")
            print(f"  URL: {url}")

            retries = 3
            for attempt in range(retries):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 4)
                    break
                except PlaywrightTimeoutError:
                    print(f"  Timeout on attempt {attempt + 1}/{retries}")
                    if attempt == retries - 1:
                        print("  Skipping page.")
                        continue

            # Check for CAPTCHA
            if "captcha" in page.url.lower() or page.locator("text=Let us know you're not a robot").count() > 0:
                print("  CAPTCHA detected — waiting 30s...")
                time.sleep(30)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                human_delay(3, 5)

            jobs = extract_jobs_from_page(page)
            if not jobs:
                print("  No jobs found — stopping pagination.")
                break

            if fetch_details:
                print(f"  Fetching details for {len(jobs)} jobs...")
                for i, job in enumerate(jobs):
                    print(f"    [{i+1}/{len(jobs)}] {job['Job Title']} @ {job['Company']}")
                    jobs[i] = fetch_job_details(page, job)
                    human_delay(1.5, 3)

            all_jobs.extend(jobs)
            print(f"  Total collected: {len(all_jobs)}")

            # Stop if fewer than 25 results (last page)
            if len(jobs) < 25:
                print("  Reached last page.")
                break

            human_delay(2, 5)

        browser.close()

    return all_jobs


def save_to_excel(jobs: list[dict], keyword: str, location: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = re.sub(r"[^\w]", "_", keyword)
    safe_location = re.sub(r"[^\w]", "_", location)
    filename = OUTPUT_DIR / f"linkedin_{safe_keyword}_{safe_location}_{timestamp}.xlsx"

    df = pd.DataFrame(jobs, columns=[
        "Job Title", "Company", "Location", "Posted",
        "Job URL", "Seniority", "Employment Type", "Description"
    ])

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jobs")
        ws = writer.sheets["Jobs"]

        # Column widths
        col_widths = {
            "A": 40,  # Job Title
            "B": 30,  # Company
            "C": 20,  # Location
            "D": 15,  # Posted
            "E": 50,  # Job URL
            "F": 20,  # Seniority
            "G": 20,  # Employment Type
            "H": 80,  # Description
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width

        # Freeze header row
        ws.freeze_panes = "A2"

    return filename


def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job listings.")
    parser.add_argument("--keyword", default="Sales", help="Job search keyword")
    parser.add_argument("--location", default="Singapore", help="Job location")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to scrape (25 jobs each)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--fetch-details", action="store_true", help="Visit each job page for full description")
    parser.add_argument("--exp-levels", default="", help="Experience level codes e.g. '2,3,4'")
    parser.add_argument("--industries", default="", help="Industry codes e.g. '4,6,96'")
    parser.add_argument("--min-salary", default="", help="Minimum salary code (1–9)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"LinkedIn Job Scraper")
    print(f"  Keyword : {args.keyword}")
    print(f"  Location: {args.location}")
    print(f"  Max pages: {args.max_pages} (~{args.max_pages * 25} jobs)")
    print(f"  Headless: {args.headless}")
    print(f"  Fetch details: {args.fetch_details}")
    if args.exp_levels:  print(f"  Exp levels: {args.exp_levels}")
    if args.industries:  print(f"  Industries: {args.industries}")
    if args.min_salary:  print(f"  Min salary: {args.min_salary}")
    print("=" * 60)

    jobs = scrape(
        keyword=args.keyword,
        location=args.location,
        max_pages=args.max_pages,
        headless=args.headless,
        fetch_details=args.fetch_details,
        exp_levels=args.exp_levels,
        industries=args.industries,
        min_salary=args.min_salary,
    )

    if not jobs:
        print("\nNo jobs collected. Check your connection or LinkedIn may have blocked the request.")
        sys.exit(1)

    # Deduplicate by Job URL
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = job["Job URL"] or job["Job Title"] + job["Company"]
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    print(f"\nCollected {len(unique_jobs)} unique jobs (from {len(jobs)} total).")

    output_path = save_to_excel(unique_jobs, args.keyword, args.location)
    print(f"\nSaved to: {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
