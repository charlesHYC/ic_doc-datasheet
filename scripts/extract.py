#!/usr/bin/env python3
"""Pull the module header out of a Verilog-2001 source file.

Scoped to what this project's RTL actually uses: ANSI-style headers, parameters
with or without a type, `// ---- ... ----` banners used as port grouping, and
trailing comments. It reads the header and stops; it is not a general parser.

All structural scanning runs over a copy of the source with comments and string
bodies blanked out, so a semicolon or bracket inside a comment cannot mislead it.
"""
import json
import re
import sys

BANNER = re.compile(r'^\s*//\s*[-=]{3,}\s*$')
PORT = re.compile(r"""^\s*
    (?P<dir>input|output|inout)\b\s*
    (?:(?P<net>wire|reg|logic)\b\s*)?
    (?:(?:signed|unsigned)\b\s*)?
    (?P<width>\[[^\]]*\]\s*)?
    (?P<name>[A-Za-z_][A-Za-z_0-9$]*)
    \s*(?:,\s*)?$""", re.X)
PARAM = re.compile(r"""^\s*parameter\b\s*
    (?:(?P<type>integer|real|signed|\[[^\]]*\])\s*)?
    (?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*
    (?P<value>.+?)\s*,?\s*$""", re.X)
LOCALPARAM = re.compile(r'^\s*localparam\s+(?:\[[^\]]*\]\s*)?'
                        r'(?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*(?P<value>[^;]+);')


def blank(src):
    """Same length as src, with comment and string bodies turned into spaces."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            while i < n and src[i] != '\n':
                out.append(' '); i += 1
        elif c == '/' and i + 1 < n and src[i + 1] == '*':
            while i < n and not (src[i] == '*' and i + 1 < n and src[i + 1] == '/'):
                out.append('\n' if src[i] == '\n' else ' '); i += 1
            out.append('  '); i += 2
        elif c == '"':
            out.append('"'); i += 1
            while i < n and src[i] != '"':
                out.append(' '); i += 1
            if i < n:
                out.append('"'); i += 1
        else:
            out.append(c); i += 1
    return ''.join(out)


def split_header(src):
    """(module name, header source text, 1-based start line)."""
    b = blank(src)
    m = re.search(r'\bmodule\s+([A-Za-z_][A-Za-z_0-9$]*)', b)
    if not m:
        return None, None, None
    start = m.start()
    depth, seen, i = 0, False, start
    while i < len(b):
        if b[i] == '(':
            depth += 1; seen = True
        elif b[i] == ')':
            depth -= 1
            if seen and depth == 0:
                j = b.find(';', i)
                j = len(b) if j < 0 else j + 1
                return m.group(1), src[start:j], src[:start].count('\n') + 1
        i += 1
    return m.group(1), src[start:], src[:start].count('\n') + 1


def clean(text):
    """Drop the dashes a banner comment is padded with."""
    t = re.sub(r'^[\s-]*', '', text or '')
    return re.sub(r'[\s-]*$', '', t).strip()


def strip_trailing(line):
    """(code, trailing comment) for one source line."""
    in_s = False
    for i in range(len(line) - 1):
        if line[i] == '"':
            in_s = not in_s
        elif not in_s and line[i:i + 2] == '//':
            return line[:i], line[i + 2:].strip()
    return line, ''


def parse(path):
    src = open(path, encoding='utf-8', errors='replace').read()
    name, header, hline = split_header(src)
    if header is None:
        return None

    params, ports = [], []
    group, note, banner_buf, in_banner = None, [], [], False
    hb = blank(header).split('\n')

    for off, raw in enumerate(header.split('\n')):
        code, cmt = strip_trailing(raw)
        lineno = hline + off

        if BANNER.match(raw):
            if in_banner:
                in_banner = False
                if banner_buf:
                    # first line is the heading; anything after it is prose
                    group = banner_buf[0].strip()
                    if len(banner_buf) > 1:
                        note = list(banner_buf[1:])
            else:
                in_banner, banner_buf = True, []
            continue
        if not code.strip():
            if cmt:
                (banner_buf if in_banner else note).append(cmt)
            continue

        p = PARAM.match(code)
        if p and 'parameter' in hb[off]:
            params.append({'name': p.group('name'),
                           'value': p.group('value').rstrip(',').strip(),
                           'type': (p.group('type') or '').strip(),
                           'comment': clean(cmt or ' '.join(note)),
                           'line': lineno})
            note = []
            continue

        q = PORT.match(code)
        if q:
            ports.append({'name': q.group('name'),
                          'dir': q.group('dir'),
                          'net': q.group('net') or '',
                          'width': (q.group('width') or '').strip(),
                          'group': group or 'Ports',
                          'comment': clean(cmt or ' '.join(note)),
                          'line': lineno})
            note = []
            continue
        note = []

    body = src[len(header):]
    bb = blank(body)
    locals_ = [{'name': m.group('name'), 'value': m.group('value').strip()}
               for m in LOCALPARAM.finditer(bb)]
    insts = sorted(set(re.findall(r'^\s*([a-z_][a-z_0-9]*)\s*#?\s*\(', bb, re.M)) - {
        'if', 'for', 'case', 'casez', 'casex', 'always', 'initial', 'assign',
        'begin', 'else', 'module', 'input', 'output', 'inout', 'wire', 'reg',
        'localparam', 'parameter', 'generate', 'function', 'task', 'endcase',
        'posedge', 'negedge', 'or', 'and', 'not', 'repeat', 'while', 'integer'})

    return {'module': name, 'file': path, 'params': params, 'ports': ports,
            'localparams': locals_, 'instantiates': insts}


if __name__ == '__main__':
    print(json.dumps([o for o in (parse(p) for p in sys.argv[1:]) if o],
                     indent=1, ensure_ascii=False))
