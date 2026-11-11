"""Authenticated GitHub statistics for the portfolio."""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

GITHUB_USERNAME = "Ryoishin"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
CACHE_TTL_SECONDS = 900
MAX_STALE_SECONDS = 21_600
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT_SECONDS = 5

_GRAPHQL_QUERY = """
query PortfolioStats(
  $login: String!,
  $from: DateTime!,
  $to: DateTime!,
  $after: String,
  $includeRepositories: Boolean!,
  $includeContributions: Boolean!
) {
  viewer {
    login
  }
  user(login: $login) {
    createdAt
    followers {
      totalCount
    }
    following {
      totalCount
    }
    repositories(
      first: 100,
      after: $after,
      privacy: PUBLIC,
      ownerAffiliations: OWNER,
      orderBy: { field: UPDATED_AT, direction: DESC }
    ) @include(if: $includeRepositories) {
      totalCount
      pageInfo {
        endCursor
        hasNextPage
      }
      nodes {
        id
        name
        nameWithOwner
        description
        primaryLanguage {
          name
        }
        stargazerCount
        updatedAt
        url
        homepageUrl
        isFork
        repositoryTopics(first: 10) {
          nodes {
            topic {
              name
            }
          }
        }
        languages(first: 100, orderBy: { field: SIZE, direction: DESC }) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
    contributionsCollection(from: $from, to: $to)
      @include(if: $includeContributions) {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

_cache: dict[str, Any] | None = None
_cache_written_at = 0.0
_cache_lock = asyncio.Lock()


class GitHubStatsUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def calculate_streaks(
    contribution_days: list[dict[str, Any]], today: date | None = None
) -> tuple[int, int]:
    """Return current and longest consecutive days with at least one contribution."""
    days = {
        date.fromisoformat(item["date"]): int(item["contributionCount"])
        for item in contribution_days
    }
    if not days:
        return 0, 0

    longest = 0
    current_run = 0
    previous_day: date | None = None
    for day in sorted(days):
        if days[day] > 0 and previous_day is not None and (day - previous_day).days == 1:
            current_run += 1
        elif days[day] > 0:
            current_run = 1
        else:
            current_run = 0
        longest = max(longest, current_run)
        previous_day = day

    today = today or datetime.now(timezone.utc).date()
    current = 0
    cursor = today if days.get(today, 0) > 0 else date.fromordinal(today.toordinal() - 1)
    while days.get(cursor, 0) > 0:
        current += 1
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return current, longest


def _rate_limited(response: httpx.Response, payload: Any = None) -> bool:
    if response.status_code == 429 or response.headers.get("x-ratelimit-remaining") == "0":
        return True
    if response.status_code != 403:
        return False
    if isinstance(payload, dict):
        message = str(payload.get("message", "")).lower()
        errors = payload.get("errors", [])
        if "rate limit" in message or any(
            isinstance(error, dict)
            and error.get("extensions", {}).get("type") == "RATE_LIMITED"
            for error in errors
        ):
            return True
    return False


def _retry_delay(response: httpx.Response, attempt: int) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            delay = float(retry_after)
        except ValueError:
            delay = None
        if delay is not None:
            return delay if 0 <= delay <= MAX_RETRY_WAIT_SECONDS else None

    reset_at = response.headers.get("x-ratelimit-reset")
    if response.headers.get("x-ratelimit-remaining") == "0" and reset_at:
        try:
            delay = max(0.0, float(reset_at) - time.time())
        except ValueError:
            delay = None
        if delay is not None:
            return delay if delay <= MAX_RETRY_WAIT_SECONDS else None

    return min(0.25 * (2**attempt), MAX_RETRY_WAIT_SECONDS)


async def _github_graphql(
    client: httpx.AsyncClient,
    token: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Ryoishin-Portfolio",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await client.post(
                GITHUB_GRAPHQL_URL,
                headers=headers,
                json={"query": _GRAPHQL_QUERY, "variables": variables},
            )
        except httpx.TransportError as exc:
            if attempt + 1 == MAX_ATTEMPTS:
                raise GitHubStatsUnavailable("network") from exc
            await asyncio.sleep(min(0.25 * (2**attempt), MAX_RETRY_WAIT_SECONDS))
            continue

        try:
            payload = response.json()
        except ValueError as exc:
            raise GitHubStatsUnavailable("invalid_response") from exc

        if response.status_code in {401, 403} and not _rate_limited(response, payload):
            raise GitHubStatsUnavailable("authentication_or_permission")

        retryable_status = response.status_code in {
            429,
            500,
            502,
            503,
            504,
        } or _rate_limited(response, payload)
        if retryable_status:
            delay = _retry_delay(response, attempt)
            if attempt + 1 < MAX_ATTEMPTS and delay is not None:
                await asyncio.sleep(delay)
                continue
            reason = "rate_limited" if _rate_limited(response, payload) else "upstream"
            raise GitHubStatsUnavailable(reason)

        if response.is_error:
            raise GitHubStatsUnavailable("upstream")

        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        if errors:
            is_rate_limited = any(
                isinstance(error, dict)
                and (
                    error.get("extensions", {}).get("type") == "RATE_LIMITED"
                    or "rate limit" in str(error.get("message", "")).lower()
                )
                for error in errors
            )
            if is_rate_limited:
                delay = _retry_delay(response, attempt)
                if attempt + 1 < MAX_ATTEMPTS and delay is not None:
                    await asyncio.sleep(delay)
                    continue
                raise GitHubStatsUnavailable("rate_limited")
            raise GitHubStatsUnavailable("graphql")

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise GitHubStatsUnavailable("invalid_response")
        return data

    raise GitHubStatsUnavailable("upstream")


def _map_repository(repository: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": repository["id"],
        "name": repository["name"],
        "full_name": repository["nameWithOwner"],
        "description": repository.get("description"),
        "language": (repository.get("primaryLanguage") or {}).get("name"),
        "stargazers_count": repository["stargazerCount"],
        "updated_at": repository["updatedAt"],
        "html_url": repository["url"],
        "homepage": repository.get("homepageUrl"),
        "fork": repository["isFork"],
        "topics": [
            item["topic"]["name"]
            for item in repository.get("repositoryTopics", {}).get("nodes", [])
            if item.get("topic")
        ],
    }


async def _fetch_dashboard(
    client: httpx.AsyncClient, token: str, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    variables: dict[str, Any] = {
        "login": GITHUB_USERNAME,
        "from": "2008-01-01T00:00:00Z",
        "to": now.isoformat().replace("+00:00", "Z"),
        "after": None,
        "includeRepositories": True,
        "includeContributions": False,
    }
    repositories: list[dict[str, Any]] = []
    language_bytes: dict[str, int] = {}
    total_stars = 0
    profile: dict[str, Any] | None = None
    user_created_at: str | None = None

    while True:
        data = await _github_graphql(client, token, variables)
        viewer = data.get("viewer") or {}
        if str(viewer.get("login", "")).lower() != GITHUB_USERNAME.lower():
            raise GitHubStatsUnavailable("token_owner_mismatch")
        user = data.get("user")
        if not isinstance(user, dict):
            raise GitHubStatsUnavailable("profile_not_found")

        connection = user.get("repositories") or {}
        if profile is None:
            profile = {
                "public_repos": int(connection.get("totalCount", 0)),
                "followers": int((user.get("followers") or {}).get("totalCount", 0)),
                "following": int((user.get("following") or {}).get("totalCount", 0)),
            }
            user_created_at = user.get("createdAt")

        for repository in connection.get("nodes", []):
            if not isinstance(repository, dict):
                continue
            repositories.append(_map_repository(repository))
            if repository.get("isFork"):
                continue
            total_stars += int(repository.get("stargazerCount", 0))
            for edge in (repository.get("languages") or {}).get("edges", []):
                language = edge.get("node", {}).get("name")
                if language:
                    language_bytes[language] = language_bytes.get(language, 0) + int(
                        edge.get("size", 0)
                    )

        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            raise GitHubStatsUnavailable("pagination")
        variables["after"] = cursor

    if not user_created_at:
        raise GitHubStatsUnavailable("profile_not_found")

    created_date = date.fromisoformat(user_created_at[:10])
    contribution_start = date(created_date.year, 1, 1)
    contribution_end = now.date()
    contribution_days_by_date: dict[str, dict[str, Any]] = {}
    total_contributions = 0
    total_commits = 0
    while contribution_start <= contribution_end:
        next_year = date(contribution_start.year + 1, 1, 1)
        range_end = min(contribution_end, date.fromordinal(next_year.toordinal() - 1))
        contribution_variables = {
            "login": GITHUB_USERNAME,
            "from": f"{contribution_start.isoformat()}T00:00:00Z",
            "to": f"{range_end.isoformat()}T23:59:59Z",
            "after": None,
            "includeRepositories": False,
            "includeContributions": True,
        }
        data = await _github_graphql(client, token, contribution_variables)
        viewer = data.get("viewer") or {}
        user = data.get("user") or {}
        if str(viewer.get("login", "")).lower() != GITHUB_USERNAME.lower():
            raise GitHubStatsUnavailable("token_owner_mismatch")
        contributions = user.get("contributionsCollection")
        if not isinstance(contributions, dict):
            raise GitHubStatsUnavailable("contributions_unavailable")
        calendar = contributions.get("contributionCalendar") or {}
        total_contributions += int(calendar.get("totalContributions", 0))
        total_commits += int(contributions.get("totalCommitContributions", 0))
        for week in calendar.get("weeks", []):
            for day in week.get("contributionDays", []):
                contribution_days_by_date[day["date"]] = day
        contribution_start = next_year

    if profile is None:
        raise GitHubStatsUnavailable("invalid_response")

    contribution_days = list(contribution_days_by_date.values())
    current_streak, longest_streak = calculate_streaks(
        contribution_days, today=contribution_end
    )
    total_language_bytes = sum(language_bytes.values())
    languages = [
        {
            "name": name,
            "bytes": size,
            "percentage": round(size / total_language_bytes * 100, 1)
            if total_language_bytes
            else 0,
        }
        for name, size in sorted(
            language_bytes.items(), key=lambda item: (-item[1], item[0].lower())
        )[:8]
    ]

    return {
        "profile": profile,
        "stats": {
            "total_contributions": total_contributions,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "public_repositories": profile["public_repos"],
            "total_stars": total_stars,
            "followers": profile["followers"],
            "total_commits": total_commits,
        },
        "languages": languages,
        "repos": repositories,
    }


@router.get("/api/github/stats", tags=["GitHub"])
async def github_stats() -> dict[str, Any]:
    global _cache, _cache_written_at

    now = time.monotonic()
    if _cache is not None and now - _cache_written_at < CACHE_TTL_SECONDS:
        result = copy.deepcopy(_cache)
        result["stale"] = False
        return result

    async with _cache_lock:
        now = time.monotonic()
        if _cache is not None and now - _cache_written_at < CACHE_TTL_SECONDS:
            result = copy.deepcopy(_cache)
            result["stale"] = False
            return result

        token = os.getenv("PAT_1", "").strip()
        try:
            if not token:
                raise GitHubStatsUnavailable("missing_token")
            async with httpx.AsyncClient(timeout=10.0) as client:
                result = await _fetch_dashboard(client, token)
        except GitHubStatsUnavailable as exc:
            logger.warning("GitHub statistics unavailable: %s", exc.reason)
            if _cache is not None and now - _cache_written_at <= MAX_STALE_SECONDS:
                stale_result = copy.deepcopy(_cache)
                stale_result["stale"] = True
                return stale_result
            raise HTTPException(
                status_code=503,
                detail="GitHub statistics are temporarily unavailable.",
            ) from exc

        result["updated_at"] = datetime.now(timezone.utc).isoformat()
        result["stale"] = False
        _cache = copy.deepcopy(result)
        _cache_written_at = time.monotonic()
        return result
