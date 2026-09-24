import re
import json
from playwright.sync_api import Page, expect
from pages import HomePage, AdminPage
from utils.encryption import decrypt_value

# TC-UI-001
def test_homepage_load_and_title(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    expect(page).to_have_url("https://automationintesting.online/")
    expect(page).to_have_title("Restful-booker-platform demo")

# TC-UI-002
def test_homepage_main_heading_and_navigation_visibility(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    expect(home_page.main_heading).to_be_visible()
    expect(home_page.nav_rooms).to_be_visible()
    expect(home_page.nav_booking).to_be_visible()
    expect(home_page.nav_amenities).to_be_visible()
    expect(home_page.nav_location).to_be_visible()
    expect(home_page.nav_contact).to_be_visible()
    expect(home_page.nav_admin).to_be_visible()

# TC-UI-003
def test_hotel_contact_information_in_footer(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.scroll_to_bottom()
    expect(home_page.footer_address).to_be_visible()

# TC-UI-004
def test_room_listings_display_and_booking_buttons(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    page.locator(".row.hotel-room-info").first.scroll_into_view_if_needed()
    room_cards = page.locator(".row.hotel-room-info")
    expect(room_cards.first).to_be_visible()
    expect(home_page.room_book_now_single).to_be_visible()
    expect(page.get_by_role("button", name="Check Availability").first).to_be_visible()

# TC-UI-005
def test_open_room_booking_interface(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.room_book_now_single.scroll_into_view_if_needed()
    home_page.room_book_now_single.click()
    expect(page.get_by_role("button", name="Book This Room")).to_be_visible()

# TC-UI-006
def test_contact_form_successful_submission(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.fill_contact_form(
        name="John Doe",
        email="john.doe@example.com",
        phone="01234567890",
        subject="Inquiry about booking",
        message="Hello, I would like to know more details about your rooms and availability."
    )
    home_page.submit_contact_form()
    expect(page.get_by_text("Thanks for getting in touch")).to_be_visible()

# TC-UI-007
def test_contact_form_empty_fields_validation(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.contact_submit_button.scroll_into_view_if_needed()
    home_page.submit_contact_form()
    expect(page.locator(".alert-danger, .alert")).to_be_visible()

# TC-UI-008
def test_contact_form_invalid_email_format_validation(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.fill_contact_form(
        name="John Doe",
        email="invalid-email-format",
        phone="01234567890",
        subject="Test Subject",
        message="Test message description here."
    )
    home_page.submit_contact_form()
    expect(page.locator(".alert-danger, .alert")).to_be_visible()

# TC-UI-009
def test_contact_form_insufficient_phone_number_characters_validation(page: Page):
    home_page = HomePage(page)
    home_page.navigate()
    home_page.fill_contact_form(
        name="John Doe",
        email="john.doe@example.com",
        phone="123",
        subject="Test Subject",
        message="Test message description here."
    )
    home_page.submit_contact_form()
    expect(page.locator(".alert-danger, .alert")).to_be_visible()

# TC-UI-010
def test_admin_login_page_elements_visibility(page: Page):
    admin_page = AdminPage(page)
    admin_page.navigate()
    expect(admin_page.username_textbox).to_be_visible()
    expect(admin_page.password_textbox).to_be_visible()
    expect(admin_page.login_button).to_be_visible()

# TC-UI-011
def test_admin_successful_login_and_dashboard_access(page: Page):
    with open("input/credentials.json") as f:
        creds = json.load(f)
    username = creds["username"]
    password = decrypt_value(creds["password"])

    admin_page = AdminPage(page)
    admin_page.navigate()
    admin_page.login(username, password)
    expect(page).to_have_url(re.compile(r".*/admin/rooms/?$"))
    expect(admin_page.logout_button).to_be_visible()

# TC-UI-012
def test_admin_login_failure_with_invalid_credentials(page: Page):
    admin_page = AdminPage(page)
    admin_page.navigate()
    admin_page.login("wronguser", "wrongpassword")
    expect(page).to_have_url(re.compile(r".*/admin/?$"))
    expect(admin_page.login_button).to_be_visible()

# TC-UI-013
def test_admin_login_failure_with_empty_fields(page: Page):
    admin_page = AdminPage(page)
    admin_page.navigate()
    admin_page.login_button.click()
    expect(page).to_have_url(re.compile(r".*/admin/?$"))
    expect(admin_page.login_button).to_be_visible()

# TC-UI-014
def test_admin_logout_functionality(page: Page):
    with open("input/credentials.json") as f:
        creds = json.load(f)
    username = creds["username"]
    password = decrypt_value(creds["password"])

    admin_page = AdminPage(page)
    admin_page.navigate()
    admin_page.login(username, password)
    expect(admin_page.logout_button).to_be_visible()
    admin_page.logout()
    expect(page).to_have_url(re.compile(r".*/admin/?$"))
    expect(admin_page.login_button).to_be_visible()