#!/usr/bin/env python3
"""
Kontrolisana dorada stranice public-activity/index.html.

Podrazumevana upotreba iz korena repozitorijuma:
    python scripts/update_public_activity_page.py

Rezultat:
    public-activity/index.updated.html

Direktna zamena uz rezervnu kopiju:
    python scripts/update_public_activity_page.py --in-place
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path


REQUIRED_IDS = {
    "top",
    "main-content",
    "newspaper-articles",
    "serials",
    "interviews",
    "online-articles",
    "av-interviews",
    "public-appearances",
}

SECTION_DESCRIPTIONS = {
    "newspaper-articles": (
        "This section contains a selection of newspaper and popular-history articles "
        "published in daily, weekly and periodical press."
    ),
    "serials": (
        "This section presents serialised newspaper texts and thematic series published "
        "in successive instalments."
    ),
    "interviews": (
        "This section contains selected print and online interviews devoted to history, "
        "cultural heritage, museum work and public debates about the past."
    ),
    "online-articles": (
        "This section lists texts available in online editions and on web portals; "
        "printed versions are recorded separately under Newspaper Articles."
    ),
    "av-interviews": (
        "This section contains television, video, radio and podcast appearances, grouped "
        "by medium while preserving the permanent section anchor."
    ),
    "public-appearances": (
        "This section presents selected conference papers, public lectures, book "
        "presentations, exhibition openings and other professional appearances."
    ),
}

NEW_STYLE = r"""  <style>
    :root {
      --text: #111;
      --muted: #555;
      --line: #dedede;
      --link: #0645ad;
      --link-hover: #04357f;
      --card-background: #eeeeee;
      --card-border: #d2d2d2;
      --soft-background: #f8f8f8;
    }

    * { box-sizing: border-box; }

    html {
      background: #fff;
      scroll-behavior: smooth;
    }

    body {
      max-width: 980px;
      margin: 0 auto;
      padding: 42px 28px 30px;
      color: var(--text);
      background: #fff;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 17px;
      line-height: 1.58;
    }

    h1, h2, h3 {
      color: var(--text);
      line-height: 1.25;
    }

    h1 {
      margin: 0 0 .08em;
      font-size: 2.05rem;
    }

    h2 {
      margin: 0 0 .85rem;
      padding: 0 0 .32rem;
      border-bottom: 1px solid var(--line);
      font-size: 1.45rem;
    }

    h3 {
      margin: 1.25rem 0 .45rem;
      font-size: 1.08rem;
    }

    p { margin: .68rem 0; }
    ol, ul { padding-left: 1.4rem; }
    li { margin: .42rem 0; }

    a {
      color: var(--link);
      text-decoration: none;
      text-underline-offset: .15em;
    }

    a:hover,
    a:focus-visible {
      color: var(--link-hover);
      text-decoration: underline;
    }

    section[id] { scroll-margin-top: 1rem; }

    .skip-link {
      position: absolute;
      left: 1rem;
      top: -5rem;
      z-index: 1000;
      padding: .55rem .75rem;
      border: 2px solid var(--link);
      color: #fff;
      background: var(--link);
    }

    .skip-link:focus {
      top: 1rem;
      color: #fff;
    }

    .page-header {
      padding-bottom: 1.1rem;
      border-bottom: 1px solid var(--line);
    }

    .back-link {
      margin: 0 0 1.1rem;
      font-size: .94rem;
    }

    .name-latin {
      margin: .18rem 0;
      color: var(--muted);
      font-size: 1rem;
    }

    .subtitle {
      margin: .45rem 0 0;
      color: #444;
      font-size: 1rem;
    }

    .intro {
      margin: 1.35rem 0;
      padding: 1.05rem 1.15rem;
      border-left: 4px solid #bbb;
      background: var(--soft-background);
    }

    .intro p { margin: .35rem 0; }

    .contents {
      margin: 1.35rem 0 1.75rem;
      padding: 1rem 1.15rem;
      border: 1px solid var(--card-border);
      background: var(--card-background);
    }

    .contents h2 {
      margin-top: 0;
      border-bottom-color: #c8c8c8;
      font-size: 1.2rem;
    }

    .contents ol {
      columns: 2;
      column-gap: 2.5rem;
      margin-bottom: 0;
      padding-left: 1.35rem;
    }

    .contents li {
      break-inside: avoid;
      margin-bottom: .4rem;
    }

    .public-activity-section {
      padding: 1.45rem 0;
      border-top: 1px solid var(--line);
    }

    .public-activity-section > p {
      margin-bottom: .55rem;
    }

    .section-description-en {
      color: var(--muted);
      font-size: .95rem;
    }

    .public-activity-section details {
      margin: 1rem 0 1.35rem;
      padding: .85rem 1rem;
      border: 1px solid var(--card-border);
      background: #fbfbfb;
    }

    .public-activity-section summary {
      cursor: pointer;
      color: var(--text);
      font-weight: bold;
    }

    .public-activity-section details ol {
      margin: 1rem 0 .3rem;
      padding-left: 1.45rem;
    }

    .public-activity-section details li {
      margin-bottom: .8rem;
      overflow-wrap: anywhere;
    }

    .public-activity-section details ol ol {
      margin: .6rem 0;
    }

    .back-to-top {
      margin: .8rem 0 0;
      font-size: .9rem;
      text-align: right;
    }

    .site-links {
      margin: 2rem 0 0;
      padding: 1rem 0;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }

    .site-links p {
      display: flex;
      flex-wrap: wrap;
      gap: .35rem 1rem;
      margin: 0;
    }

    footer {
      margin-top: 1rem;
      color: #444;
      font-size: .9rem;
    }

    @media (max-width: 720px) {
      body {
        padding: 24px 18px;
        font-size: 16px;
      }

      .contents ol { columns: 1; }
      .intro, .contents, .public-activity-section details { padding: .9rem; }
      .site-links p { display: block; }
      .site-links a { display: block; margin: .28rem 0; }
    }

    @media print {
      body {
        max-width: none;
        margin: 0;
        padding: 0;
      }

      details { display: block; }
      details > * { display: block; }
      a { color: #111; text-decoration: underline; }
    }
  </style>"""

NEW_HEADER = r"""<body id="top">
  <a class="skip-link" href="#main-content">Пређи на главни садржај / Skip to main content</a>

  <header class="page-header">
    <p class="back-link"><a href="/">← Главна страна / Main Page</a></p>
    <h1>Јавни рад</h1>
    <p class="name-latin" lang="en-GB">Public Activity</p>
    <p class="subtitle">
      Новински текстови, интервјуи, јавни наступи и јавна тумачења историје<br>
      <span lang="en-GB">Newspaper articles, interviews, public appearances and public interpretations of history</span>
    </p>
  </header>

  <main id="main-content">
    <section class="intro" aria-label="Увод / Introduction">
      <p>
        Јавни рад обухвата новинске и интернет текстове, фељтоне, интервјуе,
        телевизијска, радијска и подкаст гостовања, јавна предавања, промоције,
        представљања публикација, отварања изложби и друге облике јавног тумачења
        историје, културног наслеђа и музејског рада. Страна је организована према
        облику јавног рада, а дужи спискови смештени су у отвориве целине са сталним
        сидреним везама.
      </p>
      <p lang="en-GB">
        Public activity includes newspaper and online articles, serialised texts,
        interviews, television, radio and podcast appearances, public lectures,
        book presentations, exhibition openings and other forms of public interpretation
        of history, cultural heritage and museum work. Longer lists are placed in
        expandable sections with stable anchor links.
      </p>
    </section>

"""

NEW_SITE_LINKS_AND_FOOTER = r"""    <nav class="site-links" aria-label="Везе ка другим деловима сајта / Links to other site sections">
      <p>
        <a href="/">Главна страна / Main Page</a>
        <a href="/bibliography/">Библиографија / Bibliography</a>
        <a href="/knowledge-graph/">Граф знања / Knowledge Graph</a>
        <a href="/data/">Подаци / Data</a>
        <a href="/knowledge-graph/research/local-modernity-symbolic-power.html">Истраживачки оквир / Research Framework</a>
      </p>
    </nav>
  </main>

  <footer>
    <p>Последње ажурирање / Last updated: 24. јул 2026 / 24 July 2026.</p>
  </footer>
</body>"""


class AuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.jsonld_blocks: list[list[str]] = []
        self._in_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"] or "")
        if tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True
            self.jsonld_blocks.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld and self.jsonld_blocks:
            self.jsonld_blocks[-1].append(data)


def replace_once(source: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, source, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(
            f"Neuspešna zamena: {label} (očekivano 1, pronađeno {count})"
        )
    return updated


def update_page(source: str) -> tuple[str, int]:
    source = source.replace('<html lang="sr">', '<html lang="sr-Cyrl">', 1)
    source = source.replace('lang="en"', 'lang="en-GB"')

    source = replace_once(
        source,
        r"\s*<style>.*?</style>\s*<style>.*?</style>",
        NEW_STYLE,
        "CSS blokovi",
        flags=re.S,
    )

    source, item_count = re.subn(
        r'\s*"numberOfItems"\s*:\s*\d+\s*,',
        "",
        source,
        count=1,
    )
    if item_count != 1:
        raise RuntimeError("Nije pronađen tačno jedan JSON-LD numberOfItems.")

    source, json_name_count = re.subn(
        r'("name"\s*:\s*)"Аудио-визуелни и радио интервјуи / '
        r'Audiovisual and Radio Interviews"',
        r'\1"ТВ, радио и подкаст / TV, Radio and Podcast"',
        source,
        count=1,
    )
    if json_name_count != 1:
        raise RuntimeError(
            "Nije pronađen tačno jedan stari naziv pete grupe u JSON-LD-u."
        )

    source = replace_once(
        source,
        r'<body id="top">.*?(?=<nav class="contents")',
        NEW_HEADER,
        "zaglavlje i uvod",
        flags=re.S,
    )

    source = replace_once(
        source,
        r'(<section id="av-interviews" class="public-activity-section">\s*<h2>).*?(</h2>)',
        r'\1ТВ, радио и подкаст / TV, Radio and Podcast\2',
        "naslov odeljka av-interviews",
        flags=re.S,
    )

    for section_id, description in SECTION_DESCRIPTIONS.items():
        marker = f'class="section-description-en" data-section="{section_id}"'
        if marker in source:
            continue
        pattern = (
            rf'(<section id="{re.escape(section_id)}" class="public-activity-section">'
            rf'\s*<h2>.*?</h2>\s*<p>.*?</p>)'
        )
        addition = (
            r'\1'
            + f'\n  <p lang="en-GB" class="section-description-en" '
              f'data-section="{section_id}">{description}</p>'
        )
        source = replace_once(
            source,
            pattern,
            addition,
            f"engleski opis odeljka {section_id}",
            flags=re.S,
        )

    url_pattern = re.compile(
        r'<a(?P<attrs>\s+[^>]*href="https?://[^"]+"[^>]*)>'
        r'(?P<label>https?://[^<]+)</a>',
        flags=re.I,
    )

    def shorten_url(match: re.Match[str]) -> str:
        return f'<a{match.group("attrs")}>Прочитај текст / Read online</a>'

    source, shortened = url_pattern.subn(shorten_url, source)

    source = replace_once(
        source,
        r'\s*<nav class="site-links".*?</nav>\s*</main>\s*</body>',
        NEW_SITE_LINKS_AND_FOOTER,
        "donja navigacija i footer",
        flags=re.S,
    )

    return source, shortened


def validate_result(source: str) -> None:
    parser = AuditParser()
    parser.feed(source)

    missing = sorted(REQUIRED_IDS - set(parser.ids))
    if missing:
        raise RuntimeError("Nedostaju obavezna sidra: " + ", ".join(missing))

    duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
    if duplicates:
        raise RuntimeError("Duplirana sidra: " + ", ".join(duplicates))

    for block_no, parts in enumerate(parser.jsonld_blocks, start=1):
        payload = "".join(parts).strip()
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Neispravan JSON-LD blok {block_no}: {exc}") from exc

    id_set = set(parser.ids)
    broken_fragments = sorted(
        href
        for href in parser.hrefs
        if href.startswith("#") and href[1:] not in id_set
    )
    if broken_fragments:
        raise RuntimeError(
            "Lokalne veze vode ka nepostojećim sidrima: "
            + ", ".join(broken_fragments)
        )

    if len(re.findall(r"<h1\b", source, re.I)) != 1:
        raise RuntimeError("Strana mora imati tačno jedan h1.")

    if "numberOfItems" in source:
        raise RuntimeError("numberOfItems nije uklonjen.")

    if "ТВ, радио и подкаст / TV, Radio and Podcast" not in source:
        raise RuntimeError("Nije usklađen naziv TV/radio/podkast odeljka.")

    if "Последње ажурирање / Last updated:" not in source:
        raise RuntimeError("Nedostaje vidljiv datum poslednjeg ažuriranja.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source",
        nargs="?",
        default="public-activity/index.html",
        help="Putanja do aktuelnog HTML fajla.",
    )
    parser.add_argument(
        "--output",
        default="public-activity/index.updated.html",
        help="Izlazni fajl kada se ne koristi --in-place.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Zameni izvorni fajl i napravi .bak rezervnu kopiju.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"GREŠKA: fajl ne postoji: {source_path}", file=sys.stderr)
        return 1

    original = source_path.read_text(encoding="utf-8")
    try:
        updated, shortened = update_page(original)
        validate_result(updated)
    except RuntimeError as exc:
        print(f"GREŠKA: {exc}", file=sys.stderr)
        return 1

    if args.in_place:
        backup = source_path.with_suffix(source_path.suffix + ".bak")
        shutil.copy2(source_path, backup)
        output_path = source_path
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(updated, encoding="utf-8")

    print(f"Napravljen fajl: {output_path}")
    if args.in_place:
        print(f"Rezervna kopija: {backup}")
    print(f"Skraćeno vidljivih punih URL adresa: {shortened}")
    print("Sidra, JSON-LD i lokalne veze ka sidrima: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
