from datetime import datetime


def resolve_build_metadata(env: dict, today_provider=None) -> dict[str, str]:
    today_provider = today_provider or (lambda: datetime.utcnow().strftime("%Y-%m-%d"))

    version = env.get("APP_VERSION") or env.get("RAILWAY_GIT_BRANCH", "")
    git_sha = (env.get("APP_GIT_SHA") or env.get("RAILWAY_GIT_COMMIT_SHA", ""))[:7]
    build_date = env.get("APP_BUILD_DATE", "")

    if not build_date and (version or git_sha):
        build_date = today_provider()

    return {
        "version": version,
        "git_sha": git_sha,
        "build_date": build_date,
    }


def format_build_label(version: str, git_sha: str, build_date: str) -> str:
    parts = [part for part in (version, git_sha, build_date) if part]
    return " | ".join(parts)
