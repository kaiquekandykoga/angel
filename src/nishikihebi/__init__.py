from __future__ import annotations

import sys

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.env import load_api_key
from nishikihebi.graph import build_graph
from nishikihebi.model import (
    NVIDIA_BASE_URL,
    NVIDIA_MAX_TOKENS,
    NVIDIA_MODEL,
    NvidiaModel,
)


def main() -> None:
    api_key = load_api_key()
    if not api_key:
        sys.exit("NVIDIA_API_KEY environment variable is not set.")

    client = ChatNVIDIA(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=NVIDIA_MODEL,
        max_tokens=NVIDIA_MAX_TOKENS,
    )
    model = NvidiaModel(client)
    session = start_session(build_graph(model))
    cli.run(session)
