"""Headless self-check for 胡适日记 · 本地存档.

The project's only logic entry is ``crawl/build_all.py``: it merges every
``index.json`` + ``markdown/*.md`` into the single-file reader
``阅读器.html``.  Importing it would rewrite that 7 MB artifact, so this
self-check runs the real build script with its one output file redirected into
a temporary directory (the project copy is verified untouched afterwards) and
then checks the resulting payload against the source data.

Two shims are installed only for the duration of the build run:
  * ``open()`` on the reader path is redirected to a temp file, so the
    committed artifact is never touched;
  * ``glob.glob()`` answers this script's ``<seq>_*.md`` patterns from one
    cached ``listdir`` per directory.  The build calls glob once per item
    (4603 times) over a 2913-file directory, which costs ~30 s; the cached
    resolver returns the same candidate files and keeps the run well under
    the 30 s budget.

Run from the project root:  python selfcheck.py
"""
import builtins
import contextlib
import glob as globmod
import io
import json
import os
import re
import runpy
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_SCRIPT = os.path.join(ROOT, "crawl", "build_all.py")
READER = os.path.join(ROOT, "阅读器.html")

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (book id, directory, group key, image prefix, documented count, documented chars)
BOOKS = (
    ("lx", "1910-1917", "vol_label", "1910-1917/images/", 1006, 448391),
    ("tw", "1950-1953", "year", "1950-1953/images/", 235, 62630),
    ("bl", "辑补-网络连载", "year", "辑补-网络连载/images/", 69, 31586),
    ("oc", "全编OCR-1919-1949", "year", "", 2913, 1596966),
    ("oc2", "全编OCR-1954-1962", "year", "", 380, 229377),
)
BOOK_NAME = {
    "lx": "留学日记（1910—1917）",
    "tw": "晚年日记（1950—1953）",
    "bl": "辑补卷（网络连载）",
    "oc": "全编 OCR（1919—1949）",
    "oc2": "全编 OCR（1954—1962）",
}
TAG_RE = re.compile(r"</?(?:p|div|span|br|figure|img|figcaption)\b")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
DATA_RE = re.compile(
    r'<script id="DATA" type="application/json">(.*?)</script>', re.S)
