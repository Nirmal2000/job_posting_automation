#!/usr/bin/env python3
"""Script to extract data from multiple LinkedIn job postings."""

import asyncio
import json
import sys
import argparse
import csv
from pathlib import Path
from typing import List, Dict, Any

# Add the repo root to the Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflows import linkedin_job_extract


def load_job_titles_mapping() -> Dict[str, str]:
    """Load the mapping from job_title to original_title from the CSV file."""
    mapping = {}
    csv_path = REPO_ROOT / "downloads" / "job_titles_summary.csv"

    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            job_title = row["job_title"].strip()
            original_title = row["original_title"].strip()
            mapping[job_title] = original_title

    return mapping


def find_apply_url_for_job_id(job_id: str) -> str:
    """Find the apply URL for a given job ID from promotion workflow runs."""
    workflow_runs_dir = REPO_ROOT / "workflow_runs"

    # Look for promotion files that contain this job_id
    for json_file in workflow_runs_dir.glob("*_promotion_*.json"):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if this file contains our job_id
            output = data.get("output", {})
            if output.get("jobId") == job_id:
                input_data = data.get("input", {})
                apply_url = input_data.get("apply_url", "")
                if apply_url:
                    return apply_url

        except (json.JSONDecodeError, KeyError):
            continue

    return ""


def check_job_exists(job_id: str, output_dir: Path) -> bool:
    """Check if job data already exists in the output directory."""
    output_file = output_dir / f"{job_id}.json"
    return output_file.exists()


async def extract_single_job(job_id: str) -> Dict[str, Any]:
    """Extract data from a single LinkedIn job posting."""
    input_data = {"jobId": job_id}

    print(f"Extracting data for job ID: {job_id}")

    try:
        result = await linkedin_job_extract.run_with_stagehand(input_data)
        print(f"✓ Successfully extracted data for job {job_id}")
        return result
    except Exception as e:
        print(f"✗ Failed to extract data for job {job_id}: {e}")
        return {
            "jobId": job_id,
            "status": "failed",
            "error": str(e)
        }


async def extract_multiple_jobs(job_ids: List[str], output_dir: Path = None, force: bool = False) -> tuple[List[Dict[str, Any]], List[str]]:
    """Extract data from multiple LinkedIn job postings."""
    results = []
    skipped_jobs = []
    processed_jobs = []

    # Load the job titles mapping once
    job_titles_mapping = load_job_titles_mapping()
    print(f"Loaded job titles mapping with {len(job_titles_mapping)} entries")

    # Filter out jobs that already exist (unless force is True)
    jobs_to_process = []
    for job_id in job_ids:
        if force or not check_job_exists(job_id, output_dir):
            jobs_to_process.append(job_id)
        else:
            skipped_jobs.append(job_id)
            print(f"⏭️  Skipping job ID {job_id} (already exists)")

    if skipped_jobs:
        print(f"\nSkipped {len(skipped_jobs)} existing jobs: {', '.join(skipped_jobs)}")

    if not jobs_to_process:
        print("\n✅ All jobs already exist! Use --force to re-extract.")
        return results, skipped_jobs

    print(f"\nStarting extraction for {len(jobs_to_process)} jobs...")
    print("=" * 50)

    for i, job_id in enumerate(jobs_to_process, 1):
        print(f"\n[{i}/{len(jobs_to_process)}] Processing job ID: {job_id}")

        result = await extract_single_job(job_id)

        # Enhance result with additional data
        if result.get("status") != "failed" and result.get("job_name"):
            job_name = result["job_name"]

            # Find original title
            original_title = job_titles_mapping.get(job_name, "")
            if original_title:
                result["original_job_title"] = original_title
                print(f"   Found original title: {original_title}")
            else:
                result["original_job_title"] = ""
                print(f"   No original title found for: {job_name}")

            # Find apply URL
            apply_url = find_apply_url_for_job_id(job_id)
            if apply_url:
                result["apply_url"] = apply_url
                print(f"   Found apply URL: {apply_url}")
            else:
                result["apply_url"] = ""
                print(f"   No apply URL found for job ID: {job_id}")

        # Save individual result
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{job_id}.json"

            with output_file.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

            print(f"   Saved to: {output_file}")

        results.append(result)
        processed_jobs.append(job_id)

        # Add a small delay between requests to be respectful
        await asyncio.sleep(2)

    print("\n" + "=" * 50)
    print("Extraction completed!")

    # Save summary
    if output_dir:
        summary_file = output_dir / "extraction_summary.json"
        summary = {
            "total_requested": len(job_ids),
            "processed": len(processed_jobs),
            "skipped_existing": len(skipped_jobs),
            "successful": len([r for r in results if r.get("status") != "failed"]),
            "failed": len([r for r in results if r.get("status") == "failed"]),
            "results": results
        }

        with summary_file.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Summary saved to: {summary_file}")

    return results, skipped_jobs


def load_job_ids_from_file(file_path: str) -> List[str]:
    """Load job IDs from a JSON or text file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() == '.json':
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'job_ids' in data:
                return data['job_ids']
            else:
                raise ValueError("JSON file must contain a list or a dict with 'job_ids' key")
    else:
        # Assume it's a text file with one job ID per line
        with path.open('r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Extract data from multiple LinkedIn job postings")
    parser.add_argument(
        "--job-ids",
        nargs="*",
        help="Space-separated list of job IDs to extract"
    )
    parser.add_argument(
        "--job-ids-file",
        help="File containing job IDs (JSON or text file)"
    )
    parser.add_argument(
        "--output-dir",
        default="linked_job_posts",
        help="Output directory for extracted data (default: linked_job_posts)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force extraction of all jobs, even if data already exists (default: skip existing jobs)"
    )

    args = parser.parse_args()

    # Collect job IDs
    job_ids = []

    if args.job_ids:
        job_ids.extend(args.job_ids)

    if args.job_ids_file:
        file_job_ids = load_job_ids_from_file(args.job_ids_file)
        job_ids.extend(file_job_ids)

    if not job_ids:
        print("Error: No job IDs provided. Use --job-ids or --job-ids-file")
        sys.exit(1)

    # Remove duplicates while preserving order
    seen = set()
    unique_job_ids = []
    for job_id in job_ids:
        if job_id not in seen:
            seen.add(job_id)
            unique_job_ids.append(job_id)

    print(f"Found {len(unique_job_ids)} unique job IDs to process")

    if not args.force:
        print("ℹ️  Checking for existing job data (use --force to skip this check)")

    output_dir = Path(args.output_dir)

    # Run the extraction
    results, skipped_jobs = asyncio.run(extract_multiple_jobs(unique_job_ids, output_dir, args.force))

    # Print final summary
    successful = len([r for r in results if r.get("status") != "failed"])
    failed = len([r for r in results if r.get("status") == "failed"])

    print("\nFinal Summary:")
    print(f"  Total requested: {len(unique_job_ids)}")
    print(f"  Processed: {len(results)}")
    print(f"  Skipped (existing): {len(skipped_jobs)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")

    if skipped_jobs:
        print(f"\nSkipped existing jobs: {', '.join(skipped_jobs)}")

    if failed > 0:
        print("\nFailed jobs:")
        for result in results:
            if result.get("status") == "failed":
                print(f"  - {result.get('jobId')}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()