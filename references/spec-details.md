# 14 条规范逐条判据 | Per-Rule Criteria

> 本文是 [../SKILL.md](../SKILL.md) 的展开。脚本能判的标注「机判」，判不了的标注「人判」。
> This file expands [../SKILL.md](../SKILL.md). "Machine" = checked by `spec_audit.py`; "Human" = needs a person.

| # | 规则 | 机判 | 人判要点 |
|---|------|------|---------|
| 1 | 最小运行示例 | 正文含「最小运行示例 / Quick start / Usage」且出现代码块或命令行 | 命令必须能原样复制运行，不能是 `<占位>` 拼不起来 |
| 2 | 版本号清楚 | `version` 匹配 `X.Y.Z`；正文最新 `**vX.Y.Z**` 与之相等 | 破坏性改动升主版本，别只动末位 |
| 3 | 文档不长·双语·无断链·无孤立文档 | 行数 ≤400、字节 ≤15360；markdown 链接全部可达；非入口 md 至少被引用一次 | 中英段落成对出现，别只堆中文 |
| 4 | 受众说明 | 含「受众 / Audience」且出现「新手 / beginner / 小白」 | 要明写覆盖新手到专业，不能默认读者是专家 |
| 5 | 硬代码保障 | `scripts/` 下至少 1 个 `.py`/`.ps1`/`.sh`/`.js` | 脚本必须真跑得通，不是摆设；声明式规则要配套可执行校验 |
| 6 | 步数上限与兜底 | 正文含「步数 / 兜底 / fail-open / Step budget」 | 写清最大步数、超时、异常时怎么退；护栏自身异常必须放行 |
| 7 | 自动触发并说明 | `triggers` 非空或正文含「触发条件」 | 优先 hook 自动触发，其次语义触发；写明什么场景会自己跳出来 |
| 8 | 审计报告样例 | 正文含「审计报告 / audit report / 样例」 | 样例必须来自真实运行输出，禁止手编占位 |
| 9 | FAQ 简短详尽 | 含「FAQ / 常见问题 / 坑点」 | 每条带实例 + 坑点 + 改进前后对照 |
| 10 | `unclekk-` 前缀 | 目录名、`slug`、`name` 三者都以 `unclekk-` 开头 | 无例外 |
| 11 | `UncleKK` displayName | `displayName` 含 `UncleKK` | skillhub 与 GitHub 展示名统一 |
| 12 | 双语顺序 | `--target skillhub` 中文在前；`--target github` 英文在前 | 同一个 skill 两份 README 时分别按目标排序 |
| 13 | 新手可读 | — | 术语首次出现给解释；步骤能照抄；不假设读者懂行话 |
| 14 | 路径走环境变量，不硬编码 | C18：代码命中盘符/用户目录 → ERROR；仅文档命中 → WARN | 命令与代码里的路径用 `$HOME` / `$env:` / `~` / 仓库内相对路径；不在引号里写死盘符路径或用户目录 |

## C18：路径硬编码扫描 | Hardcoded-path scan

**命中特征**（引号包裹的字符串字面量 / 文档行）：
1. 盘符绝对路径：`X:` 后紧跟 `/` 或 `\`（如数据盘、用户目录下的绝对路径）
2. Unix 用户目录：`/c/Users/`、`/Users/<名>/`、`/home/<名>/`

**豁免**：`~/...`、`$HOME/...`、`$env:NAME/...`、`%VAR%\...` 等环境变量/主目录用法——它们换用户、换机器仍然有效，不算硬编码。

**分级**：`scripts/` 与 `hooks/` 下代码文件命中 = 换机器必断的真缺陷 → **ERROR**；
SKILL.md / README / `references/*.md` 命中 = 读者照抄必失败的示例 → **WARN**（提示改 `$HOME` / `$env:` / 相对路径）。

**坑点**：给文档写反例示范时，别把真盘符写进代码块——会反被自己扫中（v1.0.0 的最小示例就因此 FAIL，已改为 `$SKILL_ROOT` 式）。

## 附加项 C17：反引号内路径 | Tick-referenced paths

文档常泛指「有 `hooks/hooks.json` 的 skill」，这类不是可点击链接，缺失只提示（WARN）不判死（ERROR）。
需要豁免时在 skill 根目录放 `.specignore`，每行一个相对路径。

## 豁免与调参 | Tuning

```bash
python3 scripts/spec_audit.py --path <skill> --max-lines 600 --max-bytes 24576
python3 scripts/spec_audit.py --path <skill> --target github   # 校验 README 英文在前
python3 scripts/spec_audit.py --path <skill> --strict          # CI 用：有 ERROR 则 exit 1
```
