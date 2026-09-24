import os
import datetime
import xml.etree.ElementTree as ET
from constants.constants import REPORTS_DIR


def generate_markdown_report(testing_type="UI", target_url=None):
    """
    Reads reports/junit_report.xml and generates a simple, clean reports/report.md.
    """
    xml_path = os.path.join(REPORTS_DIR, "junit_report.xml")
    report_md_path = os.path.join(REPORTS_DIR, "report.md")

    if not os.path.exists(xml_path):
        print(f"[Report] {xml_path} not found.")
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
    except Exception as e:
        print(f"[Report] Error parsing junit_report.xml: {e}")
        return None

    if suite is None:
        return None

    # Get test counts and duration
    total = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    duration = suite.attrib.get("time", "0.0")
    passed = max(0, total - (failures + errors + skipped))

    status = "PASSED" if (failures == 0 and errors == 0 and total > 0) else "FAILED"
    status_icon = "Passed" if status == "PASSED" else "Failed"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build report lines
    lines = []
    lines.append("# Test Execution Report\n")
    lines.append(f"- **Overall Status**: {status_icon} ({status})")
    lines.append(f"- **Testing Type**: {testing_type}")
    if target_url:
        lines.append(f"- **Target URL**: {target_url}")
    lines.append(f"- **Execution Time**: {now}")
    lines.append(f"- **Total Duration**: {duration}s\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Metric | Count |")
    lines.append("| :--- | :--- |")
    lines.append(f"| Total Tests | {total} |")
    lines.append(f"| Passed | {passed} |")
    lines.append(f"| Failed | {failures + errors} |")
    lines.append(f"| Skipped | {skipped} |\n")

    # Test cases table
    lines.append("## Test Results\n")
    lines.append("| Test Name | Status | Duration |")
    lines.append("| :--- | :---: | :---: |")

    failure_details = []
    for tc in suite.findall("testcase"):
        name = tc.attrib.get("name", "unknown")
        time_taken = tc.attrib.get("time", "0.0")

        failure = tc.find("failure")
        error = tc.find("error")
        skipped_elem = tc.find("skipped")

        if failure is not None or error is not None:
            tc_status = "FAILED"
            elem = failure if failure is not None else error
            msg = elem.attrib.get("message", "Test assertion failed")
            traceback = (elem.text or "").strip()
            failure_details.append((name, msg, traceback))
        elif skipped_elem is not None:
            tc_status = "SKIPPED"
        else:
            tc_status = "PASSED"

        lines.append(f"| `{name}` | {tc_status} | {time_taken}s |")

    # Failures section if any failed
    if failure_details:
        lines.append("\n## Failure Details\n")
        for name, msg, traceback in failure_details:
            lines.append(f"### `{name}`")
            if msg:
                lines.append(f"**Error**: {msg}\n")
            if traceback:
                lines.append(f"```text\n{traceback}\n```\n")

    # Save to reports/report.md
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_md_path
