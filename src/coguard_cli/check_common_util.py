"""
Module containing commmon functionality between the different check utils.
"""

import re

def replace_special_chars_with_underscore(string: str, keep_spaces=False) -> str:
    """
    Helper function remove any special character with underscore.
    """
    return re.sub(
        "_+",
        "_",
        re.sub(
            "[^a-zA-Z1-9- ]" if keep_spaces else "[^a-zA-Z1-9]",
            "_",
            string
        )
    ).strip("_ ")
