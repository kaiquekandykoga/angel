from nishikihebi.clients.github import Comment


def last_review_at(comments: list[Comment], reviewer_login: str) -> str | None:
    return max(
        (
            comment.created_at
            for comment in comments
            if comment.author == reviewer_login
        ),
        default=None,
    )


def render_comments(comments: list[Comment]) -> str:
    if not comments:
        return "(none)"
    return "\n\n".join(f"@{comment.author}: {comment.body}" for comment in comments)
