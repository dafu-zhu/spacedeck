"""Render a card to a local HTML page with real typeset math.

Cards stay LaTeX on disk. The page is rewritten in place for each phase — prompt,
then reveal — and refreshes itself, so the browser tab is opened once per session and
never touched again.

MathJax is vendored so sessions work offline. If the bundle is missing the page still
renders, showing raw LaTeX rather than failing: a renderer problem must never block a
review.
"""

import html as html_mod
import webbrowser

from . import paths

REFRESH_SECONDS = 2
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"

TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>{title}</title>
{mathjax}
<style>
 body {{ font: 18px/1.65 Georgia, 'Times New Roman', serif; max-width: 46rem;
         margin: 3rem auto; padding: 0 1.5rem; }}
 h2 {{ font: 600 12px/1 ui-sans-serif, system-ui, sans-serif; letter-spacing: .14em;
       text-transform: uppercase; color: #999; margin: 2.5rem 0 .75rem; }}
 section:first-of-type h2 {{ margin-top: 0; }}
 .body {{ white-space: pre-wrap; }}
 table {{ border-collapse: collapse; margin: 1rem 0; }}
 td, th {{ border: 1px solid #ddd; padding: .35rem .7rem; }}
 @media (prefers-color-scheme: dark) {{
   body {{ background: #14161a; color: #e8e8e8; }}
   h2 {{ color: #7d7d7d; }}
   td, th {{ border-color: #333; }}
 }}
</style>
</head><body>
{sections}
</body></html>
"""

_MATHJAX_TAGS = """<script>window.MathJax = {{tex: {{inlineMath: [['$', '$']], \
displayMath: [['$$', '$$']]}}, svg: {{fontCache: 'global'}}}};</script>
<script id="MathJax-script" src="{src}"></script>"""


def _mathjax_tags(repo_root):
    bundle = paths.mathjax(repo_root)
    if not bundle.is_file():
        return "<!-- MathJax not vendored; run `spacedeck setup` for typeset math -->"
    return _MATHJAX_TAGS.format(src=bundle.as_uri())


def page(repo_root, title, sections):
    """`sections` is a list of (heading, body) pairs, body being raw Markdown/LaTeX."""
    blocks = []
    for heading, body in sections:
        blocks.append(
            f"<section><h2>{html_mod.escape(heading)}</h2>\n"
            f'<div class="body">{html_mod.escape(body)}</div></section>'
        )
    return TEMPLATE.format(
        refresh=REFRESH_SECONDS,
        title=html_mod.escape(title),
        mathjax=_mathjax_tags(repo_root),
        sections="\n".join(blocks),
    )


def write(repo_root, title, sections):
    target = paths.card_html(repo_root)
    target.write_text(page(repo_root, title, sections), encoding="utf-8")
    return target


def open_in_browser(repo_root):
    """Open the rendered page once per session. Never fatal."""
    try:
        return webbrowser.open(paths.card_html(repo_root).as_uri())
    except Exception:
        return False
