from __future__ import annotations

import sys

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.graph import build_graph
from nishikihebi.model import MissingApiKeyError, build_model


def main() -> None:
    try:
        model = build_model()
    except MissingApiKeyError as error:
        sys.exit(str(error))

    graph = build_graph(model)
    session = start_session(graph)
    cli.run(session)
