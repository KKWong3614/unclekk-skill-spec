---
slug: unclekk-skill-spec
name: unclekk-skill-spec
displayName: UncleKK 技能交付规范 14 条（自动注入+硬校验） | UncleKK Skill Spec (14 Rules, Auto-Injected & Machine-Audited)
version: 1.1.1
summary: >-
  把「新建/修改 skill 必须满足的 14 条规范」做成 hook 自动注入 + 脚本硬校验，而不是靠人记得。写 SKILL.md 时自动提醒，落盘后自动出审计报告。 | Encodes KK's 14 skill delivery rules as a hook that auto-injects on write plus a script that audits on save — rules that enforce themselves instead of relying on memory.
description: >-
  当用户要新建/修改/发布一个 skill，或提到「skill 规范」「skill 自检」「14 条」「skill 质量」「发布前检查」时加载；更重要的是它由 hook 自动触发：Agent 写入 SKILL.md 或 skills 目录下任意 .md 前，自动注入 14 条精简清单，落盘后自动跑 spec_audit 输出审计报告。14 条覆盖：最小运行示例、语义化版本、文档长度与断链、受众说明、硬代码保障、步数上限与兜底、自动触发条件、审计报告样例、FAQ 实例、unclekk- 前缀、UncleKK displayName、双语顺序、新手可读性、路径走环境变量不硬编码。默认仅报告不阻断（避免误伤写文档），显式 --deny-on-error 才硬拦截。 | Load when creating/modifying/publishing a skill, or when asked about skill standards, self-audit, or pre-publish checks. More importantly it is hook-triggered: before any SKILL.md (or any .md under skills/) is written, the 14-rule checklist is auto-injected; after the file lands, spec_audit runs and prints an audit report. Report-only by default, hard deny only with --deny-on-error.
license: MIT
tags: [技能规范, 自动注入, 硬代码校验, 断链检测, 孤立文档, 新手友好, 双语, 审计报告, 环境变量路径, 不硬编码, unclekk]
triggers: [新建skill, 写skill, 改skill, skill规范, skill自检, skill审计, 13条, 14条, skill质量, 发布前检查, 硬编码路径, 环境变量, skill spec, skill standard, skill audit]
---

# UncleKK 技能交付规范 14 条 | Skill Spec (14 Rules)

**写给谁 | Audience**：所有 Agent 用户——**从完全没写过 skill 的新手，到维护几十个 skill 的专业用户**。
新手照「最小运行示例」复制一条命令就能自检；专业用户可改阈值、加豁免、接 CI。术语首次出现即解释：
*hook* = 宿主在工具调用前后自动执行的一段命令；*fail-open* = 护栏自己出错时放行，绝不把工具锁死。

---

## 60 秒最小运行示例 | Minimal example

先设 `SKILL_ROOT` 指向本 skill 所在目录——**路径用环境变量，别把机器路径写死**（规则 14）——再直接跑：

```bash
export SKILL_ROOT="$HOME/path/to/unclekk-skill-spec"   # ← 换成你本机实际存放目录
python3 "$SKILL_ROOT/scripts/spec_audit.py" --path "$SKILL_ROOT" --target github
```

PowerShell 等价写法：

```powershell
$env:SKILL_ROOT = "$env:USERPROFILE\path\to\unclekk-skill-spec"   # ← 换成你本机实际存放目录
python3 "$env:SKILL_ROOT/scripts/spec_audit.py" --path "$env:SKILL_ROOT" --target github
```

真跑一次即可看到完整报告（全绿样例见下文「审计报告样例」，那是真实输出不是手编占位）。

想看机器可读报告加 `--json`；想接 CI 加 `--strict`（有 ERROR 则 exit 1）。

---

## 自动触发条件 | Auto-triggers

| 触发方式 | 时机 | 行为 |
|---|---|---|
| **hook（主）** | `PreToolUse`，命中 `SKILL.md` 或 `skills/**/*.md` | 注入 14 条精简清单（不阻断） |
| **hook（主）** | `PostToolUse`，`SKILL.md` 落盘后 | 自动跑审计并输出报告（不阻断） |
| 语义触发（辅） | 提到「新建 skill」「skill 规范」「自检」「13 条」「14 条」「硬编码路径」「发布前检查」 | 本 skill 被加载 |
| 手动（兜底） | 任何时候 | 跑上面那条 `spec_audit.py` 命令 |

hook 失效时（脚本找不到、Python 报错）只往 stderr 打一行告警并放行，**不会静默失效也不锁死工具**。

---

## 14 条规范 | The 14 rules

