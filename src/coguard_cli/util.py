import re

def replace_special_chars_with_underscore(string: str) -> str:
    """
    Helper function remove any special character with underscore.
    """
    return re.sub("[^a-zA-Z1-9]", "_", string)
