# 数据契约 · video-vocab-preview

本文件是跨 Agent / 跨模型的唯一数据契约。所有结构均为标准 JSON，UTF-8 编码。
机器可读版本由 `python scripts/cli.py schema` 输出。

## 1. 三层数据流

```
字幕文件 / 英文文本
      │  parse_subtitle.py（确定性，零模型）
      ▼
candidates.json ── 填入 {{subtitle_text}} ──► 任意大模型 + extraction_prompt.md
                                                │
                                                ▼
                                          words.json
                                                │  build_preview.py（确定性，零模型）
                                                ▼
                                  vocab_preview.csv + vocab_preview.html + vocab_practice.html
```

只有中间「模型精筛」需要语言模型；两端脚本可独立运行、独立测试。

## 2. 输入：字幕文件

| 格式 | 扩展名 | 解析方式 |
|---|---|---|
| SubRip | `.srt` | 按空行分块，取时间行之后的文本 |
| WebVTT | `.vtt` | 跳过 `WEBVTT` 头与 `NOTE` 块，其余同 SRT |
| ASS / SSA | `.ass` / `.ssa` | 取 `Dialogue:` 行第 10 段，剥离 `{...}` 特效标签 |
| 纯文本 | 其他 | 按句号 / 换行切句 |

编码按 `utf-8-sig` → `utf-8` → `gb18030` → `latin-1` 依次尝试。

## 3. 中间产物：candidates.json

```json
{
  "source": "sample_subtitle.srt",
  "sentence_count": 32,
  "sentences": [
    { "index": 1, "start": "00:00:00.000", "text": "Every night, ..." }
  ],
  "candidates": [
    {
      "word": "consolidates",
      "frequency": 2,
      "contexts": [
        { "sentence": 2, "text": "It consolidates fragile memory traces ..." }
      ]
    }
  ]
}
```

`sentences[].start` 为字符串，无时间信息时为空字符串。`candidates` 按词频降序，
受 `--top` 限制（默认 120）；每词最多保留 3 条上下文。候选词已去停用词、
小写化、过滤长度小于 `--min-len`（默认 4）的片段，**未做词形归并**——
归并交给模型完成，避免引入第三方 NLP 依赖。

## 4. 模型输出：words.json

根级对象，只能包含 `meta` 与 `words`。

```json
{
  "meta": {
    "title": "Sleep & Memory",
    "source": "sample_subtitle.srt",
    "learner_level": "B2",
    "word_count": 20
  },
  "words": [ { "...": "12 个字段，见下表" } ]
}
```

也可直接传一个纯数组；此时 `meta` 由 `--title` / `--source` 补齐。

### words[] 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `word` | string | 是 | 小写词元或可复用短语；为空的记录会被丢弃 |
| `phonetic` | string | 否 | 国际音标，带斜杠 |
| `pos` | string | 否 | `n.` / `v.` / `adj.` / `adv.` / `phr.` |
| `cefr` | string | 是 | `A1` / `A2` / `B1` / `B2` / `C1` / `C2`；CEFR 由模型估计，非官方分级 |
| `meaning_zh` | string | 是 | 中文释义 |
| `definition_en` | string | 否 | 简明英文释义 |
| `example_from_video` | string | 否 | 视频原句，逐字引用 |
| `example_extra` | string | 否 | 自造补充例句 |
| `example_zh` | string | 否 | 补充例句中文翻译 |
| `timestamp` | string | 否 | 原句起始时间 |
| `why_hard` | string | 是 | 具体难点类型与理由 |
| `frequency` | number | 否 | 非负整数；非法值归一为 `0` |

容错：任何缺失字段自动补空字符串；`cefr` 大小写不敏感；`frequency` 接受
数字字符串；根级为数组时按纯词表处理。全部词条的 `word` 为空 → 退出码 2。

## 5. 输出文件

| 文件 | 编码 | 内容 |
|---|---|---|
| `vocab_preview.csv` | UTF-8 with BOM | 表头 `序号` + 12 个中文字段名；`csv.writer` 标准转义，Excel / WPS / Numbers 可直接打开 |
| `vocab_preview.html` | UTF-8 | 零依赖单文件；统计卡片、关键词搜索、CEFR 筛选、例句展开、列排序、打印 / 存 PDF，并链接练习页 |
| `vocab_practice.html` | UTF-8 | 零依赖单文件；主动回忆、自评、到期复习、进度导出/导入 |

预习 HTML 中动态文本经过 `html.escape` 转义；练习 HTML 的词汇数据做了脚本注入转义，使用 `textContent` 显示。两份页面均不加载外部资源。练习页用浏览器 `localStorage` 保存自评，依浏览器环境而异，应导出 `english-review-progress.json` 备份。此文件不含完整单词词表。

## 6. CLI 契约

