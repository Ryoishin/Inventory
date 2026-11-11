import asyncio
import time
from datetime import date, datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import github_stats
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_github_stats_cache(monkeypatch):
    monkeypatch.setattr(github_stats, "_cache", None)
    monkeypatch.setattr(github_stats, "_cache_written_at", 0.0)


def _repository(
    name: str,
    *,
    fork: bool = False,
    stars: int = 0,
    languages: list[tuple[str, int]] | None = None,
) -> dict:
    return {
        "id": f"repo-{name}",
        "name": name,
        "nameWithOwner": f"Ryoishin/{name}",
        "description": None,
        "primaryLanguage": {"name": "Python"},
        "stargazerCount": stars,
        "updatedAt": "2026-03-05T00:00:00Z",
        "url": f"https://github.com/Ryoishin/{name}",
        "homepageUrl": None,
        "isFork": fork,
        "repositoryTopics": {"nodes": []},
        "languages": {
            "edges": [
                {"size": size, "node": {"name": language}}
                for language, size in (languages or [])
            ]
        },
    }


def _graphql_page(
    repositories: list[dict],
    *,
    has_next_page: bool,
    cursor: str | None,
    contributions: dict | None = None,
) -> dict:
    user = {
        "createdAt": "2021-08-15T00:00:00Z",
        "followers": {"totalCount": 6},
        "following": {"totalCount": 12},
        "repositories": {
            "totalCount": 2,
            "pageInfo": {"hasNextPage": has_next_page, "endCursor": cursor},
            "nodes": repositories,
        },
    }
    if contributions is not None:
        user["contributionsCollection"] = contributions
    return {"data": {"viewer": {"login": "Ryoishin"}, "user": user}}


def test_calculate_streaks_uses_consecutive_calendar_days():
    days = [
        {"date": "2026-02-20", "contributionCount": 1},
        {"date": "2026-02-21", "contributionCount": 1},
        {"date": "2026-02-22", "contributionCount": 1},
        {"date": "2026-02-23", "contributionCount": 1},
        {"date": "2026-02-24", "contributionCount": 0},
        {"date": "2026-03-03", "contributionCount": 1},
        {"date": "2026-03-04", "contributionCount": 1},
        {"date": "2026-03-05", "contributionCount": 1},
    ]

    assert github_stats.calculate_streaks(days, today=date(2026, 3, 5)) == (3, 4)
    assert github_stats.calculate_streaks([], today=date(2026, 3, 5)) == (0, 0)


