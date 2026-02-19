# Workflow: Scrape LinkedIn Sales Jobs in Singapore

## Objective
Extract Sales job listings from LinkedIn for Singapore and export to Excel.

## Inputs
| Parameter | Value | Notes |
|-----------|-------|-------|
| keyword | Sales | Job search keyword |
| location | Singapore | Target location |
| max_pages | 10 | Pages to scrape (25 jobs/page = ~250 jobs) |
| output_dir | .tmp/ | Where Excel file is saved |

## Tool
`tools/scrape_linkedin_jobs.py`

## Steps
1. Launch Playwright (headful Chromium to avoid bot detection)
2. Navigate to LinkedIn public jobs search — no login required
3. For each page, extract job cards:
   - Job Title
   - Company Name
   - Location
   - Posted Date
   - Job URL
   - Seniority Level (if visible)
   - Employment Type (if visible)
4. Optionally visit each job URL to extract full description (slower, more detail)
5. Save all records to `.tmp/linkedin_sales_singapore_YYYYMMDD_HHMMSS.xlsx`

## Output Columns
| Column | Description |
|--------|-------------|
| Job Title | Role title |
| Company | Hiring company |
| Location | Job location |
| Posted | Relative post date ("2 days ago") |
| Job URL | Direct link to LinkedIn posting |
| Seniority | Entry/Mid/Senior (if available) |
| Employment Type | Full-time/Part-time/Contract |
| Description | Full job description (if fetched) |

## Known Constraints
- LinkedIn rate-limits aggressive scrapers — random delays (2–5s) are built in
- **Without login**: Public search returns the same top ~58 jobs regardless of `start` offset. Deduplication handles this automatically. Add credentials to `.env` for full pagination.
- **With login**: Proper pagination works, yielding up to ~1000 unique results.
- LinkedIn may show a CAPTCHA if too many requests are made quickly
- Headful (visible browser) mode is used to reduce bot detection risk
- If blocked, add LINKEDIN_EMAIL/LINKEDIN_PASSWORD to `.env` and re-run with login

## Edge Cases
- "No jobs found" → script exits with empty file + warning message
- CAPTCHA detected → script pauses 30s and retries once, then exits
- Network timeout → retries up to 3 times per page
