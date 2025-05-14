"""
The enums in this submodule.
"""
from enum import Enum

class DealEnum(Enum):
    """
    An Enum identifying the deal the current user has with CoGuard.
    """
    ENTERPRISE = "Enterprise"
    DEV = "Dev"
    FREE = "Free"
