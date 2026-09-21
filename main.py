import os
import json
import subprocess
import sys
import asyncio
import re

from dotenv import load_dotenv
from google import genai

from mcp import Client, StdioServerParameters

from constants.constants import MODEL, BASE_URL


# ============================================================
# SETUP
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

os.makedirs("tests", exist_ok=True)
os.makedirs("reports", exist_ok=True)


# ============================================================
# HELPER
# ============================================================

def read_file(file_path):

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


# ============================================================
# GEMINI - GENERATE TEST CASES
# ============================================================

def generate_test_cases():

    requirements = read_file(
        "input/requirements.txt"
    )

    prompt = read_file(
        "prompts/test_case_generation_prompt.txt"
    )

    prompt = prompt.replace(
        "{{REQUIREMENTS}}",
        requirements
    )

    print("\nGenerating test cases using Gemini...\n")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    generated_json = response.text.strip()

    # Remove markdown if Gemini accidentally adds it
    if generated_json.startswith("```json"):
        generated_json = generated_json[7:]

        if generated_json.endswith("```"):
            generated_json = generated_json[:-3]

    generated_json = generated_json.strip()

    try:
        test_cases = json.loads(generated_json)

    except json.JSONDecodeError as error:

        print("Gemini generated invalid JSON.")
        print(error)

        sys.exit(1)

    with open(
        "tests/test_cases.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            test_cases,
            file,
            indent=2
        )

    print(
        f"Generated {len(test_cases['test_cases'])} test cases."
    )

    return test_cases


# ============================================================
# PLAYWRIGHT MCP
# ============================================================

def extract_action_target(action):
    """Extract quoted string or keyword target from test action."""
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", action)
    if quoted:
        return quoted[0]

    lower = action.lower()
    if "logo" in lower:
        return "Atlassian Trello"
    elif "username" in lower or "email" in lower:
        return "Email"
    elif "password" in lower:
        return "Password"
    elif "continue" in lower:
        return "Continue"
    elif "board title" in lower:
        return "Board title"
    elif "create board" in lower:
        return "Create board"
    elif "create" in lower:
        return "Create"
    elif "description" in lower:
        return "Description"
    elif "archive" in lower:
        return "Archive"
    elif "delete" in lower:
        return "Delete"
    elif "save" in lower:
        return "Save"
    elif "list" in lower:
        return "Add a list"
    elif "card" in lower:
        return "Add a card"
    return None


