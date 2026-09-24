import os

# Project Base Directory (Root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Project Directory Paths
TESTS_DIR = os.path.join(BASE_DIR, "tests")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INPUT_DIR = os.path.join(BASE_DIR, "input")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
PAGES_DIR = os.path.join(BASE_DIR, "pages")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

# Automatically ensure standard directories exist
os.makedirs(TESTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(PAGES_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# AI & Model Configuration
MODEL = "gemini-flash-lite-latest"

# Target Application URLs
BASE_URL = "https://automationintesting.online"
API_BASE_URL = "https://automationintesting.online/api"

# Web Crawler / MCP Settings
MAX_PAGES_TO_CRAWL = 8
