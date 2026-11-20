#!/usr/bin/env python3
"""Render a vocabulary-preview word list into CSV + a standalone visual HTML table.

Input: JSON produced from references/extraction_prompt.md output.
Output: vocab_preview.csv (utf-8-sig for Excel) + vocab_preview.html (zero dependencies).
Standard library only. All dynamic text is HTML-escaped.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from datetime import date
from pathlib import Path

FIELDS = [
    ("word", "单词"),
    ("phonetic", "音标"),
    ("pos", "词性"),
    ("cefr", "CEFR"),
    ("meaning_zh", "中文释义"),
    ("definition_en", "英文释义"),
    ("example_from_video", "视频原句"),
    ("example_extra", "补充例句"),
    ("example_zh", "例句翻译"),
    ("timestamp", "出现时间"),
    ("why_hard", "难点说明"),
    ("frequency", "词频"),
]
LEVEL_CLASS = {"A1": "a1", "A2": "a2", "B1": "b1", "B2": "b2", "C1": "c1", "C2": "c2"}
LEVEL_ORDER = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def norm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return str(value)


def normalize_words(raw) -> list[dict]:
    if isinstance(raw, dict):
        items = raw.get("words", raw.get("items", []))
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("JSON root must be an object or an array")
    if not isinstance(items, list):
        raise ValueError("'words' must be an array")
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rec = {key: norm(item.get(key, "")).strip() for key, _ in FIELDS}
        if not rec["word"]:
            continue
        rec["cefr"] = rec["cefr"].upper() or "B1"
        if rec["cefr"] not in LEVEL_CLASS:
            rec["cefr"] = "B1"
        try:
            rec["frequency"] = str(max(0, int(float(rec["frequency"] or 0))))
        except (TypeError, ValueError):
            rec["frequency"] = "0"
        out.append(rec)
    return out


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · 视频单词预习表</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#1b2333;--muted:#6b7488;--line:#e6e9f0;--brand:#3b5bdb;--brand-soft:#edf1ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.6}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header h1{font-size:26px;margin:0 0 6px;letter-spacing:-.3px}
header p{margin:0;color:var(--muted);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat b{display:block;font-size:24px;line-height:1.2;color:var(--brand)}
.stat span{font-size:12px;color:var(--muted)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:14px}
.toolbar input,.toolbar select,.toolbar button{font:inherit;font-size:13px;border:1px solid var(--line);border-radius:8px;padding:8px 11px;background:#fff;color:var(--ink)}
.toolbar input{flex:1;min-width:220px}
.toolbar button,.toolbar a.practice-link{cursor:pointer;background:var(--brand-soft);border-color:#dbe3ff;color:var(--brand)}
.toolbar a.practice-link{font:inherit;font-size:13px;border:1px solid #dbe3ff;border-radius:8px;padding:8px 11px;text-decoration:none}
.toolbar button:hover{background:#e0e7ff}
.hint{font-size:12px;color:var(--muted);margin-left:auto}
.tablecard{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:14px}
thead th{background:#fafbfe;text-align:left;padding:11px 12px;font-size:12px;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);white-space:nowrap}
thead th.sortable{cursor:pointer;user-select:none}
thead th.sortable:hover{color:var(--brand)}
tbody td{padding:11px 12px;border-bottom:1px solid #f0f2f7;vertical-align:top}
tr.word-row:hover{background:#fafbff}
.idx{color:#a6adbd;font-size:12px;width:38px}
.word{font-weight:650;font-size:15px;letter-spacing:.2px}
.phon{color:var(--muted);font-size:12px;font-family:Consolas,Monaco,monospace}
.pos{color:var(--muted);font-size:12px;white-space:nowrap}
.meaning{font-weight:500;min-width:120px}
.why{color:var(--muted);font-size:12px;max-width:260px}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.3px}
.b-b1{background:#e7f5ec;color:#1f7a45}.b-b2{background:#fff2d9;color:#9a6400}
.b-c1{background:#ffe6e2;color:#b3382a}.b-c2{background:#f0e4ff;color:#7134b5}
.b-a1,.b-a2{background:#eceff4;color:#5c6478}
.toggle{border:1px solid var(--line);background:#fff;border-radius:7px;padding:4px 9px;font-size:12px;cursor:pointer;color:var(--brand)}
.toggle:hover{background:var(--brand-soft)}
tr.detail td{background:#fbfcff;padding:0 12px 16px 62px;color:#3d465c;font-size:13px}
tr.detail[hidden]{display:none}
.dl{margin:12px 0 0;display:grid;grid-template-columns:88px 1fr;gap:6px 12px}
.dl dt{color:var(--muted);font-size:12px}
.dl dd{margin:0}
.quote{border-left:3px solid #cfd9ff;padding-left:10px;color:#2c3550}
.zh{color:var(--muted)}
time{font-family:Consolas,Monaco,monospace;font-size:12px;color:var(--brand);margin-right:6px}
footer{margin-top:18px;font-size:12px;color:var(--muted);text-align:center}
.legend span{display:inline-block;margin:0 6px}
.empty{padding:40px;text-align:center;color:var(--muted)}
@media(max-width:720px){.stats{grid-template-columns:repeat(2,1fr)}.why{display:none}.hint{display:none}}
@media print{.toolbar,.toggle{display:none}body{background:#fff}.tablecard{border:none}tr.detail[hidden]{display:table-row}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>__TITLE__</h1>
  <p>视频重难点单词预习表 · 来源 __SOURCE__ · 生成于 __DATE__ · 共 __TOTAL__ 词</p>
</header>

<div class="stats">
  <div class="stat"><b>__TOTAL__</b><span>预习单词</span></div>
  <div class="stat"><b>__B2PLUS__</b><span>B2 及以上</span></div>
  <div class="stat"><b>__C1PLUS__</b><span>C1 及以上</span></div>
  <div class="stat"><b>__WITHEX__</b><span>含视频原句</span></div>
</div>

<div class="toolbar">
  <input id="q" type="search" placeholder="搜索单词、释义、例句…" aria-label="搜索">
  <select id="level" aria-label="CEFR 筛选">
    <option value="">全部等级</option>
    <option value="B1">B1 及以上</option>
    <option value="B2">B2 及以上</option>
    <option value="C1">C1 及以上</option>
  </select>
  __PRACTICE_LINK__
  <button id="expand" type="button">展开全部例句</button>
  <button onclick="window.print()" type="button">打印 / 存 PDF</button>
  <span class="hint">点击「展开」查看视频原句与补充例句</span>
</div>

<div class="tablecard">
<table>
  <thead><tr>
    <th>#</th><th class="sortable" data-key="word">单词 / 音标</th><th>词性</th>
    <th class="sortable" data-key="cefr">CEFR</th><th>中文释义</th><th>难点说明</th><th></th>
  </tr></thead>
  <tbody id="rows">
__ROWS__
  </tbody>
</table>
<div class="empty" id="empty" hidden>没有匹配的单词，试试放宽筛选条件。</div>
</div>

<footer class="legend">
  CEFR 难度：<span>B1 进阶</span>·<span>B2 中高阶</span>·<span>C1 高阶</span>·<span>C2 近母语</span>
  &nbsp;|&nbsp; 由 video-vocab-preview 生成
</footer>
</div>

<script>
(function(){
  var rows = Array.prototype.slice.call(document.querySelectorAll('#rows tr.word-row'));
  var details = Array.prototype.slice.call(document.querySelectorAll('#rows tr.detail'));
  var q = document.getElementById('q');
  var sel = document.getElementById('level');
  var order = {'A1':0,'A2':1,'B1':2,'B2':3,'C1':4,'C2':5};
  var minLevel = {'B1':2,'B2':3,'C1':4};

  function apply(){
    var term = q.value.trim().toLowerCase();
    var lvl = sel.value;
    var shown = 0;
    rows.forEach(function(r,i){
      var d = details[i];
      var ok = (!term || r.dataset.search.indexOf(term) >= 0) &&
               (!lvl || (order[r.dataset.cefr] || 2) >= minLevel[lvl]);
      r.style.display = ok ? '' : 'none';
      if(!ok && d) d.hidden = true;
      if(ok) shown++;
    });
    document.getElementById('empty').hidden = shown > 0;
  }
  q.addEventListener('input', apply);
  sel.addEventListener('change', apply);

  document.getElementById('expand').addEventListener('click', function(){
    var anyHidden = details.some(function(d){return d.hidden;});
    details.forEach(function(d,i){ if(rows[i].style.display !== 'none') d.hidden = !anyHidden; });
    this.textContent = anyHidden ? '收起全部例句' : '展开全部例句';
  });

  document.getElementById('rows').addEventListener('click', function(e){
    var btn = e.target.closest('.toggle');
    if(!btn) return;
    var d = btn.closest('tr').nextElementSibling;
    d.hidden = !d.hidden;
    btn.textContent = d.hidden ? '展开' : '收起';
  });

  document.querySelectorAll('th.sortable').forEach(function(th){
    th.addEventListener('click', function(){
      var key = th.dataset.key;
      var pairs = rows.map(function(r,i){return {r:r, d:details[i]};});
      pairs.sort(function(a,b){
        var x = key === 'cefr' ? (order[a.r.dataset.cefr]||0) : a.r.dataset.word;
        var y = key === 'cefr' ? (order[b.r.dataset.cefr]||0) : b.r.dataset.word;
        return x < y ? -1 : (x > y ? 1 : 0);
      });
      var body = document.getElementById('rows');
      pairs.forEach(function(p){body.appendChild(p.r); if(p.d) body.appendChild(p.d);});
    });
  });
})();
</script>
</body>
</html>
"""


