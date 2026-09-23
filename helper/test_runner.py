import os
import sys
import subprocess
from constants.constants import MODEL
from helper.gemini_helper import (
    read_file,
    call_gemini_with_retry,
    sanitize_playwright_python_code,
    BASE_DIR,
    TESTS_DIR,
    REPORTS_DIR,
    INPUT_DIR,
)


def heal_test_code_with_gemini(
    failure_output,
    current_code,
    testing_type="UI",
    pom_summary=None,
    client=None
):
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
        contents=prompt,
        client=client
    )

    repaired_code = response.text.strip()
    if repaired_code.startswith("```python"):
        repaired_code = repaired_code[len("```python"):]
        if repaired_code.endswith("```"):
            repaired_code = repaired_code[:-3]
    elif repaired_code.startswith("```"):
        repaired_code = repaired_code[3:]
        if repaired_code.endswith("```"):
            repaired_code = repaired_code[:-3]

    repaired_code = sanitize_playwright_python_code(repaired_code.strip())
    return repaired_code


def run_tests(
    testing_type="UI",
    max_healing_attempts=3,
    pom_summary=None,
    client=None
):
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
            text=True,
            encoding="utf-8",
            errors="replace"
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
                pom_summary=pom_summary,
                client=client
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
