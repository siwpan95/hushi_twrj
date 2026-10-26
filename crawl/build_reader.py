# -*- coding: utf-8 -*-
"""
生成本地离线阅读器: 阅读器.html (单文件, 数据内嵌)
附带: 胡适日记_1950-1953_全集.txt
"""
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "阅读器.html")

meta = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
items = meta["items"]

# 正文重新读入(避免 index.json 体积过大时重复, 这里从 markdown 目录取正文)
bodies = {}
for it in items:
    slug = it["date"] or it["seq_str"]
    p = os.path.join(ROOT, "markdown", f"{it['seq_str']}_{slug}.md")
    t = open(p, encoding="utf-8").read()
    # 去掉 front matter(标题 + 引用行 + ---)
    t = t.split("---\n", 1)[1].strip() if "---\n" in t else t
    bodies[it["seq_str"]] = t

for it in items:
    it["body"] = bodies[it["seq_str"]]

payload = {
    "title": meta["title"],
    "source": meta["source"],
    "crawled_at": meta["crawled_at"],
    "total": meta["total"],
    "by_year": meta["by_year"],
    "items": [
        {
            "seq": it["seq_str"],
            "title": it["title"],
            "date": it["date"],
            "year": it["year"],
            "chars": it["chars"],
            "url": it["url"],
            "body": it["body"],
        }
        for it in items
    ],
}

data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>胡适日记（1950—1953）· 离线阅读器</title>
<style>
:root{
  --paper:#f6f2e9; --card:#fffdf7; --ink:#2a241d; --ink-soft:#5c5348;
  --line:#e2dbcc; --accent:#8c2f26; --accent-soft:#f0e3dd; --hover:#f3ece0;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{
  font-family:"Noto Serif SC","Source Han Serif SC","Songti SC",STSong,"SimSun",Georgia,serif;
  background:var(--paper); color:var(--ink); font-size:17px; line-height:1.95;
}
#app{display:flex;height:100vh;overflow:hidden}

/* ---------- 侧栏 ---------- */
#side{
  width:330px;flex:0 0 330px;background:#f2ece0;border-right:1px solid var(--line);
  display:flex;flex-direction:column;height:100%;
}
#side header{padding:16px 16px 10px;border-bottom:1px solid var(--line)}
#side h1{margin:0;font-size:19px;letter-spacing:1px;color:var(--accent)}
#side .sub{font-size:12px;color:var(--ink-soft);margin-top:5px;line-height:1.6}
#q{
  width:100%;margin-top:11px;padding:8px 11px;font-size:14px;border:1px solid var(--line);
  border-radius:6px;background:#fffdf7;color:var(--ink);font-family:inherit;outline:none;
}
#q:focus{border-color:var(--accent)}
#stat{padding:7px 16px;font-size:12px;color:var(--ink-soft);border-bottom:1px solid var(--line)}
#toc{flex:1;overflow-y:auto;padding:6px 0 30px}
.yr{padding:9px 16px 4px;font-size:13px;color:var(--accent);font-weight:700;letter-spacing:2px;
  cursor:pointer;user-select:none;display:flex;justify-content:space-between;align-items:center}
