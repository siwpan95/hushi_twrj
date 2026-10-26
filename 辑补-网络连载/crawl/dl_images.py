# -*- coding: utf-8 -*-
"""下载 B 站专栏插图 → images/, 并生成 _map.json (url → 本地文件名)"""
import os
import re
import json
import glob
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG = os.path.join(ROOT, "images")
os.makedirs(IMG, exist_ok=True)

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
     "Accept-Encoding": "identity",
     "Referer": "https://www.bilibili.com/"}


IMGSRC = re.compile(r"<img[^>]+?src=[\"']([^\"']+)[\"']", re.I)


def main():
    urls = []
    n_body = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "raw", "articles", "*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        for u in r.get("image_urls") or []:
            urls.append(u)
        # image_urls 只给封面(banner)，正文插图要自己从 content 里挖
        for u in IMGSRC.findall(r.get("content") or ""):
            urls.append(u)
            n_body += 1
    # 去重保序（协议相对写法 //host/... 归一成 https://host/...）
    seen, uniq = set(), []
    for u in urls:
        k = "https:" + u if u.startswith("//") else u
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    print(f"唯一图片 URL {len(uniq)} 个（其中正文插图 {n_body} 处）")
    # /banner/ 是 B 站自动生成的分享卡片（正文开头预览 + 站点水印），
    # 无独立内容价值且每张 ~200KB，全部剔除，只保留正文插图
    uniq = [u for u in uniq if "/banner/" not in u]
    print(f"剔除 banner 分享卡片后需下载 {len(uniq)} 个")

    cmap, ok, fail = {}, 0, []
    for i, u in enumerate(uniq, 1):
        url = u if u.startswith("http") else ("https:" + u)
        ext = os.path.splitext(url.split("?")[0])[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = ".jpg"
        local = f"bili_{i:04d}{ext}"
        dst = os.path.join(IMG, local)
        if not (os.path.exists(dst) and os.path.getsize(dst) > 500):
            try:
                req = urllib.request.Request(url, headers=H)
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                if len(data) < 500:
                    raise ValueError("too small")
                open(dst, "wb").write(data)
            except Exception as e:  # noqa: BLE001
                fail.append((url, str(e)[:60]))
                continue
        cmap[u] = local
        ok += 1
        if i % 50 == 0:
            print(f"  ...{i}/{len(uniq)}")
    json.dump(cmap, open(os.path.join(IMG, "_map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"完成: 成功 {ok}, 失败 {len(fail)}")
    for f in fail[:8]:
        print("  x", f)
    tot = sum(os.path.getsize(os.path.join(IMG, f)) for f in os.listdir(IMG)
              if f != "_map.json")
    print(f"images/ {len(os.listdir(IMG))-1} 张, {tot/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
