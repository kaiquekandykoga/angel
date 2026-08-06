import sys

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.graph import build_graphs
from nishikihebi.llm_client import MissingApiKeyError, build_llm_client


def main() -> None:
    try:
        client = build_llm_client()
    except MissingApiKeyError as error:
        sys.exit(str(error))

    graph = build_graphs(client).chat
    session = start_session(graph)
    cli.run(session)


if __name__ == "__main__":
    main()
