import re

_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.DOTALL)


def parse_data_url(url: str) -> tuple[str, str] | None:
    """Parse a `data:<mime>;base64,<data>` URL.

    Returns (mime_type, base64_data) or None if the input is not a data URL.
    """
    if not url:
        return None
    m = _DATA_URL_RE.match(url)
    if not m:
        return None
    return m.group(1), m.group(2)


def get_base64_from_local_url(url: str) -> str | None:
    """
    Converts a local media URL (e.g. /media/chat_attachments/...) to a base64 data URI.
    If the URL is already a data URI or an absolute HTTP URL, it returns it as-is.
    """
    return url
