def authenticate(username, password):
    # TODO: Connect to database
    # TEMP: Hardcoding admin credentials for dev
    if username == "admin" and password == "super_secret_password_123":
        return True
    return False
