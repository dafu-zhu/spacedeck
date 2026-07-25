import shutil
import subprocess

import pytest

from spacedeck import config, statesync

CONFIG = """\
[spacedeck]
cards_dir = "reviews"
queue_file = "REVIEW.md"
state_branch = "main"
"""


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEDECK_HOME", str(tmp_path / "runtime"))


@pytest.fixture
def cfg(tmp_path):
    """A bare origin plus a clone standing in for the working tree, on a feature branch."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))

    work = tmp_path / "work"
    _git(tmp_path, "clone", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")

    (work / "spacedeck.toml").write_text(CONFIG, encoding="utf-8")
    cards = work / "reviews" / "probability"
    cards.mkdir(parents=True)
    (cards / "seed.md").write_text("seed card\n", encoding="utf-8")
    (work / "REVIEW.md").write_text("queue\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "init")
    _git(work, "push", "-u", "origin", "main")
    _git(work, "checkout", "-b", "feature/x")
    return config.load(work)


def _push_from_elsewhere(tmp_path, relpath, content):
    """Simulate another machine committing straight to the state branch."""
    other = tmp_path / "other"
    if not other.exists():
        _git(tmp_path, "clone", str(tmp_path / "origin.git"), str(other))
        _git(other, "config", "user.email", "b@example.com")
        _git(other, "config", "user.name", "b")
    else:
        _git(other, "pull", "--ff-only")
    target = other / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "from elsewhere")
    _git(other, "push")


# --- publish --------------------------------------------------------------------

def test_publish_lands_on_the_state_branch_from_a_feature_branch(cfg):
    (cfg.cards_dir / "probability" / "seed.md").write_text("graded\n", encoding="utf-8")
    assert statesync.publish(cfg, "review: grade") == "pushed"
    assert _git(cfg.root, "show", "origin/main:reviews/probability/seed.md") == "graded"


def test_publish_leaves_the_working_branch_alone(cfg):
    (cfg.root / "REVIEW.md").write_text("rebuilt\n", encoding="utf-8")
    statesync.publish(cfg, "review: requeue")
    assert _git(cfg.root, "rev-parse", "--abbrev-ref", "HEAD") == "feature/x"


def test_publish_propagates_deletions(cfg):
    (cfg.cards_dir / "probability" / "seed.md").unlink()
    statesync.publish(cfg, "review: split stub")
    files = _git(cfg.root, "ls-tree", "-r", "--name-only", "origin/main")
    assert "reviews/probability/seed.md" not in files


def test_publish_reports_when_there_is_nothing_to_do(cfg):
    assert statesync.publish(cfg, "noop") == "nothing to publish"


def test_publish_scopes_the_commit_to_state_paths(cfg):
    (cfg.root / "unrelated.txt").write_text("not mine\n", encoding="utf-8")
    (cfg.root / "REVIEW.md").write_text("rebuilt\n", encoding="utf-8")
    statesync.publish(cfg, "review: requeue")
    assert "unrelated.txt" not in _git(cfg.root, "ls-tree", "-r", "--name-only", "origin/main")


def test_publish_retries_over_a_concurrent_push(cfg, tmp_path):
    _push_from_elsewhere(tmp_path, "reviews/probability/other.md", "theirs\n")
    (cfg.cards_dir / "probability" / "seed.md").write_text("mine\n", encoding="utf-8")
    # prepare() first, so their card is local and the mirror won't delete it.
    statesync.prepare(cfg)
    assert statesync.publish(cfg, "review: grade") == "pushed"
    files = _git(cfg.root, "ls-tree", "-r", "--name-only", "origin/main")
    assert "reviews/probability/other.md" in files
    assert _git(cfg.root, "show", "origin/main:reviews/probability/seed.md") == "mine"


# --- prepare --------------------------------------------------------------------

def test_prepare_pulls_a_card_published_elsewhere(cfg, tmp_path):
    _push_from_elsewhere(tmp_path, "reviews/probability/minted.md", "from the bot\n")
    pulled = statesync.prepare(cfg)
    local = cfg.cards_dir / "probability" / "minted.md"
    assert local.exists() and local.read_text(encoding="utf-8") == "from the bot\n"
    assert local in pulled


def test_prepare_does_not_clobber_a_locally_graded_card(cfg, tmp_path):
    (cfg.cards_dir / "probability" / "seed.md").write_text("mine\n", encoding="utf-8")
    _push_from_elsewhere(tmp_path, "reviews/probability/seed.md", "theirs\n")
    statesync.prepare(cfg)
    assert (cfg.cards_dir / "probability" / "seed.md").read_text(encoding="utf-8") == "mine\n"


def test_prepare_returns_empty_when_nothing_is_new(cfg):
    assert statesync.prepare(cfg) == []


# --- the worktree ---------------------------------------------------------------

def test_worktree_is_detached_so_the_branch_stays_checkoutable(cfg):
    statesync.prepare(cfg)
    assert _git(statesync.worktree(cfg.root), "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    _git(cfg.root, "checkout", "main")  # must not raise "already checked out"


def test_worktree_is_recreated_if_deleted(cfg):
    statesync.prepare(cfg)
    shutil.rmtree(statesync.worktree(cfg.root))
    statesync.prepare(cfg)
    assert statesync.worktree(cfg.root).is_dir()


def test_worktree_holds_nothing_unpublished_after_a_publish(cfg):
    (cfg.root / "REVIEW.md").write_text("rebuilt\n", encoding="utf-8")
    statesync.publish(cfg, "review: requeue")
    wt = statesync.worktree(cfg.root)
    assert _git(wt, "status", "--porcelain") == ""


def test_has_remote_is_true_for_a_clone(cfg):
    assert statesync.has_remote(cfg.root)


def test_has_remote_is_false_without_an_origin(tmp_path):
    solo = tmp_path / "solo"
    solo.mkdir()
    _git(tmp_path, "init", "-q", str(solo))
    assert not statesync.has_remote(solo)
