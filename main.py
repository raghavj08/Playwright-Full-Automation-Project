import os
import json
import subprocess
import sys
import asyncio
import time
from urllib.parse import urlparse, urljoin

from dotenv import load_dotenv
from google import genai

from constants.constants import MODEL, BASE_URL, API_BASE_URL
from helper.mcp_code import inspect_website_with_mcp

# Ensure UTF-8 output on Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ============================================================
# SETUP
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(BASE_DIR, "tests")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INPUT_DIR = os.path.join(BASE_DIR, "input")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

os.makedirs(TESTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)


# ============================================================
# HELPER
# ============================================================

def read_file(file_path):
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def sanitize_playwright_python_code(code_str):
    """Sanitizes generated Playwright Python code by replacing JavaScript/TypeScript API names with Python equivalents."""
    if not isinstance(code_str, str):
        return code_str
    import re
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


def call_gemini_with_retry(model, contents, max_retries=5, initial_delay=3):
    """Calls Gemini API with exponential backoff retry and fallback for transient 503/429/quota errors."""
    delay = initial_delay
    fallback_pool = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    model_queue = [model] + [m for m in fallback_pool if m != model]
    model_idx = 0

    for attempt in range(1, max_retries + 1):
        current_model = model_queue[model_idx % len(model_queue)]
        try:
            return client.models.generate_content(
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



# ============================================================
# GEMINI - GENERATE TEST CASES (UI vs API)
# ============================================================

def generate_test_cases(testing_type="UI", target_url=None):
    """
    Generates test cases based on testing_type ('UI' or 'API').
    Reads requirements from input/requirements.txt and uses the appropriate prompt template.
    Saves generated test cases to tests/testcase.json and tests/test_cases.json.
    """
    requirements = read_file("input/requirements.txt")

    if testing_type.upper() == "API":
        prompt_file = "prompts/api_test_case_generation_prompt.txt"
        target_url = target_url or API_BASE_URL
        print("\n[Mode: API Testing] Using prompts/api_test_case_generation_prompt.txt")
    else:
        prompt_file = "prompts/ui_test_case_generation_prompt.txt"
        target_url = target_url or BASE_URL
        print("\n[Mode: UI Testing] Using prompts/ui_test_case_generation_prompt.txt")

    prompt = read_file(prompt_file)
    prompt = prompt.replace("{{REQUIREMENTS}}", requirements)
    if "{{TARGET_URL}}" in prompt:
        prompt = prompt.replace("{{TARGET_URL}}", target_url)

    if testing_type.upper() == "API":
        prompt += f"\n\nNOTE: The target REST API base URL is: {target_url}. Generate REST API test cases for this API.\n"
    else:
        if target_url != BASE_URL:
            prompt += f"\n\nNOTE: The target website URL to test is: {target_url}. Generate UI test cases appropriate for this website.\n"

    print(f"\nGenerating {testing_type.upper()} test cases using Gemini...\n")

    response = call_gemini_with_retry(
        model=MODEL,
        contents=prompt
    )

    generated_json = response.text.strip()

    # Remove markdown if Gemini accidentally adds it
    if generated_json.startswith("```json"):
        generated_json = generated_json[7:]
        if generated_json.endswith("```"):
            generated_json = generated_json[:-3]
    elif generated_json.startswith("```"):
        generated_json = generated_json[3:]
        if generated_json.endswith("```"):
            generated_json = generated_json[:-3]

    generated_json = generated_json.strip()

    try:
        test_cases = json.loads(generated_json)
    except json.JSONDecodeError as error:
        print("Gemini generated invalid JSON.")
        print(error)
        print("Raw response:")
        print(generated_json[:500])
        sys.exit(1)

    # Save to testcase.json
    testcase_json_path = os.path.join(TESTS_DIR, "testcase.json")

    with open(testcase_json_path, "w", encoding="utf-8") as file:
        json.dump(test_cases, file, indent=2)

    count = len(test_cases.get("test_cases", []))
    print(f"Generated {count} {testing_type.upper()} test cases.")
    print(f"Saved to:\n- {testcase_json_path}")

    return test_cases


# ============================================================
# GEMINI - GENERATE PLAYWRIGHT CODE (UI vs API)
# ============================================================

def generate_playwright_code(
    test_cases,
    locator_data=None,
    pom_summary=None,
    testing_type="UI",
    target_url=None
):
    """
    Generates Playwright test automation code in tests/testcase.py.
    Uses prompts/ui_code_generation_prompt.txt for UI tests,
    and prompts/api_code_generation_prompt.txt for API tests.
    """
    if testing_type.upper() == "API":
        prompt_file = "prompts/api_code_generation_prompt.txt"
        target_url = target_url or API_BASE_URL
        prompt = read_file(prompt_file)
        prompt += f"""

==================================================
APPROVED REST API TEST CASES
==================================================

{json.dumps(test_cases, indent=2)}

==================================================
API BASE URL
==================================================

{target_url}

Generate the Playwright API automation (using APIRequestContext) now.
"""
        print("\nGenerating Playwright API automation code using Gemini...\n")
    else:
        prompt_file = "prompts/ui_code_generation_prompt.txt"
        target_url = target_url or BASE_URL
        prompt = read_file(prompt_file)

        if "{{TARGET_URL}}" in prompt:
            prompt = prompt.replace("{{TARGET_URL}}", target_url)
        if "{{POM_ARCHITECTURE}}" in prompt:
            prompt = prompt.replace("{{POM_ARCHITECTURE}}", pom_summary or "Page Objects generated in pages/ package")

        prompt += f"""

==================================================
APPROVED UI TEST CASES
==================================================

{json.dumps(test_cases, indent=2)}

==================================================
PLAYWRIGHT MCP LOCATOR DATA (DICTIONARY)
==================================================

{json.dumps(locator_data or {}, indent=2)}

==================================================
TARGET WEBSITE
==================================================

{target_url}

Generate the Playwright UI automation now.
"""
        print("\nGenerating Playwright UI automation code using Gemini...\n")

    response = call_gemini_with_retry(
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

    code = sanitize_playwright_python_code(code.strip())

    testcase_path = os.path.join(TESTS_DIR, "testcase.py")
    with open(testcase_path, "w", encoding="utf-8") as file:
        file.write(code)

    print(f"\nPlaywright {testing_type.upper()} script generated:\n- {testcase_path}\n")
    return testcase_path


# ============================================================
# PYTEST RUNNER & AUTONOMOUS SELF-HEALING LOOP
# ============================================================

def heal_test_code_with_gemini(failure_output, current_code, testing_type="UI", pom_summary=None):
    """
    Invokes Gemini to interpret pytest failure details and repair tests/testcase.py.
    """
    if not pom_summary:
        pom_summary_path = os.path.join(INPUT_DIR, "pom_summary.txt")
        if os.path.exists(pom_summary_path):
            try:
                with open(pom_summary_path, "r", encoding="utf-8") as f:
                    pom_summary = f.read()
            except Exception:
                pass

    try:
        prompt_template = read_file("prompts/self_healing_prompt.txt")
    except Exception as e:
        print(f"[Auto-Healer] Notice: Could not read prompts/self_healing_prompt.txt ({e}). Using default healing prompt.")
        prompt_template = """You are an expert Python Playwright QA engineer specializing in automated test self-healing.
A pytest test suite has failed. Analyze failure tracebacks and error logs, fix root causes (strict mode, text mismatches, missing POM properties), and output complete executable code for tests/testcase.py.
{{POM_ARCHITECTURE}}
Return ONLY valid Python code."""

    if "{{POM_ARCHITECTURE}}" in prompt_template:
        prompt_template = prompt_template.replace("{{POM_ARCHITECTURE}}", pom_summary or "Page Objects in pages/ package")

    prompt = f"""{prompt_template}

==================================================
TESTING TYPE
==================================================
{testing_type}

==================================================
PYTEST FAILURE OUTPUT & TRACEBACKS
==================================================
{failure_output}

==================================================
CURRENT tests/testcase.py CODE
==================================================
{current_code}

Diagnose and repair all failures now. Return ONLY the complete, fixed Python code for tests/testcase.py.
"""
    print(f"\n[Auto-Healer] Sending failure diagnostics to Gemini for repair...")
    response = call_gemini_with_retry(
        model=MODEL,
        contents=prompt
    )

    repaired_code = response.text.strip()
    if repaired_code.startswith("```python"):
        repaired_code = repaired_code[len("```python"):]
        if repaired_code.endswith("```"):
            repaired_code = repaired_code[:-3]
    repaired_code = sanitize_playwright_python_code(repaired_code.strip())

    return repaired_code


def run_tests(testing_type="UI", max_healing_attempts=3, pom_summary=None):
    """
    Executes pytest against the generated test script.
    If tests fail, automatically triggers the LLM to interpret failures,
    edit tests/testcase.py, and rerun until all tests pass or max attempts reached.
    """
    testcase_path = os.path.join(TESTS_DIR, "testcase.py")
    report_html = os.path.join(REPORTS_DIR, "test_report.html")
    failure_txt = os.path.join(REPORTS_DIR, "pytest_failure.txt")

    for attempt in range(1, max_healing_attempts + 2):
        print("\n" + "=" * 50)
        if attempt == 1:
            print("RUNNING PYTEST TEST SUITE")
        else:
            print(f"RE-RUNNING PYTEST AFTER SELF-HEALING (Attempt {attempt - 1} of {max_healing_attempts})")
        print("=" * 50 + "\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                testcase_path,
                f"--html={report_html}",
                "--self-contained-html"
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print("\n" + "=" * 50)
            print("SUCCESS: ALL TESTS PASSED!")
            print(f"Report: {report_html}")
            print("=" * 50 + "\n")
            if os.path.exists(failure_txt):
                try:
                    os.remove(failure_txt)
                except Exception:
                    pass
            return True

        # Tests failed
        print(f"\nTests finished with failures (exit code {result.returncode}).")
        with open(failure_txt, "w", encoding="utf-8") as file:
            file.write(result.stdout)
            file.write("\n\n")
            file.write(result.stderr)
        print(f"Failure details saved to {failure_txt}")

        if attempt <= max_healing_attempts:
            print(f"\n[Auto-Healer] Triggering Gemini to interpret failures and auto-heal test cases (Healing attempt {attempt}/{max_healing_attempts})...")
            with open(testcase_path, "r", encoding="utf-8") as file:
                current_code = file.read()

            failure_output = result.stdout + "\n" + result.stderr
            repaired_code = heal_test_code_with_gemini(
                failure_output=failure_output,
                current_code=current_code,
                testing_type=testing_type,
                pom_summary=pom_summary
            )

            if repaired_code:
                with open(testcase_path, "w", encoding="utf-8") as file:
                    file.write(repaired_code)
                print(f"[Auto-Healer] tests/testcase.py updated with healed code. Re-running tests...\n")
            else:
                print("[Auto-Healer] Failed to receive repaired code from LLM. Aborting retry loop.")
                break
        else:
            print(f"\n[Auto-Healer] Max healing attempts ({max_healing_attempts}) reached. Tests still failing.")
            return False


# ============================================================
# MAIN
# ============================================================

def main():
    # 0. Detect CLI arguments for testing type and target URL
    testing_type = None
    target_url = None

    for arg in sys.argv[1:]:
        if arg.lower() in ["--ui", "-ui", "ui"]:
            testing_type = "UI"
        elif arg.lower() in ["--api", "-api", "api"]:
            testing_type = "API"
        elif arg.lower().startswith("--type="):
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
            if choice in ["2", "api", "API"]:
                testing_type = "API"
            else:
                testing_type = "UI"
        except (EOFError, KeyboardInterrupt):
            testing_type = "UI"

    # Determine default target URL based on selected testing type
    default_url = API_BASE_URL if testing_type == "API" else BASE_URL

    if not target_url:
        try:
            prompt_label = "API Base URL" if testing_type == "API" else "Website URL"
            user_input_url = input(f"\nEnter {prompt_label} [Press Enter for default '{default_url}']: ").strip()
            if user_input_url:
                target_url = user_input_url
            else:
                target_url = default_url
        except (EOFError, KeyboardInterrupt):
            target_url = default_url

    print("\n" + "=" * 50)
    print(f"TESTING MODE : {testing_type}")
    print(f"TARGET URL   : {target_url}")
    print("=" * 50)

    # 1. Requirements -> Test cases (UI or API)
    test_cases = generate_test_cases(testing_type=testing_type, target_url=target_url)

    # 2. QA approval
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

    # 3. Handle Locator Data & Dynamic POM Synthesis (MCP Crawl for UI, Skipped for API)
    locator_data = None
    pom_summary = None
    if testing_type == "UI":
        print("\n" + "=" * 50)
        print("STARTING PLAYWRIGHT MCP INSPECTION & RUNTIME POM SYNTHESIS (UI)")
        print("=" * 50)
        locator_data, pom_summary = asyncio.run(
            inspect_website_with_mcp(
                test_cases,
                target_url=target_url,
                client=client
            )
        )
    else:
        print("\n" + "=" * 50)
        print("SKIPPING MCP INSPECTION (API MODE)")
        print("REST API tests interact with endpoints directly via APIRequestContext.")
        print("=" * 50)

    # 4. Test cases (+ MCP Locator Data & Runtime POMs for UI) -> Playwright Code
    generate_playwright_code(
        test_cases=test_cases,
        locator_data=locator_data,
        pom_summary=pom_summary,
        testing_type=testing_type,
        target_url=target_url
    )

    # 5. Run pytest with autonomous self-healing
    run_tests(testing_type=testing_type, pom_summary=pom_summary)


if __name__ == "__main__":
    main()