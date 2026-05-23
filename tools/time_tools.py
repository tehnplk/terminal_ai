# This module is part of the tools package split from tools/__init__.py.

from datetime import datetime, timezone, timedelta


def get_current_time() -> str:
    """
    Returns the current date and time in the Asia/Bangkok timezone (UTC+7).
    """
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    return f"Current date and time in Asia/Bangkok: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"

