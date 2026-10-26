# -*- coding: utf-8 -*-
"""
胡适日记(1950-1953) 解析器 —— 零依赖
从 raw/*.htm (GB18030) 提取: 序号 / 日期标题 / 正文 / 图片
输出: markdown/*.md, 胡适日记_1950-1953_全集.md, index.json

用法:
    python parse.py
"""
import os
import re
import json
import html
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(ROOT, "raw")
MD_DIR = os.path.join(ROOT, "markdown")
BASE_URL = "https://www.xuges.com/xdmj/hushi/twrj/"
os.makedirs(MD_DIR, exist_ok=True)

SKIP_TAGS = {"script", "style", "noscript"}


class CellExtractor(HTMLParser):
    """按 <td> 收集单元格文本, <br>/<p>/<div> 视为换行"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.cur = None
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag == "td":
            d = dict(attrs)
            self.cur = {"cls": (d.get("class") or "").strip(), "buf": [], "imgs": []}
            return
        if self.cur is None or self.skip_depth:
            return
        d = dict(attrs)
        if tag == "br":
            self.cur["buf"].append("\n")
        elif tag in ("p", "div", "tr", "li"):
            self.cur["buf"].append("\n")
        elif tag == "img":
            src = d.get("src")
            if src:
                self.cur["imgs"].append(src)
                self.cur["buf"].append(f"\n[[IMG:{src}]]\n")

    def handle_startendtag(self, tag, attrs):
        if tag in SKIP_TAGS:
            return
        if tag == "br" and self.cur is not None and not self.skip_depth:
            self.cur["buf"].append("\n")
        elif tag == "img" and self.cur is not None and not self.skip_depth:
            src = dict(attrs).get("src")
            if src:
                self.cur["imgs"].append(src)
                self.cur["buf"].append(f"\n[[IMG:{src}]]\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "td" and self.cur is not None:
            self.cells.append(self.cur)
            self.cur = None
        elif tag in ("p", "div", "li") and self.cur is not None and not self.skip_depth:
            self.cur["buf"].append("\n")

    def handle_data(self, data):
        if self.cur is not None and not self.skip_depth:
            self.cur["buf"].append(data)


DATE_RE = re.compile(r"(1[89]\d{2}|20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def normalize_text(raw: str) -> str:
    """清理全角空格/行尾空白, 折叠多余空行"""
    raw = raw.replace("\u3000", "  ").replace("\xa0", " ")
    lines = [ln.rstrip() for ln in raw.split("\n")]
    out, blanks = [], 0
    for ln in lines:
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


def parse_page(path: str):
    with open(path, "rb") as f:
        text = f.read().decode("gb18030", errors="replace")
    ex = CellExtractor()
    ex.feed(text)
    ex.close()

    title, body, imgs = "", "", []
    t_idx = None
    for i, c in enumerate(ex.cells):
        if c["cls"] == "t50":
            t_idx = i
            title = "".join(c["buf"]).strip()
            break
    if t_idx is None:
        # 回退: <title> 标签
        m = re.search(r"<title>(.*?)</title>", text, re.S)
        title = html.unescape(m.group(1)).split("_")[0].strip() if m else ""
        # 回退: 取最长的无 class 单元格
        cands = [c for c in ex.cells if not c["cls"]]
        if cands:
            body = max(("".join(c["buf"]) for c in cands), key=len)
            imgs = cands[0]["imgs"]
    else:
        for c in ex.cells[t_idx + 1:]:
            if not c["cls"] and "".join(c["buf"]).strip():
                body = "".join(c["buf"])
                imgs = c["imgs"]
                break
    return title, normalize_text(body), imgs


def main():
    idx_path = os.path.join(RAW_DIR, "index.htm")
    idx_text = open(idx_path, "rb").read().decode("gb18030", errors="replace")
    toc = {}
    for m in re.finditer(
        r'<a\s+href="(?:' + re.escape(BASE_URL) + r')?(\d{3})\.htm"[^>]*>\s*([^<]*?)\s*</a>',
        idx_text,
        re.I,
    ):
        toc.setdefault(m.group(1), m.group(2).strip())

    files = sorted(f for f in os.listdir(RAW_DIR) if re.fullmatch(r"\d{3}\.htm", f))
    print(f"raw 目录正文文件: {len(files)} 个")

    items, problems = [], []
    for fn in files:
        seq = fn[:3]
        raw_title, body, imgs = parse_page(os.path.join(RAW_DIR, fn))
        title = raw_title or toc.get(seq, "")
        m = DATE_RE.search(title)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            iso = f"{y:04d}-{mo:02d}-{d:02d}"
        else:
            iso, y = "", None
        n_chars = len(re.sub(r"\s", "", body))
        if not title:
            problems.append((seq, "缺标题"))
        if n_chars < 10:
            problems.append((seq, f"正文过短({n_chars}字)"))
        items.append(
            {
                "seq": int(seq),
                "seq_str": seq,
                "title": title,
                "date": iso,
                "year": y,
                "chars": n_chars,
                "images": imgs,
                "url": BASE_URL + fn,
                "body": body,
            }
        )

    items.sort(key=lambda x: x["seq"])

    def render(body: str, img_prefix: str) -> str:
        """把 [[IMG:x.jpg]] 占位替换为 markdown 图片(指向本地 images/)"""
        return re.sub(
            r"\[\[IMG:([^\]]+)\]\]",
            lambda m: f"![]({img_prefix}{os.path.basename(m.group(1))})",
            body,
        )

    # ---- 写单篇 markdown ----
    for it in items:
        date_slug = it["date"] or f"{it['seq_str']}"
        name = f"{it['seq_str']}_{date_slug}.md"
        with open(os.path.join(MD_DIR, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {it['title'] or date_slug}\n\n")
            f.write(f"> 序号 {it['seq_str']} / 235　来源: [{it['url']}]({it['url']})\n\n")
            f.write("---\n\n")
            f.write(render(it["body"], "../images/"))
            f.write("\n")

    # ---- 写合并全集 ----
    merged_path = os.path.join(ROOT, "胡适日记_1950-1953_全集.md")
    with open(merged_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 胡适日记（1950—1953）\n\n")
        f.write(
            "> 收录胡适 1950—1953 年日记 235 篇。有日常起居的琐碎记录，有文学、历史、哲学、"
            "语言文字学等学术领域的论述和研究，也有有关文章（甚至批评胡适文章）的抄录和剪贴。\n\n"
        )
        f.write(f"> 来源：[虚阁网 {BASE_URL}index.htm]({BASE_URL}index.htm)　"
                f"抓取日期：见 index.json\n\n---\n\n")
        cur_year = None
        for it in items:
            y = it["year"]
            if y and y != cur_year:
                cur_year = y
                n = sum(1 for x in items if x["year"] == y)
                f.write(f"\n\n# {y}年（共 {n} 篇）\n\n")
            f.write(f"\n## {it['title']}\n\n")
            f.write(f"<sub>序号 {it['seq_str']}｜[原文]({it['url']})｜约 {it['chars']} 字</sub>\n\n")
            f.write(render(it["body"], "images/"))
            f.write("\n\n")
    print(f"合并全集已写出: {merged_path}")

    # ---- 写 index.json ----
    meta = [
        {k: v for k, v in it.items() if k != "body"} for it in items
    ]
    import datetime

    summary = {
        "crawled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": BASE_URL + "index.htm",
        "title": "胡适日记（1950—1953）",
        "total": len(items),
        "by_year": {
            str(y): sum(1 for x in items if x["year"] == y)
            for y in sorted({x["year"] for x in items if x["year"]})
        },
        "total_chars": sum(x["chars"] for x in items),
        "items": meta,
    }
    json_path = os.path.join(ROOT, "index.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"index.json 已写出: {json_path}")

    print("\n===== 校验结果 =====")
    print(f"总篇数: {len(items)}")
    print(f"总字数: {summary['total_chars']}")
    print(f"按年份: {summary['by_year']}")
    print(f"有日期: {sum(1 for x in items if x['date'])}")
    if problems:
        print(f"!! 异常 {len(problems)} 条:")
        for p in problems:
            print("   ", p)
    else:
        print("无异常条目")
    return items, summary


if __name__ == "__main__":
    main()
