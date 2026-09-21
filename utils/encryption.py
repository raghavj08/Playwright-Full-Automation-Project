from cryptography.fernet import Fernet
import os

from dotenv import load_dotenv


load_dotenv()


def get_cipher():

    key = os.getenv("ENCRYPTION_KEY")

    if not key:
        raise Exception("ENCRYPTION_KEY not found in .env")

    return Fernet(key.encode())


def encrypt_value(value):

    cipher = get_cipher()

    encrypted_value = cipher.encrypt(
        value.encode()
    )

    return encrypted_value.decode()


def decrypt_value(encrypted_value):

    if not encrypted_value or not isinstance(encrypted_value, str):
        return encrypted_value

    try:
        cipher = get_cipher()
        decrypted_value = cipher.decrypt(
            encrypted_value.encode()
        )
        return decrypted_value.decode()
    except Exception:
        # If the value is already plaintext (e.g., email or unencrypted username), return as is
        return encrypted_value