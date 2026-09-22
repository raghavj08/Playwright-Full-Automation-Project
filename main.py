import sys
import json
import asyncio

from constants.constants import BASE_URL, API_BASE_URL
from helper import (
    get_gemini_client,
    generate_test_cases,
    generate_playwright_code,
    run_tests,
    inspect_website_with_mcp,
)

# Ensure UTF-8 output on Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def select_run_configuration():
    """Parses CLI arguments or prompts user for testing type and target URL."""
    testing_type = None
    target_url = None

    for arg in sys.argv[1:]:
        arg_lower = arg.lower()
        if arg_lower in ["--ui", "-ui", "ui"]:
            testing_type = "UI"
        elif arg_lower in ["--api", "-api", "api"]:
            testing_type = "API"
        elif arg_lower.startswith("--type="):
            t = arg.split("=", 1)[1].strip().upper()
            if t in ["UI", "API"]:
                testing_type = t
        elif arg.startswith("http://") or arg.startswith("https://"):
            target_url = arg
        elif arg.startswith("--url="):
            target_url = arg.split("=", 1)[1]

    # Prompt for testing type if not provided via CLI
    if not testing_type:
        print("\n" + "=" * 50)
        print("SELECT TESTING TYPE")
        print("=" * 50)
        print("1. UI Testing  (Playwright Web Browser automation)")
        print("2. API Testing (Playwright REST APIRequestContext)")
        print("=" * 50)
        try:
            choice = input("\nEnter choice [1/2] (default: 1 - UI): ").strip()
            testing_type = "API" if choice in ["2", "api", "API"] else "UI"
        except (EOFError, KeyboardInterrupt):
            testing_type = "UI"

    default_url = API_BASE_URL if testing_type == "API" else BASE_URL
    if not target_url:
        try:
            prompt_label = "API Base URL" if testing_type == "API" else "Website URL"
            user_input_url = input(f"\nEnter {prompt_label} [Press Enter for default '{default_url}']: ").strip()
            target_url = user_input_url if user_input_url else default_url
        except (EOFError, KeyboardInterrupt):
            target_url = default_url

    return testing_type, target_url


def main():
    # 0. Setup & Client Initialization
    client = get_gemini_client()
    testing_type, target_url = select_run_configuration()

    print("\n" + "=" * 50)
    print(f"TESTING MODE : {testing_type}")
    print(f"TARGET URL   : {target_url}")
    print("=" * 50)

    # 1. Requirements -> Test cases (UI or API)
    test_cases = generate_test_cases(testing_type=testing_type, target_url=target_url, client=client)

    # 2. QA Review & Approval
    print("\n" + "=" * 50)
    print(f"QA APPROVAL ({testing_type} TEST CASES)")
    print("=" * 50)
    print(json.dumps(test_cases, indent=2))

    try:
        approval = input("\nApprove these test cases? (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        approval = "no"

    if approval not in ["yes", "y"]:
        print("\nTest cases rejected. Exiting.")
        return

    # 3. Locator Data & Dynamic POM Synthesis (MCP for UI, Skipped for API)
    locator_data = None
    pom_summary = None
    if testing_type == "UI":
        print("\n" + "=" * 50)
        print("STARTING PLAYWRIGHT MCP INSPECTION & RUNTIME POM SYNTHESIS (UI)")
        print("=" * 50)
        locator_data, pom_summary = asyncio.run(
            inspect_website_with_mcp(test_cases, target_url=target_url, client=client)
        )
    else:
        print("\n" + "=" * 50)
        print("SKIPPING MCP INSPECTION (API MODE)")
        print("REST API tests interact with endpoints directly via APIRequestContext.")
        print("=" * 50)

    # 4. Generate Playwright Automation Code
    generate_playwright_code(
        test_cases=test_cases,
        locator_data=locator_data,
        pom_summary=pom_summary,
        testing_type=testing_type,
        target_url=target_url,
        client=client,
    )

    # 5. Run Pytest with Autonomous Self-Healing
    run_tests(testing_type=testing_type, pom_summary=pom_summary, client=client)


if __name__ == "__main__":
    main()