def test_dashboard_aggregates_all_pages_and_excludes_forks_from_stars_and_languages():
    first_page = _graphql_page(
        [
            _repository(
                "portfolio",
                stars=8,
                languages=[("Python", 600), ("JavaScript", 400)],
            )
        ],
        has_next_page=True,
        cursor="next-page",
        contributions={
            "totalCommitContributions": 17,
            "contributionCalendar": {
                "totalContributions": 21,
                "weeks": [
                    {
                        "contributionDays": [
                            {"date": "2026-02-20", "contributionCount": 1},
                            {"date": "2026-02-21", "contributionCount": 1},
                            {"date": "2026-02-22", "contributionCount": 1},
                            {"date": "2026-02-23", "contributionCount": 1},
                            {"date": "2026-02-24", "contributionCount": 0},
                            {"date": "2026-03-03", "contributionCount": 1},
                            {"date": "2026-03-04", "contributionCount": 1},
                            {"date": "2026-03-05", "contributionCount": 1},
                        ]
                    }
                ],
            },
        },
    )
    second_page = _graphql_page(
        [
            _repository(
                "forked-repo",
                fork=True,
                stars=500,
                languages=[("Java", 10_000)],
            )
        ],
        has_next_page=False,
        cursor=None,
    )
    requests = []

    contributions_page = {
        "data": {
            "viewer": {"login": "Ryoishin"},
            "user": {
                "contributionsCollection": {
                    "totalCommitContributions": 17,
                    "contributionCalendar": {
                        "totalContributions": 21,
                        "weeks": [
                            {
                                "contributionDays": [
                                    {"date": "2026-02-20", "contributionCount": 1},
                                    {"date": "2026-02-21", "contributionCount": 1},
                                    {"date": "2026-02-22", "contributionCount": 1},
                                    {"date": "2026-02-23", "contributionCount": 1},
                                    {"date": "2026-02-24", "contributionCount": 0},
                                    {"date": "2026-03-03", "contributionCount": 1},
                                    {"date": "2026-03-04", "contributionCount": 1},
                                    {"date": "2026-03-05", "contributionCount": 1},
                                ]
                            }
                        ],
                    },
                }
            },
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        requests.append(payload["variables"])
        assert request.headers["authorization"] == "Bearer test-token"
        variables = payload["variables"]
        if not variables["includeRepositories"]:
            if variables["from"].startswith("2026-"):
                return httpx.Response(200, json=contributions_page)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "viewer": {"login": "Ryoishin"},
                        "user": {
                            "contributionsCollection": {
                                "totalCommitContributions": 0,
                                "contributionCalendar": {
                                    "totalContributions": 0,
                                    "weeks": [],
                                },
                            }
                        },
                    }
                },
            )
        return httpx.Response(
            200, json=first_page if variables["after"] is None else second_page
        )

    async def run():
        now = datetime(2026, 3, 5, 12, tzinfo=timezone.utc)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_client:
            return await github_stats._fetch_dashboard(mock_client, "test-token", now=now)

    result = asyncio.run(run())

    assert [variables["after"] for variables in requests[:2]] == [None, "next-page"]
    assert len(requests) == 8
    assert [variables["includeRepositories"] for variables in requests[:2]] == [True, True]
    assert all(not variables["includeRepositories"] for variables in requests[2:])
    assert all(not variables["includeContributions"] for variables in requests[:2])
    assert all(variables["includeContributions"] for variables in requests[2:])
    assert result["stats"] == {
        "total_contributions": 21,
        "current_streak": 3,
        "longest_streak": 4,
        "public_repositories": 2,
        "total_stars": 8,
        "followers": 6,
        "total_commits": 17,
    }
    assert [(language["name"], language["bytes"]) for language in result["languages"]] == [
        ("Python", 600),
        ("JavaScript", 400),
    ]
    assert len(result["repos"]) == 2


def test_graphql_request_retries_transient_errors(monkeypatch):
    calls = []
    sleeps = []

    async def no_wait(delay: float):
        sleeps.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append(True)
        if len(calls) == 1:
            return httpx.Response(502, json={"message": "temporary"})
        return httpx.Response(200, json={"data": {"viewer": {"login": "Ryoishin"}}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_client:
            return await github_stats._github_graphql(mock_client, "test-token", {})

    monkeypatch.setattr(github_stats.asyncio, "sleep", no_wait)
    result = asyncio.run(run())

    assert result == {"viewer": {"login": "Ryoishin"}}
    assert len(calls) == 2
    assert sleeps == [0.25]


def test_stats_endpoint_requires_server_side_pat(monkeypatch):
    monkeypatch.delenv("PAT_1", raising=False)

    response = client.get("/api/github/stats")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "GitHub statistics are temporarily unavailable."
    }


def test_stats_endpoint_returns_cached_data_as_stale_when_refresh_fails(monkeypatch):
    cached = {
        "profile": {"public_repos": 1, "followers": 2, "following": 3},
        "stats": {
            "total_contributions": 4,
            "current_streak": 1,
            "longest_streak": 2,
            "public_repositories": 1,
            "total_stars": 5,
            "followers": 2,
            "total_commits": 3,
        },
        "languages": [],
        "repos": [],
        "updated_at": "2026-03-05T12:00:00+00:00",
        "stale": False,
    }
    monkeypatch.setenv("PAT_1", "invalid-token")
    monkeypatch.setattr(github_stats, "_cache", cached)
    monkeypatch.setattr(
        github_stats,
        "_cache_written_at",
        time.monotonic() - github_stats.CACHE_TTL_SECONDS - 1,
    )

    async def unavailable(*_):
        raise github_stats.GitHubStatsUnavailable("authentication")

    monkeypatch.setattr(github_stats, "_fetch_dashboard", unavailable)
    response = client.get("/api/github/stats")

    assert response.status_code == 200
    assert response.json()["stale"] is True
    assert response.json()["stats"]["total_contributions"] == 4
    assert "invalid-token" not in response.text
