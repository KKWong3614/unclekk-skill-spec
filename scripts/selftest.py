#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — skill-spec 自检：好样本必须全绿，坏样本必须被抓到

用法 / Usage:
    python3 scripts/selftest.py

覆盖 / Covers:
    1. 好样本（14 条全满足 + README 英文在前）→ 18/18 PASS，得分 100
    2. 坏样本（无前缀 / 无 UncleKK / 无 scripts / 无 frontmatter）→ 对应 ERROR 必中
    3. 断链样本 → C10 FAIL；孤立文档样本 → C11 FAIL
    4. C18：代码/文档硬编码盘符路径分别被抓（ERROR / WARN）
    5. is_skill_doc 路径过滤正确
    6. fail-open：空目录 / 不存在路径不抛异常、exit 0
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "spec_audit.py")
GATE = os.path.join(HERE, "spec_gate.py")

GOOD_SKILL = """---
slug: unclekk-demo
name: unclekk-demo
displayName: UncleKK Demo Skill
version: 1.0.0
summary: demo
description: demo description
license: MIT
tags: [demo]
triggers: [demo trigger]
---

# Demo

受众 Audience：新手 beginner 到专业用户都适用。

## 最小运行示例 Quick start

```bash
python3 scripts/demo.py
```

## 触发条件 Triggers

demo trigger

## FAQ 常见问题

- Q: 坑点？ A: 见审计报告样例 audit report。

## 步数上限与兜底 Step budget

步数 3，兜底 fail-open。

## 变更记录 Changelog

- **v1.0.0**: init
"""

BAD_SKILL = """---
slug: demo-bad
name: demo-bad
displayName: Demo Bad
version: 1.0
summary: bad
---

# Bad

没有示例，没有受众，没有脚本。
"""

LINK_SKILL = GOOD_SKILL.replace("## 变更记录 Changelog",
                                "详见 [references/nope.md](references/nope.md)\n\n## 变更记录 Changelog")

README_EN_FIRST = "# Demo\n\nEnglish first paragraph for GitHub.\n\n中文段落在后。\n"


