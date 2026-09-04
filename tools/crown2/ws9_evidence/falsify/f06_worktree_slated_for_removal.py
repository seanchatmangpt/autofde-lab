#!/usr/bin/env python3
"""
F06 — A file inside a git worktree (or inside .git/ itself) is "durable" to the
target because it is under $HOME. The target has no notion of the container's
lifecycle: `git worktree remove` / `git worktree prune` deletes the whole tree.
Demonstrates with a REAL throwaway git repo in durable scratch:

  * artifact in an added worktree               -> RESOLVED
  * artifact under .git/worktrees/<name>/       -> RESOLVED
  * git worktree remove --force                 -> both vanish; RESOLVED was point-in-time only

severity WEAKENS_CLAIM: "durable" is observed-now, not predicted; a Standing
carries no expiry/lease and nothing re-checks.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import cleanup, evidence, fresh_scratch, report, write  # noqa: E402

d = fresh_scratch("f06")
repo = os.path.join(d, "repo")
os.makedirs(repo)
env = {**os.environ, "GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@x", "GIT_COMMITTER_NAME": "f",
       "GIT_COMMITTER_EMAIL": "f@x", "HOME": os.path.expanduser("~")}
def git(*a): return subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True, text=True, env=env).stdout
git("init", "-q"); write(os.path.join(repo, "x"), "x\n"); git("add", "."); git("commit", "-q", "-m", "init")
wt = os.path.join(d, "wt-doomed")
git("worktree", "add", "-q", "-b", "doomed", wt)
art = write(os.path.join(wt, "crown-run.jsonl"), '{"i": 0}\n')
in_gitdir = write(os.path.join(repo, ".git", "worktrees", "wt-doomed", "evidence.jsonl"), '{"i": 0}\n')

r_wt = evidence.resolve(evidence.make_ref("wt-art", art, "jsonl"))
r_git = evidence.resolve(evidence.make_ref("gitdir-art", in_gitdir, "jsonl"))
ref_wt = evidence.make_ref("wt-art", art, "jsonl")
git("worktree", "remove", "--force", wt)
git("worktree", "prune")
after = evidence.resolve(ref_wt)

detail = (
    f"  worktree artifact  : {r_wt.status}\n"
    f"  .git/worktrees art : {r_git.status}\n"
    f"  after `git worktree remove --force` : {after.status} ({after.checks[0].reason})\n"
    f"  .git/worktrees/wt-doomed exists after prune: {os.path.exists(os.path.dirname(in_gitdir))}\n"
)
reproduced = r_wt.resolved and r_git.resolved and after.status == evidence.refusal("DurabilityCheck")
report("worktree / .git-internal artifacts resolve, then vanish on worktree remove", "WEAKENS_CLAIM", reproduced, detail)
cleanup("f06")
assert reproduced, "F06 did not reproduce"