| # | 规则 | 怎么算过关 |
|---|------|-----------|
| 1 | **最小运行示例** | 文档开头给一条能原样复制运行的命令，不是 `<占位>` |
| 2 | **版本号清楚** | `version` 为 `X.Y.Z`，且与变更记录最新条目一致 |
| 3 | **文档别太长·双语·无断链·无孤立文档** | `SKILL.md` ≤400 行 / 15KB；中英对照；链接全可达；`references/` 里每个 md 都被引用 |
| 4 | **受众说明** | 必须写明覆盖「新手 → 专业」全体 Agent 用户 |
| 5 | **硬代码保障** | `scripts/` 下至少 1 个可执行脚本且真跑得通，不能只有声明式文字 |
| 6 | **步数上限与兜底** | 写明最大步数 / 超时 / 异常怎么退；护栏自身异常必须 fail-open |
| 7 | **自动触发并说明触发条件** | `triggers` 必填，正文写明什么场景会自己跳出来 |
| 8 | **审计报告样例** | 给一份**真实运行**产出的报告，禁止手编占位 |
| 9 | **FAQ 简短详尽** | 每条带实例 + 坑点 + 改进前后对照 |
| 10 | **`unclekk-` 前缀** | 目录名、`slug`、`name` 三者一律 `unclekk-` 开头 |
| 11 | **`UncleKK` displayName** | skillhub 与 GitHub 的展示名都带 `UncleKK` 前缀 |
| 12 | **双语顺序** | skillhub：中文在前英文在后；GitHub：英文在前中文在后 |
| 13 | **新手可读** | 术语首次出现给解释，步骤能照抄，不假设读者懂行话 |
| 14 | **路径走环境变量，不硬编码** | 命令/代码里的路径用 `$HOME` / `$env:` / `~` / 仓库内相对路径；不得出现盘符绝对路径（如 `X:` 打头）或写死的用户目录（`/Users/<名>`、`/home/<名>`） |

逐条判据（机判 / 人判）见 [references/spec-details.md](references/spec-details.md)，
发布前检查单见 [references/publish-checklist.md](references/publish-checklist.md)。

---

## 审计器能查什么 | What the auditor checks

`spec_audit.py` 跑 18 项：C01 frontmatter 九字段、C02 语义化版本、C03 `unclekk-` 前缀、
C04 `UncleKK` displayName、C05 最小示例、C06 受众含新手、C07 触发条件、C08 硬代码脚本、
C09 文档长度、C10 断链、C11 孤立文档、C12 版本与变更记录一致、C13 FAQ、C14 报告样例、
C15 步数兜底、C16 双语顺序、C17 反引号内路径、C18 路径不硬编码（代码命中为 ERROR；
仅文档命中为 WARN——命令示例请改用 `$HOME` / `$env:` / 仓内相对路径）。
**ERROR 级 12 项，WARN 级 6 项**；WARN 不达标只提示，不判死。

---

## 步数上限与兜底 | Step budget & fail-safe

| 项 | 上限 | 超限行为 |
|---|------|---------|
| 单次扫描文件数 | 500 | 超出即停，已扫部分照常出报告 |
| 单文件读取 | 512 KB | 截断后继续，不报错 |
| hook 超时 | 15 秒 | 宿主终止，等同于未触发（放行） |
| 审计整体 | 3 步：扫描 → 判分 → 出报告 | 任一步异常 → stderr 告警 + exit 0 |

**兜底原则**：审计器和注入闸自身出任何异常都 `exit 0` 放行。护栏的职责是提醒，不是当门神锁死工具。
想让它硬拦截，必须显式传 `--deny-on-error`（仅 ERROR 级 FAIL 才 deny）。

---

## 审计报告样例 | Sample audit report

**改进前**（对 `unclekk-skill-dev-loop` v1.1.0 的真实输出，非手编）：

```
SKILL.md: 214 行 / 14389 字节
[PASS] C01  ERROR   frontmatter 九字段 / 9 fields
[PASS] C02  ERROR   版本号 semver / semver
[PASS] C03  ERROR   unclekk- 前缀 / prefix
[FAIL] C04  ERROR   displayName 含 UncleKK
        -> 技能开发闭环（实盘→派生→验证） | Skill Dev Loop (Real-Disk→Derive→Verify)
[FAIL] C05  ERROR   最小运行示例 / minimal example
        -> 章节=False 可执行痕迹=True
[FAIL] C06  ERROR   受众含新手 / audience incl. beginners
        -> 章节=False 新手关键词=False
[PASS] C07  ERROR   触发条件说明 / triggers documented
[PASS] C08  ERROR   硬代码脚本 / executable scripts
[PASS] C09  ERROR   文档长度 / doc length
[FAIL] C10  ERROR   无断链 / no broken links
        -> 断链: hooks/hooks.json
[PASS] C11  ERROR   无孤立文档 / no orphan docs
[PASS] C12  WARN    变更记录版本一致 / changelog aligned
[FAIL] C13  WARN    FAQ 章节 / FAQ section
[FAIL] C14  WARN    审计报告样例 / sample audit report
[PASS] C15  WARN    步数上限与兜底 / step budget & fail-safe
----------------------------------------------------------------
通过 9/16 · ERROR 4 · WARN 2 · SKIP 1 · 得分 56
结论: FAIL
```

