# Golden Set: Clean Application (all docs match code)
# Expected: all PASS, no HIGH/MEDIUM risk

"""
Math Utilities
==============
Simple math helper functions with accurate documentation.
"""


def add(a: float, b: float) -> float:
    """Add two numbers and return the sum.
    
    Args:
        a: First number.
        b: Second number.
        
    Returns:
        float: The sum of a and b.
    """
    return a + b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product.
    
    Args:
        a: First number.
        b: Second number.
        
    Returns:
        float: The product of a and b.
    """
    return a * b


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max bounds.
    
    Args:
        value: The value to clamp.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        
    Returns:
        float: The clamped value, guaranteed to be within [min_val, max_val].
    """
    return max(min_val, min(value, max_val))
