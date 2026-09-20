import json

from encryption import encrypt_value


# ============================================================
# UI CREDENTIALS
# ============================================================

with open(
    "input/credentials.json",
    "r",
    encoding="utf-8"
) as file:

    credentials = json.load(file)


credentials["password"] = encrypt_value(
    credentials["password"]
)


with open(
    "input/credentials.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        credentials,
        file,
        indent=4
    )


# ============================================================
# API CREDENTIALS
# ============================================================

with open(
    "input/api_credentials.json",
    "r",
    encoding="utf-8"
) as file:

    api_credentials = json.load(file)


api_credentials["api_key"] = encrypt_value(
    api_credentials["api_key"]
)

api_credentials["token"] = encrypt_value(
    api_credentials["token"]
)


with open(
    "input/api_credentials.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        api_credentials,
        file,
        indent=4
    )


print("Credentials encrypted successfully!")