"""Command line for the mechanical parts of spacedeck.

Everything a script or scheduler needs lives here. Grading stays in the `/review`
skill, because grading is a conversation and a CLI is a poor place to have one.
"""

import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

from . import card, config, ladder, mint, paths, queue, render, statesync, upload

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"


def _resolve(start=None):
    root = config.find_root(start or pathlib.Path.cwd())
    if root is None:
        sys.exit(
            f"no {config.CONFIG_NAME} found here or in any parent directory.\n"
            "Run `spacedeck init` in the repo holding your notes."
        )
    return config.load(root)


# --- commands -------------------------------------------------------------------

def cmd_init(args):
    root = pathlib.Path(args.path or pathlib.Path.cwd()).resolve()
    target = root / config.CONFIG_NAME
    if target.exists():
        sys.exit(f"{target} already exists — edit it rather than re-initialising.")

    shutil.copy2(TEMPLATES / "spacedeck.toml", target)
    cfg = config.load(root)
    cfg.cards_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATES / "card.md", cfg.cards_dir / mint.TEMPLATE_NAME)
    queue.rebuild(cfg.cards_dir, cfg.queue_file, datetime.date.today(), cfg.tiers)

    def rel(p):
        return p.relative_to(root).as_posix()

    print(f"wrote    {rel(target)}")
    print(f"created  {rel(cfg.cards_dir)}/")
    print(f"created  {rel(cfg.cards_dir / mint.TEMPLATE_NAME)}  (edit to reshape cards)")
    print(f"created  {rel(cfg.queue_file)}")
    print("\nAdd your first card with:  /review add <subject> \"<topic>\"")
    return 0


def cmd_due(args):
    cfg = _resolve()
    today = datetime.date.today()
    cards = queue.load(cfg.cards_dir)
    ready = queue.due(cards, today, cfg.tiers)[: cfg.max_cards_per_day]

    minutes = sum(ladder.estimate_minutes(c.fields.get("rung", "recall")) for c in ready)
    payload = {
        "count": len(ready),
        "subjects": sorted({c.fields["subject"] for c in ready}),
        "minutes": minutes,
        "top": [f"{c.fields['subject']} · {c.fields['topic']}" for c in ready[:3]],
    }

    if args.json:
        print(json.dumps(payload))
    elif not ready:
        print("nothing due")
    else:
        print(f"{payload['count']} due (~{minutes}m): " + ", ".join(payload["subjects"]))
        for line in payload["top"]:
            print(f"  {line}")
    return 0


def cmd_requeue(args):
    cfg = _resolve()
    queue.rebuild(cfg.cards_dir, cfg.queue_file, datetime.date.today(), cfg.tiers)
    print(f"rebuilt {cfg.queue_file}")
    return 0


SERVE_LABELS = [
    "address (always works, changes on a new lease)",
    "mDNS name (survives a new lease; most phones resolve it)",
    "hostname (NetBIOS; usually only other desktops)",
]


def _print_urls(cfg, port):
    for url, label in zip(upload.urls(cfg.root, port), SERVE_LABELS):
        print(f"  {url}\n      {label}")


def detached_command(port):
    """The argv for a server that outlives whoever started it."""
    return [sys.executable, "-m", "spacedeck.cli", "serve", "--port", str(port)]


def _spawn_detached(cfg, port):
    """Start the server so it survives the calling shell or session exiting.

    A session-owned child dies with the session, which is useless for a server
    you're meant to forget about.
    """
    env = dict(os.environ)
    package_parent = str(pathlib.Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (package_parent, env.get("PYTHONPATH", "")) if p
    )
    kwargs = {
        "cwd": str(cfg.root),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(detached_command(port), **kwargs)

    for _ in range(50):
        if upload.is_running(port):
            return True
        time.sleep(0.1)
    return False


def cmd_serve(args):
    cfg = _resolve()
    port = args.port or cfg.upload_port

    if upload.is_running(port):
        print(f"already serving on {port}")
        _print_urls(cfg, port)
        return 0

    if args.detach:
        if not _spawn_detached(cfg, port):
            sys.exit(f"failed to start a server on port {port}")
        print(f"serving on {port} (detached)")
        _print_urls(cfg, port)
        print(f"inbox: {paths.inbox(cfg.root)}")
        print(f"(stops itself after {upload.IDLE_TIMEOUT // 60} minutes idle)")
        return 0

    print("bookmark the first that loads on your phone:")
    _print_urls(cfg, port)
    print(f"inbox: {paths.inbox(cfg.root)}")
    print(f"(stops itself after {upload.IDLE_TIMEOUT // 60} minutes idle)")
    upload.serve(cfg.root, port)
    return 0


def cmd_setup(args):
    cfg = _resolve()
    target = paths.mathjax(cfg.root)
    if target.is_file() and not args.force:
        print(f"math bundle already present: {target}")
        return 0
    print(f"fetching {render.MATHJAX_URL}")
    with urllib.request.urlopen(render.MATHJAX_URL, timeout=60) as resp:
        target.write_bytes(resp.read())
    print(f"vendored {target} ({target.stat().st_size // 1024} KB)")
    return 0


def cmd_publish(args):
    cfg = _resolve()
    if not statesync.has_remote(cfg.root):
        print("no remote — nothing to publish to")
        return 0
    print(statesync.publish(cfg, args.message))
    return 0


def cmd_add(args):
    cfg = _resolve()
    path = mint.create(
        cfg.cards_dir, args.subject, args.topic, datetime.date.today(),
        tier=args.tier, source=args.source,
    )
    if args.rung != "recall":
        c = card.read(path)
        c.fields["rung"] = args.rung
        card.write(c)
    queue.rebuild(cfg.cards_dir, cfg.queue_file, datetime.date.today(), cfg.tiers)
    print(path)
    return 0


# --- entry point ----------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="spacedeck", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="scaffold config, cards directory and queue")
    init.add_argument("path", nargs="?", help="repo root (default: cwd)")
    init.set_defaults(func=cmd_init)

    due = sub.add_parser("due", help="what is due today")
    due.add_argument("--json", action="store_true", help="machine-readable, for schedulers")
    due.set_defaults(func=cmd_due)

    rq = sub.add_parser("requeue", help="regenerate the queue from card frontmatter")
    rq.set_defaults(func=cmd_requeue)

    srv = sub.add_parser("serve", help="run the photo upload endpoint")
    srv.add_argument("--port", type=int)
    srv.add_argument("--detach", action="store_true",
                     help="start in the background and return immediately")
    srv.set_defaults(func=cmd_serve)

    setup = sub.add_parser("setup", help="vendor the math bundle for offline rendering")
    setup.add_argument("--force", action="store_true")
    setup.set_defaults(func=cmd_setup)

    pub = sub.add_parser("publish", help="push card state to the state branch")
    pub.add_argument("-m", "--message", default="review: update card state")
    pub.set_defaults(func=cmd_publish)

    add = sub.add_parser("add", help="create a card with an empty body")
    add.add_argument("subject")
    add.add_argument("topic")
    add.add_argument("--rung", choices=ladder.RUNGS, default="recall")
    add.add_argument("--tier", default="P0")
    add.add_argument("--source", default="")
    add.set_defaults(func=cmd_add)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
