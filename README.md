<div align="center">

<img src="assets/logo.png" alt="Video English Coach" width="120"/>

# Video English Coach · 视频英语教练

**用喜欢的英文视频，学习真正用得上的英语。**

开源 AI 英语学习助手 / 基于视频与字幕的互动学习 Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v1.0.0-green.svg)](https://github.com/grocksdf/video-english-coach/releases)

[在线演示](https://grocksdf.github.io/video-english-coach/) · [安装](#快速开始) · [使用示例](#使用示例) · [中文文档](README.md)

</div>

---

## 为什么做这个

看英文视频时好像都听懂了，过几天单词又忘得差不多了。

问题不在于"看懂"，而在于**没有把视频里的表达变成自己能主动用的东西**。Video English Coach 就是为解决这个问题而生：它把一段英文视频或字幕，变成一堂包含**重点词汇 → 主动回忆 → 间隔复习 → 口语复述**的互动学习课。

它既是一个可以被 AI Agent 调用的通用 Skill，也是一套零依赖、可离线运行的 Python 工具链。

## 功能亮点

- 🎯 **语境抽词**：从 SRT/VTT/ASS 字幕或英语文本中，提取真正用得上的重点词汇和高频表达，而不是一味挑生僻词
- 🧠 **主动回忆**：生成离线练习页，靠"不提示想起"而不是"反复看答案"来记忆
- 📅 **间隔复习**：内置 1 / 3 / 7 / 14 / 30 天复习安排，进度仅保存在浏览器本地
- 💬 **AI 陪练**：配合 AI Agent 完成听力理解、跟读、口语复述与纠错
- 📄 **离线导出**：一键生成可搜索、可打印的 CSV 词表和独立 HTML 页面，无需联网即可复习
- 🔗 **多输入源**：视频链接、字幕文件、英语文章、单词表都能处理
- 🪶 **零依赖**：Python 3.9+ 标准库即可运行，无需安装任何第三方包，无需 API Key

## 界面预览

| 词表预览 | 主动回忆练习 |
|---|---|
| 从视频字幕提取的语境词表，带音标、CEFR、中文释义与视频原句 | 离线自评练习，支持间隔复习与进度导入导出 |

打开 [`examples/vocab_preview.html`](examples/vocab_preview.html) 和 [`examples/vocab_practice.html`](examples/vocab_practice.html) 即可查看真实产物（浏览器直接打开，无需服务器）。

## 快速开始

### 作为 Skill 使用（推荐）

在支持 Skill 的 AI 助手中加载本仓库的 `SKILL.md`，然后直接对话：

> 把这个视频链接做成单词预习表：https://youtu.be/xxxxx

### 作为命令行工具使用

克隆仓库后即可运行，无需安装依赖：

```bash
git clone https://github.com/grocksdf/video-english-coach.git
cd video-english-coach

# 从字幕文件生成学习资料
python scripts/cli.py run assets/sample_subtitle.srt -o ./my_study --level B2 --json

# 查看示例输出
python scripts/cli.py demo -o ./preview_out --json
```

`run` 命令在缺少 LLM 时会返回 `status: needs_llm`，并生成一个包含 system prompt 的 `llm_request.json`；由调用方的 AI Agent 产出词表 JSON 后，再用 `finalize` 完成校验与导出。**脚本本身不要求用户提供任何 API Key**。

详细命令与 JSON 契约见 [`references/schema.md`](references/schema.md) 和 [`references/integration.md`](references/integration.md)。

## 数据契约

词表采用统一的 12 字段结构，保证跨工具兼容。核心约束：

- `example_from_video` 必须逐字来自原字幕，不可编造
- `example_extra` 必须明确标注为模型创作例句
- CEFR 等级为语言模型估计，非官方认证

完整字段定义见 [`references/schema.md`](references/schema.md)，抽词提示词见 [`references/extraction_prompt.md`](references/extraction_prompt.md)。

## 项目结构

```
video-english-coach/
├── SKILL.md                      # Skill  definition / 教学协议
├── scripts/
│   ├── cli.py                    # 统一 CLI 入口
│   ├── parse_subtitle.py         # SRT/VTT/ASS/TXT 解析与候选词提取
│   ├── fetch_subtitle.py         # 字幕获取（链接/媒体/ASR）
│   ├── build_preview.py          # 生成 CSV + 词表 HTML
│   └── build_practice.py         # 生成离线主动回忆练习页
├── references/
│   ├── extraction_prompt.md      # 抽词 system prompt
│   ├── learning_coach.md         # 互动教学与复习协议
│   ├── schema.md                 # JSON 契约与命令说明
│   └── integration.md            # 外部 Agent / API 接入
├── assets/                       # 示例字幕与词表
├── examples/                     # 真实产物示例（可直接打开）
├── docs/
│   ├── index.html                # GitHub Pages 展示页
│   ├── PUBLISH_GUIDE.md          # 发布指南
│   └── PROMOTION.md              # 推广文案
└── LICENSE                       # MIT
```

## 能力边界（实话实说）

为了避免误解，明确说明本项目**不**做以下事情：

- ❌ 不提供云端账号同步；复习进度仅保存在浏览器本地
- ❌ 不自动转写所有视频；无字幕时需你提供字幕文本或使用外部转写工具
- ❌ 不后台推送复习提醒；它不会主动发送消息
- ❌ 不宣称能科学测量"发音分数"或"掌握率"

## 许可证

[MIT](LICENSE) © 2026 zijie zhu

---

<div align="center">

如果这个项目对你有帮助，欢迎点一个 ⭐ Star。

</div>
