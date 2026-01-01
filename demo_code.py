def process_refund(amount, user_role):
    """
    Process a refund request.
    """
    # New Logic: Only Admins can process refunds over $500
    if amount > 500 and user_role != 'admin':
        raise PermissionError("Only admins can process refunds over $500")
    
    print(f"Processing refund of ${amount}")