CHECK_NAMES = ("source index", "build payload", "bodies round trip",
               "html round trip", "images and leftovers")


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def load_index(book_dir):
    path = os.path.join(ROOT, book_dir, "index.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["items"]


def source_candidates(table, seq, date):
    """File names build_all.load() would consider for one item."""
    names = table.get(f"{seq:03d}")
    if not names and date:
        names = table.get(str(date))
    return names or []


def run_build():
    """Execute crawl/build_all.py with 阅读器.html redirected to a temp file."""
    stat_before = os.stat(READER) if os.path.exists(READER) else None
    captured = io.StringIO()
    real_open = builtins.open
    real_glob = globmod.glob
    cache = {}

    def fast_glob(pattern):
        directory, name = os.path.split(pattern)
        if name.endswith("_*.md"):
            prefix = name[:-len("*.md")]
            if directory not in cache:
                table = {}
                try:
                    for entry in os.listdir(directory):
                        if entry.endswith(".md") and "_" in entry:
                            table.setdefault(
                                entry.split("_", 1)[0] + "_", []).append(entry)
                except OSError:
                    return real_glob(pattern)
                cache[directory] = table
            return [os.path.join(directory, entry)
                    for entry in cache[directory].get(prefix, [])]
        return real_glob(pattern)

    with tempfile.TemporaryDirectory() as tmp:
        temp_html = os.path.join(tmp, "阅读器.html")

        def guarded_open(file, mode="r", *args, **kwargs):
            try:
                is_reader = os.path.abspath(os.fspath(file)) == READER
            except TypeError:
                is_reader = False
            if is_reader and any(ch in mode for ch in "wax+"):
                return real_open(temp_html, mode, *args, **kwargs)
            return real_open(file, mode, *args, **kwargs)

        builtins.open = guarded_open
        globmod.glob = fast_glob
        try:
            with contextlib.redirect_stdout(captured):
                namespace = runpy.run_path(BUILD_SCRIPT, run_name="__main__")
        finally:
            builtins.open = real_open
            globmod.glob = real_glob
        with open(temp_html, encoding="utf-8") as fh:
            built_html = fh.read()

    stat_after = os.stat(READER) if os.path.exists(READER) else None
    _check(stat_before == stat_after,
           "the real 阅读器.html was modified by the build run")
    return namespace, built_html, captured.getvalue()


def check_source_index():
    """index.json ↔ markdown coverage, dense seq numbering, sane metadata."""
    for book_id, book_dir, group_key, _prefix, count, _chars in BOOKS:
        items = load_index(book_dir)
        _check(len(items) == count,
               f"{book_id}: index has {len(items)} items, documented {count}")
        seqs = [it["seq"] for it in items]
        _check(seqs == sorted(seqs) and len(set(seqs)) == count,
               f"{book_id}: seq values are not {count} ascending unique numbers")
        _check(max(seqs) - min(seqs) + 1 == count,
               f"{book_id}: seq range {min(seqs)}-{max(seqs)} has gaps")
        markdown_dir = os.path.join(ROOT, book_dir, "markdown")
        names = os.listdir(markdown_dir)
        by_seq = {int(m.group(1)) for m in
                  (re.match(r"^(\d+)_", n) for n in names) if m}
        by_date = {m.group(1) for m in
                   (re.match(r"^(\d{4}-\d{2}-\d{2})_", n) for n in names) if m}
        missing = [it["seq"] for it in items
                   if it["seq"] not in by_seq
                   and not (it.get("date") and it["date"] in by_date)]
        _check(not missing,
               f"{book_id}: {len(missing)} items have no markdown, e.g. {missing[:3]}")
        for item in items:
            _check(item.get("title"), f"{book_id}-{item['seq']}: empty title")
            _check("chars" in item and int(item["chars"]) >= 0,
                   f"{book_id}-{item['seq']}: missing/negative chars count")
            if group_key == "year":
                _check("year" in item,
                       f"{book_id}-{item['seq']}: missing year group")


def markdown_table(book_dir):
    """prefix -> [file names] from one listdir, matching build_all's patterns."""
    directory = os.path.join(ROOT, book_dir, "markdown")
    table = {}
    for entry in os.listdir(directory):
        if entry.endswith(".md") and "_" in entry:
            table.setdefault(entry.split("_", 1)[0], []).append(entry)
    return directory, table


def body_of(directory, entry, img_prefix):
    with open(os.path.join(directory, entry), encoding="utf-8") as fh:
        text = fh.read()
    body = text.split("---\n", 1)[1].strip() if "---\n" in text else text
    return body.replace("../images/", img_prefix)


def check_payload(namespace):
    """build_all payload aggregates, ordering and group normalisation."""
    payload = namespace["payload"]
    items = payload["items"]
    _check([b["id"] for b in payload["books"]] == ["lx", "oc", "bl", "tw", "oc2"],
           f"unexpected book order: {[b['id'] for b in payload['books']]}")
    total_chars = 0
    for book_id, book_dir, _group_key, _prefix, count, chars in BOOKS:
        index_items = load_index(book_dir)
        book = next(b for b in payload["books"] if b["id"] == book_id)
        _check(book["count"] == count,
               f"{book_id}: book count {book['count']} != {count}")
        _check(book["chars"] == chars,
               f"{book_id}: book chars {book['chars']} != documented {chars}")
        index_chars = sum(it["chars"] for it in index_items)
        _check(book["chars"] == index_chars,
               f"{book_id}: book chars {book['chars']} != index sum {index_chars}")
        total_chars += book["chars"]
        book_items = [it for it in items if it["id"].startswith(book_id + "-")]
        _check(len(book_items) == count,
               f"{book_id}: payload carries {len(book_items)} items != {count}")
        for it in book_items:
            _check(it["book"] == BOOK_NAME[book_id],
                   f"{it['id']}: wrong book label {it['book']!r}")
            _check(bool(it["title"]), f"{it['id']}: empty title")
            _check(isinstance(it["body"], str), f"{it['id']}: body is not text")
            _check("url" in it, f"{it['id']}: missing url")
            _check(it["chars"] >= 0, f"{it['id']}: negative chars")
            if book_id == "lx":
                _check(bool(it["group"]), f"{it['id']}: empty vol group")
            else:
                _check(it["group"].endswith("年") or it["group"] == "日期未标",
                       f"{it['id']}: bad group {it['group']!r}")

    _check(len(items) == sum(b[4] for b in BOOKS),
           f"payload has {len(items)} items")
    _check(sum(it["chars"] for it in items) == total_chars,
           "item chars do not add up to the book chars")
    _check(total_chars == 2368950,
           f"total chars {total_chars} != documented 2368950")
    ids = [it["id"] for it in items]
    _check(len(set(ids)) == len(ids), "duplicate item ids in the payload")
    nonempty = sum(1 for it in items if it["body"].strip())
    _check(nonempty >= len(items) - 50,
           f"only {nonempty}/{len(items)} bodies carry text")

    index_titles = {b[0]: {it["seq"]: it["title"]
                           for it in load_index(b[1])} for b in BOOKS}
    for book_id in ("oc", "oc2"):
        rows = [(it["year"] or 9999, it["seq"])
                for it in items if it["id"].startswith(book_id + "-")]
        _check(rows == sorted(rows), f"{book_id}: items are not year/seq sorted")
        for it in (it for it in items if it["id"].startswith(book_id + "-")):
            title = index_titles[book_id].get(it["seq"])
            _check(title is not None and it["title"].startswith(title),
                   f"{it['id']}: title does not start with the index title")
    _check(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
                    payload["crawled_at"]) is not None,
           f"bad crawled_at: {payload['crawled_at']!r}")
    return payload


