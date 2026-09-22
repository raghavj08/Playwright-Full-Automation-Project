import os
import sys
import time
import re
from dotenv import load_dotenv
from google import genai

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(BASE_DIR, "tests")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INPUT_DIR = os.path.join(BASE_DIR, "input")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

os.makedirs(TESTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)

_client = None


def get_gemini_client():
    """Initializes and caches the Google Gemini Client."""
    global _client
    if _client is None:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("ERROR: GEMINI_API_KEY not found in .env")
            sys.exit(1)
        _client = genai.Client(api_key=gemini_api_key)
    return _client


def read_file(file_path):
    """Reads a file relative to BASE_DIR if not an absolute path."""
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def sanitize_playwright_python_code(code_str):
    """Sanitizes generated Playwright Python code by replacing JavaScript/TypeScript API names with Python equivalents."""
    if not isinstance(code_str, str):
        return code_str
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


def call_gemini_with_retry(model, contents, client=None, max_retries=5, initial_delay=3):
    """Calls Gemini API with exponential backoff retry and fallback for transient 503/429/quota errors."""
    active_client = client or get_gemini_client()
    delay = initial_delay
    fallback_pool = [
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-flash-latest"
    ]
    model_queue = [model] + [m for m in fallback_pool if m != model]
    model_idx = 0

    for attempt in range(1, max_retries + 1):
        current_model = model_queue[model_idx % len(model_queue)]
        try:
            return active_client.models.generate_content(
                model=current_model,
                contents=contents
            )
        except Exception as e:
            err_msg = str(e)
            if any(code in err_msg for code in ["503", "429", "UNAVAILABLE", "404", "RESOURCE_EXHAUSTED"]):
                model_idx += 1
                next_model = model_queue[model_idx % len(model_queue)]
                print(f"[Gemini] Issue with '{current_model}' ({err_msg[:60]}...). Switching to '{next_model}'...")
                if attempt < max_retries:
                    print(f"[Gemini] Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    delay = min(delay * 2, 8)
                    continue
            raise e
