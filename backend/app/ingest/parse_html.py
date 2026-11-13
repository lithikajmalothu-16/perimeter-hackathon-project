"""HTML -> clean page text + same-domain links (for index sources, depth 1)."""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

WS = re.compile(r"[ \t\r\f\v]+")


def normalize(text: str) -> str:
    """The text the evidence check runs against: collapsed spaces, straight quotes, lowercase."""
    t = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def parse(html: str, base_url: str) -> tuple[str, list[str], str]:
    """Returns (clean_text, same_domain_links, title)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe", "form", "header", "footer", "nav"]):
        t.decompose()
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:160]
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "dt", "dd", "a", "span", "div"], recursive=True):
        if el.find(["p", "li", "h1", "h2", "h3", "div"]):   # only leaf-ish blocks, avoids duplicate text
            continue
        t = WS.sub(" ", el.get_text(" ", strip=True))
        if len(t) > 2 and (not lines or lines[-1] != t):
            lines.append(t)
    text = "\n".join(lines)
    host = urlparse(base_url).hostname
    links = []
    for a in main.find_all("a", href=True):
        u = urljoin(base_url, a["href"]).split("#")[0]
        if urlparse(u).hostname == host and u.startswith("http") and u != base_url and not re.search(r"\.(pdf|jpg|png|docx?|zip)$", u, re.I):
            links.append(u)
    return text, list(dict.fromkeys(links)), title