def render_rows(words: list[dict]) -> str:
    parts = []
    for i, w in enumerate(words, 1):
        blob = " ".join(w[k] for k, _ in FIELDS).lower()
        lvl = w["cefr"]
        cls = LEVEL_CLASS.get(lvl, "b1")
        video = w["example_from_video"]
        video_html = (
            '<time>' + esc(w["timestamp"]) + '</time><span class="quote">' + esc(video) + '</span>'
            if w["timestamp"] else '<span class="quote">' + esc(video) + '</span>'
        ) if video else '<span class="zh">（字幕中未定位到原句）</span>'
        extra = w["example_extra"] or "—"
        parts.append(
            '<tr class="word-row" data-cefr="' + esc(lvl) + '" data-word="' + esc(w["word"].lower())
            + '" data-search="' + esc(blob) + '">'
            + '<td class="idx">' + str(i) + '</td>'
            + '<td><div class="word">' + esc(w["word"]) + '</div><div class="phon">' + esc(w["phonetic"]) + '</div></td>'
            + '<td class="pos">' + esc(w["pos"]) + '</td>'
            + '<td><span class="badge b-' + cls + '">' + esc(lvl) + '</span></td>'
            + '<td class="meaning">' + esc(w["meaning_zh"]) + '</td>'
            + '<td class="why">' + esc(w["why_hard"]) + '</td>'
            + '<td><button class="toggle" type="button">展开</button></td></tr>'
            + '<tr class="detail" hidden><td colspan="7"><dl class="dl">'
            + '<dt>英文释义</dt><dd>' + esc(w["definition_en"] or "—") + '</dd>'
            + '<dt>视频原句</dt><dd>' + video_html + '</dd>'
            + '<dt>补充例句</dt><dd>' + esc(extra) + '</dd>'
            + '<dt>例句翻译</dt><dd class="zh">' + esc(w["example_zh"] or "—") + '</dd>'
            + '<dt>词频 / 难点</dt><dd>' + esc(w["frequency"]) + ' 次 · ' + esc(w["why_hard"] or "—") + '</dd>'
            + '</dl></td></tr>'
        )
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CSV + visual HTML vocabulary preview")
    ap.add_argument("input", help="word list JSON (object with 'words', or a plain array)")
    ap.add_argument("-o", "--outdir", default=".", help="output directory")
    ap.add_argument("--title", default="", help="table title")
    ap.add_argument("--source", default="", help="source label shown in subtitle")
    ap.add_argument("--practice-link", action="store_true", help="link to vocab_practice.html when bundled")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print("ERROR: file not found: " + str(src), file=sys.stderr)
        return 2
    try:
        raw = json.loads(src.read_text(encoding="utf-8-sig"))
        words = normalize_words(raw)
    except (ValueError, OSError) as e:
        print("ERROR: invalid input JSON: " + str(e), file=sys.stderr)
        return 2
    if not words:
        print("ERROR: no valid words (each item needs a non-empty 'word')", file=sys.stderr)
        return 2

    meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    title = args.title or norm(meta.get("title", "")) or "视频单词预习表"
    source = args.source or norm(meta.get("source", "")) or src.stem
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / "vocab_preview.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序号"] + [label for _, label in FIELDS])
        for i, w in enumerate(words, 1):
            writer.writerow([i] + [w[key] for key, _ in FIELDS])

    b2plus = sum(1 for w in words if LEVEL_ORDER[w["cefr"]] >= LEVEL_ORDER["B2"])
    c1plus = sum(1 for w in words if LEVEL_ORDER[w["cefr"]] >= LEVEL_ORDER["C1"])
    withex = sum(1 for w in words if w["example_from_video"])
    html_text = (HTML_TEMPLATE
                 .replace("__TITLE__", esc(title))
                 .replace("__SOURCE__", esc(source))
                 .replace("__PRACTICE_LINK__", ('<a class="practice-link" href="vocab_practice.html">开始主动回忆练习 →</a>' if args.practice_link else ''))
                 .replace("__DATE__", date.today().isoformat())
                 .replace("__TOTAL__", str(len(words)))
                 .replace("__B2PLUS__", str(b2plus))
                 .replace("__C1PLUS__", str(c1plus))
                 .replace("__WITHEX__", str(withex))
                 .replace("__ROWS__", render_rows(words)))
    html_path = outdir / "vocab_preview.html"
    html_path.write_text(html_text, encoding="utf-8")

    print("OK: " + str(len(words)) + " words")
    print("CSV : " + str(csv_path))
    print("HTML: " + str(html_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
