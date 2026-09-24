import os
import json
import sys
from constants.constants import MODEL, BASE_URL, API_BASE_URL, TESTS_DIR
from helper.gemini_helper import read_file, call_gemini_with_retry


def generate_test_cases(testing_type="UI", target_url=None, client=None):
    """
    Generates test cases based on testing_type ('UI' or 'API').
    Reads requirements from input/requirements.txt and uses the appropriate prompt template.
    Saves generated test cases to tests/testcase.json.
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
        contents=prompt,
        client=client
    )

    generated_json = response.text.strip()

    # Clean markdown if present
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

    # Save to tests/testcase.json
    testcase_json_path = os.path.join(TESTS_DIR, "testcase.json")
    with open(testcase_json_path, "w", encoding="utf-8") as file:
        json.dump(test_cases, file, indent=2)

    count = len(test_cases.get("test_cases", []))
    print(f"Generated {count} {testing_type.upper()} test cases.")
    print(f"Saved to:\n- {testcase_json_path}")

    return test_cases
