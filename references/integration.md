# 接入指南 · 给其他 Agent / 大模型 / 框架

本 Skill 与平台解耦：目录内没有机器专属硬编码路径，也不依赖 LLM SDK。只在用户显式提供远程 URL 时才需要联网。
复制整个 `video-vocab-preview/` 目录即可在支持 `SKILL.md` 的环境使用；实际安装路径以所在产品文档为准。

## A. 作为 Agent Skill 加载（WorkBuddy / Claude Agent Skills / 类似实现）

1. 把整个目录放到目标平台的 skills 目录：
   - WorkBuddy 用户级：`~/.workbuddy/skills/video-vocab-preview/`
   - 项目级：`<workspace>/.workbuddy/skills/video-vocab-preview/`
   - 其他读 `SKILL.md` 的 Agent：其文档中约定的 skills 目录
2. 保留 `SKILL.md` 的 YAML frontmatter（`name` / `description`）。
   `description` 已写明触发场景，供自动匹配。
3. Agent 按 `SKILL.md` 的「端到端工作流」执行；需要字段细节时再读
   `references/schema.md` 与 `references/extraction_prompt.md`。

无需安装、无需注册、无需配置文件。

## B. 仅取 system prompt 给任意大模型

先生成已填充变量的提示词（也可以直接手工替换 3 个占位符）：

```bash
python scripts/cli.py prompt \
  --subtitle-file assets/sample_subtitle.srt \
  --level B2 --max-words 20 \
  -o filled_system_prompt.txt
```

随后用任意兼容 chat-completions 的 API 调用；以下是与 SDK 无关的伪代码：

```python
import json
from pathlib import Path

system_prompt = Path("filled_system_prompt.txt").read_text(encoding="utf-8")
# 任意厂商 / 本地模型均可；建议开启 JSON 输出模式并关闭创造性采样
response = llm.chat(
    model="YOUR_MODEL",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "按 Output Format 输出词表 JSON。"},
    ],
    temperature=0,
    response_format={"type": "json_object"},
)
data = json.loads(response.text)          # 失败时先修 JSON 再继续
Path("words.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

然后交给确定性脚本出表：

```bash
python scripts/cli.py render words.json -o ./preview_out --title "Sleep & Memory"
```

模型可替换为 GPT / Claude / Gemini / Qwen / DeepSeek / Ollama / LM Studio 等任意实现；
提示词不含厂商特有语法。若模型不支持 `response_format`，在 user 消息里重复
「只输出单个合法 JSON 对象」即可。

## C. 任意 Agent 框架通过 CLI 调用（推荐用于自动化）

所有命令加 `--json` 后，stdout 是单个 JSON 对象，便于程序解析：

```python
import json, subprocess, sys

