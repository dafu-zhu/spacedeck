"""Publish card state to the state branch from whatever branch you're on.

Many repos forbid committing directly to the trunk, so day-to-day work happens on a
feature branch while anything reading the repo from elsewhere — a scheduler, a bot, a
second machine — sees the trunk. Grades written on a feature branch never reach it.

This keeps a disposable worktree detached at `origin/<state_branch>` and mirrors card
state into it. The working tree is the source of truth; the worktree never holds
anything unpublished, so it can be reset or deleted at any moment without losing work.

Detached rather than a branch checkout, so `git checkout <state_branch>` in the real
tree never fails with "already checked out elsewhere".
"""

import pathlib
import shutil
import subprocess

from . import paths


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=check, capture_output=True, text=True
    )


def _state_paths(cfg):
    """Repo-relative paths this module publishes."""
    return [
        cfg.cards_dir.relative_to(cfg.root).as_posix(),
        cfg.queue_file.relative_to(cfg.root).as_posix(),
    ]


def worktree(repo_root):
    return paths.state_worktree(repo_root)


def _ensure(cfg):
    wt = worktree(cfg.root)
    if (wt / ".git").exists():
        return wt
    if wt.exists():
        shutil.rmtree(wt)
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(cfg.root, "worktree", "prune", check=False)
    _git(cfg.root, "worktree", "add", "--detach", str(wt), f"origin/{cfg.state_branch}")
    return wt


def _sync(cfg):
    wt = _ensure(cfg)
    _git(cfg.root, "fetch", "origin", cfg.state_branch, check=False)
    _git(wt, "reset", "--hard", f"origin/{cfg.state_branch}", check=False)
    _git(wt, "clean", "-fd", check=False)
    return wt


def prepare(cfg):
    """Fetch, then copy in cards published elsewhere that we don't have yet.

    Cards flow inward here; grades flow outward at publish. Doing it in this order
    makes the working tree a superset before anything is mirrored back, so the
    mirror's deletions can't remove someone else's new card.
    """
    wt = _sync(cfg)
    pulled = []
    remote_cards = wt / cfg.cards_dir.relative_to(cfg.root)
    if not remote_cards.is_dir():
        return pulled
    for remote in remote_cards.rglob("*.md"):
        local = cfg.root / remote.relative_to(wt)
        if not local.exists():
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(remote, local)
            pulled.append(local)
    return pulled


def _mirror(cfg, wt):
    for rel in _state_paths(cfg):
        src, dst = cfg.root / rel, wt / rel
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        elif dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()


def _stage_and_commit(cfg, wt, message):
    rels = _state_paths(cfg)
    _mirror(cfg, wt)
    _git(wt, "add", "-A", *rels, check=False)
    if _git(wt, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    _git(wt, "commit", "-m", message)
    return True


def publish(cfg, message):
    """Mirror card state onto the state branch and push.

    Returns "pushed", "nothing to publish", or "committed locally; push skipped".
    Offline is not an error: the commit stays local and the next publish carries it,
    and because the worktree is disposable a lost local commit costs nothing.
    """
    wt = _sync(cfg)
    if not _stage_and_commit(cfg, wt, message):
        return "nothing to publish"

    target = f"HEAD:{cfg.state_branch}"
    if _git(wt, "push", "origin", target, check=False).returncode == 0:
        return "pushed"

    # Something landed on the branch while we worked. Rebuild on top and retry once.
    _git(cfg.root, "fetch", "origin", cfg.state_branch, check=False)
    _git(wt, "reset", "--hard", f"origin/{cfg.state_branch}", check=False)
    if _stage_and_commit(cfg, wt, message):
        if _git(wt, "push", "origin", target, check=False).returncode == 0:
            return "pushed"
    return "committed locally; push skipped"


def has_remote(repo_root):
    """False for a repo with no origin — publishing is then simply skipped."""
    result = _git(pathlib.Path(repo_root), "remote", check=False)
    return bool(result.stdout.strip())