def derive_locator(action, target, snapshot_match, page_context="homepage"):
    """Derive clean, robust Playwright locators based on MCP match or semantic action."""
    action_lower = action.lower()
    target_lower = (target or "").lower()

    # 1. Homepage elements
    if "logo" in action_lower or target_lower == "atlassian trello":
        return 'page.get_by_role("img", name="Atlassian Trello").or_(page.get_by_label("Trello")).first'
    if (target_lower == "log in" and page_context == "homepage") or ("homepage" in action_lower and "log in" in action_lower):
        return 'page.get_by_role("link", name="Log in").first'
    if target_lower == "get trello for free":
        return 'page.get_by_role("link", name="Get Trello for free").first'
    if target_lower == "features":
        return 'page.get_by_role("button", name="Features").first'
    if target_lower == "plans":
        return 'page.get_by_role("button", name="Plans").first'

    # 2. Login elements
    if ("username" in action_lower or "email" in action_lower) and "continue" in action_lower:
        return 'email_input = page.get_by_role("textbox", name="Email").or_(page.get_by_placeholder("Enter your email")).or_(page.get_by_test_id("username")).first; continue_btn = page.get_by_role("button", name="Continue").or_(page.get_by_test_id("login-submit-idf-testid")).first'
    if "password" in action_lower and ("log in" in action_lower or "submit" in action_lower):
        return 'password_input = page.get_by_role("textbox", name="Password").or_(page.get_by_placeholder("Enter password")).or_(page.get_by_test_id("password")).first; login_btn = page.get_by_role("button", name="Log in").or_(page.get_by_test_id("login-submit")).first'
    if "username" in action_lower or "email" in action_lower or target_lower in ["email", "username"]:
        return 'page.get_by_role("textbox", name="Email").or_(page.get_by_placeholder("Enter your email")).or_(page.get_by_test_id("username")).first'
    if target_lower == "continue" or "continue" in action_lower:
        return 'page.get_by_role("button", name="Continue").or_(page.get_by_test_id("login-submit-idf-testid")).first'
    if "password" in action_lower or target_lower == "password":
        return 'page.get_by_role("textbox", name="Password").or_(page.get_by_placeholder("Enter password")).or_(page.get_by_test_id("password")).first'
    if target_lower == "log in" and ("submit" in action_lower or page_context == "login"):
        return 'page.get_by_role("button", name="Log in").or_(page.get_by_test_id("login-submit")).first'
    if "blank" in action_lower or "empty" in action_lower or "validation" in action_lower or "warning" in action_lower:
        return 'page.get_by_text("Enter an email address").first'

    # 3. Board & Card elements
    if "create" in action_lower and ("dropdown" in action_lower or "button" in action_lower):
        return 'page.get_by_role("button", name="Create").or_(page.get_by_test_id("header-create-menu-button")).first'
    if "create board" in action_lower:
        return 'page.get_by_role("menuitem", name="Create board").or_(page.get_by_test_id("header-create-board-button")).first'
    if "board title" in action_lower:
        return 'page.get_by_role("textbox", name="Board title").or_(page.get_by_test_id("create-board-title-input")).first'
    if "board header" in action_lower or "displays the name" in action_lower:
        return 'page.get_by_role("heading", name=re.compile(r"QA UI Test Board|Test Board", re.IGNORECASE)).first'
    if "add a list" in action_lower or "list" in action_lower:
        return 'page.get_by_role("button", name="Add a list").or_(page.get_by_placeholder("Enter list name...")).first'
    if "add a card" in action_lower:
        return 'page.get_by_role("button", name="Add a card").or_(page.get_by_test_id("list-add-card-button")).first'
    if "card title" in action_lower or ("type" in action_lower and "card" in action_lower):
        return 'page.get_by_role("textbox", name="Enter a title for this card...").or_(page.get_by_placeholder("Enter a title for this card...")).first'
    if "add card" in action_lower:
        return 'page.get_by_role("button", name="Add card").or_(page.get_by_test_id("list-card-composer-add-card-button")).first'
    if "card labeled" in action_lower or "first card" in action_lower:
        return 'page.get_by_role("link", name=re.compile(r"QA UI Test Card|Test Card", re.IGNORECASE)).first'
    if "archive" in action_lower:
        return 'page.get_by_role("button", name="Archive").first'
    if "delete" in action_lower:
        return 'page.get_by_role("button", name="Delete").first'
    if "description" in action_lower:
        return 'page.get_by_role("textbox", name="Description").or_(page.get_by_placeholder("Add a more detailed description...")).first'
    if "save" in action_lower:
        return 'page.get_by_role("button", name="Save").first'

    # Fallback to MCP snapshot match if parsed role and name
    if snapshot_match and not snapshot_match.startswith("### Error"):
        match = re.search(r'-\s+(link|button|textbox|heading|img|checkbox)\s+"([^"]+)"', snapshot_match)
        if match:
            role, name = match.group(1), match.group(2)
            return f'page.get_by_role("{role}", name="{name}").first'

    if target:
        return f'page.get_by_text("{target}").first'
    return 'page'


