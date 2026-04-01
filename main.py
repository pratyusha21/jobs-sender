import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

import pandas as pd
from jobspy import scrape_jobs

RECIPIENT_EMAIL = "pratyusharavuri21@gmail.com"
SENDER_EMAIL = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

SITES = ["linkedin", "indeed", "glassdoor", "zip_recruiter"]

SEARCH_CONFIGS = [
    {"term": "software engineer",           "count": 8},
    {"term": "data scientist",              "count": 5},
    {"term": "machine learning engineer",   "count": 5},
    {"term": "data analyst",               "count": 4},
    {"term": "data engineer",              "count": 4},
]


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
    combined = combined.head(25)
    return combined


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
    {len(jobs)} remote roles across Software Engineering, Data Science, ML/AI, Data Analytics, and Data Engineering.
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
  <p style="color:#94a3b8;font-size:12px;margin-top:24px;">Sent by jobs-sender &bull; Remote roles only &bull; US-based listings</p>
</body>
</html>"""


def send_email(html: str, job_count: int) -> None:
    subject = f"Daily Jobs ({job_count} listings) — {date.today().strftime('%b %d, %Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())


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
