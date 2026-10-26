# 胡适日记 · 辑补卷（网络连载转抄）

> ## ⚠ 来源性质
>
> 本卷辑自 **B 站专栏连载**（[readlist/rl692101](https://www.bilibili.com/read/readlist/rl692101)），
> 系网友据安徽教育出版社《胡适日记全编》等纸本**转抄的片段**，属**二手来源**。
>
> 与 `../1910-1917/`、`../1950-1953/` 两册（直接采自文献站点、逐页对应原书）不同，本卷：
> - 标题多为 UP 主**自拟**（如「胡适日记——第一次坐飞机1930.02.20」），非胡适原题
> - 内容为**节选**，同一天的日记可能被拆分或省略
> - 使用现代标点，繁简混排，**可能存在转抄讹误**
>
> **引用前请核对纸本。**

正编未覆盖的 1917—1949 段，目前没有可直连抓取的完整结构化文本源（详见 `../README.md`），
本卷是这一空缺的**部分补充**：**69 篇 / 31,586 字**，覆盖 1921（1）、1922（1）、1930（16）、
1931（15）、1932（6）、1933（6）、1934（7）、1935（5）、1937（4）、1938（8）。
相对全编 3–7 册而言只是零星片段，请勿当作完整文本使用。

## 目录结构

```
辑补-网络连载/
├── 胡适日记_辑补卷_网络连载.md / .txt
├── index.json                  # 元数据：日期/年份/事由/字数/原文URL/插图
├── markdown/                   # 单篇 .md
├── images/                     # 正文插图 + _map.json(url→本地名)
├── raw/
│   ├── list.json               # 目录 69 条（已去重）
│   ├── articles/*.json         # 各篇原始 API 返回（69/69）
│   └── missing.json            # 抓全后为空
└── crawl/
    ├── fetch_bili.py           # 直连抓取（已被 412 封死，留作记录）
    ├── fetch_bili_browser.py   # ✅ 无头浏览器抓取（当前可用）
    ├── dl_images.py            # 下载正文插图并生成 _map.json
    └── parse_bili.py           # 解析 → markdown/全集/index.json
```

## 抓取技术要点（B 站专栏）

1. **正文只能走 API**：`www.bilibili.com/read/cv{id}` 与 `m.bilibili.com` 均为 SPA 空壳
   （约 3KB，无 SSR），HTML 里没有正文。
2. **接口**：`https://api.bilibili.com/x/article/view?id={id}`（`viewinfo` **不返回 content**，
   别用错）。
3. **⚠ 412 指纹风控（本项目最大的坑）**：`api.bilibili.com/x/article/view` 对**非浏览器 TLS/JA3
   指纹**直接返回 `HTTP 412 Precondition Failed`。已实测**全部失效**的绕法：
   - 补齐全套浏览器头（sec-ch-ua / Sec-Fetch-* / b_nut / b_lsid）
   - 先取 `finger/spi` 设备指纹再带 `buvid3/buvid4` Cookie
   - 用 CookieJar 走完整会话（先逛首页 → read 页 → bili_ticket → 再打 API）
   - 换备用域名（`app.bilibili.com` / `api.vc.bilibili.com` 等，均 404）
   - 并发/长退避（并发会加重，长退避不划算）

   期间**同 IP 的其他接口照常 200**（`finger/spi`、`list/web/articles`、图片 CDN），
   说明封的不是 IP，是 TLS 指纹 → 任何纯 HTTP 库（urllib/requests）都无解。
4. **✅ 正确解法：真浏览器**。无头 Edge/Chrome 的 TLS 指纹可正常通过（`code:0`）。
   用 `msedge --headless=new --dump-dom` 打 API URL，再从输出的 `<pre>` 里
   `html.unescape()` + `json.loads` 即可，无需任何第三方库。
5. **限流仍在，但会放行**：`-509`（请求过于频繁）与 `-352`（风控）按**累计请求数**触发，
   与单次间隔关系不大——逐轮补抓（每轮等几秒冷却）比"单条长退避"有效得多。
   实测 69 篇分 3 次会话抓完，成功率约 70%，补抓 10 轮左右收尾。
6. **冷却周期**：被 -352 硬封后放置约 1 小时，成功率即可恢复；不必死磕。
7. **列表分页是假的**：`list/web/articles?page=N` 的 `page` 参数**不生效**，任何页都返回同样的
   首屏 69 条。若按"翻页直到无新条目"累加而不按 id 去重，会得到 552 条假数据（69×8）
   —— 本项目踩过此坑。抓取前务必 `len(set(ids))` 校验唯一性。
8. **`image_urls` 只给封面**：字段里全是 `/bfs/article/banner/` 开头的**分享卡片**
   （正文开头预览 + 站点水印），无独立内容价值，已全部剔除；真正的正文插图要从
   `content` 的 `<img>` 里自己挖，且是**协议相对 URL**（`//i0.hdslb.com/...`），
   与 `image_urls` 的 `https://` 写法对不上，映射时必须归一化。

## 复现

```bash
cd crawl
python fetch_bili_browser.py     # 无头浏览器抓取；缺失自动多轮补抓
python dl_images.py              # 下载正文插图 → images/ + _map.json
python parse_bili.py             # 生成 markdown/全集/index.json
cd ../../crawl && python build_all.py && python verify_all.py   # 并入总集并校验
```

## 说明

内容为网络公开的用户转载内容，仅作个人学习研究用的本地存档，请勿用于商业用途。
如权利人主张权利，可随时删除本卷。
