"""Tests for EPUB HTML cleanup functions."""

from mkdocs_epub_generate.html_cleanup import (
    strip_site_chrome,
    sanitize_svg_for_epub,
    expand_tabbed_content,
    html_to_xhtml,
    collect_image_refs,
)


class TestStripSiteChrome:
    def test_removes_header(self):
        html = '<div>content</div><header class="md-header">nav</header>'
        assert "md-header" not in strip_site_chrome(html)

    def test_removes_footer(self):
        html = '<div>content</div><footer class="md-footer">foot</footer>'
        assert "md-footer" not in strip_site_chrome(html)

    def test_removes_sidebar(self):
        html = '<div class="md-sidebar">sidebar</div><div>content</div>'
        assert "md-sidebar" not in strip_site_chrome(html)

    def test_removes_scripts(self):
        html = '<div>content</div><script>alert(1)</script>'
        assert "<script" not in strip_site_chrome(html)

    def test_preserves_content(self):
        html = '<div class="md-content"><p>Hello world</p></div>'
        assert "Hello world" in strip_site_chrome(html)

    def test_opens_details(self):
        html = '<details><summary>Info</summary><p>Hidden</p></details>'
        result = strip_site_chrome(html)
        assert "<details open" in result


class TestSanitizeSvgForeignObjects:
    def test_strips_foreign_object(self):
        svg = '<svg><foreignObject><div>text</div></foreignObject></svg>'
        result = sanitize_svg_for_epub(svg)
        assert "<foreignObject" not in result

    def test_preserves_valid_svg(self):
        svg = '<svg><rect width="10" height="10"/></svg>'
        result = sanitize_svg_for_epub(svg)
        assert "<rect" in result

    def test_returns_placeholder_on_total_failure(self):
        result = sanitize_svg_for_epub("")
        assert result == ""


class TestExpandTabbedContent:
    def test_expands_tabs(self):
        html = (
            '<div class="tabbed-set" data-tabs="1">'
            '<input type="radio" name="__tabbed_1" id="__tabbed_1_1" checked>'
            '<label for="__tabbed_1_1">Tab A</label>'
            '<div class="tabbed-content">'
            '<div class="tabbed-block"><p>Content A</p></div>'
            '</div>'
            '<input type="radio" name="__tabbed_1" id="__tabbed_1_2">'
            '<label for="__tabbed_1_2">Tab B</label>'
            '<div class="tabbed-content">'
            '<div class="tabbed-block"><p>Content B</p></div>'
            '</div>'
            '</div>'
        )
        result = expand_tabbed_content(html)
        assert "Content A" in result
        assert "Content B" in result
        assert '<input type="radio"' not in result


class TestHtmlToXhtml:
    def test_self_closing_br(self):
        result = html_to_xhtml("<p>line1<br>line2</p>")
        assert "<br/>" in result or "<br />" in result

    def test_self_closing_img(self):
        result = html_to_xhtml('<p><img src="test.png"></p>')
        assert "/>" in result

    def test_preserves_content(self):
        result = html_to_xhtml("<p>Hello &amp; world</p>")
        assert "Hello" in result
        assert "world" in result


class TestCollectImageRefs:
    def test_finds_img_tags(self):
        html = '<img src="images/fig1.png"><img src="images/fig2.jpg">'
        refs = collect_image_refs(html)
        assert "images/fig1.png" in refs
        assert "images/fig2.jpg" in refs

    def test_skips_mermaid_svgs(self):
        html = '<div class="mermaid-svg"><svg>...</svg></div><img src="real.png">'
        refs = collect_image_refs(html)
        assert "real.png" in refs
        assert len(refs) == 1

    def test_deduplicates(self):
        html = '<img src="a.png"><img src="a.png">'
        refs = collect_image_refs(html)
        assert len(refs) == 1
