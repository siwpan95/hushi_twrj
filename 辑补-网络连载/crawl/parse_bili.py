# -*- coding: utf-8 -*-
"""
解析 B 站专栏「胡适日记」连载 → markdown / index.json / 全集
从标题提取日期(1930.02.20 / 19301023 / 1933.06.16、18 等写法)
"""
import os
import re
import json
import datetime
import glob
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw", "articles")
MD = os.path.join(ROOT, "markdown")
os.makedirs(MD, exist_ok=True)


class Html2Text(HTMLParser):
    """专栏 HTML → 文本;<p>/<br> 换行,<img> 转占位,<figcaption> 作图片说明"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf = []
        self.skip = 0
        self.imgs = []
        self._cap = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
            return
        if tag == "p":
            self.buf.append("\n\n")
        elif tag == "br":
            self.buf.append("\n")
        elif tag == "img":
            src = d.get("src") or d.get("data-src")
            if src:
                self.imgs.append(src)
                self.buf.append(f"\n[[IMG:{src}]]\n")
        elif tag == "figcaption":
            self._cap = []
        elif tag in ("li", "div", "h1", "h2", "h3", "h4", "blockquote"):
            self.buf.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.buf.append("\n")
        elif tag == "img":
            src = dict(attrs).get("src") or dict(attrs).get("data-src")
            if src:
                self.imgs.append(src)
                self.buf.append(f"\n[[IMG:{src}]]\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag == "p":
            self.buf.append("\n")
        elif tag == "figcaption" and self._cap is not None:
            cap = "".join(self._cap).strip()
            if cap:
                self.buf.append(f"\n[图注] {cap}\n")
            self._cap = None
        elif tag in ("li", "h1", "h2", "h3", "h4", "blockquote", "div"):
            self.buf.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self._cap is not None:
            self._cap.append(data)
        else:
            self.buf.append(data)


def to_text(html: str):
    p = Html2Text()
    p.feed(html)
    p.close()
    raw = "".join(p.buf)
    raw = raw.replace("\u3000", "  ").replace("\xa0", " ").replace("　", "  ")
    out, blanks = [], 0
    for ln in [x.strip() for x in raw.split("\n")]:
        if not ln:
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(ln)
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out), p.imgs


# ---- 日期解析 ----
D1 = re.compile(r"(19\d{2})\s*[.\-年/]\s*(\d{1,2})\s*[.\-月/]\s*(\d{1,2})")
D2 = re.compile(r"(?<!\d)(19\d{2})(\d{2})(\d{2})(?!\d)")
# 只有年月（1938.11 / 1938年11月）→ 日补 0
D3 = re.compile(r"(19\d{2})\s*[.\-年/]\s*(\d{1,2})\s*[月/]?(?!\s*[.\-/]?\s*\d)")
# 只有年份（标题末尾的 1938）
D4 = re.compile(r"(?<!\d)(19\d{2})(?!\d)")


def parse_dates(title: str):
    """返回 [(y,m,d), ...]; 支持 1930.02.20 / 19301023 / 1933.06.16、18 /
    1938.11（日=0）/ 1938（月日=0）"""
    ds = []
    for m in D1.finditer(title):
        ds.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not ds:
        for m in D2.finditer(title):
            ds.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            break
    if not ds:
        for m in D3.finditer(title):
            ds.append((int(m.group(1)), int(m.group(2)), 0))
            break
    if not ds:
        for m in D4.finditer(title):
            ds.append((int(m.group(1)), 0, 0))
            break
    # 形如 "1933.06.16、18" → 补同年同月
    tail = re.search(r"(\d{4})\s*[.\-]\s*(\d{1,2})\s*[.\-]\s*(\d{1,2})\s*、\s*(\d{1,2})", title)
    if tail and ds:
        ds.append((int(tail.group(1)), int(tail.group(2)), int(tail.group(4))))
    # 去重保序
    seen, out = set(), []
    for d in ds:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def fmt_date(t):
    """(y,m,d) → '1930-02-20' / '1938-11'（无日） / '1938'（无月日） / ''"""
    if not t:
        return ""
    y, m, d = t
    if d:
        return f"{y:04d}-{m:02d}-{d:02d}"
    if m:
        return f"{y:04d}-{m:02d}"
    return f"{y:04d}"


def load_imgmap():
    """images/_map.json: {url: local_filename}; 不存在则图片降级为[插图]。
    正文里是协议相对 URL（//host/...），image_urls 里是 https://host/...，
    故同时登记两种写法，否则正文插图会全部降级。"""
    p = os.path.join(ROOT, "images", "_map.json")
    if not os.path.exists(p):
        return {}
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    m = {}
    for u, local in raw.items():
        m[u] = local
        for scheme in ("https:", "http:"):
            if u.startswith(scheme):
                m[u[len(scheme):]] = local   # //host/path
        if u.startswith("//"):
            m["https:" + u] = local
    return m


def render(body, imgmap):
    def rep(m):
        u = m.group(1)
        return f"![](../images/{imgmap[u]})" if u in imgmap else "[插图]"
    return re.sub(r"\[\[IMG:([^\]]+)\]\]", rep, body)


def main():
    files = sorted(glob.glob(os.path.join(RAW, "*.json")))
    print(f"raw 文章 {len(files)} 篇")
    imgmap = load_imgmap()
    if imgmap:
        print(f"图片映射 {len(imgmap)} 条")

    recs = []
    for f in files:
        r = json.load(open(f, encoding="utf-8"))
        title = (r.get("title") or "").strip()
        body, imgs = to_text(r.get("content") or "")
        ds = parse_dates(title)
        main_d = ds[0] if ds else None
        # 去掉标题里的日期尾巴，得到「事由」：从首个日期匹配的起点切掉
        subject = title
        for pat in (D1, D2, D3, D4):
            m = pat.search(title)
            if m:
                subject = title[:m.start()]
                break
        subject = subject.strip(" —-—·、")
        subject = re.sub(r"^胡适日记[—\-–]*", "", subject).strip()
        recs.append({
            "id": r["id"],
            "title": title,
            "subject": subject or title,
            "date": fmt_date(main_d),
            "dates": [fmt_date(x) for x in ds],
            "year": main_d[0] if main_d else None,
            "chars": len(re.sub(r"\s", "", body)),
            "images": imgs,
            "publish_time": r.get("publish_time"),
            "url": f"https://www.bilibili.com/read/cv{r['id']}",
            "body": body,
        })

    # 排序: 有日期的按日期, 无日期的排最后(按发布时间)
    recs.sort(key=lambda x: (x["date"] or "9999-99-99", x["date"] == "", x["id"]))

    for i, r in enumerate(recs, 1):
        r["seq"] = i

    # ---- 单篇 md ----
    for r in recs:
        slug = re.sub(r"[\\/:*?\"<>|]", "_", r["subject"])[:40]
        name = f"{r['seq']:03d}_{r['date'] or 'nodate'}_{slug}.md"
        with open(os.path.join(MD, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {r['title']}\n\n")
            f.write(f"> 辑补卷 · {r['date'] or '日期未标'}"
                    + (f"（另含 {', '.join(r['dates'][1:])}）" if len(r["dates"]) > 1 else "")
                    + f"　序号 {r['seq']} / {len(recs)}\n")
            f.write(f"> 来源（网络连载转抄，二手来源）：[{r['url']}]({r['url']})\n\n---\n\n")
            f.write(render(r["body"], imgmap))
            f.write("\n")

    # ---- 全集 md ----
    merged = os.path.join(ROOT, "胡适日记_辑补卷_网络连载.md")
    with open(merged, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 胡适日记 · 辑补卷（网络连载转抄）\n\n")
        f.write("> **来源性质说明**：本卷辑自 B 站专栏连载（readlist/rl692101），"
                "系网友据安徽教育出版社《胡适日记全编》转抄的**片段**，非原始文献。\n")
        f.write("> 存在自拟标题、节选、现代标点与可能的转抄讹误；**引用前请核对纸本**。\n")
        f.write(f"> 抓取日期：{datetime.datetime.now():%Y-%m-%d %H:%M}　共 {len(recs)} 条\n\n---\n\n")
        cur = None
        for r in recs:
            y = r["year"]
            if y != cur:
                cur = y
                n = sum(1 for x in recs if x["year"] == y)
                f.write(f"\n\n# {y if y else '日期未标'}年（{n} 条）\n\n")
            f.write(f"\n## {r['title']}\n\n")
            f.write(f"<sub>{r['date'] or '日期未标'}｜[原文]({r['url']})｜约 {r['chars']} 字</sub>\n\n")
            f.write(render(r["body"], imgmap))
            f.write("\n\n")

    # ---- txt ----
    txt = os.path.join(ROOT, "胡适日记_辑补卷_网络连载.txt")
    with open(txt, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("胡适日记 · 辑补卷（网络连载转抄）\n")
        f.write("来源：B 站专栏 readlist/rl692101（二手转抄，引用请核对纸本）\n")
        f.write("=" * 60 + "\n\n")
        cur = None
        for r in recs:
            if r["year"] != cur:
                cur = r["year"]
                f.write(f"\n\n{'#' * 40}\n# {cur or '日期未标'} 年\n{'#' * 40}\n\n")
            f.write(f"\n【{r['title']}】\n\n")
            f.write(re.sub(r"\[\[IMG:[^\]]+\]\]", "[插图]", r["body"]))
            f.write("\n\n" + "-" * 40 + "\n")

    # ---- index.json ----
    years = {}
    for r in recs:
        if r["year"]:
            years[str(r["year"])] = years.get(str(r["year"]), 0) + 1
    summary = {
        "crawled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": "胡适日记 · 辑补卷（网络连载转抄）",
        "source": "https://www.bilibili.com/read/readlist/rl692101",
        "source_note": "网友据安徽教育版《胡适日记全编》转抄片段，二手来源，非原始文献",
        "total": len(recs),
        "total_chars": sum(r["chars"] for r in recs),
        "by_year": dict(sorted(years.items())),
        "items": [{k: v for k, v in r.items() if k != "body"} for r in recs],
    }
    json.dump(summary, open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("\n===== 校验 =====")
    print(f"总条数 {len(recs)}　总字数 {summary['total_chars']}")
    print(f"年份分布 {summary['by_year']}")
    nodate = [r["seq"] for r in recs if not r["date"]]
    print(f"标题无日期: {len(nodate)} {nodate[:15]}")
    empty = [r["seq"] for r in recs if r["chars"] < 10]
    print(f"正文过短(<10字): {len(empty)} {empty[:15]}")
    withimg = sum(1 for r in recs if r["images"])
    print(f"含插图条目: {withimg}　图片总数: {sum(len(r['images']) for r in recs)}")
    return summary


if __name__ == "__main__":
    main()
