import os
import re
import html
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import markdown
import bleach

SITE_NAME = "Window Service Journal"
SITE_URL = "https://window-service-journal-cloudflare.pages.dev"
REPOSITORY = os.environ.get(
    "GITHUB_REPOSITORY",
    "emmabrown121003-svg/window-service-journal-cloudflare"
)
TOKEN = os.environ.get("GITHUB_TOKEN", "")

OUTPUT = Path("site")
ARTICLES = OUTPUT / "articles"

OUTPUT.mkdir(parents=True, exist_ok=True)
ARTICLES.mkdir(parents=True, exist_ok=True)

# Distinctive visual identity for Window Service Journal
CSS = """
:root {
  --ink: #233b43;
  --teal: #276e75;
  --cream: #f8f6ef;
  --gold: #d5a45f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--cream);
  color: var(--ink);
  font-family: Georgia, serif;
  line-height: 1.75;
}
header {
  background: #fff;
  border-bottom: 1px solid #e6e8e3;
}
nav {
  max-width: 1080px;
  margin: auto;
  padding: 22px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}
.brand {
  color: var(--ink);
  font-size: 24px;
  font-weight: bold;
  text-decoration: none;
}
nav a { color: var(--ink); text-decoration: none; }
nav .links { display: flex; gap: 24px; }
.hero {
  background: linear-gradient(120deg, #234b55, #43817b);
  color: white;
  padding: 105px 24px;
}
.wrap { max-width: 1080px; margin: auto; }
.hero h1 {
  font-size: clamp(38px, 6vw, 68px);
  line-height: 1.12;
  max-width: 850px;
}
.hero p { max-width: 720px; font-size: 20px; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 3px;
  color: #f0c58b;
  font: bold 13px Arial, sans-serif;
}
main { max-width: 1080px; margin: auto; padding: 65px 24px; }
h2 { font-size: 34px; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
  gap: 25px;
}
.card {
  background: white;
  border: 1px solid #e5e8e3;
  border-top: 4px solid var(--gold);
  padding: 26px;
}
.card h3 { margin-top: 0; }
.card a, article a { color: var(--teal); }
article {
  background: white;
  padding: clamp(24px, 5vw, 60px);
  max-width: 850px;
  margin: auto;
  overflow-wrap: anywhere;
}
article img { max-width: 100%; height: auto; }
article h1 { font-size: clamp(32px, 5vw, 50px); line-height: 1.2; }
article pre { overflow-x: auto; }
article blockquote {
  border-left: 4px solid var(--gold);
  padding-left: 20px;
}
.meta { color: #66757a; font: 14px Arial, sans-serif; }
footer {
  background: #203c44;
  color: white;
  text-align: center;
  padding: 30px 20px;
  font: 14px Arial, sans-serif;
}
@media(max-width:600px) {
  nav { flex-direction: column; }
  .hero { padding: 70px 24px; }
}
"""

def escape(value):
    return html.escape(str(value or ""), quote=True)

def page(title, description, content, canonical):
    title = escape(title)
    description = escape(description[:160])
    canonical = escape(canonical)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<style>{CSS}</style>
</head>
<body>
<header>
<nav>
<a class="brand" href="/">Window Service Journal</a>
<div class="links">
<a href="/">Home</a>
<a href="/#articles">Articles</a>
</div>
</nav>
</header>
{content}
<footer>© {datetime.now(timezone.utc).year} Window Service Journal.
Practical knowledge for better windows and everyday comfort.</footer>
</body>
</html>"""

def fetch_issues():
    url = f"https://api.github.com/repos/{REPOSITORY}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    result = []
    page_number = 1
    while True:
        response = requests.get(
            url,
            headers=headers,
            params={
                "state": "open",
                "per_page": 100,
                "page": page_number
            },
            timeout=30
        )
        response.raise_for_status()
        batch = response.json()
        result.extend(
            item for item in batch if "pull_request" not in item
        )
        if len(batch) < 100:
            break
        page_number += 1
    return result

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "b", "i", "a",
    "h1", "h2", "h3", "h4", "ul", "ol", "li",
    "blockquote", "code", "pre", "hr", "img",
    "table", "thead", "tbody", "tr", "th", "td"
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"]
}

def clean_content(body):
    rendered = markdown.markdown(
        body or "",
        extensions=["extra", "sane_lists"]
    )
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True
    )

def excerpt(body, length=155):
    plain = re.sub(r"<[^>]+>", " ", body or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:length].rstrip()

issues = fetch_issues()
issues.sort(
    key=lambda item: item.get("created_at", ""),
    reverse=True
)

# Remove stale generated articles.
for old_file in ARTICLES.glob("issue-*.html"):
    old_file.unlink()

cards = []
sitemap_urls = [SITE_URL + "/"]

for issue in issues:
    number = issue["number"]
    title = issue.get("title") or "Untitled Article"
    body = issue.get("body") or ""
    date = (issue.get("created_at") or "")[:10]
    filename = f"issue-{number}.html"
    article_url = f"{SITE_URL}/articles/{filename}"

    content_html = clean_content(body)
    description = excerpt(body) or title

    article_content = f"""
<main>
<article>
<p class="meta">{escape(date)}</p>
<h1>{escape(title)}</h1>
{content_html}
</article>
</main>"""

    (ARTICLES / filename).write_text(
        page(
            f"{title} | {SITE_NAME}",
            description,
            article_content,
            article_url
        ),
        encoding="utf-8"
    )

    cards.append(f"""
<div class="card">
<p class="meta">{escape(date)}</p>
<h3><a href="/articles/{filename}">{escape(title)}</a></h3>
<p>{escape(description)}</p>
<a href="/articles/{filename}">Read article →</a>
</div>""")

    sitemap_urls.append(article_url)

cards_html = "\n".join(cards) if cards else (
    "<p>No articles published yet.</p>"
)

homepage = f"""
<section class="hero">
<div class="wrap">
<p class="eyebrow">Window service & home improvement</p>
<h1>Practical Window Knowledge for Every Home</h1>
<p>Discover useful guides on window repairs, glass care,
hardware maintenance, and keeping your home comfortable
through every season.</p>
</div>
</section>
<main id="articles">
<h2>Latest Articles</h2>
<div class="cards">{cards_html}</div>
</main>"""

(OUTPUT / "index.html").write_text(
    page(
        SITE_NAME + " | Window Care & Repair Guides",
        "Window Service Journal shares practical information "
        "about window repair, glass care, hardware and maintenance.",
        homepage,
        SITE_URL + "/"
    ),
    encoding="utf-8"
)

(OUTPUT / "robots.txt").write_text(
    "User-agent: *\nAllow: /\n"
    f"Sitemap: {SITE_URL}/sitemap.xml\n",
    encoding="utf-8"
)

sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap += (
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
)
for url in sitemap_urls:
    sitemap += f"  <url><loc>{escape(url)}</loc></url>\n"
sitemap += "</urlset>\n"

(OUTPUT / "sitemap.xml").write_text(
    sitemap,
    encoding="utf-8"
)

print(f"Generated {len(issues)} articles for {SITE_NAME}")
