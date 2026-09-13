"""Catalog identity shared by the builder and the generated website."""
import json
import os
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "catalog.config.json")
FIELDS = {"name", "description", "site_url", "repository_url", "client_url"}


def load(path=FILE):
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError(f"{path}: expected exactly {', '.join(sorted(FIELDS))}")
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError(f"{path}: {key} must be a nonempty string without surrounding spaces")
    if len(data["name"]) > 80 or len(data["description"]) > 240:
        raise ValueError(f"{path}: name or description is too long")
    for key in ("site_url", "repository_url", "client_url"):
        value = data[key]
        parsed = urlparse(value)
        if (len(value) > 300 or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(ord(c) < 32 for c in value)):
            raise ValueError(f"{path}: {key} must be a plain HTTPS URL")
    if not data["site_url"].endswith("/"):
        raise ValueError(f"{path}: site_url must end with /")
    data["catalog_url"] = data["site_url"] + "catalog.json"
    return data
