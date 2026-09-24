from playwright.sync_api import Page, Locator
from pages.base_page import BasePage

class HomePage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://automationintesting.online/"
        
        # Navigation Links (Scoped to avoid strict mode collisions with footer)
        self.nav_rooms = page.locator("nav").get_by_role("link", name="Rooms")
        self.nav_booking = page.locator("nav").get_by_role("link", name="Booking")
        self.nav_amenities = page.locator("nav").get_by_role("link", name="Amenities")
        self.nav_location = page.locator("nav").get_by_role("link", name="Location")
        self.nav_contact = page.locator("nav").get_by_role("link", name="Contact")
        self.nav_admin = page.locator("nav").get_by_role("link", name="Admin")

        # Headings
        self.main_heading = page.get_by_role("heading", name="Welcome to Shady Meadows B&B")
        self.rooms_heading = page.get_by_role("heading", name="Our Rooms")
        self.location_heading = page.get_by_role("heading", name="Our Location")
        self.contact_heading = page.get_by_role("heading", name="Send Us a Message")

        # Booking Check Availability Form
        self.checkin_textbox = page.locator("input.form-control[type='text']").first
        self.checkout_textbox = page.locator("input.form-control[type='text']").nth(1)
        self.check_availability_button = page.get_by_role("button", name="Check Availability")

        # Room Cards Book Now Links
        self.room_book_now_single = page.locator("div.hotel-room-info").filter(has_text="Single").get_by_role("link", name="Book now")
        self.room_book_now_double = page.locator("div.hotel-room-info").filter(has_text="Double").get_by_role("link", name="Book now")
        self.room_book_now_suite = page.locator("div.hotel-room-info").filter(has_text="Suite").get_by_role("link", name="Book now")

        # Contact Form Inputs & Button
        self.contact_name = page.get_by_role("textbox", name="Name")
        self.contact_email = page.get_by_role("textbox", name="Email")
        self.contact_phone = page.get_by_role("textbox", name="Phone")
        self.contact_subject = page.get_by_role("textbox", name="Subject")
        self.contact_message = page.locator("#description")
        self.contact_submit_button = page.get_by_role("button", name="Submit")

        # Footer Details
        self.footer_address = page.get_by_text("Shady Meadows B&B, Shadows valley")
        self.footer_phone = page.get_by_text("012345678901")
        self.footer_email = page.get_by_text("fake@fakeemail.com")

    def navigate(self):
        self.navigate_to(self.url)

    def click_admin_nav(self):
        self.nav_admin.click()

    def fill_contact_form(self, name: str, email: str, phone: str, subject: str, message: str):
        if name:
            self.contact_name.fill(name)
        if email:
            self.contact_email.fill(email)
        if phone:
            self.contact_phone.fill(phone)
        if subject:
            self.contact_subject.fill(subject)
        if message:
            self.contact_message.fill(message)

    def submit_contact_form(self):
        self.contact_submit_button.click()
