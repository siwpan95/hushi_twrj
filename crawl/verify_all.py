# -*- coding: utf-8 -*-
"""总集阅读器端到端校验：JSON / 图片引用 / HTML 残留 / JS 语法 / 分册结构"""
import json, os, re, subprocess, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HP = os.path.join(ROOT, "阅读器.html")
t = open(HP, encoding="utf-8").read()
ok = True


def chk(name, cond, extra=""):
    global ok
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (" " + extra if extra else ""))
    if not cond:
        ok = False


print("== 1. 内联 JSON ==")
m = re.search(r'<script id="DATA" type="application/json">(.*?)</script>', t, re.S)
chk("存在 DATA 块", bool(m))
data = json.loads(m.group(1))
items = data.get("items") or data.get("allitems") or []
chk("解析成功", True, f"{len(items)} 条")
books = data.get("books") or []
print("   分册:", [(b.get("id"), b.get("count")) for b in books])

print("\n== 2. 分册计数 ==")
cnt = {}
for it in items:
    cnt[it.get("book")] = cnt.get(it.get("book"), 0) + 1
print("  ", cnt)
BL = "辑补卷（网络连载）"
LX = "留学日记（1910—1917）"
TW = "晚年日记（1950—1953）"
OC = "全编 OCR（1919—1949）"
OC2 = "全编 OCR（1954—1962）"
chk("辑补卷 = 69", cnt.get(BL) == 69, f"实际 {cnt.get(BL)}")
chk("留学日记 = 1006", cnt.get(LX) == 1006, f"实际 {cnt.get(LX)}")
chk("晚年日记 = 235", cnt.get(TW) == 235, f"实际 {cnt.get(TW)}")
chk("全编OCR 1919-1949 = 2913", cnt.get(OC) == 2913, f"实际 {cnt.get(OC)}")
chk("全编OCR 1954-1962 = 380", cnt.get(OC2) == 380, f"实际 {cnt.get(OC2)}")

print("\n== 3. 图片引用 ==")
refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', "".join(i.get("body", "") or i.get("html", "") for i in items))
refs += re.findall(r'src="([^"]+)"', t)
img_refs = [r for r in refs if "/images/" in r or r.startswith("images/")]
missing, uniq = [], set()
for r in img_refs:
    p = r.split("/")[-1]
    uniq.add(p)
    # 找到对应分册目录
    cand = [os.path.join(ROOT, "1910-1917", "images", p),
            os.path.join(ROOT, "1950-1953", "images", p),
            os.path.join(ROOT, "辑补-网络连载", "images", p)]
    if not any(os.path.exists(c) for c in cand):
        missing.append(p)
chk(f"图片引用 {len(uniq)} 个唯一文件", True)
chk("无缺失图片", not missing, f"缺失 {len(missing)}: {missing[:3]}")

print("\n== 4. HTML 残留 ==")
bodies = "".join(i.get("body", "") or i.get("html", "") for i in items)
res = re.findall(r"</?(?:p|div|span|br|figure|img|figcaption)\b", bodies)
chk("正文无未解析 HTML 标签", not res, f"{len(res)} 处")
res2 = re.findall(r"\[\[IMG:", bodies)
chk("无未渲染图片占位", not res2, f"{len(res2)} 处")

print("\n== 5. JS 语法 ==")
scripts = re.findall(r"<script>(.*?)</script>", t, re.S)
js = max(scripts, key=len)
tmp = os.path.join(tempfile.gettempdir(), "_reader_check.js")
open(tmp, "w", encoding="utf-8").write(js)
r = subprocess.run(["node", "--check", tmp], capture_output=True)
chk("node --check 通过", r.returncode == 0,
    r.stderr.decode("utf-8", "replace")[:120])

print("\n== 6. 辑补卷抽样 ==")
bl = [i for i in items if i.get("book") == BL]
if bl:
    print("   首条:", bl[0].get("title", "")[:40], "|", bl[0].get("group", ""))
    print("   末条:", bl[-1].get("title", "")[:40], "|", bl[-1].get("group", ""))
    grp = {}
    for i in bl:
        grp[i.get("group")] = grp.get(i.get("group"), 0) + 1
    print("   分组:", grp)
    chk("辑补卷有 10 个年份分组", len(grp) >= 10, f"{len(grp)}")

oc = [i for i in items if i.get("book") == OC]
if oc:
    g = {}
    for i in oc:
        g[i.get("group")] = g.get(i.get("group"), 0) + 1
    yrs = sorted(int(k.rstrip("年")) for k in g if k and k.endswith("年"))
    print(f"   OCR 卷年份分组 {len(g)} 个，覆盖 {yrs[0]}–{yrs[-1]}")
    chk("OCR 卷覆盖 1919–1949", yrs[0] == 1919 and yrs[-1] >= 1948,
        f"{yrs[0]}–{yrs[-1]}")

oc2 = [i for i in items if i.get("book") == OC2]
if oc2:
    g2 = {}
    for i in oc2:
        g2[i.get("group")] = g2.get(i.get("group"), 0) + 1
    y2 = sorted(int(k.rstrip("年")) for k in g2 if k and k.endswith("年"))
    print(f"   OCR 晚年卷年份分组 {len(g2)} 个，覆盖 {y2[0]}–{y2[-1]}")
    chk("OCR 晚年卷覆盖 1954–1962",
        y2[0] == 1954 and y2[-1] == 1962, f"{y2[0]}–{y2[-1]}")

print("\n结果:", "全部通过" if ok else "存在失败项")
sys.exit(0 if ok else 1)
