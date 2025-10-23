"""Stagehand workflow for promoting a LinkedIn job posting."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

from stagehand import Stagehand, StagehandConfig
from stagehand.page import StagehandPage
from utils.otp_fetcher import get_latest_otp_from_hdfcbnk

load_dotenv()

WORKFLOW_NAME = "linkedin_job_promotion"

REQUIRED_FIELDS = [
    "job_title",
    "employee_location",
    "job_description",
    "apply_url",
    "card_number",
    "card_expiration",
    "card_security_code",
    "card_postal_code",
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
        payload = {k: v for k, v in vars(action).items() if not k.startswith("_")}
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
            await page.act(payload, timeout_ms=15000)
            return
        except Exception as error:
            print("Action failed:", error)
            last_error = error
    raise last_error or RuntimeError(
        f"Action '{instruction}' failed after 3 attempts"
    )


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


async def observe_and_fill(page, instruction: str, value: str) -> None:
    """Locate an element via observe and fill it with the provided value."""
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
            raise RuntimeError(
                f"No selector available for instruction: {instruction}"
            )
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
    """Core workflow logic that assumes a prepared Stagehand client."""
    page = stagehand.page

    await page.goto("https://www.linkedin.com/my-items/posted-jobs/")

    await run_cached_action(
        page, 'Click the "Post a free job" button. Set method=\'click\''
    )

    await observe_and_fill(
        page,
        'Locate the "Job title" input field',
        input_data["job_title"],
    )
    await page._page.keyboard.press("Tab")
    await page.wait_for_timeout(5000)

    try:
        await run_cached_action(
            page, 'Click the "Post job" button. Set method=\'click\''
        )
    except Exception:
        print("Ignoring exception when clicking Post job button initially")

    review_url = page._page.url
    job_id = parse_qs(urlparse(review_url).query).get("jobId", [""])[0]

    if not job_id:
        raise RuntimeError("Unable to extract jobId from review URL")

    await run_cached_action(
        page, 'Click the "Edit job details" button. Set method=\'click\''
    )

    await observe_and_fill(
        page,
        'Locate the "Employee location" field',
        input_data["employee_location"],
    )
    await page.wait_for_timeout(2000)
    await page._page.keyboard.press("ArrowDown")
    await page._page.keyboard.press("Enter")

    await observe_and_fill(
        page,
        "Locate the job description editor area",
        input_data["job_description"],
    )

    await run_cached_action(
        page, 'Click the "Continue" button on job details. Set method=\'click\''
    )

    await run_cached_action(
        page, 'Click the "Edit applicant collection" button. Set method=\'click\''
    )

    await run_cached_action(
        page, 'Click the "On Linkedin" dropdown. Set method=\'click\''
    )
    await page.wait_for_timeout(500)
    await page._page.keyboard.press("ArrowDown")
    await page._page.keyboard.press("ArrowDown")
    await page._page.keyboard.press("Enter")

    await observe_and_fill(
        page,
        'Locate the "Website address" input field',
        input_data["apply_url"],
    )

    await run_cached_action(
        page, 'Click the "Edit hiring frame" button. Set method=\'click\''
    )

    await run_cached_action(
        page, 'Click the "No, don\'t add the photo frame" option. Set method=\'click\''
    )

    await run_cached_action(
        page, 'Click the "Continue" button on job settings. Set method=\'click\''
    )
    await page.wait_for_timeout(10000)

    qualification_editors = await observe_with_iframes(
        page,
        "Locate each qualification text editor on the page"
    )
    print("Locate each qualification text editor on the page", qualification_editors)
    if not qualification_editors:
        raise RuntimeError("No qualification text editors found")
    for editor in qualification_editors:
        selector = getattr(editor, "selector", None)
        if not selector:
            continue
        await page._page.click(selector)
        await page.wait_for_timeout(300)
        await page._page.keyboard.press("Meta+A")
        await page.wait_for_timeout(100)
        await page._page.keyboard.press("Backspace")

    await run_cached_action(
        page, 'Click the "Continue" button on qualifications. Set method=\'click\''
    )

    await run_cached_action(
        page,
        'Click the radio input for the promoted plan (dont click the "Promoted Plus"). Set method=\'click\'',
        use_cache=False,
    )

    await run_cached_action(
        page, 'Click the "Edit" button for the promoted budget. Set method=\'click\''
    )

    await observe_and_fill(
        page,
        "Locate the job posting budget setter input tag",
        "130",
    )

    await run_cached_action(
        page, 'Click the "Set budget" button. Set method=\'click\''
    )

    while True:
        try:
            card_iframe = page._page.frame_locator(
                'iframe[title="Credit card input fields"]'
            )
            await card_iframe.locator('div[autocomplete="cc-number"] input').first.fill(
                input_data["card_number"]
            )
            await card_iframe.locator('div[autocomplete="cc-exp"] input').first.fill(
                input_data["card_expiration"]
            )
            await card_iframe.locator('div[autocomplete="cc-csc"] input').first.fill(
                input_data["card_security_code"]
            )
            for _ in range(3):
                await page._page.keyboard.press("Tab")
                await page.wait_for_timeout(150)
            await page._page.keyboard.type(input_data["card_postal_code"])
            break
        except Exception as card_error:
            print(
                "Card entry failed, inspect browser then press Enter to retry:",
                card_error,
            )
            input()

    await run_cached_action(
        page, 'Click the "Add card" button. Set method=\'click\''
    )

    await run_cached_action(
        page, 'Click the "Promote job" button. Set method=\'click\''
    )

    await page.wait_for_timeout(20000)
    otp_result = get_latest_otp_from_hdfcbnk()
    if not otp_result:
        raise RuntimeError("No OTP found in recent messages")
    _, otp_code = otp_result
    await observe_and_fill(
        page,
        "Locate the one-time password input field",
        otp_code,
    )

    await run_cached_action(
        page, 'Click the "Submit" button to confirm the one-time password. Set method=\'click\''
    )

    

    return {
        "jobDetailUrl": f"https://www.linkedin.com/hiring/jobs/{job_id}/detail/",
        "jobId": job_id,
        "jobState": "In review",
        "status": "submitted",
    }


async def run(stagehand: Any, input_data: dict[str, str]) -> dict[str, str]:
    """Execute when Stagehand provides an initialized client."""
    validate_input(input_data)
    return await _execute_workflow(stagehand, input_data)


async def run_with_stagehand(input_data: dict[str, str]) -> dict[str, str]:
    """Initialize Stagehand internally and execute the workflow."""
    validate_input(input_data)
    stagehand_client = Stagehand(
        StagehandConfig(
            env="LOCAL",
            local_browser_launch_options={
                "cdp_url":"http://localhost:9222"
            },            
            model_api_key=os.environ.get("OPENAI_API_KEY", ""),
            model_name="openrouter/google/gemini-2.5-flash-preview-09-2025",
            model_client_options={
                "api_base": os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
            }
            
        )
    )
    await stagehand_client.init()
    try:
        return await _execute_workflow(stagehand_client, input_data)
    finally:
        await stagehand_client.close()


def save_run_record(input_data: dict[str, str], output_data: dict[str, str]) -> Path:
    """Persist the workflow run details to disk."""
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
    """Run the workflow from the terminal using a JSON input file."""
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python workflows/linkedin_job_promotion.py <input_json_path>"
        )

    input_path = Path(sys.argv[1])
    with input_path.open("r", encoding="utf-8") as handle:
        input_data = json.load(handle)

    output_data = asyncio.run(run_with_stagehand(input_data))
    output_path = save_run_record(input_data, output_data)
    print(f"Saved workflow run to {output_path}")


if __name__ == "__main__":
    main()
