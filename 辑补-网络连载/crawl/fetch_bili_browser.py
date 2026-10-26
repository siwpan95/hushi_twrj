# -*- coding: utf-8 -*-
"""
用 Edge/Chrome 无头浏览器抓取 B 站专栏正文。

为什么不用 urllib：
  api.bilibili.com/x/article/view 对非浏览器 TLS/JA3 指纹返回 HTTP 412，
  Python urllib / requests 无论带什么 Header 都会被拦（已实测全组合失败）。
  真浏览器的 TLS 指纹可以通过，实测 code=0 正常返回。
  本脚本直接让浏览器访问 JSON 接口，再解析 --dump-dom 输出的 <pre> 内容。
  零第三方依赖：只用标准库 + 系统已安装的 Edge（或 Chrome）。

用法:
    python fetch_bili_browser.py            # 增量抓缺失的
    python fetch_bili_browser.py --all      # 全量重抓
    python fetch_bili_browser.py --id 22644548
"""
import argparse, html, json, os, re, subprocess, sys, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIST = os.path.join(ROOT, "raw", "list.json")
ART = os.path.join(ROOT, "raw", "articles")
PROFILE = os.path.join(HERE, "_edge_profile")
VIEW = "https://api.bilibili.com/x/article/view?id={}"

# 依次探测系统里的浏览器
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def find_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 Edge/Chrome，无法使用浏览器抓取路线")


def dump_dom(browser, url, timeout=45):
    """无头浏览器打开 url，返回渲染后的 DOM 文本。"""
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--disable-extensions", "--mute-audio", "--no-first-run",
           "--disable-dev-shm-usage",
           "--virtual-time-budget=15000",
           "--user-data-dir=" + PROFILE,
           "--dump-dom", url]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    out = p.stdout.decode("utf-8", "replace")
    if not out.strip():
        return None, (p.stderr.decode("utf-8", "replace")[-300:] or "empty")
    return out, None


PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.S)


def extract_json(dom):
    """从 dump-dom 的 <pre> 里取出并还原 JSON。"""
    m = PRE_RE.search(dom)
    if not m:
        return None
    txt = html.unescape(m.group(1)).strip()
    # 有时浏览器会在 JSON 里插 <br> 或零宽字符
    txt = txt.replace("\u200b", "")
    try:
        return json.loads(txt)
    except Exception:
        return None


def save(aid, d):
    rec = {
        "id": d.get("id", aid),
        "title": d.get("title", ""),
        "publish_time": d.get("publish_time"),
        "ctime": d.get("ctime"),
        "words": d.get("words"),
        "image_urls": d.get("image_urls") or [],
        "content": d.get("content") or "",
    }
    path = os.path.join(ART, f"{aid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return len(rec["content"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全量重抓")
    ap.add_argument("--id", type=int, help="只抓指定 id")
    ap.add_argument("--gap", type=float, default=1.2, help="每次请求间隔秒")
    ap.add_argument("--rounds", type=int, default=4, help="补抓轮数")
    args = ap.parse_args()

    os.makedirs(ART, exist_ok=True)
    browser = find_browser()

    if args.id:
        targets = [args.id]
    else:
        lst = json.load(open(LIST, encoding="utf-8"))
        targets = [x["id"] for x in lst]

    def pending():
        if args.all or args.id:
            return list(targets)
        return [i for i in targets
                if not os.path.exists(os.path.join(ART, f"{i}.json"))]

    todo = pending()
    print(f"浏览器: {browser}")
    print(f"目标 {len(targets)} 篇，待抓 {len(todo)} 篇\n")

    log = open(os.path.join(HERE, "_fetch_log.txt"), "w", encoding="utf-8")

    def one(aid):
        dom, err = dump_dom(browser, VIEW.format(aid))
        if dom is None:
            return "err", err
        d = extract_json(dom)
        if d is None:
            return "err", "JSON 解析失败(可能被风控页拦截)"
        if d.get("code") != 0:
            return "err", f"code={d.get('code')} {d.get('message')}"
        data = d.get("data") or {}
        if not (data.get("content") or "").strip():
            return "err", "正文为空"
        n = save(aid, data)
        return "ok", n

    total_ok = 0
    for rnd in range(1, args.rounds + 1):
        todo = pending()
        if not todo:
            break
        if rnd > 1:
            w = 3 * rnd
            print(f"\n--- 补抓第 {rnd} 轮，剩余 {len(todo)}，等待 {w}s ---")
            time.sleep(w)
        ok = fail = 0
        for k, aid in enumerate(todo, 1):
            st, info = one(aid)
            if st == "ok":
                ok += 1
                total_ok += 1
                print(f"[{k}/{len(todo)}] {aid} ok  正文 {info} 字")
                log.write(f"{aid}\tok\t{info}\n")
            else:
                fail += 1
                print(f"[{k}/{len(todo)}] {aid} ERR  {info}")
                log.write(f"{aid}\terr\t{info}\n")
            log.flush()
            time.sleep(args.gap)
        print(f"  第 {rnd} 轮: 成功 {ok} / 失败 {fail}")

    log.close()
    left = pending()
    print(f"\n完成。本轮新增 {total_ok}，仍缺 {len(left)}")
    if left:
        print("缺失 id:", left)
        json.dump(left, open(os.path.join(ROOT, "raw", "missing.json"), "w"),
                  ensure_ascii=False)


if __name__ == "__main__":
    main()
