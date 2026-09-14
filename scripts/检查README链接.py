#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 README.md（或任意 markdown）内所有相对链接是否指向仓库内真实存在的文件。

规则（对应交付要求「README 内相对链接必须指向仓库内存在的文件」）:
  - 提取所有 markdown 链接 [text](target)。
  - 跳过 http(s):// 与 mailto: 外链。
  - 纯锚点链接 (#sec) 校验其指向的标题是否存在（由本文件内标题生成 GitHub 风格 slug）。
  - 文件链接（可带 #anchor 尾部）: 去掉锚点后检查该相对路径在磁盘上是否存在。
      * 存在且未被 .gitignore 排除            -> OK
      * 存在但被 .gitignore 排除（如 outputs/) -> WARN（clone 后不存在，需本地生成，应改为行内代码或注明）
      * 不存在                                 -> FAIL
  - 退出码: 有 FAIL 则 2；仅有 WARN 则 1；全 OK 则 0。

用法: python scripts/检查README链接.py [README.md ...]
"""
import os
import re
import sys
import subprocess

ROOT = os.environ.get('SUGAR_ROOT', '/scratch/e1351071/zju_test_test')

LINK_RE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')


def slugify(title):
    """GitHub 风格 anchor: 小写, 去标点(保留中日文/字母数字/连字符), 空格->连字符。"""
    s = title.strip().lower()
    # 去掉 markdown 行内代码反引号与常见标点
    s = s.replace('`', '')
    out = []
    for ch in s:
        if ch.isalnum() or ch in ('-', '_'):
            out.append(ch)
        elif ch.isspace():
            out.append('-')
        # 其它标点直接丢弃
    return ''.join(out)


def collect_headers(md_path):
    slugs = set()
    with open(md_path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^(#{1,6})\s+(.*?)\s*$', line)
            if m:
                slugs.add(slugify(m.group(2)))
    return slugs


def is_gitignored(path):
    try:
        r = subprocess.run(['git', 'check-ignore', '-q', path],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def check(md_path):
    md_path = os.path.abspath(md_path)
    base = os.path.dirname(md_path)
    slugs = collect_headers(md_path)
    with open(md_path, encoding='utf-8') as f:
        text = f.read()

    results = []  # (status, target, note)
    for m in LINK_RE.finditer(text):
        tgt = m.group(1).strip()
        if tgt.startswith(('http://', 'https://', 'mailto:')):
            continue
        if tgt.startswith('#'):
            anchor = tgt[1:]
            status = 'OK' if anchor in slugs else 'FAIL'
            results.append((status, tgt, 'anchor' + ('' if status == 'OK' else ' 未找到对应标题')))
            continue
        # 文件链接（可能带 #anchor）
        path = tgt.split('#', 1)[0]
        if not path:
            continue
        abspath = os.path.normpath(os.path.join(base, path))
        rel_from_root = os.path.relpath(abspath, ROOT)
        if os.path.exists(abspath):
            if is_gitignored(rel_from_root):
                results.append(('WARN', tgt, 'gitignore 排除, clone 后不存在 (需本地生成)'))
            else:
                results.append(('OK', tgt, 'file'))
        else:
            results.append(('FAIL', tgt, '文件不存在'))
    return results


def main():
    targets = sys.argv[1:] or [os.path.join(ROOT, 'README.md')]
    n_fail = n_warn = n_ok = 0
    for md in targets:
        print(f'== {md} ==')
        for status, tgt, note in check(md):
            print(f'  [{status:4}] {tgt}    ({note})')
            if status == 'FAIL':
                n_fail += 1
            elif status == 'WARN':
                n_warn += 1
            else:
                n_ok += 1
    print(f'\n汇总: OK={n_ok}  WARN={n_warn}  FAIL={n_fail}')
    sys.exit(2 if n_fail else (1 if n_warn else 0))


if __name__ == '__main__':
    main()
