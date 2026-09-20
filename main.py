import os
import subprocess
import sys

from dotenv import load_dotenv
from google import genai

from constants.constants import MODEL, BASE_URL


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# GET GEMINI API KEY
# ============================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Gemini API key not found!")
    exit()


# ============================================================
# CREATE GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=api_key
)

# ============================================================
# READ QA REQUIREMENTS
# ============================================================

with open(
    "input/requirements.txt",
    "r",
    encoding="utf-8"
) as file:

    requirements = file.read()


# ============================================================
# READ TEST GENERATION PROMPT
# ============================================================

with open(
    "prompts/test_generation_prompt.txt",
    "r",
    encoding="utf-8"
) as file:

    prompt = file.read()


# ============================================================
# INSERT WEBSITE AND REQUIREMENTS INTO PROMPT
# ============================================================

prompt = prompt.replace(
    "{website_url}",
    BASE_URL
)

prompt = prompt.replace(
    "{requirements}",
    requirements
)


# ============================================================
# GENERATE TEST PLAN
# ============================================================

print("\n")
print("=" * 60)
print("GENERATING TEST PLAN")
print("=" * 60)

response = client.models.generate_content(
    model=MODEL,
    contents=prompt
)


# ============================================================
# GET TEST PLAN
# ============================================================

test_plan = response.text


# ============================================================
# DISPLAY TEST PLAN
# ============================================================

print("\n")
print("=" * 60)
print("GENERATED TEST PLAN")
print("=" * 60)

print(test_plan)


# ============================================================
# SAVE TEST PLAN
# ============================================================

with open(
    "tests/test_plan.md",
    "w",
    encoding="utf-8"
) as file:

    file.write(test_plan)


print("\nTest plan saved to:")
print("tests/test_plan.md")


# ============================================================
# QA APPROVAL
# ============================================================

print("\n")
print("=" * 60)
print("QA APPROVAL REQUIRED")
print("=" * 60)

approval = input(
    "\nDo you approve this test plan? (yes/no): "
)


# ============================================================
# STOP IF QA DOES NOT APPROVE
# ============================================================

if approval.lower() != "yes":

    print("\nTest plan was not approved.")
    print("No test cases were generated.")

    exit()


# ============================================================
# QA APPROVED
# ============================================================

print("\n")
print("=" * 60)
print("TEST PLAN APPROVED")
print("=" * 60)

print("\nGenerating Playwright test cases...\n")


# ============================================================
# READ CODE GENERATION PROMPT
# ============================================================

with open(
    "prompts/code_generation_prompt.txt",
    "r",
    encoding="utf-8"
) as file:

    code_prompt = file.read()


# ============================================================
# INSERT WEBSITE AND TEST PLAN
# ============================================================

code_prompt = code_prompt.replace(
    "{website_url}",
    BASE_URL
)

code_prompt = code_prompt.replace(
    "{test_plan}",
    test_plan
)


# ============================================================
# GENERATE TEST CASES
# ============================================================

response = client.models.generate_content(
    model=MODEL,
    contents=code_prompt
)


# ============================================================
# GET GENERATED CODE
# ============================================================

test_code = response.text


# ============================================================
# REMOVE MARKDOWN CODE FENCES
# ============================================================

if test_code.startswith("```python"):

    test_code = test_code.replace(
        "```python",
        "",
        1
    )


if test_code.endswith("```"):

    test_code = test_code[:-3]


# ============================================================
# SAVE GENERATED TEST CASES
# ============================================================

with open(
    "tests/testcases.py",
    "w",
    encoding="utf-8"
) as file:

    file.write(test_code.strip())


print("\nPlaywright test cases generated successfully!")

print("\nSaved to:")
print("tests/testcases.py")


# ============================================================
# RUN PYTEST WITH ALLURE
# ============================================================

print("\n")
print("=" * 60)
print("RUNNING TESTS")
print("=" * 60)

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/testcases.py",
        "--alluredir",
        "allure-results"
    ],
    capture_output=True,
    text=True
)


# ============================================================
# DISPLAY PYTEST OUTPUT
# ============================================================

print("\n")
print("=" * 60)
print("PYTEST OUTPUT")
print("=" * 60)

print(result.stdout)

if result.stderr:
    print("\nPYTEST ERRORS:")
    print(result.stderr)


# ============================================================
# GENERATE ALLURE HTML REPORT
# ============================================================

print("\n")
print("=" * 60)
print("GENERATING ALLURE REPORT")
print("=" * 60)

allure_result = subprocess.run(
    [
        "allure",
        "generate",
        "allure-results",
        "-o",
        "allure-report",
        "--clean"
    ],
    capture_output=True,
    text=True
)


if allure_result.returncode == 0:

    print("\nAllure report generated successfully!")
    print("Report location: allure-report/")

else:

    print("\nFailed to generate Allure report.")
    print(allure_result.stderr)


# ============================================================
# FAILURE DETECTION
# ============================================================

if result.returncode == 0:

    print("\n")
    print("=" * 60)
    print("TEST RESULT: PASSED")
    print("=" * 60)

    print("\nAll tests passed successfully!")

else:

    print("\n")
    print("=" * 60)
    print("TEST RESULT: FAILED")
    print("=" * 60)

    print("\nSome tests failed.")

    # Create reports folder if it doesn't exist
    os.makedirs("reports", exist_ok=True)

    # Save pytest failure information
    with open(
        "reports/pytest_failure.txt",
        "w",
        encoding="utf-8"
    ) as file:

        file.write("PYTEST OUTPUT\n")
        file.write("=" * 60)
        file.write("\n")
        file.write(result.stdout)

        file.write("\n\nPYTEST ERRORS\n")
        file.write("=" * 60)
        file.write("\n")
        file.write(result.stderr)

    print("\nFailure details saved to:")
    print("reports/pytest_failure.txt")


# ============================================================
# FINAL MESSAGE
# ============================================================

print("\n")
print("=" * 60)
print("PROCESS COMPLETED")
print("=" * 60)

print("\nGenerated files:")

print("1. tests/test_plan.md")
print("2. tests/testcases.py")
print("3. allure-results/")
print("4. allure-report/")

if result.returncode != 0:
    print("5. reports/pytest_failure.txt")