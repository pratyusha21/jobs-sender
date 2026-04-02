import os
from datetime import date

import pandas as pd
from jobspy import scrape_jobs

RECIPIENT_EMAIL = "pratyusharavuri21@gmail.com"
SENDER_EMAIL = "pratyusharavuri21@gmail.com"
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]

SITES = ["linkedin", "indeed", "glassdoor", "zip_recruiter"]

# Each base role is paired with nonprofit/university employer contexts.
# We fetch more candidates than needed so the filter can trim to 25.
SEARCH_CONFIGS = [
    {"term": "junior software engineer university nonprofit",          "count": 20},
    {"term": "associate data scientist university research",           "count": 20},
    {"term": "entry level machine learning engineer nonprofit",        "count": 15},
    {"term": "data analyst entry level nonprofit university",          "count": 15},
    {"term": "data engineer associate nonprofit research institute",   "count": 15},
]

# Company name substrings that indicate a 501(c)(3) / mission-driven employer.
NONPROFIT_KEYWORDS = [
    "university", "college", "institute", "institution",
    "foundation", "research", "health system", "hospital",
    "medical center", "clinic", "nonprofit", "non-profit",
    "association", "society", "council", "alliance",
    "museum", "library", "academy", "school",
    "ngo", "charity", "trust", "fund",
]


# Job title prefixes/keywords that indicate senior, PhD-level, or postdoc roles to exclude.
EXCLUDE_TITLE_KEYWORDS = [
    # Seniority
    "postdoc", "post-doc", "post doc", "post doctoral", "postdoctoral",
    "senior", "sr.", "lead", "principal", "staff", "director", "manager",
    "head of", "vp ", "vice president", "chief", "fellow",
    "phd", "ph.d",
    # Academic / faculty roles
    "professor", "faculty", "lecturer", "instructor", "adjunct",
    "visiting scholar", "research chair", "tenure", "provost", "dean",
    "assistant professor", "associate professor",
]

# CS-related keywords — at least one must appear in the title
CS_TITLE_KEYWORDS = [
    "software engineer", "software developer", "software architect",
    "data engineer", "data scientist", "data analyst", "data analyst",
    "machine learning", "ml engineer", "ai engineer", "artificial intelligence",
    "backend", "frontend", "front-end", "back-end", "full stack", "fullstack",
    "devops", "cloud engineer", "platform engineer", "infrastructure engineer",
    "site reliability", "sre", "computer scientist",
    "nlp engineer", "deep learning", "business intelligence", "bi developer",
    "database engineer", "etl developer", "analytics engineer",
    "python developer", "java developer", "web developer",
]

# Description phrases that signal PhD required or 5+ years experience.
EXCLUDE_DESCRIPTION_PHRASES = [
    # PhD requirements
    "ph.d. required", "phd required", "doctorate required",
    "phd preferred", "ph.d preferred",
    "postdoctoral", "post-doctoral",
    # 3+ years experience
    "3+ years", "4+ years", "5+ years", "6+ years", "7+ years", "8+ years", "10+ years",
    "3 or more years", "4 or more years", "5 or more years",
    "minimum 3 years", "minimum 4 years", "minimum 5 years",
    "at least 3 years", "at least 4 years", "at least 5 years",
    "3 years of experience", "4 years of experience", "5 years of experience",
    "three years of experience", "four years of experience", "five years of experience",
]


