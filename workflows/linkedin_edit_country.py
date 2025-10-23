"""Stagehand workflow for editing employee location on an existing LinkedIn job."""

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
load_dotenv()

WORKFLOW_NAME = "linkedin_edit_country"

REQUIRED_FIELDS = [
    "job_detail_url",
    "employee_location",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "workflow_runs"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_FILE = CACHE_DIR / f"{WORKFLOW_NAME}.json"


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


async def observe_and_fill(page, instruction: str, value: str) -> None:
    """Observe an input field, cache its selector, and fill it."""
    last_error: Exception | None = None
    for attempt in range(3):
        action = await get_cached_action(
            page,
            instruction,
            use_cache=True if attempt == 0 else False,
        )
        selector = None
        if isinstance(action, dict):
            selector = action.get("selector")
        elif hasattr(action, "selector"):
            selector = action.selector
        if not selector:
            raise RuntimeError(f"No selector available for instruction: {instruction}")
        try:
            await page._page.fill(selector, "" if value is None else str(value))
            return
        except Exception as error:
            print("Action failed:", error)
            last_error = error
    raise last_error or RuntimeError(
        f"Fill for '{instruction}' failed after 3 attempts"
    )


async def _execute_workflow(
    stagehand: Stagehand, input_data: dict[str, str]
) -> dict[str, str]:
    page = stagehand.page

    await page.goto(input_data["job_detail_url"])

    job_state_text = ""
    try:
        state_extraction = await page.extract(
            "Extract the job state label shown on this page (for example Active or In review)."
        )
        print("Extracted job state:", state_extraction)
        if hasattr(state_extraction, "extraction"):
            job_state_text = (getattr(state_extraction, "extraction") or "").strip()
    except Exception as state_error:
        print("Unable to extract job state:", state_error)
    normalized_state = job_state_text.lower()
    current_url = page._page.url
    job_id = parse_digits_from_url(current_url or input_data["job_detail_url"])

    if "active" not in normalized_state:
        return {
            "jobDetailUrl": current_url,
            "jobId": job_id,
            "jobState": job_state_text or "unknown",
            "status": "job_not_active",
        }

    await run_cached_action(
        page, 'Click the "Edit job details" button. Set method=\'click\''
    )

    await run_cached_action(
        page,
        'Click the "Edit employee location" pencil icon. Set method=\'click\'',
    )

    await observe_and_fill(
        page,
        'Locate the "Employee location" input field',
        input_data["employee_location"],
    )
    await page.wait_for_timeout(2000)
    await page._page.keyboard.press("ArrowDown")
    await page._page.keyboard.press("Enter")

    await run_cached_action(
        page,
        'Click the "Continue" button on job details. Set method=\'click\'',
    )

    return {
        "jobDetailUrl": page._page.url,
        "jobId": job_id,
        "jobState": job_state_text or "Active",
        "status": "updated",
    }


async def run(stagehand: Any, input_data: dict[str, str]) -> dict[str, str]:
    validate_input(input_data)
    return await _execute_workflow(stagehand, input_data)


async def run_with_stagehand(input_data: dict[str, str]) -> dict[str, str]:
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


def save_run_record(input_data: dict[str, str], output_data: dict[str, str]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = OUTPUT_DIR / f"{WORKFLOW_NAME}_{timestamp_str}.json"
    record = {
        "workflow_name": WORKFLOW_NAME,
        "run_time": datetime.now(timezone.utc).isoformat(),
        "input": input_data,
        "output": output_data,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    return output_path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python workflows/linkedin_edit_country.py <input_json_path>"
        )

    input_path = Path(sys.argv[1])
    with input_path.open("r", encoding="utf-8") as handle:
        input_data = json.load(handle)

    output_data = asyncio.run(run_with_stagehand(input_data))
    output_path = save_run_record(input_data, output_data)
    print(f"Saved workflow run to {output_path}")


if __name__ == "__main__":
    main()
