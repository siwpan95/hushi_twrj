# -*- coding: utf-8 -*-
"""
质检: 检查是否存在被遗漏的正文单元格 / 统计插图 / 抽样核验
"""
import os
import re
import sys
import json
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(ROOT, "raw")
BASE_URL = "https://www.xuges.com/xdmj/hushi/twrj/"
IMG_DIR = os.path.join(ROOT, "images")
os.makedirs(IMG_DIR, exist_ok=True)


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.cur = None
        self.skip = 0

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
        if tag == "br":
            self.cur["buf"].append("\n")
        elif tag in ("p", "div", "tr", "li"):
            self.cur["buf"].append("\n")
        elif tag == "img":
            s = dict(attrs).get("src")
            if s:
                self.cur["imgs"].append(s)

    def handle_startendtag(self, tag, attrs):
        if tag in ("script", "style"):
            return
        if self.cur is None or self.skip:
            return
        if tag == "br":
            self.cur["buf"].append("\n")
        elif tag == "img":
            s = dict(attrs).get("src")
            if s:
                self.cur["imgs"].append(s)

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


def main():
    files = sorted(f for f in os.listdir(RAW_DIR) if re.fullmatch(r"\d{3}\.htm", f))
    multi_cell, all_imgs, no_t50 = [], {}, []
    cell_count_stats = {}

    for fn in files:
        t = open(os.path.join(RAW_DIR, fn), "rb").read().decode("gb18030", errors="replace")
        p = Cells()
        p.feed(t)
        p.close()
        idx = next((i for i, c in enumerate(p.cells) if c["cls"] == "t50"), None)
        if idx is None:
            no_t50.append(fn)
            continue
        # t50 之后所有"无 class 且文本非空"的单元格(排除纯 hr 单元格)
        after = []
        for c in p.cells[idx + 1:]:
            if c["cls"]:
                continue
            txt = "".join(c["buf"])
            if txt.strip():
                after.append({"text": txt.strip()[:120], "imgs": c["imgs"]})
        cell_count_stats[len(after)] = cell_count_stats.get(len(after), 0) + 1
        if len(after) > 1:
            multi_cell.append((fn, after))
        for c in after:
            for im in c["imgs"]:
                all_imgs.setdefault(im, []).append(fn)

    print("=== 质检报告 ===")
    print(f"正文文件数: {len(files)}")
    print(f"缺 t50 标题单元格: {no_t50 or '无'}")
    print(f"正文单元格数量分布: {cell_count_stats}")
    print(f"多单元格(需人工确认是否漏内容): {len(multi_cell)}")
    for fn, cells in multi_cell[:10]:
        print(f"  -- {fn}:")
        for c in cells:
            print(f"     [{len(c['text'])}字] {c['text'][:70]!r} imgs={c['imgs']}")

    print(f"\n插图引用: {len(all_imgs)} 个唯一文件")
    for im, fns in sorted(all_imgs.items()):
        print(f"  {im}  <- {len(fns)} 处: {fns[:5]}")

    json.dump(
        {"images": all_imgs, "multi_cell": {f: c for f, c in multi_cell}},
        open(os.path.join(HERE, "_verify.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )

    # 下载插图
    if "--dl-img" in sys.argv:
        print("\n下载插图...")
        hdr = {"User-Agent": "Mozilla/5.0", "Referer": BASE_URL, "Accept-Encoding": "identity"}
        for im in sorted(all_imgs):
            dst = os.path.join(IMG_DIR, os.path.basename(im))
            if os.path.exists(dst) and os.path.getsize(dst) > 100:
                continue
            try:
                req = urllib.request.Request(BASE_URL + im.lstrip("/"), headers=hdr)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                open(dst, "wb").write(data)
                print(f"  ok {im} ({len(data)}B)")
            except Exception as e:  # noqa: BLE001
                print(f"  x  {im} -> {e}")


if __name__ == "__main__":
    main()
