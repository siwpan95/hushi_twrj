# -*- coding: utf-8 -*-
"""
抓取 B 站专栏「胡适日记」连载(readlist/rl692101) —— 零依赖
用法: python fetch_bili.py          # 增量抓取
      python fetch_bili.py --list   # 只刷新目录列表
"""
import os
import re
import sys
import json
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
ALIST = os.path.join(RAW, "list.json")
os.makedirs(RAW, exist_ok=True)
os.makedirs(os.path.join(RAW, "articles"), exist_ok=True)

LIST_URL = "https://api.bilibili.com/x/article/list/web/articles?id=692101&jsonp=jsonp&page={}"
VIEW_URL = "https://api.bilibili.com/x/article/view?id={}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


COOKIE = ""


def init_cookie():
    """申请 buvid3/buvid4 设备指纹, 实测可将 view 接口成功率由 ~25% 提到 ~60%+"""
    global COOKIE
    try:
        d = get_json("https://api.bilibili.com/x/frontend/finger/spi",
                     referer="https://www.bilibili.com/")
        b3 = (d.get("data") or {}).get("b_3")
        b4 = (d.get("data") or {}).get("b_4")
        if b3:
            COOKIE = f"buvid3={b3}; buvid4={b4}"
    except Exception as e:  # noqa: BLE001
        print("  buvid 获取失败:", e)
    print(f"  Cookie: {COOKIE[:50] or '无'}" if COOKIE else "  Cookie: 无")


def get_json(url, referer=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Encoding": "identity",
         "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        h["Referer"] = referer
    if COOKIE:
        h["Cookie"] = COOKIE
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def fetch_list():
    arts, page = [], 1
    seen = set()
    while True:
        try:
            d = get_json(LIST_URL.format(page), referer="https://www.bilibili.com/")
        except Exception as e:  # noqa: BLE001
            print("  列表获取失败:", e)
            break
        aa = (d.get("data") or {}).get("articles") or []
        if not aa:
            break
        new = 0
        for a in aa:
            aid = a.get("id")
            if aid and aid not in seen:
                seen.add(aid)
                arts.append({"id": aid, "title": a.get("title", "")})
                new += 1
        print(f"  第 {page} 页: {len(aa)} 条(新增 {new})")
        if new == 0 or page > 20:
            break
        page += 1
        time.sleep(0.6)
    json.dump(arts, open(ALIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"目录共 {len(arts)} 条 → {ALIST}")
    return arts


def fetch_one(art):
    """返回 (aid, 'ok'|'skip'|'empty'|'limit'|'fail', err)"""
    aid = art["id"]
    dst = os.path.join(RAW, "articles", f"{aid}.json")
    if os.path.exists(dst) and os.path.getsize(dst) > 200:
        return aid, "skip", None
    # 限流是 IP 级的持续限流, 长退避不划算 → 单次尝试, 失败留待补抓轮
    for attempt in range(1):
        try:
            d = get_json(VIEW_URL.format(aid),
                         referer=f"https://www.bilibili.com/read/cv{aid}")
            code = d.get("code")
            if code != 0:
                time.sleep(1)
                continue
            data = d.get("data") or {}
            if not data.get("content"):
                return aid, "empty", "code=0 但 content 为空"
            rec = {
                "id": aid,
                "title": data.get("title") or art["title"],
                "publish_time": data.get("publish_time"),
                "ctime": data.get("ctime"),
                "words": data.get("words"),
                "image_urls": data.get("image_urls") or [],
                "content": data["content"],
            }
            json.dump(rec, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
            return aid, "ok", None
        except Exception as e:  # noqa: BLE001
            time.sleep(4 * (attempt + 1))
    return aid, "limit", "限流/异常，重试耗尽"


def main():
    if os.path.exists(ALIST) and "--list" not in sys.argv:
        arts = json.load(open(ALIST, encoding="utf-8"))
        print(f"已有目录 {len(arts)} 条（加 --list 可刷新）")
    else:
        arts = fetch_list()
    if not arts:
        print("无目录，中止")
        return 1

    todo = [a for a in arts
            if not (os.path.exists(os.path.join(RAW, "articles", f"{a['id']}.json"))
                    and os.path.getsize(os.path.join(RAW, "articles", f"{a['id']}.json")) > 200)]
    print(f"待抓取正文: {len(todo)} / {len(arts)}")

    init_cookie()
    stat = {"ok": 0, "skip": 0, "empty": 0, "limit": 0}
    fails = []
    gap = 5.0   # 实测: 3s→~45%, 5s→~60%, 并发/突发→风控后接近 0%
    for i, art in enumerate(arts, 1):
        if art not in todo:
            stat["skip"] += 1
            continue
        aid, st, err = fetch_one(art)
        stat[st] = stat.get(st, 0) + 1
        if st == "limit":
            fails.append(aid)
        if (stat["ok"] + stat["limit"]) % 50 == 0:
            print(f"  ...{i}/{len(arts)}  成功 {stat['ok']} 受限 {stat['limit']}", flush=True)
        time.sleep(gap)

    print(f"\n主轮完成: {stat}", flush=True)

    # 多轮补抓受限条目(逐步放缓)
    for rnd, wait in ((1, 4), (2, 6), (3, 8), (4, 12)):
        if not fails:
            break
        print(f"\n第 {rnd} 轮补抓 {len(fails)} 条（间隔 {wait}s）", flush=True)
        still = []
        for aid in fails:
            time.sleep(wait)
            _, st, _ = fetch_one({"id": aid, "title": ""})
            if st != "ok":
                still.append(aid)
        print(f"  补回 {len(fails)-len(still)} 条，仍缺 {len(still)}", flush=True)
        fails = still
    if fails:
        print(f"最终缺失 {len(fails)} 条 → raw/missing.json", flush=True)
        json.dump(fails, open(os.path.join(RAW, "missing.json"), "w", encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
