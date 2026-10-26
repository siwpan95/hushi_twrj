# -*- coding: utf-8 -*-
"""生成《胡适留学日记》纯文本全集"""
import os
import re
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
meta = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
out = os.path.join(ROOT, "胡适留学日记_1910-1917_全集.txt")

with open(out, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("胡适留学日记（1910—1917）\n")
    f.write("原名《藏晖室札记》，台北商务印书馆版《胡适留学日记》\n")
    f.write(f"来源：{meta['source']}　抓取：{meta['crawled_at']}\n")
    f.write("=" * 60 + "\n\n")
    cur = None
    for it in meta["items"]:
        files = glob.glob(os.path.join(ROOT, "markdown", f"{it['seq']:03d}_*.md"))
        if not files:
            continue
        t = open(files[0], encoding="utf-8").read()
        body = t.split("---\n", 1)[1].strip() if "---\n" in t else t
        body = re.sub(r"!\[\]\(([^)]+)\)", "[插图]", body)
        if it["vol_label"] != cur:
            cur = it["vol_label"]
            n = sum(1 for x in meta["items"] if x["vol_label"] == cur)
            rng = next((x["vol_range"] for x in meta["items"]
                        if x["vol_label"] == cur and x.get("vol_range")), "")
            f.write(f"\n\n{'#' * 50}\n# {cur}　{rng}（{n} 条）\n{'#' * 50}\n\n")
        f.write(f"\n【{it['title']}】（序号 {it['seq']}）\n\n")
        f.write(body)
        f.write("\n\n" + "-" * 40 + "\n")

print(f"已生成: {out}  ({os.path.getsize(out)/1024:.0f} KB)")