```
python scripts/cli.py schema                      # 打印机器可读契约（JSON）
python scripts/cli.py parse  <input>   [-o <json>] [--top N] [--min-len N] [--json]
python scripts/cli.py render <words.json> [-o <dir>] [--title T] [--source S] [--json]
python scripts/cli.py prompt [--subtitle-file F] [--level B2] [--max-words 20] [-o <txt>] [--json]
python scripts/cli.py demo   [-o <dir>] [--json]
python scripts/build_practice.py words.json -o <dir>
```

`render` / `finalize` / `demo` 的 `data` 增加 `practice` 路径，指向 `vocab_practice.html`。
`finalize` 对不合法契约或伪造字幕原句返回失败，须修复词表后重试（直接 `render` 不做这个严格校验）。

`--json` 模式下 stdout 只输出一个 JSON 对象，形如
`{"ok": true, "command": "render", "data": {...}}`；
失败为 `{"ok": false, "command": "...", "error": "..."}`，退出码非 0。
非 `--json` 模式输出人类可读文本。
所有命令退出码：`0` 成功、`1` 执行失败、`2` 输入或参数错误。

## 7. 输入变量（system prompt）

| 变量 | 含义 | 示例 |
|---|---|---|
| `{{subtitle_text}}` | 字幕原文，或 candidates.json 文本 | 见 `assets/sample_subtitle.srt` |
| `{{learner_level}}` | 学习者 CEFR 水平 | `B2` |
| `{{max_words}}` | 词条数上限 | `20` |

`cli.py prompt` 可一次性把三个变量替换完，直接产出可发给任意大模型的 system prompt。

## 8. 链接 → 字幕（fetch）

`cli.py fetch <url-or-path> -o <dir> --json` 按以下顺序自动降级：

1. `--subtitle-url` 显式字幕链接 → 直接下载（零外部工具）
2. 字幕直链（`.srt` / `.vtt` / `.ass` / `.txt`）→ 直接下载（零外部工具）
3. 媒体直链（`.mp4` / `.mkv` / `.mp3` / …）→ 下载后用 ffmpeg 抽内嵌字幕；无字幕则走 ASR
4. 视频页面 URL → yt-dlp 抓人工 / 自动字幕（语言默认 `en.*`）
5. 仍无字幕 → yt-dlp 抽音频 + ASR 转写
6. 本地文件 → 字幕直接复制；视频用 ffmpeg 抽字幕或 ASR

可选外部工具（自动探测，均非必需）：`yt-dlp`、`ffmpeg`、whisper CLI。
覆盖方式：环境变量 `VVP_YTDLP` / `VVP_FFMPEG` / `VVP_ASR_CMD` / `VVP_WHISPER`，
或参数 `--ytdlp` / `--subtitle-url` / `--asr-cmd`。ASR 命令模板变量为
`{audio}`、`{outdir}`、`{srt}`。

本地回环地址（127.0.0.1 / localhost）强制绕过系统代理，避免被代理劫持。
字幕下载上限 12 MB，媒体下载上限 300 MB；失败时返回结构化 `error` 与 `hint`。

## 9. Agent 协议（给链接就出表）

```
python scripts/cli.py run <url> -o <dir> --json
  → status: needs_llm；产出字幕文件、candidates.json、llm_request.json
  → 调用方 Agent 自己作为语言模型：读 llm_request.json 的 system_prompt 与
    user_message，生成单个合法 JSON 词表，写入 <dir>/words.json
  → python scripts/cli.py finalize <dir>/words.json -o <dir> --srt <字幕> --json
  → status: completed；返回 csv / html / practice 路径与 10 项契约校验结果
```

在 WorkBuddy 或任意 Agent 对话中，第二步由 Agent 自身完成，因此**不需要任何 API key**。
非 Agent 环境可传 `--llm-cmd <command>`：该命令从 stdin 读 `llm_request.json`、
向 stdout 输出词表 JSON；也可设环境变量 `VVP_LLM_CMD`。


## 10. 主动回忆页的学习记录

- 文件 `vocab_practice.html` 支持中文释义→英文、英文释义→词、真实视频原句填空（只有词形可精确找到时才提供）；回答后由学习者自评“忘记/模糊/记得”。词形相同不等于语义或发音一定正确。
- 评分为简单启发式：独立记得则下次间隔按 `1 → 3 → 7 → 14 → 30` 天延长；模糊/忘记安排次日复习；忘记后本轮结尾最多再练一次。
- 浏览器进度位于 `localStorage`（键 `video-vocab-preview-progress-v2`），不涉及服务器或账号。支持导出 `english-review-progress.json`，可在同类页面手动导入覆盖。不同设备、不同浏览器和某些 file:// 场景不会自动同步；不提供系统通知/自动提醒。
- 导出结构为 `{"version": 2, "items": {"<16位卡片哈希ID>": {"stage": 1, "due": "YYYY-MM-DD", "attempts": 1, "successes": 1, "last_review": "YYYY-MM-DD"}}}`。卡片 ID 从小写词条+词性确定，跨视频复习同词可复用状态；用户导入进度时请保留原 `words.json` 以还原词义/例句。
