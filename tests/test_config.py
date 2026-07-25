import pytest

from spacedeck import config

MINIMAL = """\
[spacedeck]
cards_dir = "cards"
queue_file = "QUEUE.md"
"""

FULL = """\
[spacedeck]
cards_dir = "learning/reviews"
queue_file = "learning/REVIEW.md"
ladder = [1, 2, 4]
max_cards_per_day = 3
daily_minutes = 30
upload_port = 9000
state_branch = "trunk"
tiers = ["A", "B"]
"""


def _repo(tmp_path, text=FULL):
    (tmp_path / "spacedeck.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_load_reads_every_field(tmp_path):
    c = config.load(_repo(tmp_path))
    assert c.ladder == [1, 2, 4]
    assert c.max_cards_per_day == 3
    assert c.daily_minutes == 30
    assert c.upload_port == 9000
    assert c.state_branch == "trunk"
    assert c.tiers == ["A", "B"]


def test_paths_are_absolute_and_repo_rooted(tmp_path):
    c = config.load(_repo(tmp_path))
    assert c.cards_dir == tmp_path / "learning" / "reviews"
    assert c.queue_file == tmp_path / "learning" / "REVIEW.md"
    assert c.cards_dir.is_absolute()


def test_omitted_fields_fall_back_to_defaults(tmp_path):
    c = config.load(_repo(tmp_path, MINIMAL))
    assert c.ladder == config.DEFAULTS["ladder"]
    assert c.upload_port == config.DEFAULTS["upload_port"]
    assert c.state_branch == config.DEFAULTS["state_branch"]


def test_missing_config_names_the_fix(tmp_path):
    with pytest.raises(FileNotFoundError, match="init"):
        config.load(tmp_path)


def test_find_root_walks_up_from_a_subdirectory(tmp_path):
    _repo(tmp_path)
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert config.find_root(deep) == tmp_path


def test_find_root_returns_none_outside_a_configured_repo(tmp_path):
    assert config.find_root(tmp_path) is None


def test_rejects_a_ladder_that_is_not_ascending(tmp_path):
    bad = MINIMAL + "ladder = [3, 1, 7]\n"
    with pytest.raises(ValueError, match="ascending"):
        config.load(_repo(tmp_path, bad))


def test_rejects_an_empty_ladder(tmp_path):
    with pytest.raises(ValueError, match="ladder"):
        config.load(_repo(tmp_path, MINIMAL + "ladder = []\n"))


def test_retire_interval_is_the_last_ladder_entry(tmp_path):
    assert config.load(_repo(tmp_path)).retire_interval == 4
