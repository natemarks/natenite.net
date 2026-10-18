"""Guards for the poll page's HTML shell.

Purpose:
- Everything the page references must ship with it (a missing logo would
  only show up in a browser), and the page may load code and fonts only from
  places chosen on purpose.
- How the page looks is checked by eye, not here.
"""

from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest

from config.helper import PROJECT_ROOT

PAGE_DIR = PROJECT_ROOT / "site" / "polls"
# The main site's fonts are loaded the same way here, for a matching look.
FONT_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
MAIN_SITE = "natenite.net"


class _References(HTMLParser):
    """Collect (tag, attribute, url) for every link the page carries."""

    def __init__(self):
        super().__init__()
        self.found = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.images.append(attrs)
        for name in ("href", "src"):
            if name in attrs:
                self.found.append((tag, name, attrs[name]))


def _references():
    parser = _References()
    parser.feed((PAGE_DIR / "index.html").read_text(encoding="utf-8"))
    return parser


@pytest.mark.unit
def test_every_local_file_the_page_references_ships_with_it():
    """Same-origin links point at files in the page's folder."""
    local = [
        url
        for _, _, url in _references().found
        if not urlparse(url).netloc and not url.startswith("#")
    ]
    assert "/style.css" in local
    for url in local:
        assert (PAGE_DIR / url.lstrip("/")).is_file(), url


@pytest.mark.unit
def test_the_page_loads_code_and_styles_only_from_itself_and_the_fonts():
    """Scripts, stylesheets and images come from here or the font hosts."""
    for tag, _, url in _references().found:
        if tag == "a":
            continue
        host = urlparse(url).netloc
        assert host == "" or host in FONT_HOSTS, (tag, url)


@pytest.mark.unit
def test_links_that_leave_the_page_go_to_the_main_site():
    """The header and footer link out only to natenite.net."""
    links = [url for tag, _, url in _references().found if tag == "a"]
    assert links, "the header should link back to the main site"
    for url in links:
        parsed = urlparse(url)
        assert parsed.scheme == "https" and parsed.netloc == MAIN_SITE, url


@pytest.mark.unit
def test_images_have_alternative_text():
    """The logo is described for screen readers."""
    images = _references().images
    assert images
    for image in images:
        assert image.get("alt"), image
