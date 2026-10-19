# unclekk-skill-spec

给 Agent 技能用的 14 条交付规范，靠 hook 自动注入 + 脚本硬校验来兜底——不靠人脑记。

正在新建或修改 skill？本技能挂在 `PreToolUse` / `PostToolUse` 上：写 `SKILL.md` 之前自动注入 14 条清单，文件落盘后立刻打印审计报告。默认只报告不阻断，显式 `--deny-on-error` 才硬拦。

## 快速开始

```bash
export SKILL_ROOT="$HOME/path/to/unclekk-skill-spec"   # 换成你本机的仓库目录
python3 "$SKILL_ROOT/scripts/spec_audit.py" --path "$SKILL_ROOT"
```

加 `--json` 得到机器可读报告；`--strict` 在出现 ERROR 时 exit 1（供 CI 使用）；`--target github|skillhub` 校验双语顺序。

## 14 条规范

| # | 规则 |
|---|------|
| 1 | 最小运行示例 |
| 2 | 版本号语义化、清晰 |
| 3 | 文档短、双语、无断链、无孤立文档 |
| 4 | 写明受众（新手 → 专业） |
| 5 | 硬代码保障，不能只有文字声明 |
| 6 | 步数上限与兜底，闭环到底 |
| 7 | 自动触发，并写明触发条件 |
| 8 | 真实审计报告样例 |
| 9 | FAQ 简短但具体，带实例与坑点 |
| 10 | `slug` / `name` / 目录名一律 `unclekk-` 前缀 |
| 11 | `displayName` 带 `UncleKK` 前缀 |
| 12 | 双语顺序：SkillHub 中文在前，GitHub 英文在前 |
| 13 | 完全新手也能读懂 |
| 14 | 路径走环境变量 / 仓库相对路径，绝不硬编码 |

## 审计器查什么

18 项检查（C01–C18）：frontmatter 字段、semver、前缀、displayName、最小示例、受众、触发条件、可执行脚本、文档长度、断链、孤立文档、变更记录一致、FAQ、报告样例、步数兜底、双语顺序、反引号内路径、硬编码路径。C18 命中代码里的盘符 / 用户目录硬编码记为 ERROR，仅文档命中的记 WARN（请改用 `$HOME` / `$env:` / 仓库内相对路径）。其中 12 项 ERROR 级、6 项 WARN 级。

## 自动触发

| 时机 | 行为 |
|---|---|
| `PreToolUse` 命中 `SKILL.md` 或 `skills/**/*.md` | 注入 14 条清单（不阻断） |
| `PostToolUse`，`SKILL.md` 落盘后 | 打印审计报告（不阻断） |
| 脚本缺失或报错 | stderr 一行告警，随即 fail-open |

## 兜底

最多扫 500 个文件、单文件 512 KB、hook 超时 15 秒、整体 3 步。内部任何异常一律 exit 0——护栏绝不能锁死它所守护的工具。

## 目录结构

```
unclekk-skill-spec/
├── SKILL.md                        # 14 条规范（中文在前，面向 SkillHub）
├── README.md                       # 本文件（中文在前，双语）
├── hooks/hooks.json                # PreToolUse + PostToolUse
├── scripts/spec_audit.py           # 18 项硬校验
├── scripts/spec_gate.py            # hook 入口（--mode pre|post）
├── scripts/selftest.py             # 24 项断言，好样本 vs 坏样本
└── references/                     # 逐条判据、发布检查单
```

## English

Fourteen delivery rules for Agent skills, enforced by hooks and machine-checked by script — not by memory.

Creating or editing a skill? This hooks into `PreToolUse`/`PostToolUse`: the 14-rule checklist is auto-injected before you write a `SKILL.md`, and an audit report is printed right after the file lands. Report-only by default; hard deny only with `--deny-on-error`.

### Quick start

```bash
export SKILL_ROOT="$HOME/path/to/unclekk-skill-spec"   # set to your local checkout
python3 "$SKILL_ROOT/scripts/spec_audit.py" --path "$SKILL_ROOT"
```

Add `--json` for a machine-readable report, `--strict` to exit 1 on ERROR (for CI), `--target github|skillhub` to check bilingual ordering.

### The 14 rules

| # | Rule |
|---|------|
| 1 | Minimal runnable example |
| 2 | Clear semantic version |
| 3 | Short docs, bilingual, no broken links, no orphan docs |
| 4 | Audience stated (beginner → expert) |
| 5 | Hard-code guarantee, not prose only |
| 6 | Step budget and fail-safe, strict loop closure |
| 7 | Auto-triggered, with triggers documented |
| 8 | Real sample audit report |
| 9 | Short but concrete FAQ with examples and pitfalls |
| 10 | `unclekk-` prefix on slug / name / directory |
| 11 | `UncleKK` prefix on displayName |
| 12 | Bilingual order: SkillHub zh-first, GitHub en-first |
| 13 | Readable for complete beginners |
| 14 | Paths via env vars / repo-relative, never hardcoded |

### What the auditor checks

18 checks (C01–C18): frontmatter fields, semver, prefix, displayName, minimal example, audience, triggers, executable scripts, doc length, broken links, orphan docs, changelog alignment, FAQ, sample report, step budget, bilingual order, tick-referenced paths, hardcoded paths. C18 flags a hardcoded drive/user path in code as ERROR; a doc-only hit is WARN (use `$HOME` / `$env:` / repo-relative instead). 12 are ERROR-level, 6 are WARN-level.

### Fail-safe

Max 500 files scanned, 512 KB per file, 15 s hook timeout, 3 steps total. Any internal error exits 0 — a guardrail must never lock the tools it guards.

## License

MIT
