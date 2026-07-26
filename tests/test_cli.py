import json
import sys

import pytest

from spacedeck import cli, config


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEDECK_HOME", str(tmp_path / "runtime"))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "notes"
    r.mkdir()
    monkeypatch.chdir(r)
    cli.main(["init"])
    return r


def test_init_scaffolds_config_cards_and_queue(repo):
    assert (repo / "spacedeck.toml").is_file()
    assert (repo / "spacedeck").is_dir()
    assert (repo / "spacedeck" / "_template.md").is_file()
    assert (repo / "spacedeck" / "QUEUE.md").is_file()


def test_init_refuses_to_overwrite(repo):
    with pytest.raises(SystemExit):
        cli.main(["init"])


# --- init never takes over paths a repo already uses ------------------------

def _fresh(tmp_path, monkeypatch):
    r = tmp_path / "notes"
    r.mkdir()
    monkeypatch.chdir(r)
    return r


def test_the_default_paths_are_namespaced():
    """`reviews/` and `REVIEW.md` are names a repo may already mean something by."""
    assert config.DEFAULTS["cards_dir"] == "spacedeck"
    assert config.DEFAULTS["queue_file"].startswith("spacedeck/")


def test_the_shipped_template_agrees_with_the_defaults(tmp_path, monkeypatch):
    """The pre-flight check reads the template; drift would make it check the wrong paths."""
    repo = _fresh(tmp_path, monkeypatch)
    cards_dir, queue_file = cli._planned_paths(repo)
    assert cards_dir == repo / config.DEFAULTS["cards_dir"]
    assert queue_file == repo / config.DEFAULTS["queue_file"]


def test_init_refuses_when_the_cards_directory_already_exists(tmp_path, monkeypatch):
    repo = _fresh(tmp_path, monkeypatch)
    (repo / "spacedeck").mkdir()
    (repo / "spacedeck" / "mine.md").write_text("not a card\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["init"])
    assert (repo / "spacedeck" / "mine.md").read_text(encoding="utf-8") == "not a card\n"


def test_init_refuses_when_the_queue_file_already_exists(tmp_path, monkeypatch):
    repo = _fresh(tmp_path, monkeypatch)
    (repo / "spacedeck").mkdir()
    (repo / "spacedeck" / "QUEUE.md").write_text("mine\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["init"])
    assert (repo / "spacedeck" / "QUEUE.md").read_text(encoding="utf-8") == "mine\n"


def test_a_refused_init_writes_nothing_at_all(tmp_path, monkeypatch):
    """A half-initialised repo is worse than one that refused to start."""
    repo = _fresh(tmp_path, monkeypatch)
    (repo / "spacedeck").mkdir()
    with pytest.raises(SystemExit):
        cli.main(["init"])
    assert not (repo / "spacedeck.toml").exists()
    assert list((repo / "spacedeck").iterdir()) == []


def test_init_names_what_is_in_the_way(tmp_path, monkeypatch, capsys):
    repo = _fresh(tmp_path, monkeypatch)
    (repo / "spacedeck").mkdir()
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["init"])
    assert "spacedeck" in str(exit_info.value)


def test_due_is_zero_on_a_fresh_repo(repo, capsys):
    cli.main(["due", "--json"])
    assert json.loads(capsys.readouterr().out)["count"] == 0


def test_add_then_due_counts_the_card_once_it_ripens(repo, capsys):
    cli.main(["add", "probability", "Ito isometry", "--rung", "derive"])
    capsys.readouterr()

    card_path = repo / "spacedeck" / "probability" / "ito-isometry.md"
    text = card_path.read_text(encoding="utf-8")
    card_path.write_text(text.replace(text.split("next_due: ")[1].split("\n")[0], "2020-01-01"),
                         encoding="utf-8")

    cli.main(["due", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["subjects"] == ["probability"]
    assert payload["minutes"] == 8  # a derive card, not a recall one


def test_add_honours_the_requested_rung(repo, capsys):
    cli.main(["add", "probability", "X", "--rung", "derive"])
    path = capsys.readouterr().out.strip()
    assert "rung: derive" in open(path, encoding="utf-8").read()


def test_add_defaults_to_recall(repo, capsys):
    cli.main(["add", "probability", "Y"])
    path = capsys.readouterr().out.strip()
    assert "rung: recall" in open(path, encoding="utf-8").read()


def test_requeue_rewrites_the_queue(repo, capsys):
    (repo / "spacedeck" / "QUEUE.md").write_text("clobbered\n", encoding="utf-8")
    cli.main(["requeue"])
    assert "clobbered" not in (repo / "spacedeck" / "QUEUE.md").read_text(encoding="utf-8")


def test_commands_outside_a_configured_repo_explain_the_fix(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        cli.main(["due"])
    assert "init" in str(exc.value)


def test_detached_command_runs_this_interpreter_and_module():
    cmd = cli.detached_command(8765)
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "spacedeck.cli"]


def test_detached_command_carries_the_port():
    assert cli.detached_command(9001)[-2:] == ["--port", "9001"]


def test_detached_command_does_not_recurse_into_detach():
    """The child must be the blocking server, or it would spawn forever."""
    assert "--detach" not in cli.detached_command(8765)
