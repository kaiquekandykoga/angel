import sys
from collections.abc import Sequence

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.github_client import (
    GitHubClient,
    MissingGitHubTokenError,
    build_github_client,
)
from nishikihebi.graph import build_graphs
from nishikihebi.graphs.chat import build_chat_graph
from nishikihebi.llm_client import LlmClient, MissingApiKeyError, build_llm_client

COMMANDS = ("chat", "pr_review")


def run_chat(client: LlmClient) -> None:
    graph = build_chat_graph(client)
    session = start_session(graph)
    cli.run(session)


def run_pr_review(client: LlmClient, github: GitHubClient) -> None:
    graph = build_graphs(client, github).pr_review
    result = graph.invoke({"pull_requests": [], "reviews": []})
    for review in result["reviews"]:
        pull_request = review.pull_request
        print(f"Commented on {pull_request.repository}#{pull_request.number}")


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in COMMANDS:
        given = " ".join(argv) or "(none)"
        sys.exit(f"Unknown command: {given}. Valid commands: {', '.join(COMMANDS)}")

    try:
        client = build_llm_client()
        github = build_github_client() if argv[0] == "pr_review" else None
    except (MissingApiKeyError, MissingGitHubTokenError) as error:
        sys.exit(str(error))

    if github is None:
        run_chat(client)
    else:
        run_pr_review(client, github)


if __name__ == "__main__":
    main()