def run_audit(path, extra=None):
    cmd = [sys.executable, AUDIT, "--path", path, "--json"] + (extra or [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode not in (0, 1):
        raise RuntimeError("audit exited %s: %s" % (p.returncode, p.stderr[:200]))
    out = p.stdout.strip()
    # 审计器 --json 输出是缩进多行，必须整体解析，不能只取最后一行
    try:
        return json.loads(out)
    except Exception:
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except Exception:
                    continue
        raise RuntimeError("audit produced no JSON: %s | stderr=%s" % (out[:200], p.stderr[:200]))


def make_skill(root, name, skill_md, scripts=None, extra_files=None):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill_md)
    if scripts:
        sdir = os.path.join(d, "scripts")
        os.makedirs(sdir, exist_ok=True)
        for s in scripts:
            with open(os.path.join(sdir, s), "w", encoding="utf-8") as f:
                f.write("print('ok')\n")
    for rel, content in (extra_files or {}).items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    return d


def status_of(rep, cid):
    for c in rep["checks"]:
        if c["id"] == cid:
            return c["status"]
    return "MISSING"


RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("[%s] %s%s" % ("PASS" if cond else "FAIL", name, (" -> " + detail) if detail and not cond else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="skillspec-")
    try:
        # 1 好样本
        good = make_skill(tmp, "unclekk-demo", GOOD_SKILL, scripts=["demo.py"],
                          extra_files={"README.md": README_EN_FIRST})
        rep = run_audit(good, ["--target", "github"])
        s = rep["summary"]
        check("好样本全绿 18/18", s["passed"] == 18 and s["errors"] == 0 and s["warnings"] == 0,
              "passed=%s errors=%s warnings=%s skipped=%s" % (s["passed"], s["errors"], s["warnings"], s["skipped"]))
        check("好样本 verdict=PASS", rep["verdict"] == "PASS", rep["verdict"])
        check("好样本得分 100", s["score"] == 100, str(s["score"]))

        # 2 坏样本
        bad = make_skill(tmp, "demo-bad", BAD_SKILL)
        rep2 = run_audit(bad)
        for cid, label in (("C03", "unclekk- 前缀"), ("C04", "UncleKK displayName"),
                           ("C08", "硬代码脚本"), ("C02", "semver"), ("C01", "frontmatter")):
            check("坏样本命中 %s（%s）" % (cid, label), status_of(rep2, cid) == "FAIL",
                  status_of(rep2, cid))
        check("坏样本 verdict=FAIL", rep2["verdict"] == "FAIL", rep2["verdict"])

        # 3 断链 / 孤立文档
        linky = make_skill(tmp, "unclekk-linky", LINK_SKILL, scripts=["demo.py"])
        check("断链被抓 C10", status_of(run_audit(linky), "C10") == "FAIL")

        orph = make_skill(tmp, "unclekk-orph", GOOD_SKILL, scripts=["demo.py"],
                          extra_files={"references/lonely.md": "# lonely\n"})
        check("孤立文档被抓 C11", status_of(run_audit(orph), "C11") == "FAIL")

        # 4 C18 硬编码路径：代码级 ERROR / 文档级 WARN
        # 注意：坏样本里的盘符路径用 %s 变量拼接，避免字面量反被 C18 扫中本自检脚本
        drive_lit = "D"
        leak = make_skill(tmp, "unclekk-leak", GOOD_SKILL, scripts=["demo.py"])
        with open(os.path.join(leak, "scripts", "demo.py"), "a", encoding="utf-8") as f:
            f.write('open("%s:/data/x.txt")\n' % drive_lit)
        rep8 = run_audit(leak)
        c18e = [c for c in rep8["checks"] if c["id"] == "C18"]
        check("代码硬编码盘符被抓 C18=ERROR", bool(c18e) and c18e[0]["status"] == "FAIL"
              and c18e[0]["level"] == "ERROR", str(c18e[0]) if c18e else "C18 MISSING")
        check("代码硬编码盘符使 verdict=FAIL", rep8["verdict"] == "FAIL", rep8["verdict"])

        bad_cmd = 'python3 "%s:/tools/spec_audit.py" --path .' % drive_lit
        doc_leak_md = GOOD_SKILL.replace("```bash\npython3 scripts/demo.py\n```",
                                         "```bash\n%s\n```" % bad_cmd)
        docleak = make_skill(tmp, "unclekk-docleak", doc_leak_md, scripts=["demo.py"])
        rep9 = run_audit(docleak)
        c18w = [c for c in rep9["checks"] if c["id"] == "C18"]
        check("文档硬编码盘符被抓 C18=WARN", bool(c18w) and c18w[0]["status"] == "FAIL"
              and c18w[0]["level"] == "WARN", str(c18w[0]) if c18w else "C18 MISSING")

        # 4 路径过滤（用 /a/... 而非 C:/a/...，避免 C18 把本自检样本判为硬编码）
        sys.path.insert(0, HERE)
        import spec_gate
        check("is_skill_doc 命中 SKILL.md", spec_gate.is_skill_doc("/a/skills/foo/SKILL.md"))
        check("is_skill_doc 命中 skills 下 md", spec_gate.is_skill_doc("/a/skills/foo/x.md"))
        check("is_skill_doc 放过普通 md", not spec_gate.is_skill_doc("/a/notes/x.md"))
        check("is_skill_doc 放过空路径", not spec_gate.is_skill_doc(""))

        # 5 fail-open
        empty = os.path.join(tmp, "empty-dir")
        os.makedirs(empty, exist_ok=True)
        rep5 = run_audit(empty)
        check("空目录 fail-open 不崩", rep5["verdict"] in ("FAIL", "SKIP"), rep5["verdict"])
        rep6 = run_audit(os.path.join(tmp, "does-not-exist-xyz"))
        check("不存在路径 fail-open 不崩", rep6["verdict"] in ("FAIL", "SKIP"), rep6["verdict"])

        # 7 插件布局（host cache）：<root>/skills/<id>/SKILL.md + <root>/scripts/
        plug_root = os.path.join(tmp, "plug")
        plug_doc = os.path.join(plug_root, "skills", "unclekk-demo")
        os.makedirs(plug_doc, exist_ok=True)
        os.makedirs(os.path.join(plug_root, "scripts"), exist_ok=True)
        with open(os.path.join(plug_doc, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(GOOD_SKILL)
        with open(os.path.join(plug_root, "scripts", "demo.py"), "w", encoding="utf-8") as f:
            f.write("print(1)")
        with open(os.path.join(plug_doc, "README.md"), "w", encoding="utf-8") as f:
            f.write(README_EN_FIRST)
        rep7 = run_audit(plug_root, ["--target", "github"])
        check("插件布局能找到 scripts（C08）", status_of(rep7, "C08") == "PASS", status_of(rep7, "C08"))
        check("插件布局 base 取 slug 而非版本号", rep7["skill"] == "unclekk-demo", rep7["skill"])

        # 6 gate pre 模式能出 systemMessage
        p = subprocess.run([sys.executable, GATE, "--mode", "pre", "--file",
                            os.path.join(good, "SKILL.md")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok_gate = False
        try:
            out = json.loads(p.stdout.strip().splitlines()[-1])
            ok_gate = "systemMessage" in out and "14 条" in out["systemMessage"]
        except Exception:
            ok_gate = False
        check("gate pre 注入 14 条清单", ok_gate, p.stdout[:120])
        check("gate 非 skill 文件静默",
              subprocess.run([sys.executable, GATE, "--mode", "pre", "--file", "/a/notes/x.md"],
                             capture_output=True, text=True).stdout.strip() == "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [n for n, ok, _ in RESULTS if not ok]
    print("-" * 60)
    print("通过 %d/%d" % (len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print("失败项: " + ", ".join(failed))
        sys.exit(1)
    print("结论: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