def call(*args):
    r = subprocess.run([sys.executable, "scripts/cli.py", *args, "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout), r.returncode

schema, _ = call("schema")                       # 先取契约
parsed, rc = call("parse", "episode.srt", "-o", "candidates.json")
# ... 此处由调用方的模型读取 candidates.json 并产出 words.json ...
rendered, rc = call("render", "words.json", "-o", "out", "--title", "Episode 1")
print(rendered["data"]["html"])
print(rendered["data"]["practice"])
```

退出码：`0` 成功 / `1` 执行失败 / `2` 输入或参数错误；失败时 JSON 中带 `error` 字段。

## D. MCP Server / HTTP 工具封装映射

若要把能力暴露成工具，直接把下面命令包装为 tool handler，无需改动 Skill 内部代码：

| 建议 tool 名 | 对应命令 | 输入 | 返回 |
|---|---|---|---|
| `vocab_schema` | `cli.py schema` | 无 | 契约 JSON |
| `vocab_parse_subtitle` | `cli.py parse ... --json` | 字幕路径或文本 | candidates JSON |
| `vocab_build_prompt` | `cli.py prompt ... --json` | 字幕、水平、词数 | 已填充 system prompt |
| `vocab_render` | `cli.py render ... --json` | words JSON | CSV / 词表 HTML / 复习 HTML 路径 |
| `vocab_demo` | `cli.py demo --json` | 输出目录 | 自测结果 |

`parse` 与 `render` 是无需网络的确定性文件生成工具，适合直接注册；
`prompt` 只生成提示词，由调用方决定交给哪个模型。

## E. 作为 Python 模块直接 import

```python
import sys
from pathlib import Path
sys.path.insert(0, "scripts")

import build_preview, parse_subtitle

words = build_preview.normalize_words(json.loads(Path("words.json").read_text("utf-8")))
html_text = build_preview.HTML_TEMPLATE.replace("__ROWS__", build_preview.render_rows(words))
```

两个模块均只用标准库；`parse_subtitle.parse_srt / parse_vtt / parse_ass / parse_plain`
可直接接收字符串，不必落盘。

## F. 校验与回归

```bash
python scripts/cli.py demo -o ./preview_out --json
```

`demo` 用内置示例字幕与示例词表跑通解析 → 渲染全链路，校验 CSV 行数、
HTML 表格结构、离线主动回忆页与示例词是否全部出现，返回结构化结果。任何新平台接入后
先跑一次，确认 Python 3.9+、UTF-8 环境正常。

## G. 只给一个视频链接（Agent 内全自动）

```bash
python scripts/cli.py run "<video-url>" -o ./out --level B2 --max-words 20 --json
# → status: needs_llm，同时产出 ./out/llm_request.json 与 ./out/<字幕>.srt
```

调用方 Agent 读 `llm_request.json` 的 `system_prompt`，**自己**生成词表 JSON 写入
`./out/words.json`，然后：

```bash
python scripts/cli.py finalize ./out/words.json -o ./out --srt ./out/<字幕>.srt --json
# → status: completed，返回 csv / html / practice 路径
```

这三步之间不需要任何 API key——Agent 本身就是语言模型。若要在纯脚本 / CI 中
复现，写一个小命令读 stdin 的 `llm_request.json`、把词表 JSON 打到 stdout，
再给 `run` 加 `--llm-cmd "<command>"` 即可（或设 `VVP_LLM_CMD`）。

## H. 网络与工具现实约束

- `yt-dlp` 可能不在 PATH；可用 `--ytdlp <可执行文件路径>` 或 `VVP_YTDLP` 指定。不要在 Skill 中写死个人电脑路径。
- 视频站点可达性由调用方网络、平台权限和目标视频字幕轨决定。不要引用未经核验的某一天网络测试结果；不可达时 fetch 返回结构化 `error` + `hint`，不会伪造字幕。最稳妥的输入是字幕文件或字幕直链。
- 站点无字幕且未配置 ASR 时明确失败。配置示例：
  `--asr-cmd "whisper {audio} --model base.en --language en --output_format srt --output_dir {outdir}"`。该工具须在本机预先安装。
- loopback 链接自动绕过系统代理；公网链接沿用系统代理设置。

## 已知边界

- 本 Skill 不自带 ASR 模型；只有无字幕视频时需外部 ASR 或播放器导出 `.srt`。
- CEFR 分级由模型判定，不是查表；不同模型对个别词的等级可能有 1 档差异。
- 脚本不做词形归并，`candidates` 中可能同时出现 `consolidates` 与 `consolidation`；
  归并由提示词 Rules 第 5 条交给模型处理。


## I. 互动学习与主动回忆输出（新增）

`cli.py render/finalize/run` 完成时，在 `csv`、`html` 外还提供 `practice`，指向 `vocab_practice.html`。预习页也内置“开始主动回忆练习”链接。

```bash
python scripts/cli.py render assets/sample_words.json -o ./demo --json
# 输出包含 data.practice
```

打开 `./demo/vocab_practice.html`，可先输入英文答案再揭晓参考词形，之后自评决定复习间隔；浏览器不支持自动存储时，务必导出进度文件。`vocab_practice.html` 不做自动语义/发音评分，不替代在 ChatGPT 对话中复述与获得有针对性的纠错。

完整对话教学协议见 `references/learning_coach.md`。
