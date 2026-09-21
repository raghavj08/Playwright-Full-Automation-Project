import os
import sys
import json
import re

from constants.constants import MODEL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
INPUT_DIR = os.path.join(BASE_DIR, "input")


def generate_runtime_poms(page_snapshots, locator_data, test_cases, target_url, client=None):
    """
    Dynamically generates Page Object Model (POM) Python classes at runtime based on:
    1. Live page accessibility snapshots captured by Playwright MCP
    2. Accurate locators extracted from MCP
    3. Approved user requirements and test cases

    Writes the generated Python files into pages/ and returns a formatted pom_summary string.
    """
    from helper.mcp_code import call_gemini_with_retry

    print("\n" + "=" * 50)
    print("[POM Generator] Synthesizing Runtime Page Object Models...")
    print("=" * 50 + "\n")

    # Format snapshot context for the prompt
    snapshots_context = ""
    for p_name, p_info in page_snapshots.items():
        snapshots_context += f"\n=== PAGE: {p_name} ({p_info.get('url', '')}) ===\n"
        snap_text = p_info.get("snapshot", "")
        # Limit per snapshot to avoid overwhelming the token window
        snapshots_context += snap_text[:8000] + "\n"

    prompt = f"""You are a principal test automation architect specializing in Playwright and Python.

TASK:
Synthesize a complete, modular, maintainable Page Object Model (POM) architecture for the target website at runtime.
Target Website Base URL: {target_url}

The Page Object Models must be formed specifically for the pages discovered by Playwright MCP and must provide all locators and high-level action methods required to execute the approved test cases.

==================================================
LIVE PAGE ACCESSIBILITY SNAPSHOTS (FROM MCP)
==================================================
{snapshots_context}

==================================================
EXTRACTED PLAYWRIGHT LOCATORS (BY PAGE)
==================================================
{json.dumps(locator_data, indent=2)}

==================================================
APPROVED TEST CASES (REQUIREMENTS TO SATISFY)
==================================================
{json.dumps(test_cases, indent=2)}

==================================================
ARCHITECTURE REQUIREMENTS:
==================================================
1. `pages/base_page.py`:
   - Class `BasePage`
   - `__init__(self, page: Page)`: initializes `self.page = page`
   - Utility methods:
     - `navigate_to(self, url: str)`: `self.page.goto(url, wait_until="domcontentloaded")`
     - `scroll_to_bottom(self)`: `self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")`
     - Common header navigation or footer locators present across the site (scoped cleanly to avoid strict mode collisions).

2. Concrete Page Objects (e.g. `pages/home_page.py`, `pages/admin_page.py`, etc.):
   - Generate dedicated Page Object classes for each key page inspected or needed by the test cases.
   - Filenames in snake_case (e.g. `home_page.py`, `login_page.py`, `admin_page.py`, `booking_page.py`).
   - Class names in PascalCase (e.g. `HomePage(BasePage)`, `AdminPage(BasePage)`).
   - Each page class MUST:
     - Inherit from `BasePage`.
     - In `__init__(self, page: Page)`: call `super().__init__(page)` and define locators.
     - STRICT MODE SAFETY: Every locator MUST resolve uniquely. Never use `.or_` expressions that match multiple elements simultaneously (e.g. use specific `#description` or `locator("textarea")`). Scope top navbar links (e.g. `locator("#navbarNav").get_by_role("link", ...)` or `.first`) to prevent collisions with footer links.
     - ELEMENT COVERAGE: Define all key headings, inputs, buttons, and status alerts referenced in the approved test cases (e.g. `login_heading`, `welcome_heading`, `rooms_heading`, etc.) so that tests never encounter `AttributeError`.
     - Provide a `navigate(self)` method to open that page's URL.
     - Provide high-level semantic action helper methods directly serving the approved test cases (e.g. `login(username, password)`, `fill_contact_form(...)`, `submit_contact_form()`, `book_room(...)`, etc.).

3. `pages/__init__.py`:
   - Imports all generated Page Object classes.
   - Defines `__all__ = ["BasePage", ...]` exporting every page class so tests can do:
     `from pages import HomePage, AdminPage, ...`

4. `pom_summary`:
   - Provide a concise cheatsheet summary listing each Page Object class, its import statement, key locator attributes, and action methods with parameters.
   - This summary will be used by the test generation agent and auto-healer.

==================================================
OUTPUT FORMAT:
==================================================
Return ONLY a valid JSON object with the following schema:
{{
  "files": {{
    "pages/base_page.py": "from playwright.sync_api import Page, Locator, expect\\n\\nclass BasePage:\\n...",
    "pages/home_page.py": "from playwright.sync_api import Page, Locator\\nfrom pages.base_page import BasePage\\n\\nclass HomePage(BasePage):\\n...",
    "pages/__init__.py": "from pages.base_page import BasePage\\nfrom pages.home_page import HomePage\\n\\n__all__ = ['BasePage', 'HomePage']\\n"
  }},
  "pom_summary": "### Available Page Objects\\n- `HomePage(page)`: ...\\n"
}}

Rules:
- Python code inside "files" must be valid, syntactically correct Python 3.
- Use Playwright sync API (`from playwright.sync_api import Page, Locator, expect`).
- Do NOT use markdown outside the JSON. Return ONLY the JSON object.
"""

    response = call_gemini_with_retry(
        model=MODEL,
        contents=prompt,
        client=client
    )

    output = response.text.strip()
    if output.startswith("```json"):
        output = output[7:]
    elif output.startswith("```"):
        output = output[3:]
    if output.endswith("```"):
        output = output[:-3]
    output = output.strip()

    parsed_result = None
    try:
        parsed_result = json.loads(output)
    except json.JSONDecodeError:
        start_idx = output.find("{")
        end_idx = output.rfind("}")
        if start_idx != -1 and end_idx != -1:
            try:
                parsed_result = json.loads(output[start_idx:end_idx + 1])
            except json.JSONDecodeError as err:
                print(f"[POM Generator] Error parsing JSON from Gemini response: {err}")
                print("Raw output sample:\n", output[:500])

    if not parsed_result or "files" not in parsed_result:
        print("[POM Generator] Warning: Could not parse generated POM files dictionary. Retrying with targeted prompt...")
        # Fallback basic structure if synthesis failed
        return _fallback_pom_generation(target_url, locator_data)

    files_dict = parsed_result.get("files", {})
    pom_summary = parsed_result.get("pom_summary", "")

    os.makedirs(PAGES_DIR, exist_ok=True)

    def sanitize_code(code_str):
        if not isinstance(code_str, str):
            return code_str
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
            code_str = re.sub(pattern, rep, code_str)
        return code_str

    # Write each generated file to disk
    written_files = []
    for rel_path, code in files_dict.items():
        clean_rel = rel_path.replace("\\", "/")
        if clean_rel.startswith("pages/"):
            filename = os.path.basename(clean_rel)
            full_path = os.path.join(PAGES_DIR, filename)
        else:
            filename = os.path.basename(clean_rel)
            full_path = os.path.join(PAGES_DIR, filename)

        sanitized_code = sanitize_code(code.strip())
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(sanitized_code + "\n")
        written_files.append(filename)

    # Save pom_summary to input/pom_summary.txt for debugging and prompt feeding
    summary_path = os.path.join(INPUT_DIR, "pom_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(pom_summary)

    print(f"[POM Generator] Successfully generated {len(written_files)} runtime Page Object files in 'pages/':")
    for wf in written_files:
        print(f"  - pages/{wf}")
    print(f"[POM Generator] POM Summary saved to: {summary_path}\n")

    return pom_summary


def _fallback_pom_generation(target_url, locator_data):
    """Provides a safe fallback BasePage and HomePage if LLM JSON fails to parse."""
    base_page_code = '''from playwright.sync_api import Page, Locator, expect

class BasePage:
    """Base Page Object providing common locators and utility actions."""

    def __init__(self, page: Page):
        self.page = page

    def navigate_to(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def scroll_to_bottom(self):
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
'''
    home_locators = locator_data.get("HomePage", {}).get("locators", {})
    loc_lines = []
    for name, expr in home_locators.items():
        loc_lines.append(f"        self.{name} = {expr}")

    loc_block = "\n".join(loc_lines) if loc_lines else "        pass"

    home_page_code = f'''from playwright.sync_api import Page, Locator
from pages.base_page import BasePage

class HomePage(BasePage):
    """Runtime Page Object for Home Page."""

    URL = "{target_url}"

    def __init__(self, page: Page):
        super().__init__(page)
{loc_block}

    def navigate(self):
        self.page.goto(self.URL, wait_until="domcontentloaded")
'''
    init_code = '''from pages.base_page import BasePage
from pages.home_page import HomePage

__all__ = ["BasePage", "HomePage"]
'''
    os.makedirs(PAGES_DIR, exist_ok=True)
    with open(os.path.join(PAGES_DIR, "base_page.py"), "w", encoding="utf-8") as f:
        f.write(base_page_code)
    with open(os.path.join(PAGES_DIR, "home_page.py"), "w", encoding="utf-8") as f:
        f.write(home_page_code)
    with open(os.path.join(PAGES_DIR, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(init_code)

    summary = f"""### Fallback Runtime Page Objects
- `HomePage(page)`: `navigate()`, locators: {list(home_locators.keys())}
"""
    return summary
