from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflows import linkedin_edit_country, linkedin_job_promotion

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUTS_DIR = REPO_ROOT / "inputs"
WORKFLOW_RUNS_DIR = REPO_ROOT / "workflow_runs"
CACHE_DIR = REPO_ROOT / "cache"
DOWNLOADS_DIR = REPO_ROOT / "downloads"
SUMMARY_CSV = DOWNLOADS_DIR / "job_titles_summary.csv"


def load_summary() -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    with SUMMARY_CSV.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            job_title = row["job_title"].strip()
            countries = [c.strip() for c in row["countries"].split(",")]
            summary[job_title] = {
                "original_title": row["original_title"],
                "countries": [c for c in countries if c],
            }
    return summary


def load_input_files() -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}
    for path in INPUTS_DIR.glob("*.json"):
        if path.name == "linkedin_edit_country_sample.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        job_title = data.get("job_title")
        if job_title:
            inputs[job_title] = {"path": path, "payload": data}
    return inputs


async def run_promotion_for_job(
    job_title: str,
    template: dict[str, Any],
    run_count: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index in range(run_count):
        input_data = dict(template["payload"])
        print(f"Posting job '{job_title}' run {index + 1}/{run_count}")
        try:
            output = await linkedin_job_promotion.run_with_stagehand(input_data)
        except Exception as error:
            print(f"Promotion failed for '{job_title}' run {index + 1}: {error}")
            continue

        record_path = WORKFLOW_RUNS_DIR / f"{job_title.replace(' ', '_')}_promotion_run{index + 1}.json"
        record = {
            "workflow": "linkedin_job_promotion",
            "input": input_data,
            "output": output,
        }
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        results.append(record)
    return results


async def edit_job_location(job_detail_url: str, country: str) -> dict[str, Any] | None:
    payload = {
        "job_detail_url": job_detail_url,
        "employee_location": country,
    }
    print(f"Updating job at {job_detail_url} to location '{country}'")
    try:
        return await linkedin_edit_country.run_with_stagehand(payload)
    except Exception as error:
        print(f"Failed to update location for {job_detail_url} to {country}: {error}")
        return None


async def main() -> None:
    summary = load_summary()
    input_files = load_input_files()

    # Step 1: promote each job as many times as there are countries listed
    promotion_results: dict[str, list[dict[str, Any]]] = {}
    for job_title, template in input_files.items():
        country_list = summary.get(job_title, {}).get("countries", [""])
        run_count = len(country_list) or 1
        records = await run_promotion_for_job(job_title, template, run_count)
        promotion_results[job_title] = records

    # Step 2: for each successful promotion, update location per country list
    for job_title, records in promotion_results.items():
        countries = summary.get(job_title, {}).get("countries", [])
        for country, record in zip(countries, records):
            output = record.get("output", {})
            job_id = output.get("jobId")
            if not job_id:
                continue
            job_url = f"https://www.linkedin.com/hiring/jobs/{job_id}/detail/"
            result = await edit_job_location(job_url, country)
            if not result:
                continue
            path = WORKFLOW_RUNS_DIR / f"{job_title.replace(' ', '_')}_location_{country.replace(' ', '_')}.json"
            path.write_text(json.dumps({"input": job_url, "country": country, "output": result}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
