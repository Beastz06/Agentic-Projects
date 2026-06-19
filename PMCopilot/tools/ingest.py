import config
import os
import json
import time
from github import Github
from github.GithubException import RateLimitExceededException
import argparse
from itertools import islice

MAX_RETRIES = 5


def _is_pull_request(issue) -> bool:
    return issue.pull_request is not None


def _has_labels(issue) -> bool:
    return len(issue.labels) > 0


def _extract_issue(issue) -> dict:
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body,
        "labels": [lbl.name for lbl in issue.labels],
        "reactions": {  # issue-level, free, "collected not yet consumed"
            "total": issue.reactions["total_count"],
            # optionally per-type: issue.reactions["+1"], etc.
        },
        "comments": [
            {
                "body": c.body,
                "author": c.user.login,
                "created_at": c.created_at.isoformat(),
            }
            for c in islice(issue.get_comments(), 5)  # up to 5, stops early, no IndexError
        ],
        "state": issue.state,
        "url": issue.html_url,
    }


def fetch_issues(repo_name: str, target: int = 200):
    client = Github(config.GITHUB_TOKEN)
    repo = client.get_repo(repo_name)

    issue_iter = iter(repo.get_issues(state="open"))  # explicit iterator
    collected = []

    while len(collected) < target:
        # --- advance the stream (this is the part that can hit rate limits) ---
        for attempt in range(MAX_RETRIES):
            try:
                issue = next(issue_iter)
                break  # got one, exit retry loop
            except RateLimitExceededException:
                wait = 2 ** attempt  # exponential backoff: 1, 2, 4, 8, 16
                print(f"Rate limited. Backing off {wait}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})", flush=True)
                time.sleep(wait)
            except StopIteration:
                return collected  # stream ran dry before target
        else:
            # retry loop exhausted without a successful next()
            raise RuntimeError(
                f"Rate limit retries exhausted after {MAX_RETRIES} attempts"
            )

        # --- process the issue (pure logic, no network, no retry needed) ---
        if _is_pull_request(issue):
            continue
        if not _has_labels(issue):
            continue
        collected.append(_extract_issue(issue))

    return collected


def persist(issues: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Ingest GitHub issues into the corpus.")
    parser.add_argument("--repo", default="langchain-ai/langchain",
                        help="owner/name of the repo to ingest")
    parser.add_argument("--target", type=int, default=200,
                        help="number of filtered issues to collect")
    parser.add_argument("--out", default="data/raw/github_issues.json",
                        help="output path for the corpus JSON")
    args = parser.parse_args()

    issues = fetch_issues(args.repo, args.target)
    persist(issues, args.out)

    count = len(issues)
    print(f"Collected {count} issues from {args.repo} → {args.out}")
    if count < args.target:
        print(f"  ⚠ Wanted {args.target} but stream ran dry at {count}. "
              f"Corpus is short.")


if __name__ == "__main__":
    main()
