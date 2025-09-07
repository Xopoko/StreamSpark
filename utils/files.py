r"""File-related utilities and validations."""

from typing import Final


# Allowed characters for video filenames (no path separators)
_ALLOWED_FILENAME_CHARS: Final[set[str]] = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


def is_safe_video_filename(filename: str) -> bool:
    r"""
    Validate a video filename to prevent path traversal and only allow safe characters.

    Rules:
    - Non-empty
    - No path traversal or separators (.., /, \)
    - Must end with .mp4 (case-insensitive)
    - Only contains alphanumeric, dash, underscore, and dot characters

    This mirrors the checks used across routes and OBS widget.
    """
    if not filename:
        return False

    # No path traversal or separators
    if ".." in filename or "/" in filename or "\\" in filename:
        return False

    # Enforce extension
    if not filename.lower().endswith(".mp4"):
        return False

    # Character whitelist
    if not all(c in _ALLOWED_FILENAME_CHARS for c in filename):
        return False

    return True
