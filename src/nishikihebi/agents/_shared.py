from __future__ import annotations

import logging
import re
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from nishikihebi.clients.github import Comment, GitHubClient, Issue, PullRequest

if TYPE_CHECKING:
    from nishikihebi.agents.issue_review.state import IssueReviewState
    from nishikihebi.agents.pr_review.state import PrReviewState

logger = logging.getLogger(__name__)


class Severity(StrEnum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    NIT = "nit"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Severity = Field(description="How serious this finding is.")
    title: str = Field(description="A short one-line summary of the finding.")
    detail: str = Field(description="A detailed explanation of the finding.")
    file: str | None = Field(
        default=None, description="The path of the file this finding refers to, if any."
    )
    line: int | None = Field(
        default=None, description="The line number this finding refers to, if any."
    )


class PullRequestReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        description="A short overall summary of the pull request review."
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Specific findings from the review."
    )


class IssueReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="A short overall summary of the issue review.")
    findings: list[Finding] = Field(
        default_factory=list, description="Specific findings from the review."
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Acceptance criteria the issue should satisfy.",
    )
    suggested_approach: str = Field(
        default="", description="A suggested approach for resolving the issue."
    )


def _render_finding(finding: Finding) -> str:
    location = ""
    if finding.file is not None:
        location = f" — `{finding.file}"
        if finding.line is not None:
            location += f":{finding.line}"
        location += "`"
    return f"**[{finding.severity}] {finding.title}**{location}\n{finding.detail}"


def _render_findings_section(findings: list[Finding]) -> str:
    if not findings:
        return "No findings."
    return "### Findings\n\n" + "\n\n".join(
        _render_finding(finding) for finding in findings
    )


def render_pull_request_review(output: PullRequestReviewOutput) -> str:
    return f"{output.summary}\n\n{_render_findings_section(output.findings)}"


def render_issue_review(output: IssueReviewOutput) -> str:
    sections = [output.summary, _render_findings_section(output.findings)]
    if output.acceptance_criteria:
        criteria = "\n".join(f"- {item}" for item in output.acceptance_criteria)
        sections.append(f"### Acceptance criteria\n\n{criteria}")
    if output.suggested_approach:
        sections.append(f"### Suggested approach\n\n{output.suggested_approach}")
    return "\n\n".join(sections)


class Review(NamedTuple):
    target: PullRequest | Issue
    body: str


class ItemFailure(NamedTuple):
    repository: str
    number: int
    stage: str
    error_type: str
    error: str


def last_review_at(comments: list[Comment], reviewer_login: str) -> str | None:
    return max(
        (
            comment.created_at
            for comment in comments
            if comment.author == reviewer_login
        ),
        default=None,
    )


_MARKER_PATTERN = re.compile(r"<!-- nishikihebi: sha=(\S+) -->")


def review_marker(sha: str) -> str:
    return f"<!-- nishikihebi: sha={sha} -->"


def reviewed_sha(comments: list[Comment], reviewer_login: str) -> str | None:
    matches = [
        (comment.created_at, comment_matches[-1])
        for comment in comments
        if comment.author == reviewer_login
        if (comment_matches := _MARKER_PATTERN.findall(comment.body))
    ]
    return max(matches)[1] if matches else None


def render_comments(comments: list[Comment]) -> str:
    if not comments:
        return "(none)"
    return "\n\n".join(f"@{comment.author}: {comment.body}" for comment in comments)


def post_review_comments(github: GitHubClient):
    def node(state: PrReviewState | IssueReviewState) -> dict:
        reviews = state["reviews"]
        logger.info(f"posting {len(reviews)} review comments")
        failures: list[ItemFailure] = []
        for review in reviews:
            target = review.target
            logger.debug(
                "posting comment",
                extra={
                    "context": {
                        "repository": target.repository,
                        "number": target.number,
                        "body_length": len(review.body),
                    }
                },
            )
            try:
                github.post_comment(target, review.body)
            except Exception as error:
                logger.warning(
                    "failed to post comment",
                    extra={
                        "context": {
                            "repository": target.repository,
                            "number": target.number,
                            "stage": "post_review_comments",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    },
                )
                failures.append(
                    ItemFailure(
                        repository=target.repository,
                        number=target.number,
                        stage="post_review_comments",
                        error_type=type(error).__name__,
                        error=str(error),
                    )
                )
                continue
            logger.info(f"posted {target.repository}#{target.number}")
        return {"failures": failures}

    return node
