# -*- coding: utf-8 -*-
"""
通用多卷下载器(胡适日记系列) —— 零依赖
用法:
    python fetch.py --base https://www.xuges.com/xdmj/hushi/lx/ --out ../raw/lx
    python fetch.py --all            # 按 VOLUMES 配置抓取全部卷
"""
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

VOLUMES = [
    ("lx", "https://www.xuges.com/xdmj/hushi/lx/"),
    ("lx2", "https://www.xuges.com/xdmj/hushi/lx2/"),
    ("lx3", "https://www.xuges.com/xdmj/hushi/lx3/"),
    ("lx4", "https://www.xuges.com/xdmj/hushi/lx4/"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Encoding": "identity",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}


def http_get(url, referer=None, timeout=30, retries=4):
    last = None
    h = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                raise ValueError("empty body")
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(str(last))


def crawl_volume(name, base, force=False):
    out = os.path.join(ROOT, "raw", name)
    os.makedirs(out, exist_ok=True)
    idx_path = os.path.join(out, "index.htm")
    if force or not os.path.exists(idx_path):
        open(idx_path, "wb").write(http_get(base + "index.htm", referer=base))
    text = open(idx_path, "rb").read().decode("gb18030", errors="replace")

    pat = re.compile(
        r'<a\s+href="(?:' + re.escape(base) + r')?(\d{3})\.htm"[^>]*>\s*([^<]*?)\s*</a>', re.I
    )
    toc = {}
    for m in pat.finditer(text):
        toc.setdefault(m.group(1), m.group(2).strip())
    print(f"[{name}] 目录条目 {len(toc)}")

    todo = [
        (s, t) for s, t in sorted(toc.items())
        if force or not os.path.exists(os.path.join(out, s + ".htm"))
        or os.path.getsize(os.path.join(out, s + ".htm")) < 200
    ]
    print(f"[{name}] 待下载 {len(todo)}")

    fails = []

    def work(item):
        seq, title = item
        fn = seq + ".htm"
        try:
            d = http_get(base + fn, referer=base + "index.htm")
            open(os.path.join(out, fn), "wb").write(d)
            return seq, len(d), None
        except Exception as e:  # noqa: BLE001
            return seq, 0, str(e)

    done = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(work, t) for t in todo]
        for fu in as_completed(futs):
            seq, size, err = fu.result()
            if err:
                fails.append((seq, err))
            else:
                done += 1
            if done % 100 == 0:
                print(f"  [{name}] {done}/{len(todo)}")
            time.sleep(0.05)

    # 串行补抓
    still = []
    for seq, _ in sorted(fails):
        try:
            d = http_get(base + seq + ".htm", referer=base + "index.htm", retries=5)
            open(os.path.join(out, seq + ".htm"), "wb").write(d)
            print(f"  [{name}] 补抓成功 {seq}")
        except Exception as e:  # noqa: BLE001
            still.append((seq, str(e)))
        time.sleep(0.3)

    total = len([f for f in os.listdir(out) if re.fullmatch(r"\d{3}\.htm", f)])
    print(f"[{name}] 完成: raw 中共 {total} 个正文页, 仍失败 {len(still)} {still if still else ''}")
    return total, still


def main():
    if "--all" in sys.argv:
        force = "--force" in sys.argv
        grand, bad = 0, []
        for name, base in VOLUMES:
            n, s = crawl_volume(name, base, force)
            grand += n
            bad += [(name,) + x for x in s]
        print(f"\n总计下载 {grand} 个正文页, 失败 {len(bad)}")
        return 0 if not bad else 2
    # 单卷模式
    base = None
    out = None
    for i, a in enumerate(sys.argv):
        if a == "--base":
            base = sys.argv[i + 1]
        if a == "--out":
            out = sys.argv[i + 1]
    if not base:
        print(__doc__)
        return 1
    name = out or os.path.basename(base.rstrip("/"))
    crawl_volume(name, base, "--force" in sys.argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
