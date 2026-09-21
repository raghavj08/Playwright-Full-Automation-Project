# Simple AI Playwright Automation

This project is a simple **AI-powered Playwright automation framework** that follows a human-in-the-loop QA workflow.

The project uses **Google Gemini** to generate test plans, generate Playwright automation code, and analyze test failures.

The QA engineer remains in control of the test generation and approval process.

---

## Flow

The project follows this workflow:

1. Read QA requirements from `input/requirements.txt`.
2. Call Gemini to generate a detailed test plan.
3. Save the generated test plan.
4. QA engineer reviews and approves the test plan.
5. If approved, call Gemini again to generate Playwright automation code.
6. Save the generated Playwright code.
7. Automatically execute the generated tests using Pytest.
8. Generate Allure test results and an HTML report.
9. If all tests pass, the process completes successfully.
10. If any test fails, capture the failure information.
11. Send the failure information to Gemini for detailed error analysis.
12. Save the error analysis report.

### Overall Flow

```text
QA Requirements
       ↓
Gemini generates Test Plan
       ↓
QA Engineer Reviews
       ↓
   ┌───┴───┐
   ↓       ↓
Reject   Approve
   ↓       ↓
Stop    Gemini generates
        Playwright Code
             ↓
        Run Pytest Tests
             ↓
        ┌────┴────┐
        ↓         ↓
      PASS       FAIL
        ↓         ↓
 Allure Report  Save Failure
                  Details
                     ↓
                  Gemini
                     ↓
              Error Analysis
                     ↓
          error_analysis.md
```

---

## Project Structure

```text
AI_Playwright_Simple/
│
├── main.py
├── .env
├── .gitignore
├── requirements.txt
├── README.md
│
├── constants/
│   └── constants.py
│
├── helper/
│   ├── __init__.py
│   └── mcp_code.py
│
├── input/
│   ├── requirements.txt
│   ├── credentials.json
│   ├── api_credentials.json
│   └── locator_data.json
│
├── prompts/
│   ├── ui_test_case_generation_prompt.txt
│   ├── api_test_case_generation_prompt.txt
│   ├── ui_code_generation_prompt.txt
│   └── api_code_generation_prompt.txt
│
├── tests/
│   ├── conftest.py
│   ├── testcase.json
│   └── testcase.py
│
├── reports/
│   ├── pytest_failure.txt
│   └── test_report.html
│
└── utils/
    ├── __init__.py
    ├── encryption.py
    ├── encrypt_credentials.py
    └── generate_key.py
```

### Important Files

| File / Folder | Purpose |
| --- | --- |
| `main.py` | Orchestrates test case & Playwright code generation, and pytest execution |
| `helper/mcp_code.py` | Multi-page Playwright MCP website crawler and locator extractor |
| `input/requirements.txt` | Software requirements for UI and REST API |
| `input/credentials.json` | Encrypted UI login credentials |
| `input/api_credentials.json` | Encrypted REST API credentials (key & token) |
| `input/locator_data.json` | Structured multi-page locator dictionary extracted by MCP crawler |
| `prompts/ui_test_case_generation_prompt.txt` | Prompt for generating UI test cases |
| `prompts/api_test_case_generation_prompt.txt` | Prompt for generating REST API test cases |
| `prompts/ui_code_generation_prompt.txt` | Prompt for generating Playwright browser UI automation |
| `prompts/api_code_generation_prompt.txt` | Prompt for generating Playwright API automation |
| `tests/testcase.json` | Generated test cases based on selected testing mode |
| `tests/testcase.py` | Generated executable Playwright test script |
| `tests/conftest.py` | Pytest fixtures and failure screenshot hooks |
| `reports/test_report.html` | Generated self-contained HTML test execution report |

---

# Setup

## 1. Create a Virtual Environment

Open PowerShell in the project directory:

```powershell
python -m venv venv
```

---

## 2. Activate the Virtual Environment

On Windows:

```powershell
venv\Scripts\activate
```

You should see something similar to:

```text
(venv) PS C:\...\AI_Playwright_Simple>
```

---

## 3. Install Required Packages

Install all Python dependencies:

```powershell
pip install -r requirements.txt
```

The project uses:

```text
google-genai
python-dotenv
pytest
playwright
pytest-playwright
allure-pytest
```

---

## 4. Install Playwright Browsers

Run:

```powershell
playwright install
```

This installs the browsers required by Playwright.

---

# Gemini API Setup

## 1. Create a `.env` File

Create a file named:

```text
.env
```

Add your Gemini API key:

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

Do not commit this file to Git.

The `.gitignore` file should contain:

```text
.env
```

---

# Test Credentials

The project uses separate credential files for UI and API testing.

## UI Credentials

Create:

```text
input/credentials.json
```

Example:

```json
{
    "username": "your_email@example.com",
    "password": "your_password"
}
```

---

## API Credentials

Create:

```text
input/api_credentials.json
```

Example:

