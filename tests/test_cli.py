import json
import sys

import pytest

from spacedeck import cli


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
    assert (repo / "reviews").is_dir()
    assert (repo / "reviews" / "_template.md").is_file()
    assert (repo / "REVIEW.md").is_file()


def test_init_refuses_to_overwrite(repo):
    with pytest.raises(SystemExit):
        cli.main(["init"])


def test_due_is_zero_on_a_fresh_repo(repo, capsys):
    cli.main(["due", "--json"])
    assert json.loads(capsys.readouterr().out)["count"] == 0


def test_add_then_due_counts_the_card_once_it_ripens(repo, capsys):
    cli.main(["add", "probability", "Ito isometry", "--rung", "derive"])
    capsys.readouterr()

    card_path = repo / "reviews" / "probability" / "ito-isometry.md"
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
    (repo / "REVIEW.md").write_text("clobbered\n", encoding="utf-8")
    cli.main(["requeue"])
    assert "clobbered" not in (repo / "REVIEW.md").read_text(encoding="utf-8")


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
