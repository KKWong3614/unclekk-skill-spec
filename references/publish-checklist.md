# 发布前检查单 | Pre-Publish Checklist

> 配合 [spec-details.md](spec-details.md) 使用。`skillhub publish` 前逐项打勾，未全绿不发布。
> Use with [spec-details.md](spec-details.md). Tick every box before `skillhub publish`.

## 1. 元数据 | Metadata

- [ ] `slug` / `name` / 目录名三者均为 `unclekk-` 前缀
- [ ] `displayName` 含 `UncleKK` 前缀（skillhub 与 GitHub 一致）
- [ ] `version` 为 `X.Y.Z`，且与正文变更记录最新条目相等
- [ ] `summary` 与 `description` 均为中英双语
- [ ] `license`、`tags`、`triggers` 已填

## 2. 双语顺序 | Bilingual order

- [ ] SkillHub 面向文档：**中文在前，英文在后**
- [ ] GitHub 的 `README.md`：**英文在前，中文在后**
- [ ] 用脚本验：`python3 scripts/spec_audit.py --path <skill> --target github`

## 3. 内容 | Content

- [ ] `SKILL.md` ≤400 行 / 15KB，超了就拆进 `references/`
- [ ] 最小运行示例能原样复制运行
- [ ] 受众写明「新手 → 专业」
- [ ] `scripts/` 下至少一个可执行脚本且真跑得通
- [ ] 无断链、无孤立文档
- [ ] 命令与代码无硬编码盘符/用户目录路径（规则 14）：全仓搜盘符形式应为 0 命中

## 4. 硬校验 | Hard checks

```bash
python3 scripts/spec_audit.py --path <skill> --strict   # 有 ERROR 则 exit 1
skillhub publish "<skill>" --dry-run                    # 校验 frontmatter
```

## 5. 发布 | Publish

```bash
export MSYS_NO_PATHCONV=1          # Git Bash 下避免路径被转换
export SKILL_REPO="$HOME/path/to/<slug>"   # ← 换成你实盘仓库目录（用环境变量，别写死盘符）
skillhub publish "$SKILL_REPO" --changelog "本次变更说明"
```

发布前必须把 `displayName` / `summary` / `description` / `slug` / `version` / `license` / `tags`
整理给用户确认，**不点头不发布**（见 `unclekk-skill-dev-loop` 铁律 2）。
