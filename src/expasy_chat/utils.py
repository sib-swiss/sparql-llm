import json

from expasy_chat.config import settings


def get_prefixes_dict() -> dict[str, str]:
    """Return a dictionary of all prefixes."""
    with open(settings.all_prefixes_filepath) as f:
        return json.loads(f.read())
