import sys
from pathlib import Path

import pytest


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Screenshot directory
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def get_api_creds():
    """Retrieve API credentials from input/api_credentials.json and decrypt password."""
    import json
    from utils.encryption import decrypt_value

    creds_path = PROJECT_ROOT / "input" / "api_credentials.json"
    if not creds_path.exists():
        return {"username": "admin", "password": "password"}
    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)
    return {
        "username": creds.get("username", "admin"),
        "password": decrypt_value(creds.get("password", "password")),
    }


@pytest.fixture(scope="session")
def api_context(playwright):
    """Playwright APIRequestContext configured for the base URL."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    context = playwright.request.new_context(
        base_url="https://automationintesting.online",
        extra_http_headers=headers,
    )
    yield context
    context.dispose()


@pytest.fixture(scope="session")
def auth_token(api_context) -> str:
    """Authenticates with the API and returns an admin session token."""
    creds = get_api_creds()
    res = api_context.post(
        "/api/auth/login",
        data={"username": creds["username"], "password": creds["password"]},
    )
    if res.status == 200:
        return res.json().get("token", "")
    return ""


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict:
    """Returns headers containing the authentication cookie token."""
    return {"Cookie": f"token={auth_token}"}



@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):

    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:

        page = item.funcargs.get("page")

        if page:

            file_name = (
                item.name
                .replace("/", "_")
                .replace("\\", "_")
            )

            screenshot = SCREENSHOTS_DIR / f"{file_name}.png"

            try:

                page.screenshot(
                    path=str(screenshot),
                    full_page=True
                )

                print(
                    f"\nScreenshot saved: {screenshot}"
                )

            except Exception as error:

                print(
                    f"\nCould not save screenshot: {error}"
                )