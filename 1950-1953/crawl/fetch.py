# -*- coding: utf-8 -*-
"""
胡适日记(1950-1953) 下载器 —— 零依赖(仅标准库)
站点: https://www.xuges.com/xdmj/hushi/twrj/
编码: GB2312/GB18030

用法:
    python fetch.py            # 下载全部
    python fetch.py --force    # 忽略已存在, 全部重下
"""
import os
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://www.xuges.com/xdmj/hushi/twrj/"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(ROOT, "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# 关键: 不接受 br 压缩, 避免标准库无法解码 brotli 导致静默乱码
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Encoding": "identity",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": BASE + "index.htm",
    "Connection": "keep-alive",
}


def http_get(url: str, timeout: int = 30, retries: int = 4) -> bytes:
    """带重试的 GET, 返回原始字节。失败抛异常。"""
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if not data:
                    raise ValueError("empty body")
                return data
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"GET failed: {url} -> {last_err}")


def parse_index(html_bytes: bytes):
    """从目录页解析 [(seq, date_title, filename)]"""
    text = html_bytes.decode("gb18030", errors="replace")
    # 形如: <a href="001.htm">1950年1月1日</a>  或绝对 URL
    pat = re.compile(
        r'<a\s+href="(?:' + re.escape(BASE) + r')?(\d{3})\.htm"[^>]*>\s*([^<]*?)\s*</a>',
        re.I,
    )
    seen = {}
    for m in pat.finditer(text):
        seq, title = m.group(1), m.group(2).strip()
        if seq not in seen:
            seen[seq] = title
    return [(s, seen[s], s + ".htm") for s in sorted(seen)]


def main():
    force = "--force" in sys.argv
    print(f"[1/2] 抓取目录 {BASE}index.htm")
    idx_path = os.path.join(RAW_DIR, "index.htm")
    if force or not os.path.exists(idx_path):
        idx = http_get(BASE + "index.htm")
        with open(idx_path, "wb") as f:
            f.write(idx)
    else:
        idx = open(idx_path, "rb").read()

    entries = parse_index(idx)
    print(f"      目录条目: {len(entries)} 条")
    if not entries:
        print("!! 目录解析为空, 中止")
        return 1

    # 序号连续性检查
    nums = [int(s) for s, _, _ in entries]
    missing = [n for n in range(1, max(nums) + 1) if n not in set(nums)]
    if missing:
        print(f"      !! 序号缺失: {missing}")

    todo = []
    for seq, title, fn in entries:
        dst = os.path.join(RAW_DIR, fn)
        if force or not os.path.exists(dst) or os.path.getsize(dst) < 200:
            todo.append((seq, title, fn))

    print(f"[2/2] 待下载正文: {len(todo)} / {len(entries)}")

    ok, fail = 0, []

    def work(item):
        seq, title, fn = item
        url = BASE + fn
        dst = os.path.join(RAW_DIR, fn)
        try:
            data = http_get(url)
            with open(dst, "wb") as f:
                f.write(data)
            return seq, title, fn, len(data), None
        except Exception as e:  # noqa: BLE001
            return seq, title, fn, 0, str(e)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(work, t) for t in todo]
        for i, fu in enumerate(as_completed(futs), 1):
            seq, title, fn, size, err = fu.result()
            if err:
                fail.append((seq, fn, err))
                print(f"  x {fn} {title} -> {err}")
            else:
                ok += 1
                if i % 25 == 0 or i == len(todo):
                    print(f"  ...{i}/{len(todo)}  {fn} {title} ({size}B)")
            time.sleep(0.05)

    print(f"\n完成: 成功 {ok}, 失败 {len(fail)}")
    if fail:
        print("失败清单:")
        for s, fn, e in sorted(fail):
            print(f"  {fn}: {e}")
        # 串行重试一轮
        print("\n串行重试失败项...")
        still = []
        for seq, fn, _ in sorted(fail):
            title = dict((s, t) for s, t, _ in entries)[seq]
            try:
                data = http_get(BASE + fn, retries=5)
                with open(os.path.join(RAW_DIR, fn), "wb") as f:
                    f.write(data)
                print(f"  ok {fn}")
            except Exception as e:  # noqa: BLE001
                still.append((fn, str(e)))
                print(f"  x  {fn} -> {e}")
            time.sleep(0.4)
        if still:
            print("\n仍失败:", still)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
