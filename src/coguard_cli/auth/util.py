"""
Utility module for common functions, and to avoid circular imports.
"""
from enum import Enum

class DealEnum(Enum):
    """
    An Enum identifying the deal the current user has with CoGuard.
    """
    ENTERPRISE = "Enterprise"
    DEV = "Dev"
    FREE = "Free"