def check_html_round_trip(payload, html):
    """The payload embedded in the generated HTML parses back unchanged."""
    _check('__DATA__' not in html, "unreplaced __DATA__ placeholder")
    _check('__CRAWL__' not in html, "unreplaced __CRAWL__ placeholder")
    _check("胡适日记 · 离线阅读器" in html, "generated HTML lost its title")
    match = DATA_RE.search(html)
    _check(match is not None, "generated HTML has no DATA block")
    parsed = json.loads(match.group(1))
    _check(parsed == payload, "DATA block does not round-trip to the payload")
    _check(len(parsed["items"]) == len(payload["items"]),
           f"DATA block carries {len(parsed['items'])} items")
    _check(len(html.encode("utf-8")) > 3_000_000,
           "generated HTML is suspiciously small")


def check_bodies_and_images(payload):
    """Every payload body is the markdown body of its source; images resolve."""
    items = payload["items"]
    index_dates = {b[0]: {it["seq"]: it.get("date")
                          for it in load_index(b[1])} for b in BOOKS}
    verified = 0
    for book_id, book_dir, _group_key, prefix, _count, _chars in BOOKS:
        directory, table = markdown_table(book_dir)
        cache = {}
        for item in (it for it in items if it["id"].startswith(book_id + "-")):
            date = index_dates[book_id].get(item["seq"])
            candidates = source_candidates(table, item["seq"], date)
            _check(candidates,
                   f"{item['id']}: no markdown source for seq/date")
            bodies = set()
            for entry in candidates:
                if entry not in cache:
                    cache[entry] = body_of(directory, entry, prefix)
                bodies.add(cache[entry])
            _check(item["body"] in bodies,
                   f"{item['id']}: body is not derived from its markdown source")
            verified += 1
    _check(verified == len(items),
           f"verified {verified} bodies, payload has {len(items)}")

    refs = set()
    bodies = []
    for item in items:
        bodies.append(item["body"])
        for ref in IMG_RE.findall(item["body"]):
            if "/images/" in ref or ref.startswith("images/"):
                refs.add(ref)
    _check(len(refs) > 0, "no image references found in the payload")
    image_dirs = ["1910-1917/images", "1950-1953/images", "辑补-网络连载/images"]
    missing = []
    for ref in refs:
        if os.path.exists(os.path.join(ROOT, ref)):
            continue
        name = ref.split("/")[-1]
        if any(os.path.exists(os.path.join(ROOT, d, name)) for d in image_dirs):
            continue
        missing.append(ref)
    _check(not missing,
           f"{len(missing)} image refs unresolved, e.g. {missing[:3]}")

    joined = "".join(bodies)
    leaked = len(TAG_RE.findall(joined))
    _check(leaked == 0, f"{leaked} unparsed HTML tags left in bodies")
    _check("[[IMG:" not in joined, "unrendered [[IMG:]] placeholder left")


def main():
    try:
        check_source_index()
    except AssertionError as exc:
        print(f"FAIL: source data: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - report any unexpected error
        print(f"FAIL: source data: {type(exc).__name__}: {exc}")
        return 1

    try:
        namespace, html, captured = run_build()
    except AssertionError as exc:
        print(f"FAIL: build run: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: build run: {type(exc).__name__}: {exc}")
        return 1
    if "payload" not in namespace:
        print("FAIL: build run: script produced no payload")
        return 1

    payload = namespace["payload"]
    try:
        check_payload(namespace)
        check_html_round_trip(payload, html)
        check_bodies_and_images(payload)
    except AssertionError as exc:
        print(f"FAIL: build output: {exc}")
        print("--- build log ---")
        print(captured.strip())
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: build output: {type(exc).__name__}: {exc}")
        return 1

    print("selfcheck ok: " + ", ".join(CHECK_NAMES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
