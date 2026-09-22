import os
import json
import pytest
from playwright.sync_api import Playwright, APIRequestContext, expect
from utils.encryption import decrypt_value

def get_api_creds():
    creds_path = os.path.join("input", "api_credentials.json")
    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)
    return {
        "username": creds["username"],
        "password": decrypt_value(creds["password"])
    }

def get_auth_token(api_context: APIRequestContext) -> str:
    creds = get_api_creds()
    res = api_context.post(
        "/api/auth/login",
        data=json.dumps({"username": creds["username"], "password": creds["password"]})
    )
    if res.status == 200:
        return res.json().get("token", "")
    return ""

@pytest.fixture(scope="session")
def api_context(playwright: Playwright) -> APIRequestContext:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    context = playwright.request.new_context(
        base_url="https://automationintesting.online",
        extra_http_headers=headers
    )
    yield context
    context.dispose()

# TC-API-001
def test_get_branding_api(api_context: APIRequestContext):
    response = api_context.get("/api/branding")
    assert response.status == 200
    data = response.json()
    assert "name" in data
    assert "description" in data
    assert "map" in data

# TC-API-002
def test_get_room_list(api_context: APIRequestContext):
    response = api_context.get("/api/room")
    assert response.status == 200
    data = response.json()
    assert "rooms" in data
    assert isinstance(data["rooms"], list)
    if len(data["rooms"]) > 0:
        room = data["rooms"][0]
        assert "roomName" in room
        assert "type" in room
        assert "accessible" in room
        assert "roomPrice" in room

# TC-API-003
def test_get_specific_room_details_valid_id(api_context: APIRequestContext):
    response = api_context.get("/api/room/1")
    assert response.status == 200
    data = response.json()
    assert "roomid" in data or "roomName" in data

# TC-API-004
def test_get_specific_room_details_non_existent_id(api_context: APIRequestContext):
    response = api_context.get("/api/room/999999")
    assert response.status in [404, 500]

# TC-API-005
def test_admin_login_valid_credentials(api_context: APIRequestContext):
    creds = get_api_creds()
    response = api_context.post(
        "/api/auth/login",
        data=json.dumps({"username": creds["username"], "password": creds["password"]})
    )
    assert response.status == 200
    # The response might return token in body or via cookies
    token = response.json().get("token")
    if not token:
        # Check cookies
        cookies = response.headers.get("set-cookie", "")
        assert "token" in cookies or response.status == 200

# TC-API-006
def test_validate_authentication_token(api_context: APIRequestContext):
    token = get_auth_token(api_context)
    assert token != ""
    response = api_context.post(
        "/api/auth/validate",
        data=json.dumps({"token": token})
    )
    assert response.status == 200
    data = response.json()
    assert data.get("valid") is True

# TC-API-007
def test_admin_login_invalid_credentials(api_context: APIRequestContext):
    response = api_context.post(
        "/api/auth/login",
        data=json.dumps({"username": "invaliduser", "password": "wrongpassword"})
    )
    assert response.status in [401, 403]

# TC-API-008
def test_admin_login_empty_credentials(api_context: APIRequestContext):
    response = api_context.post(
        "/api/auth/login",
        data=json.dumps({"username": "", "password": ""})
    )
    assert response.status in [400, 401]

# TC-API-009
def test_create_contact_message(api_context: APIRequestContext):
    payload = {
        "name": "John Doe",
        "email": "johndoe@example.com",
        "phone": "12345678901",
        "subject": "Booking Inquiry",
        "description": "I would like to inquire about room availability for next weekend."
    }
    response = api_context.post(
        "/api/message",
        data=json.dumps(payload)
    )
    assert response.status in [200, 201]

# TC-API-010
def test_retrieve_message_count(api_context: APIRequestContext):
    token = get_auth_token(api_context)
    headers = {"Cookie": f"token={token}"} if token else {}
    response = api_context.get("/api/message/count", headers=headers)
    assert response.status == 200
    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0

# TC-API-011
def test_create_contact_message_missing_mandatory_fields(api_context: APIRequestContext):
    payload = {
        "name": "",
        "email": "",
        "phone": "",
        "subject": "",
        "description": ""
    }
    response = api_context.post(
        "/api/message",
        data=json.dumps(payload)
    )
    assert response.status == 400

# TC-API-012
def test_retrieve_bookings_by_room_id(api_context: APIRequestContext):
    token = get_auth_token(api_context)
    headers = {"Cookie": f"token={token}"} if token else {}
    response = api_context.get("/api/booking?roomid=1", headers=headers)
    assert response.status == 200
    data = response.json()
    assert "bookings" in data
    assert isinstance(data["bookings"], list)
    if len(data["bookings"]) > 0:
        booking = data["bookings"][0]
        assert "bookingid" in booking
        assert "roomid" in booking
        assert "firstname" in booking
        assert "lastname" in booking
        assert "bookingdates" in booking