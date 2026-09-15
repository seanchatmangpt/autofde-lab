# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Software repository lifecycle extractor to OCEL 2.0.

Inspired by pystackt and git engineering lifecycles across ~/ash_*:
Ingests commits, pull requests, agent tasks, and verification runs
into fully validated OcelLog (OCEL 2.0) instances.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from autofde_lab.ocel.log import OcelLog
from autofde_lab.ocel.model import EventObjectLink, OcelEvent, OcelObject

__all__ = [
    "GitCommitRecord",
    "extract_git_lifecycle_to_ocel",
]


@dataclass(frozen=True)
class GitCommitRecord:
    """A record representing a commit or engineering action in a software repo."""

    commit_sha: str
    author: str
    timestamp_iso: str
    message: str
    affected_files: tuple[str, ...] = ()
    pr_number: str | None = None
    verification_status: str = "PASSED"


def _parse_iso_to_ns(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1e9)


def extract_git_lifecycle_to_ocel(
    repo_name: str,
    commits: Sequence[GitCommitRecord],
) -> OcelLog:
    """Extract software lifecycle commits and review tasks into an OcelLog."""
    events: list[OcelEvent] = []
    objects_dict: dict[str, OcelObject] = {}
    links: list[EventObjectLink] = []

    # Repo object
    repo_obj_id = f"repo_{repo_name}"
    objects_dict[repo_obj_id] = OcelObject(id=repo_obj_id, object_type="Repository")

    for idx, c in enumerate(commits):
        event_id = f"evt_{c.commit_sha[:8]}_{idx}"
        ts_ns = _parse_iso_to_ns(c.timestamp_iso)

        # Event: commit_authored
        events.append(
            OcelEvent(
                id=event_id,
                activity="git_commit",
                timestamp_ns=ts_ns,
            )
        )

        # Objects
        author_id = f"author_{c.author}"
        objects_dict[author_id] = OcelObject(id=author_id, object_type="Developer")

        commit_id = f"commit_{c.commit_sha[:8]}"
        objects_dict[commit_id] = OcelObject(id=commit_id, object_type="Commit")

        # Links
        links.append(
            EventObjectLink(
                event_id=event_id, object_id=repo_obj_id, qualifier="repository"
            )
        )
        links.append(
            EventObjectLink(
                event_id=event_id, object_id=author_id, qualifier="committer"
            )
        )
        links.append(
            EventObjectLink(event_id=event_id, object_id=commit_id, qualifier="subject")
        )

        if c.pr_number is not None:
            pr_id = f"pr_{c.pr_number}"
            objects_dict[pr_id] = OcelObject(id=pr_id, object_type="PullRequest")
            links.append(
                EventObjectLink(
                    event_id=event_id, object_id=pr_id, qualifier="included_in"
                )
            )

        # Verification event if status present
        if c.verification_status:
            verify_evt_id = f"verify_{c.commit_sha[:8]}_{idx}"
            events.append(
                OcelEvent(
                    id=verify_evt_id,
                    activity=f"ci_verification_{c.verification_status.lower()}",
                    timestamp_ns=ts_ns + 10_000_000_000,  # 10 seconds later
                )
            )
            links.append(
                EventObjectLink(
                    event_id=verify_evt_id,
                    object_id=commit_id,
                    qualifier="verified_commit",
                )
            )
            links.append(
                EventObjectLink(
                    event_id=verify_evt_id,
                    object_id=repo_obj_id,
                    qualifier="repository",
                )
            )

    return OcelLog(
        events=tuple(events),
        objects=tuple(objects_dict.values()),
        event_object_links=tuple(links),
    )
