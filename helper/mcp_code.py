import os
import json
import asyncio
from mcp import Client, StdioServerParameters

from constants.constants import MODEL, BASE_URL
from helper.gemini_helper import (
    get_gemini_client,
    call_gemini_with_retry,
    sanitize_playwright_python_code,
)
from helper.pom_generator import generate_runtime_poms

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "input")


async def inspect_website_with_mcp(test_cases, target_url=BASE_URL, client=None):
    """
    Connects to Playwright MCP in headless mode, captures live accessibility snapshots
    of the target website (and admin page if needed), extracts Playwright locators using Gemini,
    saves them to input/locator_data.json, and synthesizes Page Object Models.
    """
    active_client = client or get_gemini_client()
    print(f"\n[MCP] Connecting to Playwright MCP for: {target_url}...")

    # Configure Playwright MCP stdio server
    server_parameters = StdioServerParameters(
        command="npx",
        args=["-y", "@playwright/mcp@latest", "--headless"]
    )

    page_snapshots = {}

    try:
        async with Client(server_parameters) as mcp_client:
            pages_to_visit = [("HomePage", target_url)]

            # If test cases mention /admin, also inspect the admin page
            test_cases_str = json.dumps(test_cases).lower()
            normalized_base = target_url.rstrip("/")
            if "/admin" in test_cases_str and not target_url.endswith("/admin"):
                pages_to_visit.append(("AdminPage", f"{normalized_base}/admin"))

            for page_name, url in pages_to_visit:
                print(f"[MCP] Navigating to {page_name}: {url}...")
                await mcp_client.call_tool("browser_navigate", {"url": url})
                # Short wait to let client-side JavaScript / SPA render
                await asyncio.sleep(2)
                res = await mcp_client.call_tool("browser_snapshot", {})
                snapshot_text = "".join(c.text for c in res.content if hasattr(c, "text"))
                page_snapshots[page_name] = {
                    "url": url,
                    "snapshot": snapshot_text
                }

    except Exception as e:
        print(f"[MCP] Warning: MCP browser session encountered an issue: {e}")
        if "HomePage" not in page_snapshots:
            page_snapshots["HomePage"] = {"url": target_url, "snapshot": ""}

    print(f"\n[MCP] Snapshots captured for: {list(page_snapshots.keys())}")
    print("[MCP] Extracting Playwright locators using Gemini...\n")

    # Build prompt context with live snapshots
    snapshots_context = ""
    for p_name, p_info in page_snapshots.items():
        snapshots_context += f"\n=== {p_name} ({p_info['url']}) ===\n"
        snapshots_context += p_info["snapshot"][:10000] + "\n"

    prompt = f"""You are an expert Playwright automation engineer.

Below are live accessibility snapshots captured directly from the target website using Playwright MCP:
Website Base URL: {target_url}

{snapshots_context}

=== APPROVED TEST CASES ===
{json.dumps(test_cases, indent=2)}

TASK:
Analyze the live accessibility snapshots.
Extract all key interactive elements (buttons, inputs, links, forms, headings, dialogs) required by the approved test cases.
For each element, extract the most accurate, resilient Playwright locator expression.

CRITICAL PYTHON PLAYWRIGHT SYNTAX:
- You MUST use Python Playwright sync API syntax (snake_case).
- NEVER use JavaScript/TypeScript syntax:
  - `page.get_by_role("...", name="...")` (NOT getByRole)
  - `page.get_by_text("...")` (NOT getByText)
  - `page.get_by_placeholder("...")` (NOT getByPlaceholder)
  - `page.get_by_label("...")` (NOT getByLabel)
  - `page.get_by_test_id("...")` (NOT getByTestId)

Return ONLY a valid JSON dictionary structured exactly like this:
{{
  "HomePage": {{
    "url": "{target_url}",
    "locators": {{
      "element_name": "page.get_by_role(\\"button\\", name=\\"Submit\\")"
    }}
  }}
}}
Return ONLY valid JSON. No markdown ticks, no extra text.
"""

    response = call_gemini_with_retry(
        model=MODEL,
        contents=prompt,
        client=active_client
    )

    output = response.text.strip()
    if output.startswith("```json"):
        output = output[7:]
    elif output.startswith("```"):
        output = output[3:]
    if output.endswith("```"):
        output = output[:-3]
    output = output.strip()

    try:
        locator_data = json.loads(output)
    except json.JSONDecodeError:
        start_idx = output.find("{")
        end_idx = output.rfind("}")
        if start_idx != -1 and end_idx != -1:
            try:
                locator_data = json.loads(output[start_idx:end_idx + 1])
            except Exception as err:
                print(f"[MCP] Warning: Failed to parse locator JSON: {err}")
                locator_data = {"HomePage": {"url": target_url, "locators": {}}}
        else:
            locator_data = {"HomePage": {"url": target_url, "locators": {}}}

    # Sanitize locator expressions
    for p_name, p_data in locator_data.items():
        if isinstance(p_data, dict) and "locators" in p_data:
            for loc_key, loc_val in p_data["locators"].items():
                p_data["locators"][loc_key] = sanitize_playwright_python_code(loc_val)

    # Save to input/locator_data.json
    os.makedirs(INPUT_DIR, exist_ok=True)
    input_loc_path = os.path.join(INPUT_DIR, "locator_data.json")
    with open(input_loc_path, "w", encoding="utf-8") as file:
        json.dump(locator_data, file, indent=2)

    print(f"[MCP] Locators saved to {input_loc_path}")

    # Synthesize Page Object Models
    pom_summary = generate_runtime_poms(
        page_snapshots=page_snapshots,
        locator_data=locator_data,
        test_cases=test_cases,
        target_url=target_url,
        client=active_client
    )

    return locator_data, pom_summary


__all__ = ["inspect_website_with_mcp", "call_gemini_with_retry"]
