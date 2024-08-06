import json

from curies_rs import Converter

# import curies
from expasy_chat.config import settings


def get_prefixes_dict() -> dict[str, str]:
    """Return a dictionary of all prefixes."""
    with open(settings.all_prefixes_filepath) as f:
        return json.loads(f.read())


def get_prefix_converter():
    """Return a prefix converter."""
    # Remove duplicates
    original_dict = get_prefixes_dict()
    seen_values = set()
    no_dup_dict = {}
    for key, value in original_dict.items():
        if value not in seen_values:
            no_dup_dict[key] = value
            seen_values.add(value)
    # prefix_converter = curies.load_prefix_map(get_prefixes_dict())
    return Converter.from_prefix_map(json.dumps(no_dup_dict))
