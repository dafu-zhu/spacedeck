import pytest

from spacedeck import paths


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEDECK_HOME", str(tmp_path / "runtime"))


def test_home_lives_under_the_configured_root(tmp_path):
    assert (tmp_path / "runtime") in paths.home(tmp_path / "repo").parents


def test_home_creates_the_directory_and_inbox(tmp_path):
    paths.home(tmp_path / "repo")
    assert paths.inbox(tmp_path / "repo").is_dir()


def test_slug_includes_the_repo_name(tmp_path):
    repo = tmp_path / "my-notes"
    assert paths.home(repo).name.startswith("my-notes-")


def test_two_repos_sharing_a_name_do_not_collide(tmp_path):
    a = tmp_path / "one" / "notes"
    b = tmp_path / "two" / "notes"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    assert paths.home(a) != paths.home(b)


def test_slug_is_stable_across_calls(tmp_path):
    repo = tmp_path / "notes"
    assert paths.home(repo) == paths.home(repo)


def test_artifacts_sit_inside_the_repo_home(tmp_path):
    repo = tmp_path / "notes"
    home = paths.home(repo)
    for artifact in (paths.card_html, paths.mathjax, paths.token_file, paths.state_worktree):
        assert artifact(repo).parent == home or home in artifact(repo).parents


def test_default_root_is_under_the_user_home(monkeypatch, tmp_path):
    monkeypatch.delenv("SPACEDECK_HOME", raising=False)
    monkeypatch.setattr(paths.pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    assert paths.root() == tmp_path / ".spacedeck"
