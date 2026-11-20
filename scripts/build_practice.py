#!/usr/bin/env python3
"""Create a self-contained, offline active-recall and spaced-review page.

Consumes the unchanged twelve-field words.json vocabulary contract. Browser reviews
are self-rated and stored locally; progress can also be exported/imported as JSON.
Python 3.9+ standard library only. No external JavaScript, CSS or network calls.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

from build_preview import normalize_words

HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · 主动回忆训练</title>
<style>
:root{--ink:#142938;--muted:#596e7b;--paper:#f7f4ea;--card:#fffefa;--line:#dae0d9;--teal:#116e73;--mint:#d9eee5;--gold:#f8d596;--coral:#e88066;--shadow:0 16px 38px rgba(18,44,54,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.6}
.shell{max-width:960px;margin:auto;padding:34px 22px 72px}.eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;color:var(--teal)}
header{padding-bottom:22px;border-bottom:1px solid var(--line);display:flex;align-items:flex-end;justify-content:space-between;gap:18px}
h1{font-size:clamp(30px,5vw,52px);line-height:1.12;letter-spacing:-.04em;margin:13px 0 12px}header p{margin:0;color:var(--muted);max-width:640px;font-size:14px}
.monogram{flex-shrink:0;border:2px solid var(--teal);border-radius:50%;width:65px;height:65px;display:grid;place-items:center;color:var(--teal);font-family:Georgia,serif;font-size:24px;transform:rotate(-10deg)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}.stat{padding:20px;border-radius:15px;background:var(--card);border:1px solid var(--line)}.stat b{display:block;font-size:28px;line-height:1;color:var(--teal)}.stat span{display:block;color:var(--muted);font-size:12px;margin-top:10px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:26px;box-shadow:var(--shadow)}.sectiontitle{font-size:22px;letter-spacing:-.02em;margin:0 0 7px}.sub{font-size:13px;color:var(--muted);margin:0 0 24px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:16px 0}label{font-size:13px;font-weight:700;color:var(--ink)}select,input[type=text]{font:inherit;padding:12px 14px;border:1px solid #cbd6d2;border-radius:10px;background:white;color:var(--ink)}select:focus,input:focus,button:focus-visible{outline:3px solid #92c6bd;outline-offset:2px}
button,.filelabel{cursor:pointer;font:inherit;font-weight:650;border:1px solid var(--line);border-radius:11px;padding:11px 15px;background:#fff;color:var(--ink)}button:hover,.filelabel:hover{border-color:var(--teal)}.primary{background:var(--teal);color:white;border-color:var(--teal);padding:13px 20px}.primary:hover{background:#0c5459}.secondary{background:var(--mint);border-color:var(--mint);color:#104b4e}.filelabel{display:inline-block;font-size:13px}.filelabel input{display:none}.fine{font-size:12px;color:var(--muted)}.notice{background:#eef4ec;border-radius:12px;padding:13px 16px;font-size:13px;color:#355c58;margin:20px 0 0}
#practice,#results{display:none}#practice{padding-top:28px}.bar{height:7px;background:#e9eae2;border-radius:99px;overflow:hidden;margin:15px 0 27px}.bar>div{height:100%;background:var(--teal);width:0;transition:width .2s}.qtag{color:var(--teal);font-size:12px;font-weight:800;letter-spacing:.08em}
.question{font-size:clamp(24px,4vw,35px);font-weight:720;line-height:1.35;margin:18px 0 26px;white-space:pre-wrap;overflow-wrap:anywhere}.inputrow{display:flex;gap:12px}.inputrow input{min-width:0;flex:1;font-size:18px}.inputrow button{white-space:nowrap}.reveal{margin:22px 0 0;background:#ecf4f1;padding:20px;border-radius:13px;border-left:4px solid var(--teal)}.answer{font-size:28px;font-weight:800;color:var(--teal);margin:3px 0}.example{font-size:14px;color:#36535d;margin:8px 0}.translation{font-size:13px;color:var(--muted)}.grades{margin-top:20px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.grades button{padding:14px 10px}.grades button:nth-child(1){background:#fbe6dd;border-color:#f5c9ba}.grades button:nth-child(2){background:#fff1cd;border-color:#eedaa9}.grades button:nth-child(3){background:#d7eee3;border-color:#c2ddcf}
#results{margin-top:28px}.resultno{font-family:Georgia,serif;font-size:54px;color:var(--teal);line-height:1.2;margin:8px 0}.howto{margin-top:24px;padding-top:20px;border-top:1px solid var(--line)}.howto strong{font-size:13px}.howto p{font-size:13px;color:var(--muted);margin:5px 0}.status{min-height:22px;margin-top:14px;color:var(--teal);font-size:13px}
footer{margin-top:28px;border-top:1px solid var(--line);padding-top:15px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px}
@media(max-width:650px){.shell{padding:24px 14px 54px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:16px}.panel{padding:20px}.inputrow{flex-direction:column}.grades{grid-template-columns:1fr}header .monogram{display:none}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<div class="shell"><header><div><div class="eyebrow">ENGLISH LAB · ACTIVE RECALL / 02</div>
<h1>记得住，才算学会。</h1><p>__TITLE__ · 先尝试说出答案，再翻开提示。学过的词会按记忆情况安排后续复习。</p></div><div class="monogram" aria-hidden="true">EN</div></header>
<main>
<section class="stats" aria-label="学习进度"><div class="stat"><b id="due">—</b><span>今日到期复习</span></div><div class="stat"><b id="new">—</b><span>可以新学</span></div><div class="stat"><b id="seen">—</b><span>已练过的词</span></div><div class="stat"><b id="accuracy">—</b><span>自评记得比例</span></div></section>
<section class="panel" id="setup"><div class="eyebrow">01 / START HERE</div><h2 class="sectiontitle">开启今天的 10 分钟回忆练习</h2><p class="sub">每轮只学少量词。先回答，再对照答案，最后如实评价自己的掌握程度。</p>
<div class="row"><label for="mode">练习范围</label><select id="mode"><option value="due">今天到期 + 新词</option><option value="dueonly">仅复习到期词</option><option value="all">全部词汇（额外练习）</option></select><label for="limit">本轮数量</label><select id="limit"><option value="5">5 个</option><option value="10" selected>10 个</option><option value="15">15 个</option><option value="20">20 个</option></select></div>
<div class="row"><button class="primary" id="start">开始练习 →</button><button id="export">导出学习进度</button><label class="filelabel" for="import">导入进度文件<input type="file" id="import" accept="application/json,.json"></label></div>
<div class="fine">支持单词、词组、英文释义回忆和视频原句填空。答案核对仅检查参考词形，不等于智能评估口语或语义。</div>
<div class="notice">🔐 本页面不主动向服务器发送学习数据；进度保存在当前浏览器本地，不会自动跨设备同步。建议定期导出 JSON 备份，切换浏览器时可手动导入。</div><div class="status" id="status" role="status" aria-live="polite"></div></section>
<section id="practice" aria-label="回忆练习"><div class="eyebrow" id="counter">02 / PRACTICE</div><div class="bar"><div id="fill"></div></div><div class="panel"><div class="qtag" id="qtype"></div><div class="question" id="qtext"></div>
<div class="inputrow"><input id="attempt" type="text" autocomplete="off" spellcheck="false" placeholder="先在这里输入你想出的英文答案"><button class="secondary" id="reveal">查看参考答案</button></div>
<div id="revealbox" class="reveal" hidden><div class="qtag">REFERENCE ANSWER</div><div id="answer" class="answer"></div><div class="fine" id="comparison"></div><div id="original" class="example"></div><div id="extra" class="example"></div><div id="translation" class="translation"></div><div class="row"><button type="button" id="speak">🔊 系统朗读单词</button></div></div>
<div class="grades" id="grades" hidden><button data-grade="0">忘记了 · 本轮再练一次</button><button data-grade="1">有点模糊 · 明天复习</button><button data-grade="2">记得住 · 延长间隔</button></div><div class="fine" id="feedback" style="margin-top:15px">选择评价前先查看答案；「记得住」需要你自己确认理解和用法。</div></div></section>
<section id="results" class="panel"><div class="eyebrow">03 / WRAP UP</div><h2 class="sectiontitle">这轮复习完成啦 ✨</h2><div class="resultno" id="resultno"></div><p id="resulttext" class="sub"></p><button id="again" class="primary">返回学习面板</button>
<div class="howto"><strong>再向前一步 · 口语输出</strong><p>选 2–3 个今天的词，尝试不看字幕，用英文说 30 秒视频内容。把你的复述发给 ChatGPT，请它只纠正最影响表达的 2 个问题，然后再说一遍。</p></div></section>
</main><footer><span>VIDEO VOCAB · LEARN → RECALL → USE → REVIEW</span><span>离线练习 · 非自动提醒 · 词汇水平为估计值</span></footer></div>
<noscript>本练习页需要浏览器启用 JavaScript；词汇预习可使用同目录的 vocab_preview.html。</noscript>
<script>
'use strict';
const DATA=__DATA__;
const STORAGE_KEY='video-vocab-preview-progress-v2';
const el=id=>document.getElementById(id);
let memory={version:2,items:{}};
let storageWorks=true;
function today(){const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function plusDays(n){const d=new Date();d.setHours(12,0,0,0);d.setDate(d.getDate()+n);return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function safeId(x){return typeof x==='string' && /^[a-f0-9]{16}$/.test(x);}
function cleanItem(x){if(!x||typeof x!=='object'||Array.isArray(x))return null;return {stage:Math.max(0,Math.min(5,Number.isFinite(Number(x.stage))?Math.floor(Number(x.stage)):0)),due:typeof x.due==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x.due)?x.due:today(),attempts:Math.max(0,Math.min(100000,Math.floor(Number(x.attempts)||0))),successes:Math.max(0,Math.min(100000,Math.floor(Number(x.successes)||0))),last_review:typeof x.last_review==='string'?x.last_review:''};}
function load(){try{const raw=localStorage.getItem(STORAGE_KEY);if(raw){const p=JSON.parse(raw);if(p&&p.items&&typeof p.items==='object'){Object.keys(p.items).forEach(k=>{if(safeId(k)){const item=cleanItem(p.items[k]);if(item)memory.items[k]=item;}});}}}catch(e){storageWorks=false;el('status').textContent='浏览器未允许保存本地进度。练习可以进行，但结束后请导出进度 JSON。';}}
function save(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(memory));storageWorks=true;}catch(e){storageWorks=false;el('status').textContent='无法自动保存。请使用「导出学习进度」保留结果。';}}
function dueCards(){return DATA.cards.filter(c=>memory.items[c.id]&&memory.items[c.id].due<=today());}
function newCards(){return DATA.cards.filter(c=>!memory.items[c.id]);}
function refresh(){const items=Object.values(memory.items);let at=0,good=0;items.forEach(x=>{at+=x.attempts;good+=x.successes;});el('due').textContent=String(dueCards().length);el('new').textContent=String(newCards().length);el('seen').textContent=String(DATA.cards.filter(c=>!!memory.items[c.id]).length);el('accuracy').textContent=at?Math.round(good/at*100)+'%':'—';}
function shuffled(arr){const a=arr.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
let queue=[],current=null,total=0,shown=0,successes=0,recallLapses=new Set(),requeued=new Set();
function mask(original,word){const re=new RegExp('\\b'+word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\b','i');return re.test(original)?original.replace(re,'_____'):'';}
function question(c,index){const m=mask(c.example_from_video||'',c.word);
 if(index%3===2&&m)return ['字幕原句填空 · 回忆词汇',m];
 if(index%3===1&&c.definition_en)return ['英文释义 · 回忆词汇',c.definition_en];
 return ['中文释义 · 说出英文',c.meaning_zh||c.definition_en||'请回忆这个词'];}
function normal(s){return (s||'').toLowerCase().trim().replace(/[’‘]/g,"'").replace(/\s+/g,' ');}
function next(){
 el('revealbox').hidden=true;el('grades').hidden=true;el('feedback').textContent='先尝试想出答案，再核对词形与意思。';
 if(!queue.length){finish();return;}
 current=queue.shift();shown++;const x=question(current,shown-1);
 el('qtype').textContent=x[0]+' · '+current.cefr;el('qtext').textContent=x[1];el('attempt').value='';el('answer').textContent=current.word;
 el('original').textContent=current.example_from_video?'原句：'+current.example_from_video:'';
 el('extra').textContent=current.example_extra?'例句：'+current.example_extra:'';
 el('translation').textContent=current.example_zh?'例句翻译：'+current.example_zh:'';
 el('counter').textContent='02 / PRACTICE · 第 '+shown+' 题 · 还剩 '+queue.length+' 题';
 el('fill').style.width=Math.min(100,100*(shown-1)/(total||1))+'%';el('attempt').focus();
}
function reveal(){if(!current)return;el('revealbox').hidden=false;el('grades').hidden=false;
 const typed=normal(el('attempt').value);el('comparison').textContent=typed?(typed===normal(current.word)?'✓ 输入词形与参考答案一致（请自行确认意义和语境）。':'输入词形与参考答案不完全一致；可能存在词形变化或其他正确表达，请自行判断。'):'没有输入答案；请根据记忆情况评分。';}
function grade(n){if(!current||el('grades').hidden)return;const id=current.id;
 let x=memory.items[id]||{stage:0,due:today(),attempts:0,successes:0,last_review:''};
 x.attempts++;if(n===2){x.successes++;successes++;x.stage=Math.min(5,x.stage+1);x.due=plusDays([1,3,7,14,30][x.stage-1]);}
 else if(n===1){x.stage=0;x.due=plusDays(1);}else{x.stage=0;x.due=plusDays(1);recallLapses.add(id);if(!requeued.has(id)){queue.push(current);requeued.add(id);}}
 x.last_review=today();memory.items[id]=x;save();refresh();next();}
function finish(){el('practice').style.display='none';el('results').style.display='block';el('fill').style.width='100%';el('resultno').textContent=successes+' / '+shown;
 el('resulttext').textContent='上面是本轮自评“记得住”的次数（包含忘记后返场复习）。'+(recallLapses.size?' 有 '+recallLapses.size+' 个词曾经卡住，建议结合视频原句再说一次。':' 尝试用今天的三个词口头复述视频。');el('results').scrollIntoView({behavior:'smooth',block:'start'});}
function start(){const mode=el('mode').value,limit=Number(el('limit').value);const due=shuffled(dueCards()),fresh=shuffled(newCards());
 let list=mode==='dueonly'?due:mode==='all'?shuffled(DATA.cards):due.concat(fresh);
 queue=list.slice(0,limit);total=queue.length;shown=0;successes=0;recallLapses.clear();requeued.clear();
 if(!queue.length){el('status').textContent='当前范围没有要复习的词。可以切换成“全部词汇（额外练习）”。';return;}
 el('status').textContent='';el('setup').style.display='none';el('results').style.display='none';el('practice').style.display='block';next();}
function exportProgress(){const data=JSON.stringify({...memory,exported_at:new Date().toISOString()},null,2);const blob=new Blob([data],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='english-review-progress.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);el('status').textContent='已创建进度备份文件。';}
async function importProgress(e){const f=e.target.files&&e.target.files[0];if(!f)return;
 try{if(f.size>2*1024*1024)throw Error('文件超过 2 MB');const data=JSON.parse(await f.text());if(!data||data.version!==2||!data.items||typeof data.items!=='object'||Array.isArray(data.items))throw Error('格式不匹配');
 const imported={};Object.keys(data.items).forEach(k=>{if(safeId(k)){const x=cleanItem(data.items[k]);if(x)imported[k]=x;}});
 if(!Object.keys(imported).length)throw Error('没有有效记录');if(!confirm('用导入文件覆盖当前浏览器的复习进度吗？'))return;
 memory={version:2,items:imported};save();refresh();el('status').textContent='已导入 '+Object.keys(imported).length+' 条记录。';
 }catch(err){el('status').textContent='导入失败：'+err.message;}finally{e.target.value='';}}
el('start').addEventListener('click',start);el('reveal').addEventListener('click',reveal);el('attempt').addEventListener('keydown',e=>{if(e.key==='Enter')reveal();});
el('grades').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>grade(Number(b.dataset.grade))));
el('again').addEventListener('click',()=>{el('results').style.display='none';el('setup').style.display='block';el('setup').scrollIntoView({block:'start'});});
el('export').addEventListener('click',exportProgress);el('import').addEventListener('change',importProgress);
el('speak').addEventListener('click',()=>{if(!('speechSynthesis' in window)){el('feedback').textContent='这个浏览器不支持设备朗读。';return;}speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(current.word);u.lang='en-US';u.rate=.85;speechSynthesis.speak(u);el('feedback').textContent='这是设备合成朗读，并非视频原音；发音效果取决于设备和浏览器。';});
load();refresh();
</script>
</body></html>'''


def build_data(raw):
    words = normalize_words(raw)
    if not words:
        raise ValueError("word list is empty")
    meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    title = str(meta.get("title") or "英文视频词汇练习")
    source = str(meta.get("source") or "")
    cards = []
    for w in words:
        card = {k: w[k] for k in ["word", "cefr", "pos", "meaning_zh", "definition_en", "example_from_video", "example_extra", "example_zh"]}
        card["id"] = hashlib.sha256((w["word"].casefold().strip() + "|" + w["pos"].strip()).encode("utf-8")).hexdigest()[:16]
        if card["id"] not in [c["id"] for c in cards]:
            cards.append(card)
    return {"title": title, "source": source, "cards": cards}


def render(data):
    """Escape all potentially dangerous sequences inside the inline JSON assignment."""
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    serialized = (serialized.replace("<", "\\u003c").replace(">", "\\u003e")
                  .replace("&", "\\u0026").replace("\u2028", "\\u2028")
                  .replace("\u2029", "\\u2029"))
    return HTML.replace("__TITLE__", html.escape(data["title"])).replace("__DATA__", serialized)


def main():
    ap = argparse.ArgumentParser(description="Build a self-contained English active-recall practice page")
    ap.add_argument("input", help="words.json")
    ap.add_argument("-o", "--outdir", default=".")
    args = ap.parse_args()
    try:
        src = Path(args.input)
        raw = json.loads(src.read_text(encoding="utf-8-sig"))
        data = build_data(raw)
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        target = out / "vocab_practice.html"
        target.write_text(render(data), encoding="utf-8")
        print("OK: {} cards -> {}".format(len(data["cards"]), target))
        return 0
    except (OSError, ValueError, TypeError) as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