def is_entry_level(title: str, description: str = "") -> bool:
    """Return True if the job is suitable for someone with a Masters in CS and ~2 years experience."""
    t = title.lower()
    d = description.lower()
    if any(kw in t for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    if any(phrase in d for phrase in EXCLUDE_DESCRIPTION_PHRASES):
        return False
    if not any(kw in t for kw in CS_TITLE_KEYWORDS):
        return False
    return True


DESCRIPTION_INDICATORS = [
    "501(c)(3)", "501c3", "501 c 3",
    "nonprofit", "non-profit", "not-for-profit",
    "tax-exempt", "tax exempt",
    "mission-driven", "mission driven",
    "public benefit", "charitable organization",
    "ngo", "non-governmental",
]


def is_nonprofit(company: str, description: str = "") -> bool:
    """Return True if the company name OR job description signals a 501(c)(3) / mission-driven org."""
    name = company.lower()
    if any(kw in name for kw in NONPROFIT_KEYWORDS):
        return True
    desc = description.lower()
    return any(ind in desc for ind in DESCRIPTION_INDICATORS)


def fetch_jobs() -> pd.DataFrame:
    all_jobs: list[pd.DataFrame] = []

    for cfg in SEARCH_CONFIGS:
        try:
            jobs = scrape_jobs(
                site_name=SITES,
                search_term=cfg["term"],
                location="United States",
                results_wanted=cfg["count"],
                is_remote=True,
                hours_old=48,
                country_indeed="USA",
            )
            if not jobs.empty:
                all_jobs.append(jobs)
                print(f"  [{cfg['term']}] fetched {len(jobs)} results")
        except Exception as exc:
            print(f"  [{cfg['term']}] error: {exc}")

    if not all_jobs:
        return pd.DataFrame()

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"])

    # Keep only nonprofit / university / research employers.
    # Check both company name and job description so orgs with Inc./LLC suffixes
    # (e.g. "RAND Corporation", "SRI International Inc.") are still caught.
    mask = combined.apply(
        lambda row: is_nonprofit(
            str(row.get("company") or ""),
            str(row.get("description") or ""),
        ),
        axis=1,
    )
    filtered = combined[mask].reset_index(drop=True)
    print(f"  After nonprofit filter: {len(filtered)} of {len(combined)} jobs kept")

    # Drop senior / PhD / postdoc roles — keep entry-to-mid level (0-2 yrs, Masters OK)
    level_mask = filtered.apply(
        lambda row: is_entry_level(
            str(row.get("title") or ""),
            str(row.get("description") or ""),
        ),
        axis=1,
    )
    filtered = filtered[level_mask].reset_index(drop=True)
    print(f"  After experience filter: {len(filtered)} jobs kept")

    return filtered.head(25)


def build_html(jobs: pd.DataFrame) -> str:
    today = date.today().strftime("%B %d, %Y")
    rows = ""

    for _, job in jobs.iterrows():
        title      = job.get("title", "N/A") or "N/A"
        company    = job.get("company", "N/A") or "N/A"
        location   = job.get("location", "N/A") or "N/A"
        job_url    = job.get("job_url", "#") or "#"
        site       = str(job.get("site", "N/A") or "N/A").capitalize()
        posted     = str(job.get("date_posted", "N/A") or "N/A")

        rows += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">
            <a href="{job_url}" style="color:#2563eb;font-weight:600;text-decoration:none;">{title}</a>
          </td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{company}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{location}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{site}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{posted}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:950px;margin:0 auto;padding:24px;color:#1e293b;">
  <h2 style="margin-bottom:4px;">Daily Job Listings &mdash; {today}</h2>
  <p style="color:#64748b;margin-top:4px;">
    {len(jobs)} remote roles from universities, nonprofits, research foundations, and 501(c)(3) organizations across Software Engineering, Data Science, ML/AI, Data Analytics, and Data Engineering.
  </p>
  <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:14px;">
    <thead>
      <tr style="background:#f1f5f9;text-align:left;">
        <th style="padding:10px 12px;">Title</th>
        <th style="padding:10px 12px;">Company</th>
        <th style="padding:10px 12px;">Location</th>
        <th style="padding:10px 12px;">Source</th>
        <th style="padding:10px 12px;">Posted</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <p style="color:#94a3b8;font-size:12px;margin-top:24px;">Sent by jobs-sender &bull; Remote roles only &bull; US-based &bull; Universities, nonprofits &amp; 501(c)(3) orgs &bull; Entry/mid-level &bull; No PhD or postdoc roles</p>
</body>
</html>"""


def send_email(html: str, job_count: int) -> None:
    import urllib.request
    import json

    subject = f"Daily Jobs ({job_count} listings) — {date.today().strftime('%b %d, %Y')}"

    payload = json.dumps({
        "personalizations": [{"to": [{"email": RECIPIENT_EMAIL}]}],
        "from": {"email": SENDER_EMAIL},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }).encode()

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status not in (200, 202):
            raise RuntimeError(f"SendGrid error: {resp.status}")


def main() -> None:
    print("Fetching jobs...")
    jobs = fetch_jobs()

    if jobs.empty:
        print("No jobs found — skipping email.")
        return

    print(f"Building email for {len(jobs)} jobs...")
    html = build_html(jobs)
    send_email(html, len(jobs))
    print("Email sent successfully!")


if __name__ == "__main__":
    main()
