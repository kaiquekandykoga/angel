from __future__ import annotations

import os
import sys

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.model import NVIDIA_BASE_URL, NvidiaModel


def main() -> None:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        sys.exit("NVIDIA_API_KEY environment variable is not set.")

    client = ChatNVIDIA(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model="nvidia/nemotron-3-super-120b-a12b",
        max_tokens=1024,
    )
    model = NvidiaModel(client)
    session = start_session(model)
    cli.run(session)
