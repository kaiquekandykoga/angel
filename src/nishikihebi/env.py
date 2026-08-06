from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv


def load_api_key() -> str | None:
    load_dotenv(find_dotenv(usecwd=True))
    return os.environ.get("NVIDIA_API_KEY")
