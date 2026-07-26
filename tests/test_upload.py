import datetime
import http.client
import struct
import threading

import pytest

from spacedeck import paths, upload


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEDECK_HOME", str(tmp_path / "runtime"))


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "notes"
    r.mkdir()
    return r


TODAY = datetime.date(2026, 7, 25)


def _shot(repo, name="raw.jpg"):
    p = paths.inbox(repo) / name
    p.write_bytes(b"jpeg-ish")
    return p


# --- filing a graded shot ---------------------------------------------------

def test_file_shot_moves_the_photo_into_the_cards_folder(repo):
    filed = upload.file_shot(repo, "ito-isometry", _shot(repo), TODAY)
    assert filed == paths.card_work(repo, "ito-isometry") / "2026-07-25.jpg"
    assert filed.read_bytes() == b"jpeg-ish"


def test_file_shot_empties_the_inbox(repo):
    shot = _shot(repo)
    upload.file_shot(repo, "ito-isometry", shot, TODAY)
    assert not shot.exists()
    assert list(paths.inbox(repo).glob("*.jpg")) == []


def test_a_second_attempt_the_same_day_is_numbered_not_overwritten(repo):
    first = upload.file_shot(repo, "ito", _shot(repo, "a.jpg"), TODAY)
    second = upload.file_shot(repo, "ito", _shot(repo, "b.jpg"), TODAY)
    assert first.name == "2026-07-25.jpg"
    assert second.name == "2026-07-25-2.jpg"
    assert first.exists() and second.exists()


def test_shots_for_different_cards_never_mix(repo):
    upload.file_shot(repo, "ito", _shot(repo, "a.jpg"), TODAY)
    upload.file_shot(repo, "dominated", _shot(repo, "b.jpg"), TODAY)
    assert len(upload.filed_shots(repo, "ito")) == 1
    assert len(upload.filed_shots(repo, "dominated")) == 1


def test_the_work_folder_resolves_under_the_runtime_root_not_the_repo(repo):
    filed = upload.file_shot(repo, "ito", _shot(repo), TODAY)
    assert paths.root() in filed.parents
    assert repo not in filed.parents


def test_the_work_folder_is_one_flat_directory_per_card(repo):
    folder = paths.card_work(repo, "ito-isometry")
    assert folder.is_dir()
    assert folder.name == "ito-isometry"
    assert folder.parent == paths.work(repo)


def test_filed_shots_are_oldest_first(repo):
    upload.file_shot(repo, "ito", _shot(repo, "a.jpg"), TODAY)
    upload.file_shot(repo, "ito", _shot(repo, "b.jpg"), TODAY)
    upload.file_shot(repo, "ito", _shot(repo, "c.jpg"), TODAY)
    names = [p.name for p in upload.filed_shots(repo, "ito")]
    assert names == ["2026-07-25.jpg", "2026-07-25-2.jpg", "2026-07-25-3.jpg"]


