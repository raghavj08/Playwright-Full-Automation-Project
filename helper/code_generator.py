import os
import json
from constants.constants import MODEL, BASE_URL, API_BASE_URL, TESTS_DIR
from helper.gemini_helper import (
    read_file,
    call_gemini_with_retry,
    sanitize_playwright_python_code,
)


def generate_playwright_code(
    test_cases,
    locator_data=None,
    pom_summary=None,
    testing_type="UI",
    target_url=None,
    client=None
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
        contents=prompt,
        client=client
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
