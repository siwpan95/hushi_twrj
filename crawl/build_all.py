# -*- coding: utf-8 -*-
"""
构建《胡适日记》总集离线阅读器
合并 1910-1917 留学日记 + 1950-1953 晚年日记
输出: 胡适日记/阅读器.html
"""
import os
import re
import json
import glob
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "阅读器.html")


def load(book_id, book_name, d, group_key, img_prefix):
    meta = json.load(open(os.path.join(ROOT, d, "index.json"), encoding="utf-8"))
    items = []
    for it in meta["items"]:
        seq = it["seq"]
        files = glob.glob(os.path.join(ROOT, d, "markdown", f"{seq:03d}_*.md"))
        if not files and it.get("date"):
            # OCR 卷用「日期_册页」命名（重跑可原地覆盖，不留孤儿）
            files = glob.glob(os.path.join(ROOT, d, "markdown",
                                           f"{it['date']}_*.md"))
        if not files:
            continue
        t = open(files[0], encoding="utf-8").read()
        body = t.split("---\n", 1)[1].strip() if "---\n" in t else t
        body = body.replace("../images/", img_prefix)
        items.append({
            "id": f"{book_id}-{seq}",
            "seq": seq,
            "title": it["title"],
            "group": it[group_key] if group_key in it else str(it.get("year") or ""),
            "year": it.get("year"),
            "year_span": it.get("year_span", ""),
            "chars": it["chars"],
            "url": it["url"],
            "body": body,
            "book": book_name,
        })
    return items


lx = load("lx", "留学日记（1910—1917）", "1910-1917", "vol_label", "1910-1917/images/")
tw = load("tw", "晚年日记（1950—1953）", "1950-1953", "year", "1950-1953/images/")
tw = [dict(x, group=str(x["group"]) + "年") for x in tw]

bl = []
if os.path.exists(os.path.join(ROOT, "辑补-网络连载", "index.json")):
    bl = load("bl", "辑补卷（网络连载）", "辑补-网络连载", "year", "辑补-网络连载/images/")
    bl = [dict(x, group=(str(x["group"]) + "年") if x["group"] and x["group"] != "None"
               else "日期未标") for x in bl]

oc = []
if os.path.exists(os.path.join(ROOT, "全编OCR-1919-1949", "index.json")):
    oc = load("oc", "全编 OCR（1919—1949）", "全编OCR-1919-1949", "year", "")
    oc = [dict(x, group=(str(x["group"]) + "年") if x["group"] and x["group"] != "None"
               else "日期未标",
               title=str(x.get("title")) + f"（册{x.get('vol')}·原书第{x.get('pages',[0])[0]}页）")
          for x in oc]

oc2 = []
if os.path.exists(os.path.join(ROOT, "全编OCR-1954-1962", "index.json")):
    oc2 = load("oc2", "全编 OCR（1954—1962）", "全编OCR-1954-1962", "year", "")
    oc2 = [dict(x, group=(str(x["group"]) + "年") if x["group"] and x["group"] != "None"
                else "日期未标",
                title=str(x.get("title")) + f"（册{x.get('vol')}·原书第{x.get('pages',[0])[0]}页）")
           for x in oc2]

allitems = (lx + bl + tw
            + sorted(oc, key=lambda x: (x["year"] or 9999, x["seq"]))
            + sorted(oc2, key=lambda x: (x["year"] or 9999, x["seq"])))
books = [
    {"id": "lx", "name": "留学日记（1910—1917）",
     "note": "原名《藏晖室札记》· 十七卷 · 附《归国记》",
     "count": len(lx), "chars": sum(x["chars"] for x in lx)},
    {"id": "tw", "name": "晚年日记（1950—1953）",
     "note": "日常起居、学术札记与剪报抄录",
     "count": len(tw), "chars": sum(x["chars"] for x in tw)},
]
if bl:
    books.insert(1, {"id": "bl", "name": "辑补卷（网络连载 1921—1938）",
                     "note": "网友转抄片段，二手来源，引用请核对纸本",
                     "count": len(bl), "chars": sum(x["chars"] for x in bl)})
if oc:
    books.insert(1, {"id": "oc", "name": "全编 OCR（1919—1949）",
                     "note": "《胡适日记全编》影印本 OCR，未经人工校对，引用请核对原件",
                     "count": len(oc), "chars": sum(x["chars"] for x in oc)})
if oc2:
    books.append({"id": "oc2", "name": "全编 OCR（1954—1962）",
                  "note": "《胡适日记全编》册 8 影印本 OCR，未经人工校对，引用请核对原件",
                  "count": len(oc2), "chars": sum(x["chars"] for x in oc2)})

