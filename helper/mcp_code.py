import os
import sys
import json
import asyncio
import re
import time
from urllib.parse import urlparse, urljoin

from dotenv import load_dotenv
from google import genai
from mcp import Client, StdioServerParameters

from constants.constants import MODEL, BASE_URL, MAX_PAGES_TO_CRAWL

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "input")
TESTS_DIR = os.path.join(BASE_DIR, "tests")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_default_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def call_gemini_with_retry(model, contents, client=None, max_retries=5, initial_delay=3):
    """Calls Gemini API with exponential backoff retry and fallback for transient 503/429/quota errors."""
    active_client = client or _default_client
    if not active_client:
        raise ValueError("Gemini client is not initialized. Please ensure GEMINI_API_KEY is in .env")

    delay = initial_delay
    fallback_pool = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    model_queue = [model] + [m for m in fallback_pool if m != model]
    model_idx = 0

    for attempt in range(1, max_retries + 1):
        current_model = model_queue[model_idx % len(model_queue)]
        try:
            return active_client.models.generate_content(
                model=current_model,
                contents=contents
            )
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "404" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                model_idx += 1
                next_model = model_queue[model_idx % len(model_queue)]
                print(f"[Gemini] Issue with '{current_model}' ({err_msg[:60]}...). Switching to '{next_model}'...")
                if attempt < max_retries:
                    print(f"[Gemini] Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    delay = min(delay * 2, 8)
                    continue
            raise e



async def inspect_website_with_mcp(test_cases, target_url=BASE_URL, client=None):
    """
    Connects to Playwright MCP, systematically crawls and inspects multiple pages
    of the target website URL, captures live accessibility snapshots, and extracts
    accurate Playwright locators for all pages stored as a clean dictionary in
    input/locator_data.json.
    """
    active_client = client or _default_client
    print(f"\n[MCP] Connecting to Playwright MCP for website: {target_url}...\n")

    server_parameters = StdioServerParameters(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--caps=testing"
        ]
    )

    parsed_target = urlparse(target_url)
    base_origin = f"{parsed_target.scheme}://{parsed_target.netloc}"
    normalized_base = target_url.rstrip("/")

    page_snapshots = {}

    async with Client(server_parameters) as mcp_client:
        # 1. Inspect base/home URL
        print(f"[MCP] (1) Navigating to base URL: {target_url}...")
        try:
            await mcp_client.call_tool("browser_navigate", {"url": target_url})
            try:
                await mcp_client.call_tool("browser_evaluate", {"function": "() => new Promise(resolve => setTimeout(resolve, 2500))"})
            except Exception:
                pass
            res_home = await mcp_client.call_tool("browser_snapshot", {})
            home_snapshot = "".join(c.text for c in res_home.content if hasattr(c, "text"))
            page_snapshots["HomePage"] = {
                "url": target_url,
                "snapshot": home_snapshot
            }
        except Exception as e:
            print(f"[MCP] Error accessing base URL {target_url}: {e}")
            page_snapshots["HomePage"] = {
                "url": target_url,
                "snapshot": ""
            }

        # 2. Discover internal links on the site via JavaScript evaluate
        print(f"[MCP] Discovering internal links across {target_url}...")
        js_extract_links = """() => {
            const origin = window.location.origin;
            const links = Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href.split('#')[0].split('?')[0])
                .filter(href => {
                    try {
                        const u = new URL(href);
                        return u.origin === origin && !u.pathname.match(/\\.(png|jpg|jpeg|gif|svg|webp|pdf|css|js|ico|woff|woff2|zip|exe|dmg)$/i);
                    } catch (e) {
                        return false;
                    }
                });
            return Array.from(new Set(links));
        }"""

        discovered_links = []
        try:
            eval_res = await mcp_client.call_tool("browser_evaluate", {"function": js_extract_links})
            raw_text = "".join(c.text for c in eval_res.content if hasattr(c, "text"))
            if "[" in raw_text:
                start_idx = raw_text.index("[")
                discovered_links, _ = json.JSONDecoder().raw_decode(raw_text[start_idx:])
        except Exception as e:
            print(f"[MCP] Link extraction notice: {e}")

        # 3. Add potential routes mentioned in test cases or standard web features
        test_cases_json_str = json.dumps(test_cases)
        for route_candidate in ["/admin", "/admin/rooms", "/admin/message", "/admin/branding", "/admin/report", "/reservation/1"]:
            if route_candidate in test_cases_json_str.lower() or route_candidate in ["/admin", "/admin/rooms", "/reservation/1"]:
                full_cand = f"{normalized_base}{route_candidate}"
                if full_cand not in discovered_links:
                    discovered_links.append(full_cand)

        # 4. Filter, prioritize, and limit pages to crawl
        unique_urls = []
        for link in discovered_links:
            norm_link = link.rstrip("/")
            if norm_link and norm_link != normalized_base and norm_link.startswith(base_origin) and norm_link not in unique_urls:
                unique_urls.append(norm_link)

        def sort_priority(u):
            lower_u = u.lower()
            if lower_u.endswith("/admin"):
                return 0
            if "admin" in lower_u:
                return 1
            if "room" in lower_u:
                return 2
            if "reservation" in lower_u or "booking" in lower_u:
                return 3
            if "message" in lower_u:
                return 4
            return 10

        unique_urls.sort(key=sort_priority)
        pages_to_crawl = unique_urls[:MAX_PAGES_TO_CRAWL - 1]

        print(f"[MCP] Discovered {len(unique_urls)} internal pages. Inspecting up to {len(pages_to_crawl)} key subpages...")

        # 5. Visit each discovered page and snapshot
        for idx, page_url in enumerate(pages_to_crawl, start=2):
            print(f"[MCP] ({idx}/{len(pages_to_crawl) + 1}) Inspecting page: {page_url}...")
            try:
                await mcp_client.call_tool("browser_navigate", {"url": page_url})
                try:
                    await mcp_client.call_tool("browser_evaluate", {"function": "() => new Promise(resolve => setTimeout(resolve, 2500))"})
                except Exception:
                    pass
                res = await mcp_client.call_tool("browser_snapshot", {})
                snap = "".join(c.text for c in res.content if hasattr(c, "text"))

                path_part = urlparse(page_url).path.strip("/")
                clean_name = "".join(p.capitalize() for p in re.split(r"[-_/]", path_part)) if path_part else f"SubPage{idx}"
                page_key = f"{clean_name}Page"
                if page_key in page_snapshots:
                    page_key = f"{page_key}_{idx}"

                page_snapshots[page_key] = {
                    "url": page_url,
                    "snapshot": snap
                }
            except Exception as err:
                print(f"[MCP] Warning: Could not inspect {page_url}: {err}")

        # 6. Optional authenticated view snapshot
        login_key = next((k for k in page_snapshots if "login" in k.lower()), None)
        creds_file = os.path.join(INPUT_DIR, "credentials.json")
        if login_key and os.path.exists(creds_file):
            try:
                with open(creds_file, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                username = creds.get("username")
                raw_pwd = creds.get("password")
                if username and raw_pwd:
                    from utils.encryption import decrypt_value
                    password = decrypt_value(raw_pwd)
                    print(f"[MCP] Attempting authenticated view inspection for {username}...")
                    await mcp_client.call_tool("browser_navigate", {"url": page_snapshots[login_key]["url"]})
                    await mcp_client.call_tool("browser_fill_form", {
                        "fields": [
                            {"selector": "input[type='email'], input[name='user'], input[name='email']", "value": username}
                        ]
                    })
                    await mcp_client.call_tool("browser_press_key", {"key": "Enter"})
                    await asyncio.sleep(2)
                    post_auth = await mcp_client.call_tool("browser_snapshot", {})
                    post_snap = "".join(c.text for c in post_auth.content if hasattr(c, "text"))
                    if len(post_snap) > 150 and post_snap != page_snapshots[login_key]["snapshot"]:
                        page_snapshots["AuthenticatedDashboardPage"] = {
                            "url": f"{normalized_base}/boards",
                            "snapshot": post_snap
                        }
                        print("[MCP] Successfully captured authenticated dashboard snapshot.")
            except Exception as auth_err:
                print(f"[MCP] Authenticated view note: {auth_err}")

    print(f"\n[MCP] Live accessibility snapshots captured for {len(page_snapshots)} pages: {list(page_snapshots.keys())}")
    print("Extracting accurate Playwright locators for all pages into a dictionary...\n")

    snapshots_context = ""
    for p_name, p_info in page_snapshots.items():
        snapshots_context += f"\n=== {p_name} ({p_info['url']}) ===\n"
        snapshots_context += p_info["snapshot"][:12000]
        snapshots_context += "\n"

    prompt = f"""You are an expert Playwright automation engineer.

Below are live accessibility snapshots captured directly from multiple pages across the website using Playwright MCP:
Website Base URL: {target_url}

{snapshots_context}

=== APPROVED TEST CASES ===
{json.dumps(test_cases, indent=2)}

TASK:
Analyze the live accessibility snapshots captured for each page above.
Extract all key interactive elements (buttons, inputs, links, forms, dropdowns, navigation items, headings, dialogs) as well as any specific elements required by the approved test cases.
For each element, extract the most accurate, resilient Playwright locator expression.

CRITICAL PYTHON PLAYWRIGHT SYNTAX:
- You MUST use Python Playwright sync API syntax.
- All method and argument names MUST be snake_case!
- NEVER use JavaScript/TypeScript names:
  - NEVER use `getByRole` -> ALWAYS use `page.get_by_role("...", name="...")`
  - NEVER use `getByText` -> ALWAYS use `page.get_by_text("...")`
  - NEVER use `getByPlaceholder` -> ALWAYS use `page.get_by_placeholder("...")`
  - NEVER use `getByLabel` -> ALWAYS use `page.get_by_label("...")`
  - NEVER use `getByTestId` -> ALWAYS use `page.get_by_test_id("...")`
  - NEVER use `hasText` -> ALWAYS use `filter(has_text="...")` or `filter(has=...)`
- Prefer standard Playwright locators:
  - page.get_by_role("...", name="...")
  - page.get_by_placeholder("...")
  - page.get_by_label("...")
  - page.get_by_text("...")
  - page.get_by_test_id("...")

Return ONLY a valid JSON object formatted as a DICTIONARY where each top-level key is a Page Name (e.g. 'HomePage', 'LoginPage', etc.), structured exactly like this:
{{
  "HomePage": {{
    "url": "{target_url}",
    "locators": {{
      "trello_logo": "page.get_by_role(\\"link\\", name=\\"Atlassian Trello\\").first",
      "login_link": "page.get_by_role(\\"link\\", name=\\"Log in\\").first",
      "get_trello_free_button": "page.get_by_role(\\"link\\", name=\\"Get Trello for free\\")",
      "features_button": "page.get_by_role(\\"button\\", name=\\"Features\\")",
      "plans_button": "page.get_by_role(\\"button\\", name=\\"Plans\\")"
    }}
  }},
  "LoginPage": {{
    "url": "{target_url}/login",
    "locators": {{
      "email_input": "page.get_by_placeholder(\\"Enter email\\")",
      "continue_button": "page.get_by_role(\\"button\\", name=\\"Continue\\")",
      "password_input": "page.get_by_placeholder(\\"Enter password\\")",
      "login_button": "page.get_by_role(\\"button\\", name=\\"Log in\\")"
    }}
  }}
}}

Make sure every inspected page is represented in the dictionary with all its useful locators.
Return ONLY valid JSON. Do not return markdown. Do not provide explanations.
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
            except json.JSONDecodeError as error:
                print("Error: Gemini returned invalid JSON for locator data:", error)
                print("Output was:\n", output)
                sys.exit(1)
        else:
            print("Error: Could not parse JSON from Gemini output.")
            print("Output was:\n", output)
            sys.exit(1)

    # Sanitize locator expressions to guarantee valid Python Playwright syntax
    def sanitize_expr(expr):
        if not isinstance(expr, str):
            return expr
        replacements = [
            (r"\.getByRole\(", ".get_by_role("),
            (r"\.getByText\(", ".get_by_text("),
            (r"\.getByLabel\(", ".get_by_label("),
            (r"\.getByPlaceholder\(", ".get_by_placeholder("),
            (r"\.getByTestId\(", ".get_by_test_id("),
            (r"\.getByTitle\(", ".get_by_title("),
            (r"\.getByAltText\(", ".get_by_alt_text("),
            (r"hasText\s*[:=]", "has_text="),
            (r"hasNotText\s*[:=]", "has_not_text="),
        ]
        for pattern, rep in replacements:
            expr = re.sub(pattern, rep, expr)
        return expr

    for p_name, p_data in locator_data.items():
        if isinstance(p_data, dict) and "locators" in p_data:
            for loc_key, loc_val in p_data["locators"].items():
                p_data["locators"][loc_key] = sanitize_expr(loc_val)

    # Save dictionary to input/locator_data.json
    input_loc_path = os.path.join(INPUT_DIR, "locator_data.json")
    os.makedirs(INPUT_DIR, exist_ok=True)
    with open(input_loc_path, "w", encoding="utf-8") as file:
        json.dump(locator_data, file, indent=2)

    print("Accurate locator dictionary saved to:")
    print(f" - {input_loc_path}")

    # Synthesize Page Object Models at runtime based on visited pages, locators, and test cases
    from helper.pom_generator import generate_runtime_poms
    pom_summary = generate_runtime_poms(
        page_snapshots=page_snapshots,
        locator_data=locator_data,
        test_cases=test_cases,
        target_url=target_url,
        client=active_client
    )

    return locator_data, pom_summary
