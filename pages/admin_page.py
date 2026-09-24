from playwright.sync_api import Page, Locator
from pages.base_page import BasePage

class AdminPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://automationintesting.online/admin"

        # Admin Login Elements
        self.login_heading = page.get_by_role("heading", name="Login")
        self.username_textbox = page.get_by_role("textbox", name="Username")
        self.password_textbox = page.get_by_role("textbox", name="Password")
        self.login_button = page.get_by_role("button", name="Login")

        # Admin Dashboard Elements
        self.logout_button = page.get_by_role("button", name="Logout")
        self.front_page_link = page.get_by_role("link", name="Front Page")

    def navigate(self):
        self.navigate_to(self.url)

    def login(self, username: str, password: str):
        if username:
            self.username_textbox.fill(username)
        if password:
            self.password_textbox.fill(password)
        self.login_button.click()

    def logout(self):
        self.logout_button.click()
