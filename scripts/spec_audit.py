#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_audit.py — UncleKK 技能交付规范 14 条硬代码自检（skill-spec C 层）

用法 / Usage:
    python3 spec_audit.py --path <skill_dir> [--json] [--target skillhub|github]
                          [--max-lines 400] [--max-bytes 15360] [--strict]

做什么 / What it does:
    对一个 skill 目录跑 18 项可机器校验的检查（14 条规范的可自动化部分），
    输出人类可读摘要或 JSON 审计报告。

设计约束 / Design constraints:
    - 零第三方依赖（不 import yaml，frontmatter 手写解析）。
    - 任何异常都 fail-open：默认 exit 0，绝不因为审计器自身故障阻断工具。
    - 编码安全：stdout/stderr 强制 utf-8，Windows GBK 控制台下不炸。
    - 步数上限：最多扫 500 个文件、单文件最多读 512 KB，防止大仓库拖死 hook。

Exit code:
    0  默认（fail-open）；也用于"有 FAIL 但不 --strict"
    1  仅当 --strict 且存在 ERROR 级 FAIL（供 CI 用，不用于 hook 拦截）
"""

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

MAX_FILES = 500
MAX_FILE_BYTES = 512 * 1024

REQUIRED_FRONTMATTER = ["slug", "name", "displayName", "version", "summary",
                        "description", "license", "tags", "triggers"]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.\-]+)?$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# C18 规则 14：路径硬编码特征——引号包裹的盘符绝对路径（D:/x、C:\x）或 Unix 用户目录
# （/c/Users/...、/Users/...、/home/...）。~/、$HOME、$env:、%VAR% 属环境变量用法，不命中。
HARDCODE_RE = re.compile(
    r"""["'](?:[A-Za-z]:[\\/]|/(?:c/Users|Users|home)/)[^"'\n]{0,100}["']""")

SECTION_PATTERNS = {
    "C05_example": [r"最小运行示例", r"最小示例", r"快速开始", r"60\s*秒", r"Quick\s*start", r"Minimal\s*example", r"Usage"],
    "C06_audience": [r"受众", r"Audience", r"Who\s+is\s+this\s+for", r"适用人群"],
    "C07_trigger": [r"触发条件", r"触发", r"When\s+to\s+use", r"Auto-?triggers?", r"Triggers"],
    "C13_faq": [r"FAQ", r"常见问题", r"坑点"],
    "C14_report": [r"审计报告", r"样例", r"audit\s*report", r"Sample\s*report"],
    "C15_budget": [r"步数", r"兜底", r"fail-?open", r"Step\s*budget", r"Fallback", r"上限"],
}

SAMPLE_MARKERS = ["```", "python3 ", "npm ", "node ", "bash ", "powershell ", "$ ", "skillhub "]


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def read_text(path, limit=MAX_FILE_BYTES):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except Exception:
        return ""


def parse_frontmatter(text):
    """极简 YAML frontmatter 解析：只取顶层 key，支持 `key: [a, b]` 与 `key: >-` 折叠。"""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[3:end]
    body = text[end + 4:]
    fm = {}
    key = None
    buf = []
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*):\s*(.*)$", line)
        if m:
            if key:
                fm[key] = " ".join(x.strip() for x in buf if x.strip())
            key = m.group(1)
            buf = [m.group(2).strip()]
        elif key and (line.startswith(" ") or line.startswith("\t") or not line.strip()):
            buf.append(line.strip())
    if key:
        fm[key] = " ".join(x.strip() for x in buf if x.strip())
    for k, v in list(fm.items()):
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            fm[k] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        else:
            fm[k] = v.strip("'\"")
    return fm, body


def find_section(body, patterns):
    for p in patterns:
        if re.search(p, body, re.IGNORECASE):
            return True
    return False


def list_md_files(root):
    out = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules", ".venv")]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                out.append(os.path.join(dirpath, fn))
                count += 1
                if count >= MAX_FILES:
                    return out
    return out


def has_cjk(s):
    return bool(CJK_RE.search(s or ""))


EXAMPLE_NAME_RE = re.compile(
    r"(^|/)([a-z]\.(py|md|sh|ps1|js|json)|"
    r"(foo|bar|baz|xxx|yyy|example|sample|demo|placeholder|your[\-_]?skill)[A-Za-z0-9_\-]*\.\w+)$",
    re.IGNORECASE)


def is_example_name(p):
    """占位/示例文件名不算断链（如 a.py、foo.md、your-skill/SKILL.md）。"""
    return bool(EXAMPLE_NAME_RE.search(p.replace("\\", "/")))


def locate(path):
    """定位 (root, skill_md, doc_dir)，兼容两种布局。

    扁平布局（实盘 / 用户级 skill）：<root>/SKILL.md + <root>/scripts/
    插件布局（host cache）      ：<root>/skills/<id>/SKILL.md + <root>/scripts/

    root    = 有 scripts/ 的那一层（硬代码脚本判定基准）
    doc_dir = SKILL.md 所在目录（文档内相对链接的解析基准）
    """
    p = os.path.abspath(path)
    if os.path.isfile(p) and p.lower().endswith(".md"):
        skill_md = p
    else:
        skill_md = os.path.join(p, "SKILL.md")

    if not os.path.isfile(skill_md):
        cand = p if os.path.isdir(p) else os.path.dirname(p)
        sk = os.path.join(cand, "skills")
        if os.path.isdir(sk):
            for sub in sorted(os.listdir(sk)):
                q = os.path.join(sk, sub, "SKILL.md")
                if os.path.isfile(q):
                    skill_md = q
                    break
    if not os.path.isfile(skill_md):
        return None, None, None

    doc_dir = os.path.dirname(skill_md)
    root = doc_dir
    if not os.path.isdir(os.path.join(root, "scripts")):
        up2 = os.path.dirname(os.path.dirname(doc_dir))
        if os.path.isdir(os.path.join(up2, "scripts")):
            root = up2
    return root, skill_md, doc_dir


def load_ignore(skill_dir):
    """读取 .specignore：每行一个相对路径，用于豁免有意的泛指引用。"""
    out = set()
    p = os.path.join(skill_dir, ".specignore")
    if os.path.isfile(p):
        for line in read_text(p, 32 * 1024).splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                out.add(s.replace("\\", "/"))
    return out


# --------------------------------------------------------------------------
# 检查项
# --------------------------------------------------------------------------

class Result(object):
    def __init__(self):
        self.checks = []

    def add(self, cid, name, level, status, detail):
        self.checks.append({
            "id": cid, "name": name, "level": level,
            "status": status, "detail": detail,
        })


def audit(skill_dir, target=None, max_lines=400, max_bytes=15360):
    r = Result()
    root, skill_md, doc_dir = locate(skill_dir)
    if not skill_md:
        r.add("C00", "SKILL.md 存在 / exists", "ERROR", "FAIL", "未找到 SKILL.md: %s" % skill_dir)
        return r, {"lines": 0, "bytes": 0}, os.path.basename(os.path.normpath(skill_dir))

    text = read_text(skill_md)
    lines = text.count("\n") + 1
    nbytes = len(text.encode("utf-8", errors="replace"))
    fm, body = parse_frontmatter(text)
    # 插件布局下目录名可能是版本号（1.0.0），此时以 frontmatter slug 为准
    base = os.path.basename(doc_dir)
    if not base.startswith("unclekk-"):
        base = str((fm or {}).get("slug") or base)

    # C01 frontmatter 必填字段
    if fm is None:
        r.add("C01", "frontmatter 可解析 / parseable", "ERROR", "FAIL", "缺少 --- 包裹的 frontmatter")
        missing = REQUIRED_FRONTMATTER[:]
    else:
        missing = [k for k in REQUIRED_FRONTMATTER if not fm.get(k)]
        r.add("C01", "frontmatter 九字段 / 9 fields", "ERROR",
              "PASS" if not missing else "FAIL",
              "齐全" if not missing else "缺失: " + ", ".join(missing))

    # C02 语义化版本
    ver = (fm or {}).get("version", "")
    ok_ver = bool(SEMVER_RE.match(str(ver)))
    r.add("C02", "版本号 semver / semver", "ERROR",
          "PASS" if ok_ver else "FAIL",
          str(ver) if ok_ver else "非 X.Y.Z: %r" % ver)

    # C03 unclekk- 前缀
    slug = str((fm or {}).get("slug", ""))
    nm = str((fm or {}).get("name", ""))
    prefixed = base.startswith("unclekk-") and slug.startswith("unclekk-") and nm.startswith("unclekk-")
    r.add("C03", "unclekk- 前缀 / prefix", "ERROR",
          "PASS" if prefixed else "FAIL",
          "dir=%s slug=%s name=%s" % (base, slug, nm))

    # C04 displayName 含 UncleKK
    dn = str((fm or {}).get("displayName", ""))
    r.add("C04", "displayName 含 UncleKK", "ERROR",
          "PASS" if "UncleKK" in dn else "FAIL", dn[:60])

    # C05 最小运行示例（章节 + 可执行痕迹）
    has_sec = find_section(body, SECTION_PATTERNS["C05_example"])
    has_cmd = any(m in body for m in SAMPLE_MARKERS)
    r.add("C05", "最小运行示例 / minimal example", "ERROR",
          "PASS" if (has_sec and has_cmd) else "FAIL",
          "章节=%s 可执行痕迹=%s" % (has_sec, has_cmd))

    # C06 受众说明（含新手）
    aud = find_section(body, SECTION_PATTERNS["C06_audience"])
    newbie = bool(re.search(r"新手|小白|初学|beginner|newcomer|newbie", body, re.IGNORECASE))
    r.add("C06", "受众含新手 / audience incl. beginners", "ERROR",
          "PASS" if (aud and newbie) else "FAIL",
          "章节=%s 新手关键词=%s" % (aud, newbie))

    # C07 触发条件
    trig = (fm or {}).get("triggers")
    trig_ok = bool(trig) if isinstance(trig, list) else bool(str(trig or "").strip())
    sec_ok = find_section(body, SECTION_PATTERNS["C07_trigger"])
    r.add("C07", "触发条件说明 / triggers documented", "ERROR",
          "PASS" if (trig_ok or sec_ok) else "FAIL",
          "frontmatter.triggers=%s 正文章节=%s" % (trig_ok, sec_ok))

    # C08 硬代码保障：scripts/ 至少 1 个可执行脚本
    sdir = os.path.join(root, "scripts")
    scripts = []
    if os.path.isdir(sdir):
        scripts = [f for f in os.listdir(sdir)
                   if f.lower().endswith((".py", ".ps1", ".sh", ".js", ".ts")) and f != "__init__.py"]
    r.add("C08", "硬代码脚本 / executable scripts", "ERROR",
          "PASS" if scripts else "FAIL",
          ", ".join(scripts[:5]) if scripts else "scripts/ 下无可运行脚本")

    # C09 文档长度
    ok_len = lines <= max_lines and nbytes <= max_bytes
    r.add("C09", "文档长度 / doc length", "ERROR",
          "PASS" if ok_len else "FAIL",
          "%d 行 / %d 字节（上限 %d 行 / %d 字节）" % (lines, nbytes, max_lines, max_bytes))

    # C10 断链（硬）：只认 markdown 链接 [x](p)——这是可点击的导航引用，断了用户点不动。
    ignore = load_ignore(skill_dir)
    link_refs = set()
    # 先剥离代码块与行内代码：文档里常写 `[x](p)` 这类"示例链接"，不是真引用
    stripped = re.sub(r"```.*?```", "", text, flags=re.S)
    stripped = re.sub(r"`[^`\n]*`", "", stripped)
    for m in re.finditer(r"\]\((?!https?://|#|mailto:)([^)\s]+)\)", stripped):
        link_refs.add(m.group(1).rstrip(".,)）"))
    broken = sorted(p for p in link_refs
                    if p not in ignore and not is_example_name(p)
                    and not os.path.exists(os.path.join(doc_dir, p.replace("/", os.sep))))
    r.add("C10", "无断链 / no broken links", "ERROR",
          "PASS" if not broken else "FAIL",
          "链接 %d 个全部可达" % len(link_refs) if not broken
          else "断链: %s（若为泛指，写入 .specignore 豁免）" % ", ".join(broken[:5]))

    # C17 反引号内路径（软）：文档常泛指"有 `hooks/hooks.json` 的 skill"，
    # 这不是可点击链接，缺失只提示不判死，避免误伤。
    tick_refs = set()
    for m in re.finditer(r"`((?:references|scripts|hooks|assets|templates)/[A-Za-z0-9_\-./]+)`", text):
        tick_refs.add(m.group(1).rstrip(".,)／"))
    # 反引号路径可能指向 root 层的 scripts/（插件布局）或 doc_dir 层的 references/，双基准任一命中即算存在
    missing_tick = []
    for p in tick_refs:
        if p in ignore or is_example_name(p):
            continue
        if (os.path.exists(os.path.join(doc_dir, p.replace("/", os.sep)))
                or os.path.exists(os.path.join(root, p.replace("/", os.sep)))):
            continue
        missing_tick.append(p)
    missing_tick = sorted(missing_tick)
    r.add("C17", "反引号路径存在 / tick-referenced paths", "WARN",
          "PASS" if not missing_tick else "FAIL",
          "引用 %d 个全部存在" % len(tick_refs) if not missing_tick
          else "提及但不存在: %s（泛指可写 .specignore）" % ", ".join(missing_tick[:5]))

    # C11 孤立文档：非入口 md 至少被一个 md 引用
    mds = [p for p in list_md_files(doc_dir)]
    corpus = []
    for p in mds:
        corpus.append((p, read_text(p, 200 * 1024)))
    entry_names = {"skill.md", "readme.md", "changelog.md", "license.md", "license", "contributing.md"}
    orphans = []
    for p, _ in corpus:
        rel = os.path.relpath(p, doc_dir).replace("\\", "/")
        low = os.path.basename(p).lower()
        if low in entry_names:
            continue
        hit = False
        for q, c in corpus:
            if q == p:
                continue
            if rel in c or low in c.lower():
                hit = True
                break
        if not hit:
            orphans.append(rel)
    r.add("C11", "无孤立文档 / no orphan docs", "ERROR",
          "PASS" if not orphans else "FAIL",
          "md 文件 %d 个" % len(mds) if not orphans else "孤立: " + ", ".join(orphans[:5]))

    # C12 版本号与变更记录一致
    m = re.search(r"\*\*v?(\d+\.\d+\.\d+)[^*]*\*\*", body)
    changelog_ver = m.group(1) if m else None
    if changelog_ver is None:
        r.add("C12", "变更记录版本一致 / changelog aligned", "WARN", "SKIP", "正文未找到 **vX.Y.Z** 变更记录")
    else:
        r.add("C12", "变更记录版本一致 / changelog aligned", "WARN",
              "PASS" if changelog_ver == str(ver) else "FAIL",
              "变更记录=%s frontmatter=%s" % (changelog_ver, ver))

    # C13 FAQ
    faq = find_section(body, SECTION_PATTERNS["C13_faq"])
    r.add("C13", "FAQ 章节 / FAQ section", "WARN",
          "PASS" if faq else "FAIL", "存在" if faq else "未找到 FAQ/常见问题章节")

    # C14 审计报告样例
    rep = find_section(body, SECTION_PATTERNS["C14_report"])
    r.add("C14", "审计报告样例 / sample audit report", "WARN",
          "PASS" if rep else "FAIL", "存在" if rep else "未找到审计报告样例")

    # C15 步数上限与兜底
    bud = find_section(body, SECTION_PATTERNS["C15_budget"])
    r.add("C15", "步数上限与兜底 / step budget & fail-safe", "WARN",
          "PASS" if bud else "FAIL", "存在" if bud else "未找到步数/兜底说明")

    # C16 双语顺序（仅当指定 --target）
    if not target:
        r.add("C16", "双语顺序 / bilingual order", "WARN", "SKIP", "未指定 --target（skillhub|github），跳过")
    else:
        readme = None
        for cand in ("README.md", "readme.md"):
            p = os.path.join(doc_dir, cand)
            if os.path.isfile(p):
                readme = p
                break
        if not readme:
            r.add("C16", "双语顺序 / bilingual order", "WARN", "SKIP", "无 README.md，跳过")
        else:
            head = read_text(readme, 4000)
            paras = [x.strip() for x in head.split("\n\n") if x.strip() and not x.strip().startswith("#")]
            cn_i = next((i for i, x in enumerate(paras) if has_cjk(x)), None)
            en_i = next((i for i, x in enumerate(paras) if not has_cjk(x) and re.search(r"[A-Za-z]{4,}", x)), None)
            if cn_i is None or en_i is None:
                r.add("C16", "双语顺序 / bilingual order", "WARN", "SKIP", "未同时检出中英段落")
            else:
                want_cn_first = (target == "skillhub")
                actual_cn_first = cn_i < en_i
                r.add("C16", "双语顺序 / bilingual order", "WARN",
                      "PASS" if actual_cn_first == want_cn_first else "FAIL",
                      "target=%s 要求%s在前，实际%s在前"
                      % (target, "中文" if want_cn_first else "英文", "中文" if actual_cn_first else "英文"))

    # C18 路径走环境变量/相对推导，不硬编码（规则 14）
    # 命中特征：引号包裹的盘符绝对路径（D:/x、C:\x）或 Unix 用户目录（/c/Users /Users /home）。
    # 分级：代码文件（scripts/、hooks/）命中 = 换机器必断的硬编码 → ERROR；
    #       文档（SKILL.md / README / references/*.md）命中 = 照抄必失败的示例 → WARN。
    # 豁免：~/、$HOME、$env:、%VAR% 等环境变量/用户主目录用法（正则不命中它们）。
    code_hits, doc_hits = [], []
    code_exts = (".py", ".ps1", ".sh", ".js", ".ts", ".bat", ".cmd")
    for sub in ("scripts", "hooks"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if not os.path.isfile(p):
                continue
            low = fn.lower()
            is_json = sub == "hooks" and low.endswith(".json")
            if not (low.endswith(code_exts) or is_json):
                continue
            for i, line in enumerate(read_text(p, 128 * 1024).splitlines(), 1):
                if HARDCODE_RE.search(line):
                    code_hits.append("%s:%d: %s"
                                     % (os.path.relpath(p, root).replace("\\", "/"), i, line.strip()[:100]))
                    break
    for p in list_md_files(doc_dir):
        for i, line in enumerate(read_text(p, 200 * 1024).splitlines(), 1):
            if HARDCODE_RE.search(line):
                doc_hits.append("%s:%d: %s"
                                % (os.path.relpath(p, doc_dir).replace("\\", "/"), i, line.strip()[:100]))
                break
    if code_hits:
        r.add("C18", "路径走环境变量/不硬编码 / env paths, no hardcode", "ERROR", "FAIL",
              "代码硬编码机器路径: " + "; ".join(code_hits[:3]))
    elif doc_hits:
        r.add("C18", "路径走环境变量/不硬编码 / env paths, no hardcode", "WARN", "FAIL",
              "文档含盘符/用户目录路径: " + "; ".join(doc_hits[:3])
              + "（命令示例请用 $HOME / $env: / 仓库内相对路径）")
    else:
        r.add("C18", "路径走环境变量/不硬编码 / env paths, no hardcode", "ERROR", "PASS",
              "代码与文档均无盘符/用户目录硬编码")

    stats = {"lines": lines, "bytes": nbytes}
    return r, stats, base


def build_report(res, stats, base, skill_dir):
    total = len(res.checks)
    errs = [c for c in res.checks if c["level"] == "ERROR" and c["status"] == "FAIL"]
    warns = [c for c in res.checks if c["level"] == "WARN" and c["status"] == "FAIL"]
    skipped = [c for c in res.checks if c["status"] == "SKIP"]
    passed = total - len(errs) - len(warns) - len(skipped)
    score = int(round(100.0 * passed / total)) if total else 0
    verdict = "FAIL" if errs else ("WARN" if warns else "PASS")
    return {
        "skill": base,
        "path": os.path.normpath(skill_dir),
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "skill_md": stats,
        "summary": {"total": total, "passed": passed, "errors": len(errs),
                    "warnings": len(warns), "skipped": len(skipped), "score": score},
        "checks": res.checks,
        "verdict": verdict,
    }


def main():
    ap = argparse.ArgumentParser(description="UncleKK skill spec 14-point audit")
    ap.add_argument("--path", default=".", help="skill 目录（或 SKILL.md 文件路径）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 审计报告")
    ap.add_argument("--target", choices=["skillhub", "github"], default=None,
                    help="指定发布目标以校验双语顺序（skillhub=中文在前，github=英文在前）")
    ap.add_argument("--max-lines", type=int, default=400)
    ap.add_argument("--max-bytes", type=int, default=15360)
    ap.add_argument("--strict", action="store_true", help="存在 ERROR 级 FAIL 时 exit 1（CI 用）")
    args = ap.parse_args()

    path = os.path.abspath(args.path)
    if os.path.isfile(path):
        path = os.path.dirname(path)

    try:
        res, stats, base = audit(path, args.target, args.max_lines, args.max_bytes)
        rep = build_report(res, stats, base, path)
    except Exception as e:
        # fail-open：审计器自身异常绝不阻断调用方
        sys.stderr.write("[skill-spec] audit error, fail-open: %s\n" % e)
        print(json.dumps({"skill": os.path.basename(path), "verdict": "SKIP",
                          "summary": {"total": 0, "passed": 0, "errors": 0,
                                      "warnings": 0, "skipped": 0, "score": 0},
                          "checks": [], "error": str(e)}))
        sys.exit(0)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        s = rep["summary"]
        print("=" * 64)
        print("UncleKK Skill Spec Audit · %s" % rep["skill"])
        print("=" * 64)
        print("SKILL.md: %d 行 / %d 字节" % (stats["lines"], stats["bytes"]))
        print("-" * 64)
        for c in rep["checks"]:
            mark = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[c["status"]]
            print("[%s] %-4s %-7s %s" % (mark, c["id"], c["level"], c["name"]))
            if c["status"] != "PASS":
                print("        -> %s" % c["detail"])
        print("-" * 64)
        print("通过 %d/%d · ERROR %d · WARN %d · SKIP %d · 得分 %d"
              % (s["passed"], s["total"], s["errors"], s["warnings"], s["skipped"], s["score"]))
        print("结论: %s" % rep["verdict"])
        print("=" * 64)

    if args.strict and rep["summary"]["errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