.yr .cnt{font-size:11px;color:var(--ink-soft);font-weight:400;letter-spacing:0}
.it{padding:7px 16px 7px 22px;font-size:14.5px;cursor:pointer;border-left:3px solid transparent;
  display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.it:hover{background:var(--hover)}
.it.on{background:var(--accent-soft);border-left-color:var(--accent);color:var(--accent);font-weight:600}
.it .d{flex:1}
.it .c{font-size:11px;color:#9a9082;flex:0 0 auto}
.it.hide{display:none}
mark{background:#ffe9a8;color:inherit;padding:0 1px}

/* ---------- 主区 ---------- */
#main{flex:1;overflow-y:auto;display:flex;justify-content:center}
#wrap{max-width:760px;width:100%;padding:38px 44px 120px}
#cover{max-width:220px;border:1px solid var(--line);display:block;margin:0 auto 26px;
  box-shadow:0 2px 10px rgba(0,0,0,.07)}
.hd{border-bottom:2px double var(--line);padding-bottom:14px;margin-bottom:22px}
.hd h2{margin:0 0 8px;font-size:27px;letter-spacing:1px}
.hd .meta{font-size:12.5px;color:var(--ink-soft)}
.hd .meta a{color:var(--accent);text-decoration:none}
.hd .meta a:hover{text-decoration:underline}
.bd p{margin:0 0 1.15em;text-align:justify;text-indent:0}
.bd img{max-width:100%;border:1px solid var(--line);background:#fff;padding:6px;margin:10px 0}
.nav{display:flex;justify-content:space-between;gap:12px;margin-top:44px;padding-top:18px;
  border-top:1px solid var(--line);font-size:14px}
.nav a{color:var(--accent);text-decoration:none;max-width:45%;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.nav a:hover{text-decoration:underline}
.nav span.dis{color:#bdb4a5}
.empty{color:var(--ink-soft);text-align:center;margin-top:20vh;font-size:15px}

#tools{position:fixed;right:18px;bottom:18px;display:flex;gap:7px;z-index:20}
#tools button{width:34px;height:34px;border-radius:50%;border:1px solid var(--line);
  background:#fffdf7;color:var(--ink-soft);cursor:pointer;font-size:15px;font-family:inherit}
#tools button:hover{border-color:var(--accent);color:var(--accent)}
#menuBtn{display:none}

@media(max-width:820px){
  #side{position:fixed;left:-340px;top:0;z-index:30;transition:left .22s;box-shadow:2px 0 14px rgba(0,0,0,.13)}
  #side.open{left:0}
  #menuBtn{display:block}
  #wrap{padding:26px 20px 110px}
}
</style>
</head>
<body>
<div id="app">
  <aside id="side">
    <header>
      <h1>胡适日记</h1>
      <div class="sub">1950—1953　共 <b id="tt">0</b> 篇<br>来源：虚阁网 · 本地离线版</div>
      <input id="q" placeholder="搜索日期或正文关键词…" autocomplete="off" />
    </header>
    <div id="stat"></div>
    <nav id="toc"></nav>
  </aside>
  <main id="main"><div id="wrap">
    <img id="cover" src="images/fm.jpg" alt="封面" />
    <div class="hd">
      <h2>胡适日记（1950—1953）</h2>
      <div class="meta">
        收录日记 235 篇。有日常起居的琐碎记录，有文学、历史、哲学、语言文字学等学术领域的
        论述和研究，也有有关文章（甚至批评胡适文章）的抄录和剪贴。<br>
        原始来源：<a href="__SOURCE__" target="_blank" rel="noopener">虚阁网 xuges.com</a>
        　抓取于 __CRAWL__
      </div>
    </div>
    <div class="bd" style="color:#5c5348">
      <p>← 请从左侧目录选择一篇开始阅读。支持 <b>全文搜索</b>、
      <b>← →</b> 键翻阅、字号调节（右下角 <b>A-</b> / <b>A+</b>）。</p>
    </div>
  </div></main>
</div>
<div id="tools">
  <button id="menuBtn" title="目录">☰</button>
  <button id="fs" title="缩小字号">A-</button>
  <button id="fb" title="放大字号">A+</button>
</div>

<script id="DATA" type="application/json">__DATA__</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById('DATA').textContent);
  var items = DATA.items, bySeq = {};
  items.forEach(function(it){ bySeq[it.seq] = it; });

  var toc = document.getElementById('toc'), stat = document.getElementById('stat'),
      wrap = document.getElementById('wrap'), q = document.getElementById('q');
  document.getElementById('tt').textContent = DATA.total;

  var keyword = '', cur = null;

  function esc(s){
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function hl(s){
    if(!keyword) return esc(s);
    var re = new RegExp('(' + keyword.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&') + ')','gi');
    return esc(s).replace(re,'<mark>$1</mark>');
  }
  function toHtml(body){
    var out = '';
    body.split(/\\n{2,}/).forEach(function(p){
      p = p.trim(); if(!p) return;
      var m = p.match(/^!\\[\\]\\((.+?)\\)$/);
      if(m){ out += '<p><img src="' + m[1].replace(/&/g,'&amp;') + '" loading="lazy" alt="插图"></p>'; return; }
      out += '<p>' + hl(p).replace(/\\n/g,'<br>') + '</p>';
    });
    return out;
  }

  // ---- 目录 ----
  function buildToc(){
    var html = '', year = null;
    items.forEach(function(it){
      if(it.year !== year){
        if(year !== null) html += '</div>';
        year = it.year;
        var cnt = items.filter(function(x){return x.year===year;}).length;
        html += '<div class="yr" data-y="'+year+'"><span>'+year+' 年</span>' +
                '<span class="cnt">'+cnt+' 篇</span></div><div data-g="'+year+'">';
      }
      html += '<div class="it" data-s="'+it.seq+'"><span class="d">'+esc(it.title)+'</span>' +
              '<span class="c">'+it.chars+'字</span></div>';
    });
    html += '</div>';
    toc.innerHTML = html;

    toc.querySelectorAll('.yr').forEach(function(el){
      el.onclick = function(){
        var g = toc.querySelector('[data-g="'+el.dataset.y+'"]');
        var hid = g.dataset.h === '1';
        g.dataset.h = hid ? '0' : '1';
        g.querySelectorAll('.it').forEach(function(i){ i.style.display = hid ? '' : 'none'; });
      };
    });
    toc.querySelectorAll('.it').forEach(function(el){
      el.onclick = function(){ show(el.dataset.s, true); if(innerWidth<=820) side.classList.remove('open'); };
    });
  }

  function filter(){
    keyword = q.value.trim();
    var n = 0;
    items.forEach(function(it){
      var el = toc.querySelector('.it[data-s="'+it.seq+'"]');
      if(!el) return;
      var hit = !keyword || it.title.indexOf(keyword) >= 0 || it.body.indexOf(keyword) >= 0;
      el.classList.toggle('hide', !hit);
      if(hit) n++;
    });
    stat.textContent = keyword ? ('匹配 ' + n + ' 篇') : ('共 ' + items.length + ' 篇');
    if(cur) show(cur, false);
  }

  // ---- 正文 ----
  function show(seq, scrollTop){
    var it = bySeq[seq]; if(!it) return;
    cur = seq;
    var idx = items.indexOf(it);
    var prev = items[idx-1], next = items[idx+1];
    wrap.innerHTML =
      '<div class="hd"><h2>' + hl(it.title) + '</h2><div class="meta">' +
      '序号 ' + it.seq + ' / ' + DATA.total + '　·　约 ' + it.chars + ' 字　·　' +
      '<a href="' + it.url + '" target="_blank" rel="noopener">查看原文</a></div></div>' +
      '<div class="bd">' + toHtml(it.body) + '</div>' +
      '<div class="nav">' +
        (prev ? '<a href="#" data-s="'+prev.seq+'">← ' + esc(prev.title) + '</a>'
              : '<span class="dis">← 已是第一篇</span>') +
        (next ? '<a href="#" data-s="'+next.seq+'">' + esc(next.title) + ' →</a>'
              : '<span class="dis">已是最后一篇 →</span>') +
      '</div>';
    wrap.querySelectorAll('.nav a').forEach(function(a){
      a.onclick = function(e){ e.preventDefault(); show(a.dataset.s, true); };
    });
    toc.querySelectorAll('.it.on').forEach(function(e){ e.classList.remove('on'); });
    var el = toc.querySelector('.it[data-s="'+seq+'"]');
    if(el){ el.classList.add('on'); el.scrollIntoView({block:'nearest'}); }
    if(scrollTop) document.getElementById('main').scrollTop = 0;
    location.hash = 'p' + seq;
  }

  // ---- 事件 ----
  q.oninput = filter;
  var base = 17, fs = document.getElementById('fs'), fb = document.getElementById('fb');
  fs.onclick = function(){ base = Math.max(13, base-1); document.body.style.fontSize = base+'px'; };
  fb.onclick = function(){ base = Math.min(24, base+1); document.body.style.fontSize = base+'px'; };
  var side = document.getElementById('side');
  document.getElementById('menuBtn').onclick = function(){ side.classList.toggle('open'); };
  document.addEventListener('keydown', function(e){
    if(e.target === q) return;
    if(!cur) return;
    var idx = items.indexOf(bySeq[cur]);
    if(e.key === 'ArrowLeft' && idx > 0){ show(items[idx-1].seq, true); }
    if(e.key === 'ArrowRight' && idx < items.length-1){ show(items[idx+1].seq, true); }
  });

  buildToc();
  stat.textContent = '共 ' + items.length + ' 篇';
  var h = location.hash.match(/^#p(\\d{3})$/);
  if(h && bySeq[h[1]]) show(h[1], true);
})();
</script>
</body>
</html>
"""

HTML = HTML.replace("__DATA__", data_json)
HTML = HTML.replace("__SOURCE__", meta["source"])
HTML = HTML.replace("__CRAWL__", meta["crawled_at"])

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(HTML)
print(f"阅读器已生成: {OUT} ({len(HTML.encode('utf-8'))/1024:.0f} KB)")

# ---- 纯文本全集 ----
txt_path = os.path.join(ROOT, "胡适日记_1950-1953_全集.txt")
with open(txt_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("胡适日记（1950—1953）\n")
    f.write(f"来源：{meta['source']}　抓取：{meta['crawled_at']}\n")
    f.write("=" * 60 + "\n\n")
    year = None
    for it in items:
        if it["year"] != year:
            year = it["year"]
            f.write(f"\n\n{'#' * 40}\n# {year} 年\n{'#' * 40}\n\n")
        f.write(f"\n【{it['title']}】（序号 {it['seq']}）\n\n")
        f.write(it["body"].replace("\n\n", "\n"))
        f.write("\n\n" + "-" * 40 + "\n")
print(f"纯文本全集已生成: {txt_path}")
