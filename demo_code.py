def process_refund(amount, user_role):
    """
    Process a refund request.
    """
    # New Logic: Only Admins can process refunds over $100 (Stricter!)
    if amount > 100 and user_role != 'admin':
        raise PermissionError("Only admins can process refunds over $100")
    
    print(f"Processing refund of ${amount}")
