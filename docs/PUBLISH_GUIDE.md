# 发布指南 · video-english-coach

本仓库已准备为可直接推送的公开仓库，无需重新生成 README 或 LICENSE。

## 1. 推送前检查

```bash
cd video-english-coach

# 确认没有残留的用户名占位符（USERNAME 为待替换标记）
grep -rn 'USERNAME' . --exclude-dir=.git --exclude=PUBLISH_GUIDE.md || echo "OK: 无占位符"

# 本地冒烟测试（零依赖）
python scripts/cli.py demo -o ./preview_out --json
```

## 2. 首次推送到 GitHub

```bash
# 若仓库已由维护者在 GitHub 网页端创建为空仓库
git remote add origin https://github.com/grocksdf/video-english-coach.git
git branch -M main
git push -u origin main

# 打首个版本标签
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

> 如果推送时提示认证失败，请使用 Personal Access Token（PAT）作为密码：
> 设置 → Developer settings → Personal access tokens → Tokens (classic)，
> 勾选 `repo` 权限。推送时用户名填 `grocksdf`，密码粘贴 token。

## 3. 发布 Release

1. 进入仓库 → Releases → Draft a new release
2. Tag 选择 `v1.0.0`
3. 标题填写 `Video English Coach v1.0.0`
4. 正文可直接使用 [`PROMOTION.md`](PROMOTION.md) 中的「Release 文案」一节
5. （可选）上传 `dist/video-english-coach.zip` 作为附件

## 4. 开启 GitHub Pages 展示页

1. 进入仓库 → Settings → Pages
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `main`，目录选择 `/docs`
4. 保存后访问 `https://grocksdf.github.io/video-english-coach/`

## 5. 推荐仓库设置

- **Description**（可直接复制）：
  `Turn English videos and subtitles into interactive lessons with AI-powered vocabulary, speaking practice, and spaced repetition. 📚`
- **Topics**：
  `english-learning` `chatgpt` `ai-education` `language-learning` `agent-skills` `vocabulary` `spaced-repetition` `python`
- 勾选 Issues，方便收集用户反馈
- 在 About 中勾选 "Use this template" 若希望他人基于本项目二次开发

## 6. 后续维护

- 词表契约变更时，同步更新 `references/schema.md` 与 `SKILL.md`
- 每次发布新版本，更新 README 顶部的 version badge 并打新 tag
- 推广文案位于 [`PROMOTION.md`](PROMOTION.md)，包含小红书、B 站与英文版本
