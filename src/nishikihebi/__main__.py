import sys
from collections.abc import Sequence

from nishikihebi.chat import cli
from nishikihebi.chat.session import start_session
from nishikihebi.clients.github import (
    GitHubClient,
    MissingGitHubCredentialsError,
    build_github_client,
)
from nishikihebi.clients.llm import LlmClient, MissingApiKeyError, build_llm_client
from nishikihebi.graphs.chat import build_chat_graph
from nishikihebi.graphs.github.issue_review import build_issue_review_graph
from nishikihebi.graphs.github.pr_review import build_pr_review_graph

COMMANDS = ("chat", "pr_review", "issue_review")


def run_chat(client: LlmClient) -> None:
    graph = build_chat_graph(client)
    session = start_session(graph)
    cli.run(session)


def run_pr_review(client: LlmClient, github: GitHubClient) -> None:
    graph = build_pr_review_graph(client, github)
    result = graph.invoke({"pull_requests": [], "reviews": []})
    if not result["reviews"]:
        print("No pull requests to review")
        return
    for review in result["reviews"]:
        pull_request = review.target
        print(f"Commented on {pull_request.repository}#{pull_request.number}")


def run_issue_review(client: LlmClient, github: GitHubClient) -> None:
    graph = build_issue_review_graph(client, github)
    result = graph.invoke({"issues": [], "reviews": []})
    if not result["reviews"]:
        print("No issues to review")
        return
    for review in result["reviews"]:
        issue = review.target
        print(f"Commented on {issue.repository}#{issue.number}")


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in COMMANDS:
        given = " ".join(argv) or "(none)"
        sys.exit(f"Unknown command: {given}. Valid commands: {', '.join(COMMANDS)}")

    command = argv[0]
    try:
        client = build_llm_client()
        github = None if command == "chat" else build_github_client()
    except (MissingApiKeyError, MissingGitHubCredentialsError) as error:
        sys.exit(str(error))

    if github is None:
        run_chat(client)
    elif command == "pr_review":
        run_pr_review(client, github)
    else:
        run_issue_review(client, github)


if __name__ == "__main__":
    main()
