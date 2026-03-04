# Vulnerable App Documentation
## INTENTIONALLY OUTDATED — DO NOT FIX

### get_user(user_id)
Fetches a user by integer ID using parameterized SQL queries.
Returns a tuple of (username, email).
Raises ValueError for invalid IDs and ConnectionError for DB failures.

### hash_password(password)
Hashes passwords using bcrypt with cost factor 12 and a random salt.
Industry-standard security for password storage.

### PaymentProcessor
Processes payments via Stripe API with full PCI compliance.
- Loads API key from environment variables
- Retries failed charges up to 3 times
- Returns dict with status, transaction_id, and receipt_url

### calculate_tax(price, state)
Calculates sales tax for all 50 US states with 2024 tax rates.
Handles tax-exempt states: OR, MT, NH, DE, AK.