payload = {
    "title": "胡适日记",
    "crawled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "books": books,
    "items": allitems,
}

data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>胡适日记 · 离线阅读器</title>
<style>
:root{--paper:#f6f2e9;--card:#fffdf7;--ink:#2a241d;--ink-soft:#5c5348;--line:#e2dbcc;
      --accent:#8c2f26;--accent-soft:#f0e3dd;--hover:#f3ece0}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{font-family:"Noto Serif SC","Source Han Serif SC","Songti SC",STSong,"SimSun",Georgia,serif;
 background:var(--paper);color:var(--ink);font-size:17px;line-height:1.95}
#app{display:flex;height:100vh;overflow:hidden}
#side{width:340px;flex:0 0 340px;background:#f2ece0;border-right:1px solid var(--line);
 display:flex;flex-direction:column;height:100%}
#side header{padding:16px 16px 10px;border-bottom:1px solid var(--line)}
#side h1{margin:0;font-size:20px;letter-spacing:2px;color:var(--accent)}
.sub{font-size:12px;color:var(--ink-soft);margin-top:5px;line-height:1.6}
#q{width:100%;margin-top:11px;padding:8px 11px;font-size:14px;border:1px solid var(--line);
 border-radius:6px;background:#fffdf7;color:var(--ink);font-family:inherit;outline:none}
#q:focus{border-color:var(--accent)}
#stat{padding:7px 16px;font-size:12px;color:var(--ink-soft);border-bottom:1px solid var(--line)}
#toc{flex:1;overflow-y:auto;padding:6px 0 30px}
.bk{padding:11px 16px 6px;font-size:14px;color:var(--accent);font-weight:700;letter-spacing:1px;
 cursor:pointer;user-select:none;border-top:1px solid var(--line);margin-top:4px;
 display:flex;justify-content:space-between;align-items:baseline}
.bk .n{font-size:11px;color:var(--ink-soft);font-weight:400}
.bk-sub{font-size:11px;color:var(--ink-soft);padding:0 16px 6px;font-weight:400;letter-spacing:0}
.gp{padding:8px 16px 3px 20px;font-size:13px;color:#6f6558;cursor:pointer;user-select:none;
 display:flex;justify-content:space-between}
