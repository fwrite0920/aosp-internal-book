"""HTML cleanup utilities for EPUB generation."""

import re

from lxml import etree, html


def strip_site_chrome(html_str: str) -> str:
    """Extract article content from Material theme HTML, removing all site chrome.

    Instead of trying to strip individual elements (header, sidebar, footer...),
    we extract the actual content from <article class="md-content__inner md-typeset">
    which is the only part that matters for EPUB.
    """
    # Try to extract just the article content
    m = re.search(
        r'<article[^>]*class="[^"]*md-typeset[^"]*"[^>]*>(.*)</article>',
        html_str,
        re.DOTALL,
    )
    if m:
        content = m.group(1)
    else:
        # Fallback: strip known chrome elements
        content = html_str
        patterns = [
            r"<header[^>]*>.*?</header>",
            r"<footer[^>]*>.*?</footer>",
            r"<nav[^>]*>.*?</nav>",
            r'<div[^>]*class="[^"]*md-sidebar[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*md-tabs[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*md-header[^"]*"[^>]*>.*?</div>',
        ]
        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.DOTALL)

    # Remove remaining Material-specific elements
    content = re.sub(r'<input[^>]*/?\s*>', "", content)
    content = re.sub(r'<label[^>]*class="[^"]*md-[^"]*"[^>]*>.*?</label>', "", content, flags=re.DOTALL)
    content = re.sub(r'<label[^>]*for="__[^"]*"[^>]*/?\s*>', "", content)
    content = re.sub(r'<a[^>]*class="[^"]*md-skip[^"]*"[^>]*>.*?</a>', "", content, flags=re.DOTALL)
    content = re.sub(r'<a[^>]*class="[^"]*headerlink[^"]*"[^>]*>.*?</a>', "", content, flags=re.DOTALL)
    content = re.sub(r'<button[^>]*class="[^"]*md-clipboard[^"]*"[^>]*>.*?</button>', "", content, flags=re.DOTALL)
    content = re.sub(r'<div[^>]*id="mermaid-zoom-overlay"[^>]*>.*?</div>', "", content, flags=re.DOTALL)
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)

    # Expand <details> elements
    content = re.sub(r"<details(?!\s+open)", "<details open", content)

    return content


def sanitize_svg_for_epub(html_str: str) -> str:
    """Fix all SVGs in HTML for EPUB reflowable layout.

    EPUB readers handle SVG sizing poorly with width="100%". Instead,
    parse each SVG's viewBox, compute pixel dimensions that fit within
    a ~550px EPUB viewport, and set explicit width/height attributes.
    Also fixes viewbox→viewBox (XHTML is case-sensitive) and strips
    foreignObject (invalid in EPUB3).
    """
    if not html_str:
        return html_str

    # Strip foreignObject globally
    html_str = re.sub(
        r"<foreignObject[^>]*>.*?</foreignObject>",
        "",
        html_str,
        flags=re.DOTALL,
    )

    # Fix each <svg> tag individually
    def _fix_svg_tag(m):
        tag = m.group(0)
        # Fix case: viewbox → viewBox
        tag = tag.replace("viewbox=", "viewBox=")
        # Remove inline style (max-width etc.)
        tag = re.sub(r'\s+style="[^"]*"', '', tag)
        # Extract viewBox dimensions
        vb = re.search(r'viewBox="([^"]*)"', tag)
        if vb:
            parts = vb.group(1).split()
            if len(parts) == 4:
                try:
                    vb_w = float(parts[2])
                    vb_h = float(parts[3])
                    # Scale to fit within 550px wide EPUB viewport
                    max_w = 550
                    if vb_w > 0 and vb_h > 0:
                        scale = min(1.0, max_w / vb_w)
                        w = int(vb_w * scale)
                        h = int(vb_h * scale)
                        # Replace/set width and height
                        tag = re.sub(r'\s+width="[^"]*"', '', tag)
                        tag = re.sub(r'\s+height="[^"]*"', '', tag)
                        tag = tag.replace('<svg', f'<svg width="{w}" height="{h}"', 1)
                except (ValueError, ZeroDivisionError):
                    pass
        return tag

    html_str = re.sub(r'<svg[^>]*>', _fix_svg_tag, html_str)
    return html_str


def expand_tabbed_content(html_str: str) -> str:
    """Expand pymdownx.tabbed content: show all panels sequentially."""
    html_str = re.sub(
        r'<input[^>]*name="__tabbed[^"]*"[^>]*/?>',
        "",
        html_str,
    )
    html_str = re.sub(
        r'<label[^>]*for="__tabbed[^"]*"[^>]*>(.*?)</label>',
        r"<h4>\1</h4>",
        html_str,
        flags=re.DOTALL,
    )
    html_str = re.sub(
        r'<div[^>]*class="[^"]*tabbed-set[^"]*"[^>]*>',
        "<div>",
        html_str,
    )
    return html_str


def html_to_xhtml(html_str: str) -> str:
    """Convert HTML5 to valid XHTML for EPUB3."""
    try:
        doc = html.fromstring(html_str)
        result = etree.tostring(doc, encoding="unicode", method="xml")
        return result
    except Exception:
        html_str = re.sub(r"<br\s*/?>", "<br/>", html_str)
        html_str = re.sub(r"<img([^>]*?)(?<!/)>", r"<img\1/>", html_str)
        html_str = re.sub(r"<hr\s*/?>", "<hr/>", html_str)
        return html_str


def collect_image_refs(html_str: str) -> list[str]:
    """Collect unique non-Mermaid image src paths from HTML."""
    refs = re.findall(r'<img[^>]*\bsrc="([^"]+)"', html_str)
    seen = set()
    unique = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique.append(ref)
    return unique
