"""Where runtime artifacts live.

Everything here sits outside any repo and is never committed: the rendered page, the
vendored math bundle, the upload token, photographed work, and the staging worktree.

Directories are namespaced per consuming repo, so one installed plugin serving several
repos doesn't hand them a shared inbox or a shared rendered card.
"""

import hashlib
import os
import pathlib


def root():
    """The runtime root for all repos. `SPACEDECK_HOME` overrides it, for tests."""
    override = os.environ.get("SPACEDECK_HOME")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".spacedeck"


def slug(repo_root):
    """A stable per-repo directory name: readable prefix, collision-proof suffix.

    The path is normalised before hashing. Without that, `D:\\Repo` and `d:\\repo`
    hash differently while being the same directory on Windows, so the same repo
    would end up with two inboxes and two upload tokens depending on how it was
    spelled.
    """
    repo_root = pathlib.Path(repo_root)
    canonical = os.path.normcase(str(repo_root.resolve()))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"{repo_root.name}-{digest}"


def home(repo_root):
    path = root() / slug(repo_root)
    path.mkdir(parents=True, exist_ok=True)
    (path / "inbox").mkdir(exist_ok=True)
    return path


def inbox(repo_root):
    return home(repo_root) / "inbox"


def card_html(repo_root):
    return home(repo_root) / "card.html"


def mathjax(repo_root):
    return home(repo_root) / "tex-svg.js"


def token_file(repo_root):
    return home(repo_root) / "token"


def state_worktree(repo_root):
    return home(repo_root) / "state"
