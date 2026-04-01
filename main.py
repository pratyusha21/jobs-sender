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
    {"term": "software engineer university nonprofit",         "count": 15},
    {"term": "data scientist university research foundation",  "count": 15},
    {"term": "machine learning engineer nonprofit research",   "count": 10},
    {"term": "data analyst nonprofit university",              "count": 10},
    {"term": "data engineer nonprofit research institute",     "count": 10},
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
  <p style="color:#94a3b8;font-size:12px;margin-top:24px;">Sent by jobs-sender &bull; Remote roles only &bull; US-based listings &bull; Universities, nonprofits &amp; 501(c)(3) orgs</p>
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
