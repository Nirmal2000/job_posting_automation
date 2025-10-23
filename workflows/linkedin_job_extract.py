"""Stagehand workflow for extracting job posting data from LinkedIn."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os
from dotenv import load_dotenv

from stagehand import Stagehand, StagehandConfig
from stagehand.page import StagehandPage
from pydantic import BaseModel, Field

load_dotenv()

WORKFLOW_NAME = "linkedin_job_extract"

REQUIRED_FIELDS = [
    "jobId",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "linked_job_posts"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_FILE = CACHE_DIR / f"{WORKFLOW_NAME}.json"


class JobExtractSchema(BaseModel):
    """Schema for extracted job data."""
    job_name: str = Field(..., description="The job title/name")
    location: str = Field(..., description="The job location")
    job_status: str = Field(..., description="Job status - either 'Active' or 'In Review'")
    posted_when: str = Field(..., description="When the job was posted (e.g., '2 days ago', '5 hrs ago')")
    amount_spent: float = Field(..., description="Amount spent on job promotion (numeric value)")
    views: int = Field(..., description="Number of job views (numeric value)")
    apply_clicks: int = Field(..., description="Number of apply clicks (numeric value)")


def parse_digits_from_url(url: str) -> str:
    """Extract consecutive digits from the provided URL."""
    return "".join(re.findall(r"\d+", url))


def validate_input(input_data: dict[str, str]) -> None:
    """Ensure all required workflow inputs are present."""
    for field in REQUIRED_FIELDS:
        if not input_data.get(field):
            raise ValueError(f"Missing required input field: {field}")


def _load_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")


def cache_get(prompt: str) -> Any:
    return _load_cache().get(prompt)


def cache_set(prompt: str, value: Any) -> None:
    cache = _load_cache()
    cache[prompt] = value
    _save_cache(cache)


async def observe_with_iframes(page, instruction: str):
    """Run observe with iframe support enabled."""
    last_error: Exception | None = None
    for _ in range(3):
        try:
            return await page.observe(instruction=instruction, iframes=True)
        except Exception as error:
            print("Action failed:", error)
            last_error = error
    raise last_error or RuntimeError("Observe failed after 3 attempts")


async def get_cached_action(page, instruction: str, use_cache: bool = True) -> dict[str, Any]:
    if use_cache:
        cached = cache_get(instruction)
        if cached:
            print(f"{instruction} (cache hit)", cached)
            await asyncio.sleep(2)
            return cached

    results = await observe_with_iframes(page, instruction)
    print(instruction, results)
    if not results:
        raise RuntimeError(f"No elements found for instruction: {instruction}")

    first = results[0]
    action_dict = (
        first.model_dump()
        if hasattr(first, "model_dump")
        else getattr(first, "__dict__", {"selector": getattr(first, "selector", None)})
    )
    if use_cache:
        cache_set(instruction, action_dict)
    return action_dict


def _action_to_payload(action: Any) -> dict[str, Any]:
    if hasattr(action, "model_dump"):
        payload = action.model_dump()
    elif isinstance(action, dict):
        payload = dict(action)
    elif hasattr(action, "__dict__"):
        payload = {
            k: v for k, v in vars(action).items() if not k.startswith("_")
        }
    else:
        raise TypeError("Unsupported action type")
    payload["iframes"] = True
    return payload


async def run_cached_action(page: StagehandPage, instruction: str, use_cache: bool = True) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        action = await get_cached_action(
            page,
            instruction,
            use_cache=use_cache if attempt == 0 else False,
        )
        payload = _action_to_payload(action)
        try:
            await page.act(payload)
            return
        except Exception as error:
            print("Action failed:", error)
            last_error = error
    raise last_error or RuntimeError(
        f"Action '{instruction}' failed after 3 attempts"
    )


async def _execute_workflow(
    stagehand: Stagehand, input_data: dict[str, str]
) -> dict[str, Any]:
    """Core workflow logic that assumes a prepared Stagehand client."""
    page = stagehand.page

    job_id = input_data["jobId"]
    job_url = f"https://www.linkedin.com/hiring/jobs/{job_id}/detail/"

    print(f"Navigating to job URL: {job_url}")
    await page.goto(job_url)

    # Wait for the page to load completely
    await page.wait_for_timeout(5000)

    # Extract job data using stagehand extract
    print("Extracting job data...")
    try:
        extracted_data = await page.extract(
            instruction="Extract the job name, location, status, posting time, amount spent (as a number), views (as a number), and apply clicks (as a number) from this LinkedIn job posting page. Return only the numeric values for amount spent, views, and apply clicks without any text or currency symbols.",
            schema=JobExtractSchema,
            iframes=True
        )

        print("Extracted data:", extracted_data)

        return {
            "jobDetailUrl": job_url,
            "jobId": job_id,
            "job_name": extracted_data.job_name,
            "location": extracted_data.location,
            "job_status": extracted_data.job_status,
            "posted_when": extracted_data.posted_when,
            "amount_spent": float(extracted_data.amount_spent),
            "views": int(extracted_data.views),
            "apply_clicks": int(extracted_data.apply_clicks),
            "status": "extracted"
        }

    except Exception as extract_error:
        print(f"Extraction failed: {extract_error}")
        return {
            "jobDetailUrl": job_url,
            "jobId": job_id,
            "status": "extraction_failed",
            "error": str(extract_error)
        }


async def run(stagehand: Any, input_data: dict[str, str]) -> dict[str, Any]:
    validate_input(input_data)
    return await _execute_workflow(stagehand, input_data)


async def run_with_stagehand(input_data: dict[str, str]) -> dict[str, Any]:
    validate_input(input_data)
    stagehand_client = Stagehand(
        StagehandConfig(
            env="LOCAL",
            local_browser_launch_options={
                "cdp_url": os.environ.get("STAGEHAND_LOCAL_CDP_URL", "http://localhost:9222")
            },
            model_api_key=os.environ.get("OPENAI_API_KEY", ""),
            model_name=os.environ.get(
                "STAGEHAND_MODEL_NAME",
                "openrouter/google/gemini-2.5-flash-preview-09-2025",
            ),
            model_client_options={
                "api_base": os.environ.get(
                    "OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"
                ),
            },
        )
    )
    await stagehand_client.init()
    try:
        return await _execute_workflow(stagehand_client, input_data)
    finally:
        await stagehand_client.close()


def save_run_record(input_data: dict[str, str], output_data: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save the main output file as {jobId}.json (just the job data)
    job_id = input_data["jobId"]
    output_path = OUTPUT_DIR / f"{job_id}.json"

    # Create a simplified record with just the extracted data
    record = {
        "job_name": output_data.get("job_name", ""),
        "location": output_data.get("location", ""),
        "job_status": output_data.get("job_status", ""),
        "posted_when": output_data.get("posted_when", ""),
        "amount_spent": output_data.get("amount_spent", 0.0),
        "views": output_data.get("views", 0),
        "apply_clicks": output_data.get("apply_clicks", 0),
        "job_url": output_data.get("jobDetailUrl", ""),
        "job_id": job_id
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)

    print(f"Saved job extraction to {output_path}")
    return output_path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python workflows/linkedin_job_extract.py <input_json_path>"
        )

    input_path = Path(sys.argv[1])
    with input_path.open("r", encoding="utf-8") as handle:
        input_data = json.load(handle)

    output_data = asyncio.run(run_with_stagehand(input_data))
    output_path = save_run_record(input_data, output_data)
    print(f"Workflow completed. Output saved to {output_path}")


if __name__ == "__main__":
    main()