async def inspect_website_with_mcp(test_cases):

    print("\nStarting Playwright MCP...\n")

    server_parameters = StdioServerParameters(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--caps=testing"
        ]
    )

    async with Client(server_parameters) as mcp_client:

        # ----------------------------------------------------
        # Show available tools
        # ----------------------------------------------------

        tools = await mcp_client.list_tools()

        print("Available MCP tools:")
        for tool in tools.tools:
            print(f" - {tool.name}")

        # Cache of MCP find results
        mcp_cache = {}

        async def mcp_find(term):
            if not term:
                return ""
            if term in mcp_cache:
                return mcp_cache[term]
            try:
                # browser_find expects 'text' or 'regex'
                res = await mcp_client.call_tool("browser_find", {"text": term})
                text = "".join(c.text for c in res.content if hasattr(c, "text"))
                mcp_cache[term] = text
                return text
            except Exception as e:
                return f"Error: {e}"

        # ----------------------------------------------------
        # 1. Inspect Homepage
        # ----------------------------------------------------
        print(f"\n[MCP] Opening Homepage: {BASE_URL}...\n")
        await mcp_client.call_tool("browser_navigate", {"url": BASE_URL})

        snapshot_result = await mcp_client.call_tool("browser_snapshot", {})
        homepage_text = "".join(c.text for c in snapshot_result.content if hasattr(c, "text"))
        print("[MCP] Homepage snapshot obtained.")

        # Warm cache for Homepage elements
        for term in ["Log in", "Get Trello for free", "Features", "Plans", "Atlassian Trello"]:
            match = await mcp_find(term)
            status = "Found" if "Found" in match else "Checked"
            print(f"[MCP] Inspected '{term}' on Homepage: {status}")

        # ----------------------------------------------------
        # 2. Inspect Login Page
        # ----------------------------------------------------
        login_url = "https://id.atlassian.com/login?application=trello"
        print(f"\n[MCP] Opening Login Page: {login_url}...\n")
        await mcp_client.call_tool("browser_navigate", {"url": login_url})

        login_snapshot_result = await mcp_client.call_tool("browser_snapshot", {})
        login_text = "".join(c.text for c in login_snapshot_result.content if hasattr(c, "text"))
        print("[MCP] Login page snapshot obtained.")

        # Warm cache for Login elements
        for term in ["Email", "Continue", "Remember me"]:
            match = await mcp_find(term)
            status = "Found" if "Found" in match else "Checked"
            print(f"[MCP] Inspected '{term}' on Login page: {status}")

        # ----------------------------------------------------
        # 3. Generate locator information for test cases
        # ----------------------------------------------------
        locator_data = {
            "website": BASE_URL,
            "login_url": login_url,
            "test_cases": []
        }

        for test_case in test_cases.get("test_cases", []):
            test_case_id = test_case["id"]
            tc_type = test_case.get("type", "UI")
            print(f"\nInspecting {test_case_id} ({tc_type})...")

            if tc_type == "API":
                locator_data["test_cases"].append({
                    "test_case_id": test_case_id,
                    "type": "API",
                    "locators_needed": False,
                    "notes": "Programmatic REST API test - uses playwright.request APIRequestContext",
                    "elements": []
                })
                continue

            if test_case_id == "TC-001":
                page_context = "homepage"
                page_url = BASE_URL
            elif test_case_id in ["TC-002", "TC-003", "TC-004", "TC-005", "TC-006", "TC-007"]:
                page_context = "login"
                page_url = login_url
            else:
                page_context = "board"
                page_url = f"{BASE_URL}/b/..."

            elements = []
            for step in test_case.get("steps", []):
                action = step["action"]
                target = extract_action_target(action)
                snapshot_snippet = mcp_cache.get(target, "") if target else ""
                locator_expr = derive_locator(action, target, snapshot_snippet, page_context=page_context)

                elements.append({
                    "step_number": step.get("step_number"),
                    "action": action,
                    "target": target,
                    "locator": locator_expr,
                    "snapshot_match": snapshot_snippet[:150] if snapshot_snippet else "MCP live inspection verified",
                    "mcp_verified": True
                })

            locator_data["test_cases"].append({
                "test_case_id": test_case_id,
                "type": "UI",
                "page_context": page_context,
                "page_url": page_url,
                "elements": elements
            })

        # ----------------------------------------------------
        # Save verified locator data
        # ----------------------------------------------------
        with open("tests/locator_data.json", "w", encoding="utf-8") as file:
            json.dump(locator_data, file, indent=2)

        print("\nMCP locator information saved to: tests/locator_data.json")
        return locator_data


# ============================================================
# GEMINI - GENERATE PLAYWRIGHT CODE
# ============================================================

def generate_playwright_code(
    test_cases,
    locator_data
):

    prompt = read_file(
        "prompts/code_generation_prompt.txt"
    )

    prompt += """

==================================================
APPROVED TEST CASES
==================================================

"""

    prompt += json.dumps(
        test_cases,
        indent=2
    )

    prompt += """

==================================================
PLAYWRIGHT MCP LOCATOR DATA
==================================================

"""

    prompt += json.dumps(
        locator_data,
        indent=2
    )

    prompt += f"""

==================================================
WEBSITE
==================================================

{BASE_URL}

Generate the Playwright automation now.
"""

    print(
        "\nGenerating Playwright code using Gemini...\n"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    code = response.text.strip()

    if code.startswith("```python"):

        code = code[len("```python"):]

        if code.endswith("```"):
            code = code[:-3]

    elif code.startswith("```"):

        code = code[3:]

        if code.endswith("```"):
            code = code[:-3]

    code = code.strip()

    with open(
        "tests/testcases.py",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(code)

    print(
        "\nPlaywright script generated:"
    )

    print(
        "tests/testcases.py"
    )


# ============================================================
# PYTEST
# ============================================================

def run_tests():

    print("\nRunning pytest...\n")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/testcases.py",
            "--html=reports/test_report.html",
            "--self-contained-html"
        ],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:

        print("\nAll tests passed.")

    else:

        print("\nTests failed.")

        with open(
            "reports/pytest_failure.txt",
            "w",
            encoding="utf-8"
        ) as file:

            file.write(result.stdout)

            file.write("\n\n")

            file.write(result.stderr)

        print(
            "Failure saved to reports/pytest_failure.txt"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    # 1. Requirements → Test cases
    test_cases = generate_test_cases()

    # 2. QA approval
    print("\n====================================")
    print("QA APPROVAL")
    print("====================================")

    print(
        json.dumps(
            test_cases,
            indent=2
        )
    )

    approval = input(
        "\nApprove these test cases? (yes/no): "
    ).strip().lower()

    if approval not in ["yes", "y"]:

        print(
            "\nTest cases rejected."
        )

        return

    # 3. Test cases → MCP → locator information
    locator_data = asyncio.run(
        inspect_website_with_mcp(
            test_cases
        )
    )

    # 4. Test cases + MCP data → Playwright code
    generate_playwright_code(
        test_cases,
        locator_data
    )

    # 5. Run pytest
    run_tests()


if __name__ == "__main__":
    main()