#!/usr/bin/env python3
"""Unified, portable entry point for video-vocab-preview.

Every command works with Python 3.9+ standard library only. Add --json to any
command to receive a single machine-readable JSON object on stdout.

A video URL can be turned into the final CSV/HTML tables with `run`; the only
non-deterministic step (word selection) is delegated either to the calling
Agent (status: needs_llm) or to an external command via --llm-cmd.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROMPT_PATH = ROOT / "references" / "extraction_prompt.md"
SAMPLE_SRT = ROOT / "assets" / "sample_subtitle.srt"
SAMPLE_WORDS = ROOT / "assets" / "sample_words.json"

FIELDS = [
    ("word", "string", True, "小写词元"),
    ("phonetic", "string", False, "国际音标，带斜杠"),
    ("pos", "string", False, "词性缩写 n./v./adj./adv./phr."),
    ("cefr", "string", True, "A1 / A2 / B1 / B2 / C1 / C2"),
    ("meaning_zh", "string", True, "中文释义"),
    ("definition_en", "string", False, "简明英文释义"),
    ("example_from_video", "string", False, "视频原句，逐字引用"),
    ("example_extra", "string", False, "自造补充例句"),
    ("example_zh", "string", False, "补充例句中文翻译"),
    ("timestamp", "string", False, "原句起始时间"),
    ("why_hard", "string", True, "具体难点类型与理由"),
    ("frequency", "number", False, "字幕中出现次数，非负整数"),
]

SCHEMA = {
    "skill": "video-vocab-preview",
    "version": "2.0.0",
    "description": "Video vocabulary preview + active-recall practice + browser-local spaced-review (CSV + two offline HTML pages).",
    "runtime": {"python": ">=3.9", "third_party_dependencies": [],
                "network_required": "only for remote URLs",
                "optional_tools": ["yt-dlp", "ffmpeg", "whisper CLI"]},
    "entry": "python scripts/cli.py <command> [--json]",
    "variables": {
        "{{subtitle_text}}": "字幕原文或 candidates.json 文本",
        "{{learner_level}}": "学习者 CEFR 水平，例如 B2",
        "{{max_words}}": "词条数上限，例如 20",
    },
    "commands": {
        "schema": {"args": [], "returns": "本契约 JSON"},
        "fetch": {"args": ["input", "-o/--outdir", "--lang", "--ytdlp", "--ffmpeg", "--asr-cmd", "--subtitle-url", "--timeout"],
                  "returns": "字幕文件路径（srt/vtt/ass/txt）"},
        "parse": {"args": ["input", "-o/--output", "--top", "--min-len"],
                  "returns": "candidates.json 路径",
                  "accepts": [".srt", ".vtt", ".ass", ".ssa", ".txt"]},
        "prompt": {"args": ["--subtitle-file", "--level", "--max-words", "-o/--output"],
                   "returns": "已填充变量的 system prompt"},
        "prepare": {"args": ["input", "-o/--outdir", "--level", "--max-words"],
                    "returns": "candidates.json + llm_request.json，status=needs_llm"},
        "finalize": {"args": ["input(words.json)", "-o/--outdir", "--srt", "--title", "--source"],
                     "returns": "CSV + vocab_preview.html + vocab_practice.html + 契约校验"},
        "run": {"args": ["input(URL/字幕)", "-o/--outdir", "--llm-cmd"],
                "returns": "status=completed（有 LLM）或 status=needs_llm（Agent 接手）"},
        "render": {"args": ["input", "-o/--outdir", "--title", "--source"],
                   "returns": "CSV + vocab_preview.html + vocab_practice.html 路径"},
        "demo": {"args": ["-o/--outdir"], "returns": "全链路自测结果"},
    },
    "agent_protocol": {
        "1": "run <url> -o <dir> --json",
        "2": "若 status=needs_llm，读取 <dir>/llm_request.json 的 system_prompt 与 user_message",
        "3": "由调用方 Agent/LLM 产出单个合法 JSON 对象，写入 <dir>/words.json",
        "4": "finalize <dir>/words.json -o <dir> --srt <dir>/<字幕> --json",
        "5": "把返回的 csv / html / practice 路径交付用户",
    },
    "word_fields": [
        {"name": n, "type": t, "required": r, "description": d} for n, t, r, d in FIELDS
    ],
    "word_object": {
        "meta": {"title": "string", "source": "string",
                 "learner_level": "string", "word_count": "number"},
        "words": "array of objects with exactly the 12 word_fields",
    },
    "outputs": {
        "vocab_preview.csv": "UTF-8 with BOM; header = 序号 + 12 中文字段名",
        "vocab_preview.html": "UTF-8; standalone, zero external assets, offline-ready",
        "vocab_practice.html": "UTF-8; standalone self-rated recall practice with browser-local spaced-review and JSON backup",
    },
    "exit_codes": {"0": "成功（含 needs_llm 交接状态）", "1": "执行失败", "2": "输入或参数错误"},
    "json_envelope": {"ok": "boolean", "command": "string", "status": "completed|needs_llm",
                      "data": "object on success", "error": "string on failure"},
}


def emit(payload: dict, as_json: bool, human: str = "") -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif human:
        print(human)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_script(script: str, argv: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, str(HERE / script)] + [str(a) for a in argv]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except OSError as e:
        return 1, "cannot start python: " + str(e)
    text = (p.stdout or "").strip()
    if p.returncode != 0:
        return p.returncode, (p.stderr or text or "script failed").strip()
    return 0, text


def _extract_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def cmd_schema(args) -> int:
    emit(SCHEMA, args.as_json, json.dumps(SCHEMA, ensure_ascii=False, indent=2))
    return 0


def cmd_parse(args) -> int:
    src = Path(args.input)
    if not src.is_file():
        emit({"ok": False, "command": "parse", "error": "file not found: " + str(src)},
             args.as_json, "ERROR: file not found: " + str(src))
        return 2
    dest = Path(args.output) if args.output else Path.cwd() / "candidates.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(src), "-o", str(dest), "--top", str(args.top), "--min-len", str(args.min_len)]
    rc, text = run_script("parse_subtitle.py", argv)
    if rc:
        emit({"ok": False, "command": "parse", "error": text}, args.as_json, "ERROR: " + text)
        return rc
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
        count = len(data.get("candidates", []))
        sentences = data.get("sentence_count", 0)
    except (OSError, ValueError) as e:
        emit({"ok": False, "command": "parse", "error": str(e)}, args.as_json, "ERROR: " + str(e))
        return 1
    payload = {"ok": True, "command": "parse",
               "data": {"output": str(dest), "sentences": sentences, "candidates": count}}
    emit(payload, args.as_json,
         "OK: {} sentences, {} candidates -> {}".format(sentences, count, dest))
    return 0


def cmd_render(args) -> int:
    src = Path(args.input)
    if not src.is_file():
        emit({"ok": False, "command": "render", "error": "file not found: " + str(src)},
             args.as_json, "ERROR: file not found: " + str(src))
        return 2
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    argv = [str(src), "-o", str(outdir), "--practice-link"]
    if args.title:
        argv += ["--title", args.title]
    if args.source:
        argv += ["--source", args.source]
    rc, text = run_script("build_preview.py", argv)
    if rc:
        emit({"ok": False, "command": "render", "error": text}, args.as_json, "ERROR: " + text)
        return rc
    try:
        raw = json.loads(src.read_text(encoding="utf-8-sig"))
        items = raw.get("words", []) if isinstance(raw, dict) else raw
        count = len([x for x in items if isinstance(x, dict) and str(x.get("word", "")).strip()])
    except (OSError, ValueError):
        count = 0
    rc, study_msg = run_script("build_practice.py", [str(src), "-o", str(outdir)])
    if rc:
        emit({"ok": False, "command": "render", "error": study_msg}, args.as_json,
             "ERROR: " + study_msg)
        return rc
    csv_path = outdir / "vocab_preview.csv"
    html_path = outdir / "vocab_preview.html"
    practice_path = outdir / "vocab_practice.html"
    payload = {"ok": True, "command": "render",
               "data": {"word_count": count, "csv": str(csv_path), "html": str(html_path),
                        "practice": str(practice_path)}}
    emit(payload, args.as_json,
         text + "\nPRACTICE: " + str(practice_path))
    return 0


def cmd_prompt(args) -> int:
    if not PROMPT_PATH.is_file():
        msg = "missing prompt file: " + str(PROMPT_PATH)
        emit({"ok": False, "command": "prompt", "error": msg}, args.as_json, "ERROR: " + msg)
        return 2
    template = PROMPT_PATH.read_text(encoding="utf-8")
    if args.subtitle_file:
        p = Path(args.subtitle_file)
        if not p.is_file():
            msg = "subtitle file not found: " + str(p)
            emit({"ok": False, "command": "prompt", "error": msg}, args.as_json, "ERROR: " + msg)
            return 2
        subtitle = p.read_text(encoding="utf-8-sig", errors="replace")
    else:
        subtitle = "<在此粘贴字幕原文或 candidates.json 文本>"
    filled = (template
              .replace("{{subtitle_text}}", subtitle)
              .replace("{{learner_level}}", args.level)
              .replace("{{max_words}}", str(args.max_words)))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(filled, encoding="utf-8")
        payload = {"ok": True, "command": "prompt",
                   "data": {"output": str(out), "characters": len(filled),
                            "variables": {"subtitle_text": args.subtitle_file or "placeholder",
                                          "learner_level": args.level,
                                          "max_words": args.max_words}}}
        emit(payload, args.as_json, "OK: filled system prompt -> {} ({} chars)".format(out, len(filled)))
    else:
        payload = {"ok": True, "command": "prompt", "data": {"prompt": filled}}
        emit(payload, args.as_json, filled)
    return 0


# ---- 链接 → 交付物 --------------------------------------------------------

def _fetch(args, outdir: Path):
    argv = [args.input, "-o", str(outdir), "--lang", args.lang,
            "--timeout", str(args.timeout)]
    if getattr(args, "ytdlp", ""):
        argv += ["--ytdlp", args.ytdlp]
    if getattr(args, "subtitle_url", ""):
        argv += ["--subtitle-url", args.subtitle_url]
    if getattr(args, "ffmpeg", ""):
        argv += ["--ffmpeg", args.ffmpeg]
    if getattr(args, "asr_cmd", ""):
        argv += ["--asr-cmd", args.asr_cmd]
    cmd = [sys.executable, str(HERE / "fetch_subtitle.py")] + [str(a) for a in argv]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=args.timeout + 60)
        text = (p.stdout or "").strip()
        data = json.loads(_extract_json(text))
    except subprocess.TimeoutExpired:
        return None, {"error": "字幕获取超时"}
    except (OSError, ValueError) as e:
        return None, {"error": "fetch_subtitle 未返回合法 JSON: " + str(e)}
    if p.returncode != 0 or not data.get("ok"):
        return None, data
    return data["srt"], data


def _prepare(args, outdir: Path):
    srt, info = _fetch(args, outdir)
    if not srt:
        return ({"ok": False, "stage": "fetch",
                 "error": info.get("error", "字幕获取失败"),
                 "hint": info.get("hint", ""),
                 "details": info.get("details", {})}, 1)
    cand = outdir / "candidates.json"
    rc, text = run_script("parse_subtitle.py",
                          [srt, "-o", str(cand), "--top", str(args.top)])
    if rc:
        return {"ok": False, "stage": "parse", "error": text}, 1
    try:
        cand_data = json.loads(cand.read_text(encoding="utf-8"))
        subtitle_text = Path(srt).read_text(encoding="utf-8-sig", errors="replace")
        template = PROMPT_PATH.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        return {"ok": False, "stage": "prepare", "error": str(e)}, 1

    system_prompt = (template
                     .replace("{{subtitle_text}}", subtitle_text)
                     .replace("{{learner_level}}", args.level)
                     .replace("{{max_words}}", str(args.max_words)))
    request = {
        "version": "1.0",
        "skill": "video-vocab-preview",
        "system_prompt": system_prompt,
        "user_message": ("按 Output Format 输出词表 JSON。字幕共 {} 句，候选词 {} 个，"
                         "词条上限 {}。").format(cand_data.get("sentence_count", 0),
                                                len(cand_data.get("candidates", [])),
                                                args.max_words),
        "variables": {"learner_level": args.level, "max_words": args.max_words},
        "expected_output_file": str(outdir / "words.json"),
        "subtitle_file": srt,
    }
    req_path = outdir / "llm_request.json"
    req_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    return ({"ok": True, "stage": "prepare", "srt": srt,
             "candidates": str(cand), "llm_request": str(req_path),
             "words_path": str(outdir / "words.json"),
             "sentence_count": cand_data.get("sentence_count", 0),
             "candidate_count": len(cand_data.get("candidates", [])),
             "fetch": info}, 0)


def _validate_words(data, srt_text: str = ""):
    names = {n for n, _, _, _ in FIELDS}
    words = data.get("words", []) if isinstance(data, dict) else data
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    checks = []

    def chk(name, ok):
        checks.append({"name": name, "passed": bool(ok)})

    chk("词表为非空数组", isinstance(words, list) and len(words) > 0)
    if not isinstance(words, list):
        return checks
    chk("每词恰好 12 字段", all(isinstance(w, dict) and set(w) == names for w in words))
    chk("word 非空", all(isinstance(w, dict) and str(w.get("word", "")).strip() for w in words))
    chk("词条无重复", len({w.get("word") for w in words if isinstance(w, dict)}) == len(words))
    chk("cefr 取值合法", all(w.get("cefr") in {"A1", "A2", "B1", "B2", "C1", "C2"} for w in words))
    chk("补充例句均有中文翻译",
        all(not w.get("example_extra") or w.get("example_zh") for w in words))
    chk("frequency 为非负整数",
        all(isinstance(w.get("frequency", 0), int) and w.get("frequency", 0) >= 0 for w in words))
    chk("无未消费变量", "{{" not in json.dumps(data, ensure_ascii=False))
    if isinstance(data, dict):
        chk("meta.word_count 与数组长度一致", meta.get("word_count") == len(words))
    if srt_text:
        flat = " ".join(srt_text.split())
        chk("视频原句逐字来自字幕",
            all(not w.get("example_from_video") or w.get("example_from_video") in flat for w in words))
    return checks


def _finalize(words_path, outdir, title="", source="", srt=""):
    p = Path(words_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if not p.is_file():
        return {"ok": False, "stage": "finalize", "error": "words file not found: " + str(p)}, 2
    try:
        data = json.loads(_extract_json(p.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError) as e:
        return {"ok": False, "stage": "finalize", "error": "words JSON 非法: " + str(e)}, 2
    srt_text = ""
    if srt and Path(srt).is_file():
        srt_text = Path(srt).read_text(encoding="utf-8-sig", errors="replace")
    checks = _validate_words(data, srt_text)
    invalid = [c["name"] for c in checks if not c["passed"]]
    if invalid:
        return ({"ok": False, "stage": "validation", "checks": checks,
                 "invalid_checks": invalid,
                 "error": "词表契约不通过；请先修正（尤其不得伪造字幕原句）：" + "、".join(invalid)}, 2)
    words = data.get("words", []) if isinstance(data, dict) else data
    argv = [str(p), "-o", str(outdir), "--practice-link",
            "--title", title or "视频单词预习表",
            "--source", source or p.name]
    rc, text = run_script("build_preview.py", argv)
    if rc:
        return {"ok": False, "stage": "render", "error": text, "checks": checks}, 1
    rc, study_msg = run_script("build_practice.py", [str(p), "-o", str(outdir)])
    if rc:
        return {"ok": False, "stage": "practice", "error": study_msg, "checks": checks}, 1
    return ({"ok": True, "stage": "finalize",
             "contract_valid": all(c["passed"] for c in checks),
             "checks": checks, "word_count": len(words),
             "csv": str(outdir / "vocab_preview.csv"),
             "html": str(outdir / "vocab_preview.html"),
             "practice": str(outdir / "vocab_practice.html")}, 0)


def cmd_fetch(args) -> int:
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    srt, info = _fetch(args, outdir)
    if not srt:
        emit({"ok": False, "command": "fetch",
              "error": info.get("error", ""), "hint": info.get("hint", ""),
              "details": info.get("details", {})},
             args.as_json, "ERROR: " + str(info.get("error", "")))
        return 1
    payload = {"ok": True, "command": "fetch", "data": info}
    emit(payload, args.as_json,
         "OK: {}  <- {}".format(info["srt"], info.get("source", "")))
    return 0


def cmd_prepare(args) -> int:
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    data, rc = _prepare(args, outdir)
    if rc:
        emit({"ok": False, "command": "prepare", **{k: v for k, v in data.items() if k != "ok"}},
             args.as_json, "ERROR: " + str(data.get("error", "")))
        return rc
    payload = {"ok": True, "command": "prepare", "status": "needs_llm",
               "data": {"srt": data["srt"], "candidates": data["candidates"],
                        "llm_request": data["llm_request"],
                        "words_path": data["words_path"],
                        "sentence_count": data["sentence_count"],
                        "candidate_count": data["candidate_count"]},
               "next_step": ("读取 llm_request.json 的 system_prompt，由调用方 Agent/LLM 产出"
                             "词表 JSON 写入 words.json，再运行 cli.py finalize")}
    emit(payload, args.as_json,
         "PREPARE OK: {} 句 / {} 候选词\n字幕: {}\n请求: {}\n下一步: 写入 {}".format(
             data["sentence_count"], data["candidate_count"], data["srt"],
             data["llm_request"], data["words_path"]))
    return 0


def cmd_finalize(args) -> int:
    data, rc = _finalize(args.input, args.outdir, args.title, args.source, args.srt)
    if rc:
        emit({"ok": False, "command": "finalize",
              **{k: v for k, v in data.items() if k != "ok"}},
             args.as_json, "ERROR: " + str(data.get("error", "")))
        return rc
    payload = {"ok": True, "command": "finalize", "status": "completed", "data": data}
    emit(payload, args.as_json,
         "FINALIZE OK: {} 词 | 契约校验 {}\nCSV : {}\nHTML: {}".format(
             data["word_count"], "通过" if data["contract_valid"] else "有告警",
             data["csv"], data["html"]) + "\nPRACTICE: " + data["practice"])
    return 0


def cmd_run(args) -> int:
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    prep, rc = _prepare(args, outdir)
    if rc:
        emit({"ok": False, "command": "run", "stage": "prepare",
              **{k: v for k, v in prep.items() if k != "ok"}},
             args.as_json, "ERROR: " + str(prep.get("error", "")))
        return rc

    llm_cmd = args.llm_cmd or os.environ.get("VVP_LLM_CMD", "")
    if not llm_cmd:
        payload = {"ok": True, "command": "run", "status": "needs_llm",
                   "data": {"srt": prep["srt"], "candidates": prep["candidates"],
                            "llm_request": prep["llm_request"],
                            "words_path": prep["words_path"],
                            "sentence_count": prep["sentence_count"],
                            "candidate_count": prep["candidate_count"]},
                   "next_step": ("调用方 Agent 读取 llm_request.json，自己产出词表 JSON "
                                 "写入 words.json，然后运行：cli.py finalize <words.json> "
                                 "-o <outdir> --srt <srt> --json")}
        emit(payload, args.as_json,
             "STEP 1/2 完成：字幕已取得并解析（{} 句 / {} 候选词）\n请求: {}\n"
             "等待模型产出 words.json …".format(prep["sentence_count"],
                                              prep["candidate_count"], prep["llm_request"]))
        return 0

    try:
        argv = shlex.split(llm_cmd, posix=(os.name != "nt"))
        request_text = Path(prep["llm_request"]).read_text(encoding="utf-8")
        p = subprocess.run(argv, input=request_text, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        emit({"ok": False, "command": "run", "stage": "llm", "error": str(e)},
             args.as_json, "ERROR: " + str(e))
        return 1
    if p.returncode != 0:
        emit({"ok": False, "command": "run", "stage": "llm",
              "error": "LLM command exited with code {}: {}".format(
                  p.returncode, (p.stderr or "")[-400:])},
             args.as_json, "ERROR: LLM command failed")
        return 1
    words_text = _extract_json(p.stdout or "")
    try:
        json.loads(words_text)
    except ValueError as e:
        emit({"ok": False, "command": "run", "stage": "llm",
              "error": "LLM 输出不是合法 JSON: " + str(e),
              "raw": words_text[:300], "stderr": (p.stderr or "")[-300:]},
             args.as_json, "ERROR: LLM 输出不是合法 JSON")
        return 1
    Path(prep["words_path"]).write_text(words_text, encoding="utf-8")

    fin, frc = _finalize(prep["words_path"], outdir, args.title, args.source, prep["srt"])
    if frc:
        emit({"ok": False, "command": "run", "stage": "finalize",
              **{k: v for k, v in fin.items() if k != "ok"}},
             args.as_json, "ERROR: " + str(fin.get("error", "")))
        return frc
    payload = {"ok": True, "command": "run", "status": "completed",
               "data": {"srt": prep["srt"], "words": prep["words_path"], **fin}}
    emit(payload, args.as_json,
         "RUN OK: {} 词\nCSV : {}\nHTML: {}".format(fin["word_count"],
                                                   fin["csv"], fin["html"]) + "\nPRACTICE: " + fin["practice"])
    return 0


def cmd_demo(args) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    checks = []

    cand = outdir / "candidates.json"
    rc, text = run_script("parse_subtitle.py", [str(SAMPLE_SRT), "-o", str(cand), "--top", "120"])
    checks.append({"name": "parse_subtitle", "passed": rc == 0})
    if rc:
        emit({"ok": False, "command": "demo", "error": text, "checks": checks},
             args.as_json, "ERROR: " + text)
        return 1
    cand_data = json.loads(cand.read_text(encoding="utf-8"))

    rc, text = run_script("build_preview.py", [str(SAMPLE_WORDS), "-o", str(outdir),
                                               "--practice-link", "--title", "Sleep & Memory · 视频单词预习表",
                                               "--source", "sample_subtitle.srt"])
    checks.append({"name": "render_csv_html", "passed": rc == 0})
    if rc:
        emit({"ok": False, "command": "demo", "error": text, "checks": checks},
             args.as_json, "ERROR: " + text)
        return 1

    rc, text = run_script("build_practice.py", [str(SAMPLE_WORDS), "-o", str(outdir)])
    checks.append({"name": "render_practice_html", "passed": rc == 0})
    if rc:
        emit({"ok": False, "command": "demo", "error": text, "checks": checks},
             args.as_json, "ERROR: " + text)
        return 1

    words = json.loads(SAMPLE_WORDS.read_text(encoding="utf-8")).get("words", [])
    csv_path = outdir / "vocab_preview.csv"
    html_path = outdir / "vocab_preview.html"
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.reader(f))
    checks.append({"name": "csv_row_count", "passed": len(csv_rows) == len(words) + 1})
    html_text = html_path.read_text(encoding="utf-8")
    checks.append({"name": "html_table_structure",
                   "passed": "<table" in html_text and 'class="word-row"' in html_text})
    missing = [w["word"] for w in words if ">" + w["word"] + "<" not in html_text]
    checks.append({"name": "all_words_rendered", "passed": not missing})
    checks.append({"name": "no_external_assets",
                   "passed": "http://" not in html_text and "https://" not in html_text})
    practice_path = outdir / "vocab_practice.html"
    study_text = practice_path.read_text(encoding="utf-8")
    checks.append({"name": "practice_offline_and_interactive",
                   "passed": ("https://" not in study_text and "http://" not in study_text
                              and "localStorage" in study_text and "导出学习进度" in study_text
                              and "字幕原句填空" in study_text)})
    checks.append({"name": "word_contract",
                   "passed": all(c["passed"] for c in _validate_words(
                       json.loads(SAMPLE_WORDS.read_text(encoding="utf-8")),
                       SAMPLE_SRT.read_text(encoding="utf-8")))})

    passed = all(c["passed"] for c in checks)
    payload = {"ok": passed, "command": "demo",
               "data": {"outdir": str(outdir), "word_count": len(words),
                        "sentence_count": cand_data.get("sentence_count", 0),
                        "candidate_count": len(cand_data.get("candidates", [])),
                        "csv": str(csv_path), "html": str(html_path),
                        "practice": str(practice_path), "checks": checks,
                        "missing_words": missing}}
    if passed:
        emit(payload, args.as_json,
             "DEMO OK: {} words, {} checks passed\nCSV : {}\nHTML: {}".format(
                 len(words), len(checks), csv_path, html_path) +
             "\nPRACTICE: " + str(practice_path))
        return 0
    emit(payload, args.as_json, "DEMO FAILED: " + json.dumps(checks, ensure_ascii=False))
    return 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", dest="as_json", action="store_true",
                        help="emit a single machine-readable JSON object")

    link = argparse.ArgumentParser(add_help=False)
    link.add_argument("input", help="video URL, subtitle URL, subtitle file, or local media")
    link.add_argument("-o", "--outdir", default=".")
    link.add_argument("--level", default="B2")
    link.add_argument("--max-words", type=int, default=20)
    link.add_argument("--top", type=int, default=120)
    link.add_argument("--lang", default="en.*")
    link.add_argument("--timeout", type=int, default=180)
    link.add_argument("--ytdlp", default="", help="path to yt-dlp executable")
    link.add_argument("--ffmpeg", default="", help="path to ffmpeg executable")
    link.add_argument("--asr-cmd", default="", help="optional ASR command template")
    link.add_argument("--subtitle-url", default="", help="explicit subtitle URL")
    link.add_argument("--title", default="")
    link.add_argument("--source", default="")
    link.add_argument("--llm-cmd", default="",
                      help="external command reading llm_request.json on stdin, writing words JSON on stdout")

    ap = argparse.ArgumentParser(description="video-vocab-preview unified CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("schema", parents=[common], help="print the machine-readable contract")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("parse", parents=[common], help="subtitle -> candidates.json")
    p.add_argument("input")
    p.add_argument("-o", "--output", default="")
    p.add_argument("--top", type=int, default=120)
    p.add_argument("--min-len", type=int, default=4)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("render", parents=[common], help="words.json -> CSV + HTML")
    p.add_argument("input")
    p.add_argument("-o", "--outdir", default=".")
    p.add_argument("--title", default="")
    p.add_argument("--source", default="")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("prompt", parents=[common], help="emit the filled system prompt")
    p.add_argument("--subtitle-file", default="")
    p.add_argument("--level", default="B2")
    p.add_argument("--max-words", type=int, default=20)
    p.add_argument("-o", "--output", default="")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("fetch", parents=[common, link], help="URL/media -> subtitle file")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("prepare", parents=[common, link],
                       help="URL/media -> candidates.json + llm_request.json")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("finalize", parents=[common, link],
                       help="words.json -> CSV + HTML with contract checks")
    p.add_argument("--srt", default="", help="subtitle file for verbatim-quote validation")
    p.set_defaults(func=cmd_finalize)

    p = sub.add_parser("run", parents=[common, link],
                       help="one-shot URL -> CSV + HTML (needs_llm handoff or --llm-cmd)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("demo", parents=[common], help="run the full self-test")
    p.add_argument("-o", "--outdir", default=".")
    p.set_defaults(func=cmd_demo)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as e:
        emit({"ok": False, "command": args.command, "error": str(e)},
             args.as_json, "ERROR: " + str(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
