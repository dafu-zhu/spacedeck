"""Render a card to a local HTML page with real typeset math.

Cards stay Markdown-with-LaTeX on disk. The page is rewritten in place for each
phase — prompt, then reveal — and refreshes itself, so the browser tab is opened
once per session and never touched again.

The reveal is a session's last write, so it stops refreshing. That is what lets
`clear` delete the file while the answer stays on screen: with the meta refresh
still running the tab would poll a page that no longer exists and replace the
answer with a browser error.

MathJax is vendored so sessions work offline. If the bundle is missing the page
still renders, showing raw LaTeX; if the Markdown pass raises, the body falls
back to preformatted text. A renderer problem must never block a review.
"""

import html as html_mod
import webbrowser

from . import markdown, paths

REFRESH_SECONDS = 2
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"

TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}<title>{title}</title>
{mathjax}
<style>
 body {{ font: 18px/1.65 Georgia, 'Times New Roman', serif; max-width: 46rem;
         margin: 3rem auto; padding: 0 1.5rem; }}
 h2 {{ font: 600 12px/1 ui-sans-serif, system-ui, sans-serif; letter-spacing: .14em;
       text-transform: uppercase; color: #999; margin: 2.5rem 0 .75rem; }}
 section:first-of-type h2 {{ margin-top: 0; }}
 .body > :first-child {{ margin-top: 0; }}
 .body > :last-child {{ margin-bottom: 0; }}
 p {{ margin: 0 0 1rem; }}
 h3, h4, h5, h6 {{ font-size: 1.05em; margin: 1.6rem 0 .6rem; }}
 ul, ol {{ margin: 0 0 1rem; padding-left: 1.4rem; }}
 table {{ border-collapse: collapse; margin: 1rem 0; max-width: 100%; }}
 td, th {{ border: 1px solid #ddd; padding: .35rem .7rem; }}
 th {{ text-align: left; font-weight: 600; }}
 code {{ font: .88em ui-monospace, SFMono-Regular, Menlo, monospace;
         background: #f1f1f1; padding: .1em .3em; border-radius: 3px; }}
 pre {{ background: #f6f6f6; padding: .8rem 1rem; border-radius: 4px; overflow-x: auto; }}
 pre code {{ background: none; padding: 0; }}
 blockquote {{ margin: 1rem 0; padding-left: 1rem; border-left: 3px solid #ddd;
               color: #555; }}
 hr {{ border: 0; border-top: 1px solid #ddd; margin: 2rem 0; }}
 .raw {{ white-space: pre-wrap; }}
 @media (prefers-color-scheme: dark) {{
   body {{ background: #14161a; color: #e8e8e8; }}
   h2 {{ color: #7d7d7d; }}
   td, th {{ border-color: #333; }}
   code, pre {{ background: #1e2127; }}
   blockquote {{ border-left-color: #333; color: #aaa; }}
   hr {{ border-top-color: #333; }}
 }}
</style>
</head><body>
{sections}
</body></html>
"""

_REFRESH_TAG = '<meta http-equiv="refresh" content="{seconds}">\n'

_MATHJAX_TAGS = """<script>window.MathJax = {{tex: {{inlineMath: [['$', '$']], \
displayMath: [['$$', '$$']]}}, svg: {{fontCache: 'global'}}}};</script>
<script id="MathJax-script" src="{src}"></script>"""


def _mathjax_tags(repo_root):
    bundle = paths.mathjax(repo_root)
    if not bundle.is_file():
        return "<!-- MathJax not vendored; run `spacedeck setup` for typeset math -->"
    return _MATHJAX_TAGS.format(src=bundle.as_uri())


def _body(text):
    """Markdown, or the raw text if the Markdown pass ever throws."""
    try:
        return markdown.to_html(text)
    except Exception:
        return f'<div class="raw">{html_mod.escape(text)}</div>'


def page(repo_root, title, sections, refresh=True):
    """`sections` is a list of (heading, body) pairs, body being raw Markdown/LaTeX.

    Pass `refresh=False` for the last page of a session, so the tab stops polling
    a file that is about to be deleted.
    """
    blocks = []
    for heading, body in sections:
        blocks.append(
            f"<section><h2>{html_mod.escape(heading)}</h2>\n"
            f'<div class="body">{_body(body)}</div></section>'
        )
    return TEMPLATE.format(
        refresh=_REFRESH_TAG.format(seconds=REFRESH_SECONDS) if refresh else "",
        title=html_mod.escape(title),
        mathjax=_mathjax_tags(repo_root),
        sections="\n".join(blocks),
    )


def write(repo_root, title, sections, refresh=True):
    target = paths.card_html(repo_root)
    target.write_text(page(repo_root, title, sections, refresh), encoding="utf-8")
    return target


def clear(repo_root):
    """Delete the rendered page. Returns whether one was there. Never fatal.

    The card body is the one runtime artifact worth removing promptly: it holds
    the answer in plain text outside the repo. Called when a session ends and
    again when the next one starts, so an interrupted session leaves nothing.
    """
    try:
        paths.card_html(repo_root).unlink()
        return True
    except OSError:
        return False


def open_in_browser(repo_root):
    """Open the rendered page once per session. Never fatal."""
    try:
        return webbrowser.open(paths.card_html(repo_root).as_uri())
    except Exception:
        return False
