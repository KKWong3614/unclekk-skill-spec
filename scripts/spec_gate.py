#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_gate.py — 技能交付规范自动注入闸（hook 入口，事件驱动）

--mode pre   PreToolUse：Agent 即将写 SKILL.md / skill 内 .md 时，
             输出 systemMessage 注入 13 条规范精简清单（**不阻断**，只提醒）。
--mode post  PostToolUse：SKILL.md 落盘后自动跑 spec_audit，
             输出 systemMessage 审计报告（report-only，不阻断）；
             仅当显式传 --deny-on-error 且存在 ERROR 级 FAIL 时才 deny。

设计约束 / Design constraints:
    - 任何异常都 exit 0（fail-open），护栏自身绝不变成拒绝服务。
    - pre 模式只读 stdin 不扫盘，保证 hook 延迟可忽略。
    - 规范文本内嵌在此文件，不依赖外部文件存在（缺文件也能提醒）。

宿主协议 / Host protocol:
    stdout 输出 JSON：{"systemMessage": "..."} 或
    {"systemMessage": ..., "hookSpecificOutput": {"permissionDecision": "deny", ...}}
    exit code 不是拦截信号，一律 0。
"""

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SPEC_BRIEF = """[skill-spec] 新建/修改 skill 必须满足 14 条（写完会自动审计）：
 1 最小运行示例：文档开头给一条可直接复制运行的命令
 2 版本号清楚：frontmatter version 为 X.Y.Z，且与变更记录最新条目一致
 3 文档别太长：SKILL.md ≤400 行 / 15KB，中英对照，无断链、无孤立文档
 4 受众说明：必须写明覆盖"新手→专业"全体 Agent 用户
 5 硬代码保障：scripts/ 下至少 1 个可执行脚本，不能只有声明式文字
 6 步数上限与兜底：写明最大步数/超时，异常 fail-open，严格闭环
 7 自动触发：frontmatter triggers 必填，正中文档写明触发条件
 8 审计报告样例：给出一份真实的报告样例，不是占位符
 9 FAQ：简短，每条带实例与坑点，改进前后对照明显
10 slug/name/目录名一律 unclekk- 前缀
11 skillhub 与 GitHub 的 displayName 一律加 UncleKK 前缀
12 双语顺序：skillhub 中文在前英文在后；GitHub 英文在前中文在后
13 新手可读：术语要解释，步骤要能照抄
14 路径走环境变量/相对推导：命令与代码不得硬编码盘符路径或用户目录（用 $HOME / $env: / ~ / 仓内相对路径）
自动审计：python3 <skill>/scripts/spec_audit.py --path <skill目录>
"""


def emit(msg, deny=False, reason=None, event="PreToolUse"):
    payload = {"systemMessage": msg}
    if deny:
        payload["hookSpecificOutput"] = {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason or msg,
        }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def read_stdin_json():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def extract_path(data):
    """从宿主传入的工具入参里尽力取文件路径。"""
    if not isinstance(data, dict):
        return ""
    for k in ("file_path", "filePath", "path", "notebook_path"):
        v = data.get(k)
        if isinstance(v, str) and v:
            return v
    ti = data.get("tool_input")
    if isinstance(ti, dict):
        for k in ("file_path", "filePath", "path"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                return v
    ti2 = data.get("input")
    if isinstance(ti2, dict):
        for k in ("file_path", "filePath", "path"):
            v = ti2.get(k)
            if isinstance(v, str) and v:
                return v
    return ""


def norm(p):
    return (p or "").replace("\\", "/")


def is_skill_doc(path):
    """只对 skill 文档生效，避免对所有 md 噪音注入。"""
    p = norm(path)
    if not p:
        return False
    low = p.lower()
    base = os.path.basename(low)
    if base == "skill.md":
        return True
    if "/skills/" in low and low.endswith(".md"):
        return True
    return False


def trace_hit(mode, fpath):
    """执行留痕：命中 skill 文档时追加一行，供验证 hook 是否被 host 调用。
    日志在系统临时目录 skill-spec-hook-trace.log（非敏感内容）。"""
    try:
        import tempfile, time
        line = "%s\t%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), mode, os.getpid(), norm(fpath))
        with open(os.path.join(tempfile.gettempdir(), "skill-spec-hook-trace.log"), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["pre", "post"], required=True)
    ap.add_argument("--file", default="", help="直接指定文件路径（测试用，绕过 stdin）")
    ap.add_argument("--deny-on-error", action="store_true",
                    help="post 模式下存在 ERROR 级 FAIL 时硬拦截（默认仅报告）")
    args = ap.parse_args()

    try:
        data = read_stdin_json()
        fpath = args.file or extract_path(data)
    except Exception as e:
        sys.stderr.write("[skill-spec] input parse error, fail-open: %s\n" % e)
        sys.exit(0)

    if not is_skill_doc(fpath):
        sys.exit(0)
    trace_hit(args.mode, fpath)

    if args.mode == "pre":
        emit(SPEC_BRIEF + "（本次将写入：%s）" % os.path.basename(norm(fpath)))

    # ---- post：落盘后自动审计 ----
    try:
        import spec_audit
        _root, skill_md, _doc = spec_audit.locate(fpath)
        if not skill_md:
            sys.exit(0)
        res, stats, base = spec_audit.audit(fpath)
        rep = spec_audit.build_report(res, stats, base, fpath)
    except Exception as e:
        sys.stderr.write("[skill-spec] audit error, fail-open: %s\n" % e)
        sys.exit(0)

    s = rep["summary"]
    if rep["verdict"] == "PASS" and s["warnings"] == 0:
        emit("[skill-spec] %s 通过 14 条自检：%d/%d 全绿（%d 行 / %d 字节）"
             % (base, s["passed"], s["total"], stats["lines"], stats["bytes"]))
        return

    lines = ["[skill-spec] %s 自检得分 %d，结论 %s：" % (base, s["score"], rep["verdict"])]
    for c in rep["checks"]:
        if c["status"] != "PASS":
            lines.append("  %s(%s) %s -> %s" % (c["id"], c["level"], c["name"], c["detail"]))
    lines.append("修复后重跑：python3 scripts/spec_audit.py --path %s" % base)
    msg = "\n".join(lines)

    if args.deny_on_error and s["errors"] > 0:
        emit(msg, deny=True, reason="; ".join(
            c["id"] + " " + c["detail"] for c in rep["checks"]
            if c["level"] == "ERROR" and c["status"] == "FAIL"), event="PostToolUse")
    emit(msg)


if __name__ == "__main__":
    main()