@pytest.fixture
def server(repo):
    srv = upload.make_server(repo, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _post(srv, body, token, ctype="image/jpeg"):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    c.request("POST", f"/upload?t={token}", body=body, headers={"Content-Type": ctype})
    return c.getresponse()


def test_token_is_generated_once_and_reused(repo):
    first = upload.get_token(repo)
    assert first and upload.get_token(repo) == first
    assert paths.token_file(repo).read_text(encoding="utf-8").strip() == first


def test_different_repos_get_different_tokens(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert upload.get_token(a) != upload.get_token(b)


def test_get_serves_the_capture_page(server, repo):
    c = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    c.request("GET", f"/?t={upload.get_token(repo)}")
    resp = c.getresponse()
    assert resp.status == 200
    assert 'capture="environment"' in resp.read().decode("utf-8")


def test_get_without_token_is_forbidden(server):
    c = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    c.request("GET", "/")
    assert c.getresponse().status == 403


def test_post_writes_the_body_to_the_inbox(server, repo):
    assert _post(server, b"\xff\xd8jpegbytes", upload.get_token(repo)).status == 200
    written = list(paths.inbox(repo).glob("*.jpg"))
    assert len(written) == 1
    assert written[0].read_bytes() == b"\xff\xd8jpegbytes"


def test_post_with_bad_token_is_forbidden(server, repo):
    assert _post(server, b"x", "wrong").status == 403
    assert list(paths.inbox(repo).glob("*.jpg")) == []


def test_post_over_the_size_cap_is_rejected(server, repo):
    # The guard reads Content-Length and refuses before touching the body, so an
    # oversized claim is enough. Actually shipping 25MB races the server's close
    # and makes the test flaky.
    c = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    c.putrequest("POST", f"/upload?t={upload.get_token(repo)}")
    c.putheader("Content-Type", "image/jpeg")
    c.putheader("Content-Length", str(upload.MAX_BYTES + 1))
    c.endheaders()
    c.send(b"x")
    assert c.getresponse().status == 413
    assert list(paths.inbox(repo).glob("*.jpg")) == []


def test_post_with_non_image_type_is_rejected(server, repo):
    assert _post(server, b"x", upload.get_token(repo), ctype="text/html").status == 415


def test_filename_is_generated_not_taken_from_the_client(server, repo):
    c = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    c.request(
        "POST",
        f"/upload?t={upload.get_token(repo)}",
        body=b"x",
        headers={"Content-Type": "image/jpeg", "X-Filename": "../../evil.jpg"},
    )
    c.getresponse()
    names = [p.name for p in paths.inbox(repo).glob("*.jpg")]
    assert names and "evil" not in names[0]


def test_newest_since_finds_a_later_file(repo):
    before = datetime.datetime.now() - datetime.timedelta(seconds=5)
    target = paths.inbox(repo) / "shot.jpg"
    target.write_bytes(b"x")
    assert upload.newest_since(repo, before) == target


def test_newest_since_ignores_earlier_files(repo):
    (paths.inbox(repo) / "old.jpg").write_bytes(b"x")
    later = datetime.datetime.now() + datetime.timedelta(seconds=5)
    assert upload.newest_since(repo, later) is None


def test_urls_all_carry_the_port_and_token(repo):
    out = upload.urls(repo, 8765)
    assert out
    assert all(":8765/?t=" in u for u in out)
    assert all(upload.get_token(repo) in u for u in out)


def test_urls_lead_with_the_raw_address(repo):
    """The address is the one that always works; names may not resolve on a phone."""
    first = upload.urls(repo, 8765)[0]
    host = first.split("//")[1].split(":")[0]
    assert all(part.isdigit() for part in host.split("."))


def test_urls_offer_an_mdns_name(repo):
    assert any(".local:" in u for u in upload.urls(repo, 8765))


def test_is_running_detects_a_live_server(server):
    assert upload.is_running(server.server_address[1])


def test_is_running_is_false_on_a_closed_port():
    assert not upload.is_running(1)


def test_idle_timeout_is_an_hour():
    assert upload.IDLE_TIMEOUT == 3600


# --- EXIF orientation -----------------------------------------------------------

def _jpeg_with_orientation(value):
    tiff = b"MM\x00\x2a\x00\x00\x00\x08" + struct.pack(">H", 1)
    tiff += struct.pack(">HHI", 0x0112, 3, 1) + struct.pack(">H", value) + b"\x00\x00"
    tiff += struct.pack(">I", 0)
    app1 = b"Exif\x00\x00" + tiff
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


def test_reads_a_rotated_orientation():
    assert upload.read_orientation(_jpeg_with_orientation(6)) == 6


def test_reads_an_upright_orientation():
    assert upload.read_orientation(_jpeg_with_orientation(1)) == 1


def test_missing_exif_reads_as_upright():
    assert upload.read_orientation(b"\xff\xd8\xff\xd9") == 1


def test_non_jpeg_reads_as_upright():
    assert upload.read_orientation(b"not a jpeg at all") == 1


def test_orientation_of_reads_from_disk(repo):
    p = paths.inbox(repo) / "rotated.jpg"
    p.write_bytes(_jpeg_with_orientation(8))
    assert upload.orientation_of(p) == 8
