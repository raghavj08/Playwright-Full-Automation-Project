from pathlib import Path

import pytest


SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Take a screenshot when a Playwright test fails."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")

        if page:
            file_name = item.name.replace("/", "_").replace("\\", "_")
            screenshot = SCREENSHOTS_DIR / f"{file_name}.png"

            try:
                page.screenshot(path=str(screenshot), full_page=True)
                print(f"\nScreenshot saved: {screenshot}")
            except Exception as error:
                print(f"\nCould not save screenshot: {error}")
