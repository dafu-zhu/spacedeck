"""A one-button photo endpoint on your own network.

For `derive` cards you work on paper. The phone opens a bookmarked page, taps once,
and the shot lands in the inbox — no cloud account, no sync wait, nothing leaving your
router.

The file is POSTed as a raw body rather than multipart, because `cgi` was removed in
Python 3.13 and a raw body needs no parsing at all.
"""

import datetime
import http.server
import pathlib
import re
import secrets
import shutil
import socket
import struct
import threading
import urllib.parse

from . import paths

MAX_BYTES = 25 * 1024 * 1024
DEFAULT_PORT = 8765
IDLE_TIMEOUT = 3600

PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>spacedeck capture</title>
<style>
 body {{ font: 17px ui-sans-serif, system-ui, sans-serif; display: grid;
         place-items: center; min-height: 100vh; margin: 0;
         background: #14161a; color: #e8e8e8; text-align: center; }}
 label {{ background: #2f6fd0; color: #fff; padding: 1.4rem 2.6rem;
          border-radius: 14px; display: inline-block; }}
 input {{ display: none; }}
 #msg {{ margin-top: 1.5rem; color: #9a9a9a; min-height: 1.5em; }}
</style>
</head><body>
<div>
  <label>Photograph the work<input id="f" type="file" accept="image/*" capture="environment"></label>
  <div id="msg"></div>
</div>
<script>
document.getElementById('f').addEventListener('change', async (e) => {{
  const file = e.target.files[0];
  if (!file) return;
  const msg = document.getElementById('msg');
  msg.textContent = 'uploading...';
  try {{
    const r = await fetch('/upload?t={token}', {{
      method: 'POST', body: file, headers: {{'Content-Type': file.type || 'image/jpeg'}}
    }});
    msg.textContent = r.ok ? 'sent — go back to your laptop' : 'failed: ' + r.status;
  }} catch (err) {{
    msg.textContent = 'failed: ' + err;
  }}
}});
</script>
</body></html>
"""


def get_token(repo_root):
    f = paths.token_file(repo_root)
    if not f.exists():
        f.write_text(secrets.token_urlsafe(16), encoding="utf-8")
    return f.read_text(encoding="utf-8").strip()


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def urls(repo_root, port=DEFAULT_PORT):
    """Bookmark candidates, most-likely-to-work first.

    The raw address always works on the LAN but changes when the router reassigns
    it. `<host>.local` is mDNS, which phones usually resolve and which survives a
    new lease. The bare hostname relies on NetBIOS and is listed last because most
    phones don't speak it.
    """
    token = get_token(repo_root)
    host = socket.gethostname().lower()
    return [
        f"http://{_lan_ip()}:{port}/?t={token}",
        f"http://{host}.local:{port}/?t={token}",
        f"http://{host}:{port}/?t={token}",
    ]


def is_running(port=DEFAULT_PORT):
    """True when something already accepts on the port, so we start at most one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def newest_since(repo_root, when):
    shots = [
        p for p in paths.inbox(repo_root).glob("*.jpg")
        if p.stat().st_mtime > when.timestamp()
    ]
    return max(shots, key=lambda p: p.stat().st_mtime) if shots else None


def file_shot(repo_root, work_rel, image, today):
    """Move a graded shot out of the inbox into its card's folder, named by date.

    The inbox is shared by every card, so a photo means nothing until it is matched
    to the card it was taken for — which only happens at grading. Filing it there
    keeps the inbox a queue rather than an archive.

    A second attempt on the same day is numbered rather than overwritten: two goes
    at one derivation are two pieces of evidence, and the later one is not
    automatically the one worth keeping.
    """
    image = pathlib.Path(image)
    folder = paths.card_work(repo_root, work_rel)
    suffix = image.suffix or ".jpg"
    target = folder / f"{today.isoformat()}{suffix}"
    n = 2
    while target.exists():
        target = folder / f"{today.isoformat()}-{n}{suffix}"
        n += 1
    shutil.move(str(image), str(target))
    return target


_SHOT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?$")


def _shot_order(path):
    """Sort key for a filed shot.

    Not plain name order: `-` precedes `.`, so `2026-07-25-2.jpg` would sort ahead
    of `2026-07-25.jpg`. Not mtime either, which ties when several shots are filed
    in the same instant and is lost by any copy.
    """
    match = _SHOT_RE.match(path.stem)
    return (match.group(1), int(match.group(2) or 1)) if match else (path.stem, 0)


def filed_shots(repo_root, work_rel):
    """Everything filed for one card, oldest first."""
    folder = paths.card_work(repo_root, work_rel)
    return sorted((p for p in folder.iterdir() if p.is_file()), key=_shot_order)


# --- EXIF orientation -----------------------------------------------------------

_ORIENTATION_TAG = 0x0112


def read_orientation(data):
    """EXIF orientation of a JPEG byte string, or 1 when absent/unreadable."""
    if not data.startswith(b"\xff\xd8"):
        return 1
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return 1
        marker, size = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":
            return _orientation_from_tiff(data[i + 10:i + 2 + size])
        if marker in (0xDA, 0xD9):
            return 1
        i += 2 + size
    return 1


def _orientation_from_tiff(tiff):
    if len(tiff) < 8:
        return 1
    endian = "<" if tiff[:2] == b"II" else ">"
    offset = struct.unpack(endian + "I", tiff[4:8])[0]
    if offset + 2 > len(tiff):
        return 1
    count = struct.unpack(endian + "H", tiff[offset:offset + 2])[0]
    for n in range(count):
        entry = offset + 2 + n * 12
        if entry + 12 > len(tiff):
            break
        tag = struct.unpack(endian + "H", tiff[entry:entry + 2])[0]
        if tag == _ORIENTATION_TAG:
            return struct.unpack(endian + "H", tiff[entry + 8:entry + 10])[0]
    return 1


def orientation_of(path):
    return read_orientation(path.read_bytes())


# --- server ---------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    repo_root = None
    last_seen = None

    def _touch(self):
        type(self).last_seen = datetime.datetime.now()

    def _authorised(self):
        query = urllib.parse.urlparse(self.path).query
        supplied = urllib.parse.parse_qs(query).get("t", [""])[0]
        return secrets.compare_digest(supplied, get_token(self.repo_root))

    def _reply(self, status, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._touch()
        if not self._authorised():
            return self._reply(403, b"forbidden")
        body = PAGE.format(token=get_token(self.repo_root)).encode("utf-8")
        self._reply(200, body, "text/html; charset=utf-8")

    def do_POST(self):
        self._touch()
        if not self._authorised():
            return self._reply(403, b"forbidden")
        if not self.headers.get("Content-Type", "").startswith("image/"):
            return self._reply(415, b"images only")
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BYTES:
            return self._reply(413, b"too large")

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = paths.inbox(self.repo_root) / f"{stamp}.jpg"
        target.write_bytes(self.rfile.read(length))
        print(f"received {target.name} ({length} bytes)", flush=True)
        self._reply(200, b"ok")

    def log_message(self, *args):
        pass


def make_server(repo_root, port=DEFAULT_PORT):
    handler = type("_BoundHandler", (_Handler,), {"repo_root": repo_root})
    handler.last_seen = datetime.datetime.now()
    return http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)


def serve(repo_root, port=DEFAULT_PORT, idle_timeout=IDLE_TIMEOUT):
    """Serve until `idle_timeout` seconds pass with no request."""
    server = make_server(repo_root, port)
    handler = server.RequestHandlerClass

    def reap():
        while True:
            idle = (datetime.datetime.now() - handler.last_seen).total_seconds()
            if idle >= idle_timeout:
                server.shutdown()
                return
            threading.Event().wait(min(30, idle_timeout))

    threading.Thread(target=reap, daemon=True).start()
    server.serve_forever()
    server.server_close()