**改进后 · 以身作则**（本 skill 自身在 18 项体系下的真实输出，`--target github`）：

```
SKILL.md: 203 行 / 12717 字节
通过 18/18 · ERROR 0 · WARN 0 · SKIP 0 · 得分 100
结论: PASS
```

**规则 14 立刻抓到存量问题**：dev-loop 在旧 17 项体系是 94 分 PASS；升到 18 项后 C18 立刻报出
它的同步脚本 sync-to-cache.ps1 里写死的默认实盘路径（`"D:"` 打头），得分 89 → FAIL——新规则能
扫出存量硬编码，不是空话（该问题已上报，是否修复由 KK 决定）。

`--json` 输出同样内容的结构化版本，含 `checks[]` 每项 `id/level/status/detail`，可直接喂给 CI 或面板。

---

## FAQ

**Q1. 我在写 README，为什么也被注入提醒？**
A. 注入闸只认两类路径：`SKILL.md` 和 `skills/` 目录下的 `.md`。命中说明你确实在改 skill 文档。
写普通笔记不会触发。实例：改 `notes/读书笔记.md` → 静默；改 `skills/foo/SKILL.md` → 注入。

**Q2. 「断链」把我文档里泛指的 `hooks/hooks.json` 判死了，怎么破？**
A. 分两级：markdown 链接 `[x](p)` 断了是 ERROR（用户点不动）；反引号里的泛指提及只算 WARN（C17）。
真要豁免，在 skill 根目录放 `.specignore`，每行一个相对路径。
**坑点**：早期版本把散文泛指也判 ERROR，导致 dev-loop 被误报 4 项——分级后 ERROR 降到 0。

**Q3. 只想让它提醒，不想被拦，需要改什么？**
A. 不用改，默认就是 report-only。只有 hook 命令里显式加 `--deny-on-error` 才会硬拦截。

**Q4. 我的 skill 文档就是很长，怎么办？**
A. 拆。主文件留骨架和入口，细节进 `references/`（本 skill 自己就是这么做的）。
阈值可调：`--max-lines 600 --max-bytes 24576`。

**Q5. 双语顺序怎么验？**
A. `python3 scripts/spec_audit.py --path <skill> --target github` 验 README 英文在前；
`--target skillhub` 验中文在前。不传 `--target` 则跳过该项（SKIP）。

**Q6. hook 没生效怎么排查？**
A. 三步：① 确认插件已注册且 host 已重启；② 手动跑
`python3 scripts/spec_gate.py --mode pre --file <某个SKILL.md路径>`，应输出 systemMessage；
③ 无输出 = 路径没命中 `is_skill_doc()`，检查文件名是不是 `SKILL.md`。

**Q7. 为什么命令示例里不能出现盘符路径？**
A. 换机器、换用户就全断——读者照抄必失败。规则 14 要求路径用 `$HOME` / `$env:` / `~` /
仓库内相对路径。
**坑点**：本 skill v1.0.0 的最小示例就写死了本机路径，C18 一上线、自查立刻 FAIL——第 14 条
当场约束到自己，随后改成 `$SKILL_ROOT` 环境变量式才全绿。这就是"规范要硬约束自己"的证明。

---

## 参考文件 | References

- [references/spec-details.md](references/spec-details.md) — 14 条逐条判据（机判 / 人判）与调参
- [references/publish-checklist.md](references/publish-checklist.md) — 发布前检查单与双语顺序要求
- `scripts/spec_audit.py` — 18 项硬校验审计器（`--json` / `--strict` / `--target`）
- `scripts/spec_gate.py` — hook 入口（`--mode pre|post`，`--deny-on-error`）
- `scripts/selftest.py` — 自检：好样本 / 坏样本判定必须正确
- `hooks/hooks.json` — PreToolUse 注入 + PostToolUse 审计，fail-open

---

## 变更记录 | Changelog

- **v1.1.0**（2026-09-07）：新增第 14 条「路径走环境变量/相对推导，不硬编码」+ 审计项 C18（代码命中 ERROR / 仅文档命中 WARN）。最小示例改为 `$SKILL_ROOT` 环境变量式（消除自身硬编码盘符路径）；全链 13→14 条、17→18 项；版本同步至 package.json / cache plugin.json / 注册表。
- **v1.0.0**（2026-09-07）：初版。13 条规范 + hook 自动注入 + 17 项硬校验审计器；断链分 ERROR/WARN 两级并支持 `.specignore` 豁免；默认 report-only，显式 `--deny-on-error` 才硬拦截。
