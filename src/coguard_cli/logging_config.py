"""
The logging configuration shared by the entry points of the CLI: `coguard`
itself, and the commands installed along with it, such as
`coguard-cloudera-check` and `coguard-cloudera-banner`, which parse a command
line of their own.
"""

import logging

# The levels which can be passed via `--logging-level`.
LOGGING_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

COGUARD_LOGGING_FORMAT = '%(asctime)-12s [%(levelname)s] %(message)s'

def set_logging_config(level):
    """
    Sets the chosen logging level, depending on the argument provided.

    :param level: The logging level.
    :type level: ("DEBUG"|"INFO"|"WARNING"|"ERROR"|"CRITICAL")
    """
    if level not in LOGGING_LEVELS:
        raise ValueError("Log level needs to be one of "
                         "`DEBUG`,`INFO`,`WARNING`,`ERROR`, or `CRITICAL`")
    logging.basicConfig(
        format=COGUARD_LOGGING_FORMAT,
        level=getattr(logging, level)
    )