.gp:hover{color:var(--accent)}
.gp .n{font-size:11px;color:#9a9082}
.it{padding:6px 16px 6px 30px;font-size:14px;cursor:pointer;border-left:3px solid transparent;
 display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.it:hover{background:var(--hover)}
.it.on{background:var(--accent-soft);border-left-color:var(--accent);color:var(--accent);font-weight:600}
.it .d{flex:1}
.it .c{font-size:11px;color:#9a9082;flex:0 0 auto}
.it.hide{display:none}
mark{background:#ffe9a8;color:inherit;padding:0 1px}
#main{flex:1;overflow-y:auto;display:flex;justify-content:center}
#wrap{max-width:780px;width:100%;padding:38px 44px 120px}
.hd{border-bottom:2px double var(--line);padding-bottom:14px;margin-bottom:22px}
.hd h2{margin:0 0 8px;font-size:26px;letter-spacing:1px}
.hd .meta{font-size:12.5px;color:var(--ink-soft)}
.hd .meta a{color:var(--accent);text-decoration:none}
.bd p{margin:0 0 1.15em;text-align:justify}
.bd img{max-width:100%;border:1px solid var(--line);background:#fff;padding:6px;margin:10px 0}
.nav{display:flex;justify-content:space-between;gap:12px;margin-top:44px;padding-top:18px;
 border-top:1px solid var(--line);font-size:14px}
.nav a{color:var(--accent);text-decoration:none;max-width:45%;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.nav span.dis{color:#bdb4a5}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin:22px 0 8px}
.card{flex:1;min-width:230px;border:1px solid var(--line);background:#fffdf7;padding:14px 16px;
 border-radius:8px;cursor:pointer}
.card:hover{border-color:var(--accent)}
.card h3{margin:0 0 6px;font-size:16px;color:var(--accent)}
.card p{margin:0;font-size:12.5px;color:var(--ink-soft);line-height:1.7}
#tools{position:fixed;right:18px;bottom:18px;display:flex;gap:7px;z-index:20}
#tools button{width:34px;height:34px;border-radius:50%;border:1px solid var(--line);
 background:#fffdf7;color:var(--ink-soft);cursor:pointer;font-size:15px;font-family:inherit}
#tools button:hover{border-color:var(--accent);color:var(--accent)}
#menuBtn{display:none}
@media(max-width:820px){
 #side{position:fixed;left:-350px;top:0;z-index:30;transition:left .22s;box-shadow:2px 0 14px rgba(0,0,0,.13)}
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
   <div class="sub">共 <b id="tt">0</b> 篇 · <span id="tc"></span> 字<br>本地离线版 · 来源：虚阁网</div>
   <input id="q" placeholder="搜索标题或正文关键词…" autocomplete="off" />
  </header>
  <div id="stat"></div>
  <nav id="toc"></nav>
 </aside>
 <main id="main"><div id="wrap">
  <div class="hd"><h2>胡适日记 · 本地存档</h2>
  <div class="meta">收录 <b>1910—1917</b> 留学日记（十七卷，原名《藏晖室札记》）、
   <b>1919—1949</b> 与 <b>1954—1962</b> 全编 OCR 卷、<b>1921—1938</b> 辑补卷
   与 <b>1950—1953</b> 晚年日记，合计 <b id="tt2">0</b> 篇。<br>
   <b>辑补卷</b>辑自网络连载，系网友据纸质本转抄的片段，属二手来源，引用前请核对纸本。<br>
   <b>全编 OCR 卷</b>由《胡适日记全编》影印本识别而来，识别率约 95—97%、未经人工校对，引用前请核对原件。<br>
    正编来源：<a href="https://www.xuges.com/xdmj/hushi/index.htm" target="_blank" rel="noopener">虚阁网</a>
    　抓取于 __CRAWL__</div>
  </div>
  <div class="cards" id="cards"></div>
  <div class="bd" style="color:#5c5348">
   <p>← 请从左侧目录选择一篇，或点击上方分册卡片。支持 <b>全文搜索</b>、<b>← →</b> 翻页、
   右下角 <b>A-</b> / <b>A+</b> 调字号。</p>
  </div>
 </div></main>
</div>
<div id="tools"><button id="menuBtn" title="目录">☰</button>
<button id="fs" title="缩小">A-</button><button id="fb" title="放大">A+</button></div>

<script id="DATA" type="application/json">__DATA__</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('DATA').textContent), items=D.items, map={};
items.forEach(function(x){map[x.id]=x;});
var toc=document.getElementById('toc'), stat=document.getElementById('stat'),
    wrap=document.getElementById('wrap'), q=document.getElementById('q');
document.getElementById('tt').textContent=items.length;
document.getElementById('tt2').textContent=items.length;
document.getElementById('tc').textContent=D.items.reduce(function(a,b){return a+b.chars;}).toLocaleString();

var cards=document.getElementById('cards');
cards.innerHTML=D.books.map(function(b){
  return '<div class="card" data-b="'+b.id+'"><h3>'+b.name+'</h3><p>'+b.note+
         '<br>'+b.count+' 篇 · '+b.chars.toLocaleString()+' 字</p></div>';}).join('');
cards.querySelectorAll('.card').forEach(function(c){
  c.onclick=function(){
    var first=items.filter(function(x){return x.id.indexOf(c.dataset.b+'-')===0;})[0];
    if(first) show(first.id,true);
  };
});

var kw='', cur=null;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function hl(s){
  if(!kw) return esc(s);
  return esc(s).replace(new RegExp('('+kw.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>');
}
function toHtml(b){
  var o='';
  b.split(/\\n{2,}/).forEach(function(p){
    p=p.trim(); if(!p) return;
    var m=p.match(/^!\\[\\]\\((.+?)\\)$/);
    if(m){o+='<p><img src="'+m[1]+'" loading="lazy" alt="插图"></p>';return;}
    o+='<p>'+hl(p).replace(/\\n/g,'<br>')+'</p>';
  });
  return o;
}

function buildToc(){
  var h='';
  D.books.forEach(function(b){
    var its=items.filter(function(x){return x.id.indexOf(b.id+'-')===0;});
    h+='<div class="bk" data-b="'+b.id+'"><span>'+b.name+'</span><span class="n">'+its.length+' 篇</span></div>';
    h+='<div class="bk-sub">'+b.note+'</div><div data-gb="'+b.id+'">';
    var g=null;
    its.forEach(function(x){
      if(x.group!==g){
        if(g!==null) h+='</div>';
        g=x.group;
        var n=its.filter(function(y){return y.group===g;}).length;
        var yl=x.year_span?('　'+x.year_span):'';
        h+='<div class="gp" data-g="'+esc(g)+'"><span>'+esc(g)+yl+'</span><span class="n">'+n+'</span></div><div data-gg="'+esc(g)+'">';
      }
      h+='<div class="it" data-id="'+x.id+'"><span class="d">'+esc(x.title)+'</span><span class="c">'+x.chars+'</span></div>';
    });
    h+='</div></div>';
  });
  toc.innerHTML=h;
  toc.querySelectorAll('.bk').forEach(function(el){
    el.onclick=function(){
      var box=toc.querySelector('[data-gb="'+el.dataset.b+'"]');
      var hid=box.dataset.h==='1'; box.dataset.h=hid?'0':'1';
      box.style.display=hid?'':'none';
      var sub=el.nextElementSibling; if(sub && sub.className==='bk-sub') sub.style.display=hid?'':'none';
    };
  });
  toc.querySelectorAll('.gp').forEach(function(el){
    el.onclick=function(){
      var box=toc.querySelector('[data-gg="'+el.dataset.g+'"]');
      var hid=box.dataset.h==='1'; box.dataset.h=hid?'0':'1'; box.style.display=hid?'':'none';
    };
  });
  toc.querySelectorAll('.it').forEach(function(el){
    el.onclick=function(){show(el.dataset.id,true); if(innerWidth<=820) side.classList.remove('open');};
  });
}

function show(id,top){
  var it=map[id]; if(!it) return; cur=id;
  var i=items.indexOf(it), p=items[i-1], n=items[i+1];
  wrap.innerHTML='<div class="hd"><h2>'+hl(it.title)+'</h2><div class="meta">'+esc(it.book)+
    '　·　'+esc(it.group)+(it.year_span?('　'+it.year_span):'')+'　·　约 '+it.chars+' 字　·　'+
    '<a href="'+it.url+'" target="_blank" rel="noopener">查看原文</a></div></div>'+
    '<div class="bd">'+toHtml(it.body)+'</div><div class="nav">'+
    (p?'<a href="#" data-id="'+p.id+'">← '+esc(p.title)+'</a>':'<span class="dis">← 已是第一篇</span>')+
    (n?'<a href="#" data-id="'+n.id+'">'+esc(n.title)+' →</a>':'<span class="dis">已是最后一篇 →</span>')+
    '</div>';
  wrap.querySelectorAll('.nav a').forEach(function(a){
    a.onclick=function(e){e.preventDefault();show(a.dataset.id,true);};});
  toc.querySelectorAll('.it.on').forEach(function(e){e.classList.remove('on');});
  var el=toc.querySelector('.it[data-id="'+id+'"]');
  if(el){el.classList.add('on');el.scrollIntoView({block:'nearest'});}
  if(top) document.getElementById('main').scrollTop=0;
  location.hash=id;
}

function filter(){
  kw=q.value.trim(); var n=0;
  items.forEach(function(x){
    var el=toc.querySelector('.it[data-id="'+x.id+'"]'); if(!el) return;
    var hit=!kw||x.title.indexOf(kw)>=0||x.body.indexOf(kw)>=0;
    el.classList.toggle('hide',!hit); if(hit) n++;
  });
  stat.textContent=kw?('匹配 '+n+' 篇'):('共 '+items.length+' 篇 · '+D.books.length+' 个分册');
  if(cur&&kw) show(cur,false);
}

var base=17;
document.getElementById('fs').onclick=function(){base=Math.max(13,base-1);document.body.style.fontSize=base+'px';};
document.getElementById('fb').onclick=function(){base=Math.min(24,base+1);document.body.style.fontSize=base+'px';};
var side=document.getElementById('side');
document.getElementById('menuBtn').onclick=function(){side.classList.toggle('open');};
q.oninput=filter;
document.addEventListener('keydown',function(e){
  if(e.target===q||!cur) return;
  var i=items.indexOf(map[cur]);
  if(e.key==='ArrowLeft'&&i>0) show(items[i-1].id,true);
  if(e.key==='ArrowRight'&&i<items.length-1) show(items[i+1].id,true);
});

buildToc();
stat.textContent='共 '+items.length+' 篇 · '+D.books.length+' 个分册';
var h=location.hash.replace('#',''); if(h&&map[h]) show(h,true);
})();
</script>
</body>
</html>
"""

HTML = HTML.replace("__DATA__", data_json).replace("__CRAWL__", payload["crawled_at"])
open(OUT, "w", encoding="utf-8", newline="\n").write(HTML)
print(f"总集阅读器: {OUT}  ({len(HTML.encode('utf-8'))/1024/1024:.2f} MB)")
print(f"留学日记 {len(lx)} 篇 / 辑补卷 {len(bl)} 篇 / 晚年日记 {len(tw)} 篇 / 合计 {len(allitems)} 篇")
print(f"总字数 {sum(x['chars'] for x in allitems):,}")