```json
{
    "api_key": "your_trello_api_key",
    "token": "your_trello_api_token"
}
```

These files contain sensitive information and must not be committed to Git.

Add them to `.gitignore`:

```text
input/credentials.json
input/api_credentials.json
```

---

# QA Requirements

The QA requirements are stored in:

```text
input/requirements.txt
```

For example:

```text
Verify that the Trello page opens successfully.

Verify valid login.

Verify invalid login.

Create a new board and verify it.

Create a new card and verify it.

Delete the newly created card and verify it.

Add text to the card and verify it.

Delete the text from the card and verify it.

Validate the corresponding API operations.
```

The requirements are sent to Gemini to generate the test plan.

---

# Test Plan Generation

When the program starts:

```powershell
python main.py
```

Gemini reads:

```text
input/requirements.txt
```

and:

```text
prompts/test_generation_prompt.txt
```

It generates a test plan and saves it as:

```text
tests/test_plan.md
```

The test plan is also displayed in the terminal.

---

# QA Approval

After generating the test plan, the program asks:

```text
Do you approve this test plan? (yes/no):
```

### If QA approves

Enter:

```text
yes
```

The program continues to Playwright code generation.

### If QA rejects

Enter:

```text
no
```

The program stops.

The generated test plan can then be reviewed or manually modified before running the program again.

This keeps the QA engineer in control of the generated automation.

---

# Playwright Code Generation

After QA approval, Gemini reads:

```text
prompts/code_generation_prompt.txt
```

along with the generated:

```text
tests/test_plan.md
```

Gemini generates the Playwright automation code.

The generated code is saved automatically as:

```text
tests/testcases.py
```

The generated tests use:

* Python
* Pytest
* Playwright
* Playwright API request context
* UI automation
* API validation
* JSON credentials
* Allure reporting

---

# API Testing

API operations are performed using Playwright's API request functionality.

The project uses:

```python
playwright.request.new_context()
```

instead of the Python `requests` library.

The general flow is:

```text
API Operation
      ↓
Verify API Response
      ↓
Extract ID
      ↓
Perform UI Verification
```

For example:

```text
Create Board using API
        ↓
Verify API Response
        ↓
Get Board ID
        ↓
Open Trello UI
        ↓
Verify Board Exists
```

The same approach can be used for cards and other operations.

---

# Running Tests

The tests are automatically executed by `main.py`.

You do not need to manually run Pytest.

The program internally executes:

```powershell
python -m pytest tests/testcases.py --alluredir allure-results
```

The Pytest result is checked automatically.

---

# Allure Reporting

Allure results are stored in:

```text
allure-results/
```

After test execution, the project generates the HTML report in:

```text
allure-report/
```

The report can be opened using:

```powershell
allure open allure-report
```

You can also use:

```powershell
allure serve allure-results
```

to generate and open the report directly.

---

# Failure Detection

If a test fails, `main.py` detects the failure using the Pytest return code.

```text
Pytest
  ↓
Test Failed
  ↓
Failure Detected
```

The Pytest output is saved to:

```text
reports/pytest_failure.txt
```

This file contains the test output and error information that can be passed to Gemini for analysis.

---

# AI Error Analysis

When a test fails, the failure information is sent to Gemini using:

```text
prompts/error_analysis_prompt.txt
```

Gemini analyzes the failure and generates a detailed explanation.

The final analysis is saved as:

```text
reports/error_analysis.md
```

The analysis can include:

* Failed test
* Error message
* Possible cause
* Failed locator or operation
* Relevant test step
* Suggested investigation
* Suggested corrective action

The AI does **not automatically modify the generated test code**.

The QA engineer remains responsible for deciding what changes should be made.

---

# Screenshots

Screenshots can be stored in:

```text
screenshots/
```

The Playwright configuration can capture screenshots when tests fail.

These screenshots can help the QA engineer understand UI failures.

---

# Complete Execution

Run the project using:

```powershell
python main.py
```

The complete workflow is:

```text
input/requirements.txt
        ↓
       Gemini
        ↓
tests/test_plan.md
        ↓
   QA Approval
        ↓
       Gemini
        ↓
tests/testcases.py
        ↓
      Pytest
        ↓
   ┌────┴────┐
   ↓         ↓
 PASS       FAIL
   ↓         ↓
Allure    Failure Details
Report         ↓
           Gemini Analysis
                ↓
       error_analysis.md
```

---

# Important

This project intentionally uses a **human-in-the-loop** approach.

The AI generates the test plan and automation code, but the QA engineer remains responsible for reviewing and approving the generated test plan.

If the QA engineer rejects the test plan, the program stops.

The AI does not automatically modify the test plan after rejection.

The AI also does not automatically modify or fix failed Playwright code.

Instead, when a test fails, the AI generates an error analysis report:

```text
reports/error_analysis.md
```

The QA engineer can then review the analysis and decide what changes should be made.

This keeps the QA engineer in control of the automation process.
