#!/usr/bin/env python3
"""Resolve a video link / subtitle link / local media into a subtitle file.

Optional external tools are auto-detected, never bundled and never required for
direct subtitle URLs:
  yt-dlp  : extract manual / auto subtitles from video pages
  ffmpeg  : extract embedded subtitle tracks from local media, extract audio
  ASR CLI : transcribe audio when no subtitle track exists

Override with env vars VVP_YTDLP / VVP_FFMPEG / VVP_ASR_CMD / VVP_WHISPER,
or flags --ytdlp / --ffmpeg / --asr-cmd.
Stdout is always one JSON object, so any agent or script can consume it.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SUB_EXT = (".srt", ".vtt", ".ass", ".ssa", ".txt")
UA = "Mozilla/5.0 (compatible; video-vocab-preview/1.0)"
MAX_SUBTITLE_BYTES = 12 * 1024 * 1024


def make_opener(url: str):
    """Bypass system proxies for loopback URLs (they are often hijacked)."""
    host = urllib.parse.urlparse(url).hostname
    if host in ("127.0.0.1", "localhost", "::1"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def find_tool(override: str, names: list[str], envvar: str):
    cands = [c for c in (override, os.environ.get(envvar)) if c]
    cands.extend(names)
    for c in cands:
        try:
            p = shutil.which(str(c))
            if p:
                return p
            if Path(str(c)).is_file():
                return str(Path(str(c)).resolve())
        except OSError:
            continue
    return None


def ytdlp_cmd(override: str):
    exe = find_tool(override, ["yt-dlp", "yt-dlp.exe"], "VVP_YTDLP")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def run(argv: list[str], timeout: int):
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after {}s".format(timeout)
    except OSError as e:
        return 1, "", str(e)


def snapshot(outdir: Path) -> set[str]:
    return {str(p) for p in outdir.iterdir() if p.is_file()}


def subtitle_files(outdir: Path, before: set[str] | None = None) -> list[Path]:
    files = [p for p in outdir.iterdir()
             if p.is_file() and p.suffix.lower() in SUB_EXT
             and p.name != "words.json" and p.name != "llm_request.json"]
    if before is not None:
        files = [p for p in files if str(p) not in before]
    rank = {".srt": 0, ".vtt": 1, ".ass": 2, ".ssa": 3, ".txt": 4}
    files.sort(key=lambda p: (rank.get(p.suffix.lower(), 9),
                              0 if ".en" in p.name.lower() else 1, p.name))
    return files


def decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


MEDIA_EXT = (".mp4", ".mkv", ".mov", ".webm", ".m4v", ".mp3", ".m4a",
             ".wav", ".aac", ".flac", ".ogg")
MAX_MEDIA_BYTES = 300 * 1024 * 1024


def download_media(url: str, outdir: Path, timeout: int):
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "media.mp4"
    dest = outdir / name
    if parsed.scheme == "file":
        src = Path(urllib.request.url2pathname(parsed.path))
        return (src if src.is_file() else None), ("" if src.is_file() else "file 不存在")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, dest.open("wb") as f:
            total = 0
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_MEDIA_BYTES:
                    return None, "媒体文件超过 300 MB 上限"
                f.write(chunk)
    except Exception as e:
        return None, "媒体下载失败: " + str(e)
    return dest, ""


def fetch_direct_subtitle(url: str, outdir: Path, timeout: int):
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "subtitle.srt"
    if not name.lower().endswith(SUB_EXT):
        name += ".srt"
    dest = outdir / name
    if parsed.scheme == "file":
        src = Path(urllib.request.url2pathname(parsed.path))
        if not src.is_file():
            return None, "file:// 指向的文件不存在: " + str(src)
        dest.write_bytes(src.read_bytes())
        return dest, ""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with make_opener(url).open(req, timeout=timeout) as r:
            data = r.read(MAX_SUBTITLE_BYTES + 1)
    except Exception as e:
        return None, "字幕下载失败: " + str(e)
    if len(data) > MAX_SUBTITLE_BYTES:
        return None, "字幕文件超过 12 MB"
    dest.write_text(decode(data), encoding="utf-8")
    return dest, ""


def ytdlp_subs(url: str, outdir: Path, tool: list[str], lang: str, timeout: int):
    before = snapshot(outdir)
    argv = tool + [
        "--no-warnings", "--no-playlist", "--skip-download",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", lang, "--sub-format", "srt/vtt/ass/best",
        "-o", str(outdir / "%(title)s.%(ext)s"), url,
    ]
    rc, out, err = run(argv, timeout)
    files = subtitle_files(outdir, before)
    if files:
        return files[0], "yt-dlp 字幕轨道", ""
    return None, "", "yt-dlp 未取到字幕({}): {}".format(lang, (err or out)[-260:])


def ytdlp_audio(url: str, outdir: Path, tool: list[str], timeout: int):
    argv = tool + [
        "--no-warnings", "--no-playlist", "--extract-audio",
        "--audio-format", "mp3", "-o", str(outdir / "audio.%(ext)s"), url,
    ]
    rc, out, err = run(argv, timeout)
    files = [p for p in outdir.iterdir()
             if p.is_file() and p.name.startswith("audio.")
             and p.suffix.lower() in (".mp3", ".m4a", ".wav", ".webm", ".opus")]
    return (files[0] if files else None), (err or out)[-260:]


def asr_transcribe(media: Path, outdir: Path, override: str, timeout: int):
    cmd = override or os.environ.get("VVP_ASR_CMD")
    if not cmd:
        exe = find_tool("", ["whisper", "whisper-ctranslate2", "faster-whisper"], "VVP_WHISPER")
        if not exe:
            return None, ("无字幕且未配置 ASR。设置 --asr-cmd 或环境变量 VVP_ASR_CMD，"
                          "模板变量: {audio} {outdir} {srt}")
        cmd = ('"{}" "{{audio}}" --model base.en --language en '
               '--output_format srt --output_dir "{{outdir}}"').format(exe)
    srt = outdir / "asr.srt"
    cmd = (cmd.replace("{audio}", str(media))
              .replace("{outdir}", str(outdir))
              .replace("{srt}", str(srt)))
    try:
        argv = shlex.split(cmd, posix=(os.name != "nt"))
    except ValueError as e:
        return None, "ASR 命令解析失败: " + str(e)
    rc, out, err = run(argv, timeout)
    files = subtitle_files(outdir)
    if files:
        return files[0], ""
    return None, "ASR 未产出字幕: " + (err or out)[-260:]


def from_local(path: Path, outdir: Path, ffmpeg, asr_cmd: str, timeout: int):
    if path.suffix.lower() in SUB_EXT:
        dest = outdir / path.name
        shutil.copyfile(path, dest)
        return dest, "本地字幕文件", ""
    if ffmpeg:
        dest = outdir / (path.stem + ".srt")
        argv = [ffmpeg, "-nostdin", "-y", "-i", str(path),
                "-map", "0:s:0?", "-c:s", "srt", str(dest)]
        rc, out, err = run(argv, timeout)
        if dest.is_file() and dest.stat().st_size > 0:
            return dest, "ffmpeg 抽取内嵌字幕", ""
    srt, err = asr_transcribe(path, outdir, asr_cmd, timeout)
    if srt:
        return srt, "本地 ASR 转写", ""
    return None, "", err


def main() -> int:
    ap = argparse.ArgumentParser(description="video link / subtitle link / local media -> subtitle file")
    ap.add_argument("input", help="video URL, subtitle URL, or local path")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--lang", default="en.*", help="yt-dlp subtitle language pattern")
    ap.add_argument("--ytdlp", default="", help="path to yt-dlp executable")
    ap.add_argument("--ffmpeg", default="", help="path to ffmpeg executable")
    ap.add_argument("--asr-cmd", default="", help="ASR command template with {audio} {outdir} {srt}")
    ap.add_argument("--subtitle-url", default="", help="explicit subtitle URL to use directly")
    ap.add_argument("--force-subtitle", action="store_true", help="treat input as a subtitle URL")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    raw = args.input.strip()
    parsed = urllib.parse.urlparse(raw)
    is_url = parsed.scheme in ("http", "https", "file")
    base = {"input": raw, "outdir": str(outdir)}

    if args.subtitle_url:
        dest, err = fetch_direct_subtitle(args.subtitle_url, outdir, args.timeout)
        if dest:
            emit({**base, "ok": True, "srt": str(dest), "source": "subtitle-url"})
            return 0
        emit({**base, "ok": False, "error": err})
        return 1

    if not is_url:
        p = Path(raw)
        if not p.is_file():
            emit({**base, "ok": False, "error": "文件不存在且不是 URL: " + raw})
            return 2
        ffmpeg = find_tool(args.ffmpeg, ["ffmpeg", "ffmpeg.exe"], "VVP_FFMPEG")
        dest, source, err = from_local(p, outdir, ffmpeg, args.asr_cmd, args.timeout)
        if dest:
            emit({**base, "ok": True, "srt": str(dest), "source": source})
            return 0
        emit({**base, "ok": False, "error": err,
              "hint": "也可先用播放器/ASR 导出 .srt，再传本地字幕路径"})
        return 1

    if Path(parsed.path).suffix.lower() in MEDIA_EXT and not args.force_subtitle:
        media, err = download_media(raw, outdir, args.timeout)
        if not media:
            emit({**base, "ok": False, "error": err})
            return 1
        ffmpeg = find_tool(args.ffmpeg, ["ffmpeg", "ffmpeg.exe"], "VVP_FFMPEG")
        dest, source, err2 = from_local(media, outdir, ffmpeg, args.asr_cmd, args.timeout)
        if dest:
            emit({**base, "ok": True, "srt": str(dest), "source": source,
                  "media": str(media)})
            return 0
        emit({**base, "ok": False, "error": err2,
              "hint": "该媒体无内嵌字幕；可配置 ASR（--asr-cmd / VVP_ASR_CMD）或另传字幕链接"})
        return 1

    if args.force_subtitle or Path(parsed.path).suffix.lower() in SUB_EXT:
        dest, err = fetch_direct_subtitle(raw, outdir, args.timeout)
        if dest:
            emit({**base, "ok": True, "srt": str(dest), "source": "direct-subtitle-url"})
            return 0
        emit({**base, "ok": False, "error": err})
        return 1

    tool = ytdlp_cmd(args.ytdlp)
    if not tool:
        emit({**base, "ok": False,
              "error": "未找到 yt-dlp",
              "hint": "安装 yt-dlp 到 PATH，或设置 VVP_YTDLP / 传 --ytdlp 指向可执行文件；"
                      "若已有字幕直链，可直接传该链接或 --subtitle-url"})
        return 2

    dest, source, sub_err = ytdlp_subs(raw, outdir, tool, args.lang, args.timeout)
    if dest:
        emit({**base, "ok": True, "srt": str(dest), "source": source, "tool": tool[0]})
        return 0

    ffmpeg = find_tool(args.ffmpeg, ["ffmpeg", "ffmpeg.exe"], "VVP_FFMPEG")
    audio, audio_err = (ytdlp_audio(raw, outdir, tool, args.timeout)
                        if ffmpeg else (None, "未找到 ffmpeg，无法提取音频"))
    asr_err = ""
    if audio:
        srt, asr_err = asr_transcribe(audio, outdir, args.asr_cmd, args.timeout)
        if srt:
            emit({**base, "ok": True, "srt": str(srt),
                  "source": "yt-dlp 音频 + ASR 转写", "tool": tool[0]})
            return 0

    emit({**base, "ok": False,
          "error": "无法从该链接取得字幕；已尝试字幕轨道与音频转写",
          "details": {"subtitle": sub_err, "audio": audio_err, "asr": asr_err},
          "hint": ("可传字幕直链（--subtitle-url）、本地字幕文件；"
                   "或配置 ASR：--asr-cmd 'whisper {audio} --model base.en --output_format srt "
                   "--output_dir {outdir}'；部分站点需要网络可达或 cookie")})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
