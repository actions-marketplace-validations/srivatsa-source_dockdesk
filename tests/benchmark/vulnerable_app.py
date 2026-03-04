"""
Golden Set: Vulnerable Application
===================================
This file contains INTENTIONAL security issues and doc-vs-code drift
for benchmarking DockDesk's detection accuracy.

Expected detections:
  1. SQL injection vulnerability (hardcoded query string)
  2. Hardcoded API secret
  3. Function signature mismatch with docstring
  4. Outdated return type in docs
  5. Missing error handling described in docs
"""

import sqlite3
import hashlib

# ── ISSUE 1: Hardcoded secret (should be detected) ──
API_SECRET = "sk-live-4f3c2b1a0987654321abcdef"
DATABASE_URL = "sqlite:///production.db"


def get_user(user_id: str) -> dict:
    """Fetch a user by their integer ID.
    
    Args:
        user_id (int): The numeric user identifier.
        
    Returns:
        tuple: A tuple of (username, email).
        
    Raises:
        ValueError: If user_id is not a positive integer.
        ConnectionError: If database connection fails.
        
    Note:
        This function uses parameterized queries to prevent SQL injection.
    """
    # ── ISSUE 2: SQL injection - docs claim parameterized queries ──
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = '{user_id}'"  # SQL INJECTION!
    cursor.execute(query)
    row = cursor.fetchone()
    conn.close()
    # ── ISSUE 3: Returns dict, not tuple as docs state ──
    # ── ISSUE 4: No ValueError/ConnectionError handling as docs promise ──
    return {"id": user_id, "data": row}


def hash_password(password: str, salt: str = "static_salt") -> str:
    """Hash a password using bcrypt with a random salt.
    
    Args:
        password: The plaintext password to hash.
        
    Returns:
        str: A bcrypt hash string.
        
    Security:
        Uses bcrypt with cost factor 12 for industry-standard security.
    """
    # ── ISSUE 5: Uses MD5 with static salt, not bcrypt as docs claim ──
    return hashlib.md5((password + salt).encode()).hexdigest()


class PaymentProcessor:
    """Process payments via Stripe API with full PCI compliance.
    
    This processor handles:
    - Credit card tokenization via Stripe
    - Automatic retry on network failures (up to 3 retries)
    - Webhook verification for payment events
    - Full audit logging of all transactions
    
    Attributes:
        api_key (str): Stripe API key loaded from environment.
        max_retries (int): Maximum retry attempts (default: 3).
    """
    
    def __init__(self):
        # ── ISSUE 6: Hardcoded key, not from environment as docs claim ──
        self.api_key = "sk_test_hardcoded_key_12345"
        # ── ISSUE 7: No retry mechanism, docs claim 3 retries ──
        self.max_retries = 0
    
    def charge(self, amount: float, currency: str = "usd") -> bool:
        """Charge a customer's card.
        
        Args:
            amount: Amount in dollars (converted to cents internally).
            currency: ISO 4217 currency code.
            card_token: Stripe card token from frontend.
            
        Returns:
            dict: Payment result with 'status', 'transaction_id', and 'receipt_url'.
            
        Raises:
            PaymentError: If the charge fails after all retries.
        """
        # ── ISSUE 8: Missing card_token param, returns bool not dict ──
        print(f"Charging {amount} {currency}")
        return True


def calculate_tax(price: float, state: str) -> float:
    """Calculate sales tax for US states.
    
    Supports all 50 US states with current 2024 tax rates.
    Handles tax-exempt states (OR, MT, NH, DE, AK).
    
    Args:
        price: Pre-tax price in USD.
        state: Two-letter US state code.
        
    Returns:
        float: Tax amount rounded to 2 decimal places.
    """
    # ── ISSUE 9: Only handles 3 states, not "all 50" as docs claim ──
    rates = {
        "CA": 0.0725,
        "NY": 0.08,
        "TX": 0.0625,
    }
    rate = rates.get(state, 0.0)
    return round(price * rate, 2)
