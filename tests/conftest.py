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