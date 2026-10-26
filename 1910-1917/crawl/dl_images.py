# -*- coding: utf-8 -*-
"""下载留学日记插图 → images/"""
import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG = os.path.join(ROOT, "images")
os.makedirs(IMG, exist_ok=True)

BASES = {"lx": "https://www.xuges.com/xdmj/hushi/lx/",
         "lx2": "https://www.xuges.com/xdmj/hushi/lx2/",
         "lx3": "https://www.xuges.com/xdmj/hushi/lx3/",
         "lx4": "https://www.xuges.com/xdmj/hushi/lx4/"}

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept-Encoding": "identity", "Referer": "https://www.xuges.com/xdmj/hushi/lx/"}


def main():
    d = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    jobs, seen = [], set()
    for it in d["items"]:
        vol = it["src"].split("/")[0]
        for pr in it["images"]:
            if pr["local"] in seen:
                continue
            seen.add(pr["local"])
            jobs.append((BASES[vol] + pr["src"], pr["local"]))

    print(f"待下载 {len(jobs)} 张插图")
    ok, fail = 0, []

    def work(job):
        url, local = job
        dst = os.path.join(IMG, local)
        if os.path.exists(dst) and os.path.getsize(dst) > 100:
            return local, os.path.getsize(dst), None
        for i in range(4):
            try:
                req = urllib.request.Request(url, headers=H)
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                if len(data) < 100:
                    raise ValueError("too small")
                open(dst, "wb").write(data)
                return local, len(data), None
            except Exception as e:  # noqa: BLE001
                if i == 3:
                    return local, 0, f"{url} -> {e}"
        return local, 0, "unknown"

    with ThreadPoolExecutor(max_workers=5) as ex:
        for fu in as_completed([ex.submit(work, j) for j in jobs]):
            local, size, err = fu.result()
            if err:
                fail.append((local, err))
            else:
                ok += 1
    print(f"完成: 成功 {ok}, 失败 {len(fail)}")
    for f in fail[:10]:
        print("  x", f)
    total = sum(os.path.getsize(os.path.join(IMG, f)) for f in os.listdir(IMG))
    print(f"images/ 共 {len(os.listdir(IMG))} 个文件, {total/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
