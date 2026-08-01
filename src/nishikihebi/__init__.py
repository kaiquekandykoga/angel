from __future__ import annotations

import os
import sys

from openai import OpenAI

from nishikihebi import cli
from nishikihebi.model import NVIDIA_BASE_URL, NvidiaModel
from nishikihebi.session import start_session


def main() -> None:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        sys.exit("NVIDIA_API_KEY environment variable is not set.")

    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    model = NvidiaModel(client)
    session = start_session(model)
    cli.run(session)
