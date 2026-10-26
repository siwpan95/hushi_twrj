# -*- coding: utf-8 -*-
"""
胡适留学日记(1910-1917) 解析器 —— 零依赖
体例: 卷一~卷十七 + 序跋附录; 条目以"卷X 一、标题"命名
输出: markdown/, 胡适留学日记_1910-1917_全集.md, index.json
"""
import os
import re
import json
import datetime
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
MD = os.path.join(ROOT, "markdown")
os.makedirs(MD, exist_ok=True)

VOLUMES = [("lx", "https://www.xuges.com/xdmj/hushi/lx/"),
           ("lx2", "https://www.xuges.com/xdmj/hushi/lx2/"),
           ("lx3", "https://www.xuges.com/xdmj/hushi/lx3/"),
           ("lx4", "https://www.xuges.com/xdmj/hushi/lx4/")]

CN = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
      "八": 8, "九": 9, "十": 10}
CN_YEAR = {"〇": 0, "０": 0}


def cn2int(s: str):
    """中文数字 → int, 支持 一~九十九; 失败返回 None"""
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        hi = CN.get(a, 1) if a else 1
        lo = CN.get(b, 0) if b else 0
        return (hi if a else 1) * 10 + lo
    total, ok = 0, True
    for ch in s:
        if ch in CN:
            total = total * 10 + CN[ch] if total else CN[ch]
        else:
            ok = False
            break
    return total if ok else None


def cn_year(s: str):
    """中文年份如 一九一一 → 1911"""
    if not s:
        return None
    digits = "".join(str(CN.get(c, "")) if c in CN else ("" if c in "年" else None) for c in s)
    if digits is None or not digits.isdigit():
        return None
    return int(digits) if len(digits) == 4 else None


class CellExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells, self.cur, self.skip = [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        if tag == "td":
            self.cur = {"cls": (dict(attrs).get("class") or "").strip(),
                        "buf": [], "imgs": []}
            return
        if self.cur is None or self.skip:
            return
        d = dict(attrs)
        if tag == "br":
            self.cur["buf"].append("\n")
        elif tag in ("p", "div", "tr", "li"):
            self.cur["buf"].append("\n")
        elif tag == "img" and d.get("src"):
            self.cur["imgs"].append(d["src"])
            self.cur["buf"].append(f"\n[[IMG:{d['src']}]]\n")

    def handle_startendtag(self, tag, attrs):
        if tag in ("script", "style") or self.cur is None or self.skip:
            return
        if tag == "br":
            self.cur["buf"].append("\n")
        elif tag == "img" and dict(attrs).get("src"):
            self.cur["imgs"].append(dict(attrs)["src"])
            self.cur["buf"].append(f"\n[[IMG:{dict(attrs)['src']}]]\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag == "td" and self.cur is not None:
            self.cells.append(self.cur)
            self.cur = None
        elif tag in ("p", "div", "li") and self.cur is not None and not self.skip:
            self.cur["buf"].append("\n")

    def handle_data(self, d):
        if self.cur is not None and not self.skip:
            self.cur["buf"].append(d)


def normalize(raw: str) -> str:
    raw = raw.replace("\u3000", "  ").replace("\xa0", " ")
    out, blanks = [], 0
    for ln in [x.rstrip() for x in raw.split("\n")]:
        if not ln.strip():
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(ln.strip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def parse_page(path):
    text = open(path, "rb").read().decode("gb18030", errors="replace")
    ex = CellExtractor()
    ex.feed(text)
    ex.close()
    idx = next((i for i, c in enumerate(ex.cells) if c["cls"] == "t50"), None)
    title = "".join(ex.cells[idx]["buf"]).strip() if idx is not None else ""
    body, imgs = "", []
    if idx is not None:
        for c in ex.cells[idx + 1:]:
            if not c["cls"] and "".join(c["buf"]).strip():
                body, imgs = "".join(c["buf"]), c["imgs"]
                break
    return title, normalize(body), imgs


VOL_RE = re.compile(r"卷\s*([一二三四五六七八九十]+)")
YEAR_RE = re.compile(r"(1[89]\d{2}|20\d{2})")
CNY_RE = re.compile(r"([一二三四五六七八九〇]{4})\s*年")


def main():
    pages = []
    for di, (name, base) in enumerate(VOLUMES):
        d = os.path.join(RAW, name)
        for fn in sorted(f for f in os.listdir(d) if re.fullmatch(r"\d{3}\.htm", f)):
            seq = fn[:3]
            title, body, imgs = parse_page(os.path.join(d, fn))
            pages.append({
                "dir": name, "di": di, "seq": seq, "title": title,
                "body": body, "imgs": imgs, "url": base + fn,
            })

    # 文件顺序即阅读顺序; 卷号由"最近一次出现的卷首页"继承
    pages.sort(key=lambda p: (p["di"], int(p["seq"])))
    cur_vol = 0
    for p in pages:
        m = re.fullmatch(r"[◇·\s]*卷\s*([一二三四五六七八九十]+)", p["title"])
        if m:
            cur_vol = cn2int(m.group(1)) or 0
            p["is_vol_head"] = True
        p["vol"] = cur_vol

    # ---- 卷首页: 提取年份范围 ----
    vol_year = {}
    for p in pages:
        if not p.get("is_vol_head") or p["vol"] == 0:
            continue
        txt = p["body"]
        ys = [int(y) for y in YEAR_RE.findall(txt)]
        if not ys:
            cy = CNY_RE.findall(txt)
            ys = [cn_year(y) for y in cy if cn_year(y)]
        if ys:
            vol_year[p["vol"]] = (min(ys), max(ys))
        # 该卷日期范围首行
        first = next((l for l in txt.split("\n") if l.strip() and ("至" in l or "年" in l)), "")
        p["range_text"] = first.strip()

    print("卷 → 年份映射:")
    for v in sorted(vol_year):
        print(f"  卷{v:>2}: {vol_year[v]}")

    # ---- 编号与输出 ----
    items = []
    for i, p in enumerate(pages, 1):
        ys = vol_year.get(p["vol"])
        year = ys[0] if ys else None
        # 跨卷图片重名 → 加卷目录前缀
        pairs = [{"src": im, "local": f"{p['dir']}_{im}"} for im in p["imgs"]]
        body = p["body"]
        for pr in pairs:
            body = body.replace(f"[[IMG:{pr['src']}]]", f"[[IMG:{pr['local']}]]")
        items.append({
            "seq": i,
            "src": f"{p['dir']}/{p['seq']}.htm",
            "title": p["title"],
            "vol": p["vol"],
            "vol_label": f"卷{cn2str(p['vol'])}" if p["vol"] else "序跋附录",
            "vol_range": p.get("range_text", ""),
            "year": year,
            "year_span": f"{ys[0]}–{ys[1]}" if ys and ys[0] != ys[1] else (str(ys[0]) if ys else ""),
            "chars": len(re.sub(r"\s", "", body)),
            "images": pairs,
            "url": p["url"],
            "body": body,
            "is_vol_head": p.get("is_vol_head", False),
        })

    def render(b, prefix):
        return re.sub(r"\[\[IMG:([^\]]+)\]\]",
                      lambda m: f"![]({prefix}{os.path.basename(m.group(1))})", b)

    # 单篇 md
    for it in items:
        safe = re.sub(r"[\\/:*?\"<>|]", "_", it["title"])[:60]
        name = f"{it['seq']:03d}_{safe}.md"
        with open(os.path.join(MD, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {it['title']}\n\n")
            f.write(f"> {it['vol_label']}"
                    + (f"（{it['year_span']}）" if it["year_span"] else "")
                    + f"　序号 {it['seq']} / {len(items)}　"
                      f"来源: [{it['url']}]({it['url']})\n\n---\n\n")
            f.write(render(it["body"], "../images/"))
            f.write("\n")

    # 合并全集
    merged = os.path.join(ROOT, "胡适留学日记_1910-1917_全集.md")
    with open(merged, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 胡适留学日记（1910—1917）\n\n")
        f.write("> 原名《藏晖室札记》，收胡适 1910 年至 1917 年在美国留学期间的日记和杂记，"
                "凡十七卷，末附《归国记》。\n\n")
        f.write("> 来源：[虚阁网](https://www.xuges.com/xdmj/hushi/lx/index.htm)"
                "（台北商务印书馆版《胡适留学日记》）\n\n---\n\n")
        cur = None
        for it in items:
            if it["vol_label"] != cur:
                cur = it["vol_label"]
                n = sum(1 for x in items if x["vol_label"] == cur)
                f.write(f"\n\n# {cur}"
                        + (f"　{it['vol_range']}" if it.get("vol_range") else "")
                        + f"（{n} 条）\n\n")
            f.write(f"\n## {it['title']}\n\n")
            f.write(f"<sub>序号 {it['seq']}｜[原文]({it['url']})｜约 {it['chars']} 字</sub>\n\n")
            f.write(render(it["body"], "images/"))
            f.write("\n\n")
    print(f"合并全集: {merged}")

    meta = [{k: v for k, v in it.items() if k != "body"} for it in items]
    summary = {
        "crawled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": "胡适留学日记（1910—1917）",
        "source": "https://www.xuges.com/xdmj/hushi/lx/index.htm",
        "total": len(items),
        "volumes": len(vol_year),
        "vol_year": {str(k): v for k, v in vol_year.items()},
        "total_chars": sum(x["chars"] for x in items),
        "by_vol": {
            lab: sum(1 for x in items if x["vol_label"] == lab)
            for lab in dict.fromkeys(x["vol_label"] for x in items)
        },
        "items": meta,
    }
    json.dump(summary, open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("\n===== 校验 =====")
    print(f"总条目: {len(items)}　卷数: {len(vol_year)}　总字数: {summary['total_chars']}")
    print(f"各卷条目: {summary['by_vol']}")
    empty = [x["seq"] for x in items if x["chars"] < 5]
    print(f"空正文条目: {len(empty)} {empty[:20]}")
    noyear = [x["seq"] for x in items if x["vol"] and not x["year"]]
    print(f"缺年份的卷内条目: {len(noyear)}")
    imgs = [x["seq"] for x in items if x["images"]]
    print(f"含插图条目: {len(imgs)} {imgs[:20]}")
    return summary


def cn2str(n: int) -> str:
    """1→一, 11→十一, 17→十七"""
    if n <= 10:
        return "十" if n == 10 else "一二三四五六七八九"[n - 1]
    if n < 20:
        return "十" + "一二三四五六七八九"[n - 11]
    tens, ones = divmod(n, 10)
    return "一二三四五六七八九"[tens - 1] + "十" + ("一二三四五六七八九"[ones - 1] if ones else "")


if __name__ == "__main__":
    main()
