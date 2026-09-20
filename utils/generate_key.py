from cryptography.fernet import Fernet

key = Fernet.generate_key()

print("Your encryption key is:")
print(key.decode())