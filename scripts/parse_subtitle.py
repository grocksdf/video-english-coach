#!/usr/bin/env python3
"""Parse SRT / VTT / ASS / plain text into structured vocabulary candidates.

Output JSON is the input for the extraction prompt (references/extraction_prompt.md).
Standard library only. Deterministic, no network, no LLM.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because been before
being below between both but by can can't cannot could couldn't did didn't do does doesn't
doing don't down during each few for from further had hadn't has hasn't have haven't having
he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've
if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off
on once only or other ought our ours ourselves out over own same shan't she she'd she'll
she's should shouldn't so some such than that that's the their theirs them themselves then
there there's these they they'd they'll they're they've this those through to too under until
up very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's with won't would wouldn't you you'd you'll
you're you've your yours yourself yourselves just like get got make made really also even
still much many very well now here thing things way going want know think see said say
""".split())

TIME_LINE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{3})"
)
ASS_DIALOGUE = re.compile(r"^Dialogue:\s*", re.I)
ASS_TAG = re.compile(r"\{[^}]*\}")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
HTML_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = HTML_TAG.sub(" ", text)
    text = ASS_TAG.sub("", text)
    text = text.replace("\\N", " ").replace("\\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_srt(text: str) -> list[dict]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\ufeff", "", text)
    blocks = re.split(r"\n\s*\n", text)
    out: list[dict] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        time_idx = next((i for i, ln in enumerate(lines) if TIME_LINE.search(ln)), None)
        if time_idx is None:
            body = _clean(" ".join(lines))
            start = ""
        else:
            m = TIME_LINE.search(lines[time_idx])
            start = m.group(1).replace(",", ".") if m else ""
            body = _clean(" ".join(lines[time_idx + 1:]))
        if not body:
            continue
        out.append({"index": len(out) + 1, "start": start, "text": body})
    return out


def parse_vtt(text: str) -> list[dict]:
    text = re.sub(r"^WEBVTT[^\n]*\n", "", text)
    text = re.sub(r"NOTE\s+.*?(?=\n\n)", "", text, flags=re.S)
    return parse_srt(text)


def parse_ass(text: str) -> list[dict]:
    out: list[dict] = []
    for ln in text.splitlines():
        if not ASS_DIALOGUE.match(ln):
            continue
        parts = ln.split(",", 9)
        if len(parts) < 10:
            continue
        body = _clean(parts[9])
        if body:
            out.append({
                "index": len(out) + 1,
                "start": parts[1].strip(),
                "text": body,
            })
    return out


def parse_plain(text: str) -> list[dict]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    out = [{"index": i + 1, "start": "", "text": s}
           for i, s in enumerate(_clean(c) for c in chunks) if s]
    return out


def build_candidates(sentences: list[dict], min_len: int, top: int) -> list[dict]:
    freq: Counter[str] = Counter()
    contexts: dict[str, list[tuple[int, str]]] = {}
    for s in sentences:
        for raw in WORD_RE.findall(s["text"]):
            w = raw.lower().replace("’", "'").strip("-'")
            if len(w) < min_len or w in STOPWORDS or not w.isascii():
                continue
            freq[w] += 1
            contexts.setdefault(w, []).append((s["index"], s["text"]))
    result = []
    for word, count in freq.most_common():
        seen: set[int] = set()
        ctx = []
        for idx, text in contexts[word]:
            if idx not in seen:
                seen.add(idx)
                ctx.append({"sentence": idx, "text": text})
        result.append({"word": word, "frequency": count, "contexts": ctx[:3]})
    return result[:top] if top > 0 else result


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse subtitles into vocabulary candidates JSON")
    ap.add_argument("input", help="Path to .srt / .vtt / .ass / .txt")
    ap.add_argument("-o", "--output", default="", help="Output JSON path (default: stdout)")
    ap.add_argument("--top", type=int, default=120, help="Max candidates (0 = all)")
    ap.add_argument("--min-len", type=int, default=4, help="Minimum word length")
    args = ap.parse_args()

    path = Path(args.input)
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    raw = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            raw = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        print("ERROR: cannot decode file", file=sys.stderr)
        return 2

    suffix = path.suffix.lower()
    if suffix == ".ass" or suffix == ".ssa":
        sentences = parse_ass(raw)
    elif suffix == ".vtt":
        sentences = parse_vtt(raw)
    elif suffix == ".srt":
        sentences = parse_srt(raw)
    else:
        sentences = parse_plain(raw)
    if not sentences:
        print("ERROR: no subtitle text found", file=sys.stderr)
        return 2

    data = {
        "source": str(path),
        "sentence_count": len(sentences),
        "sentences": sentences,
        "candidates": build_candidates(sentences, args.min_len, args.top),
    }
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"OK: {len(sentences)} sentences, {len(data['candidates'])} candidates -> {out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
