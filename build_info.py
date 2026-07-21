from html import escape


def resolve_build_metadata(env: dict, today_provider=None) -> dict[str, str]:
    version = env.get("APP_VERSION") or env.get("RAILWAY_GIT_BRANCH", "")
    git_sha = (env.get("APP_GIT_SHA") or env.get("RAILWAY_GIT_COMMIT_SHA", ""))[:7]
    build_date = env.get("APP_BUILD_DATE", "")

    return {
        "version": version,
        "git_sha": git_sha,
        "build_date": build_date,
    }


def format_build_label(version: str, git_sha: str, build_date: str) -> str:
    parts = [part for part in (version, git_sha, build_date) if part]
    return " | ".join(parts)


def format_build_badge_html(version: str, git_sha: str, build_date: str) -> str:
    build_label = format_build_label(version, git_sha, build_date)
    if not build_label:
        return ""

    safe_label = escape(build_label)
    return (
        "<div style='text-align: right; color: #9ca3af; padding-top: 1rem;'>"
        f"{safe_label}"
        "</div>"
    )
