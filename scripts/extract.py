#!/usr/bin/env python3
"""Pull the module header out of a Verilog source file.

Handles both header styles: ANSI-2001, where directions and widths sit in the
port list, and Verilog-95, where the header carries bare names and the
declarations follow inside the module. Memory compilers and other vendor macros
almost always emit the older style.

It reads one module - the first in the file - and stops at its `endmodule`. It
is not a general parser.

All structural scanning runs over a copy of the source with comments and string
bodies blanked out, so a semicolon or bracket inside a comment cannot mislead it.
"""
import json
import re
import sys

IDENT = r'[A-Za-z_][A-Za-z_0-9$]*'

BANNER = re.compile(r'^\s*//\s*[-=]{3,}\s*$')
# One declaration may carry several names and each may have an initialiser:
#   input wire [7:0] a, b,        output reg ready = 1'b0,
PORT = re.compile(r"""^\s*
    (?P<dir>input|output|inout)\b\s*
    (?:(?P<net>wire|reg|logic)\b\s*)?
    (?:(?:signed|unsigned)\b\s*)?
    (?P<width>\[[^\]]*\]\s*)?
    (?P<names>[A-Za-z_][A-Za-z_0-9$]*\s*(?:=[^,]+)?
              (?:,\s*[A-Za-z_][A-Za-z_0-9$]*\s*(?:=[^,]+)?)*)
    \s*,?\s*$""", re.X)
PARAM = re.compile(r"""^\s*parameter\b\s*
    (?:(?P<type>integer|real|signed|\[[^\]]*\])\s*)?
    (?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*
    (?P<value>.+?)\s*,?\s*$""", re.X)
# re.M matters: without it `^` only ever matches the start of the whole body and
# every module comes back with no localparams at all.
LOCALPARAM = re.compile(r'^\s*localparam\s+(?:\[[^\]]*\]\s*)?'
                        r'(?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*(?P<value>[^;]+);', re.M)

# A Verilog-95 port declaration, which lives in the body rather than the header:
#   output [127:0] Q;      input CLK;      input a, b, c;
DECL = re.compile(r"""^\s*
    (?P<dir>input|output|inout)\b\s*
    (?:(?P<net>wire|reg|logic)\b\s*)?
    (?:(?:signed|unsigned)\b\s*)?
    (?P<width>\[[^\]]*\]\s*)?
    (?P<names>[A-Za-z_][^;]*?)\s*;""", re.X)
# Same, for parameters declared inside a Verilog-95 module.
BODY_PARAM = re.compile(r"""^\s*parameter\b\s*
    (?:(?P<type>integer|real|signed|\[[^\]]*\])\s*)?
    (?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*
    (?P<value>[^;]+);""", re.X)

# An instantiation is a type followed by an instance name and then a port list,
# with an optional parameter override and instance array range between them.
# Requiring the instance name is what keeps task and function calls out: a call
# is one identifier followed straight by "(".
INST = re.compile(r"""^[ \t]*
    (?P<type>[A-Za-z_][A-Za-z_0-9$]*)
    (?:
        [ \t]*\#\s*\((?:[^()]|\([^()]*\))*\)\s*   # override, may span lines
      | [ \t]+                                        # or nothing between them,
    )                                                 # in which case: same line
    (?P<inst>[A-Za-z_][A-Za-z_0-9$]*)\s*
    (?:\[[^\]]*\]\s*)?
    \(""", re.M | re.X)

# Keywords that can appear in the shape INST matches. Gate primitives really do
# take an instance name, so they have to be named rather than matched away.
NOT_A_MODULE = {
    'if', 'for', 'case', 'casez', 'casex', 'always', 'always_ff', 'always_comb',
    'always_latch', 'initial', 'final', 'assign', 'begin', 'else', 'module',
    'end', 'join', 'fork', 'endtask', 'endfunction', 'endprimitive',
    'input', 'output', 'inout', 'wire', 'reg', 'logic', 'localparam',
    'parameter', 'generate', 'endgenerate', 'function', 'task',
    'endcase', 'endmodule', 'posedge', 'negedge', 'repeat', 'while',
    'forever', 'wait', 'integer', 'real', 'genvar', 'defparam', 'specify',
    'endspecify', 'return', 'disable', 'force', 'release', 'deassign',
    'and', 'or', 'not', 'nand', 'nor', 'xor', 'xnor', 'buf', 'bufif0', 'bufif1',
    'notif0', 'notif1', 'pmos', 'nmos', 'cmos', 'rpmos', 'rnmos', 'rcmos',
    'tran', 'tranif0', 'tranif1', 'rtran', 'rtranif0', 'rtranif1', 'pullup',
    'pulldown', 'supply0', 'supply1', 'tri', 'triand', 'trior', 'wand', 'wor',
}


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
    """(module name, header text, 1-based start line, offset just past the header).

    The offset is returned because the header does not necessarily begin at the
    start of the file; slicing the body by len(header) instead lands in the
    middle of whatever banner comment precedes the module.
    """
    b = blank(src)
    m = re.search(r'\bmodule\s+(%s)' % IDENT, b)
    if not m:
        return None, None, None, None
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
                return m.group(1), src[start:j], src[:start].count('\n') + 1, j
        elif b[i] == ';' and not seen:
            # a module with no port list at all
            return m.group(1), src[start:i + 1], src[:start].count('\n') + 1, i + 1
        i += 1
    return m.group(1), src[start:], src[:start].count('\n') + 1, len(src)


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


def header_port_order(header):
    """Port names from a Verilog-95 header, or None if this is not one.

    A bare name list is the signature: anything carrying a direction keyword is
    an ANSI header and belongs to the other path.
    """
    b = blank(header)
    if '(' not in b:
        return None
    inner = b[b.index('(') + 1:b.rindex(')')] if ')' in b else ''
    names = [t.strip() for t in inner.split(',') if t.strip()]
    if not names or not all(re.fullmatch(IDENT, n) for n in names):
        return None
    return names


def nonansi_ports(order, body, bline):
    """Directions and widths for a Verilog-95 header.

    Only names the header actually lists are accepted, so an `input` inside a
    task or function cannot invent a port that is not on the interface.
    """
    want, found = set(order), {}
    for off, raw in enumerate(body.split('\n')):
        code, cmt = strip_trailing(raw)
        m = DECL.match(code)
        if not m:
            continue
        names = [n.strip() for n in m.group('names').split(',') if n.strip()]
        if not all(re.fullmatch(IDENT, n) for n in names):
            continue
        for n in names:
            if n in want and n not in found:
                found[n] = {'name': n, 'dir': m.group('dir'),
                            'net': m.group('net') or '',
                            'width': (m.group('width') or '').strip(),
                            'group': 'Ports', 'comment': clean(cmt),
                            'line': bline + off}
    return [found[n] for n in order if n in found]


def nonansi_params(body, bline):
    """Parameters declared inside a Verilog-95 module."""
    out = []
    for off, raw in enumerate(body.split('\n')):
        code, cmt = strip_trailing(raw)
        m = BODY_PARAM.match(code)
        if m:
            out.append({'name': m.group('name'), 'value': m.group('value').strip(),
                        'type': (m.group('type') or '').strip(),
                        'comment': clean(cmt), 'line': bline + off})
    return out


def port_names(names):
    """The names in one declaration, with any initialiser dropped."""
    out = []
    for part in names.split(','):
        part = part.split('=', 1)[0].strip()
        if part:
            out.append(part)
    return out


def top_level_groups(b):
    """(start, end) of each parenthesised group at depth zero."""
    out, depth, start = [], 0, None
    for i, ch in enumerate(b):
        if ch == '(':
            depth += 1
            if depth == 1:
                start = i + 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and start is not None:
                out.append((start, i))
                start = None
    return out


def split_commas(text):
    """Split on the commas that are not inside brackets."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        out.append(''.join(cur))
    return out


def inline_ports(header, hline):
    """Ports from an ANSI header written on one line.

    The main pass is line-oriented, so `module foo (input a, output b);` gets
    nothing: no line begins with a direction keyword. Split the port list on its
    own commas instead. The last top-level group is the ports, since a header
    with parameters has `#(...)` in front of it.
    """
    b = blank(header)
    groups = top_level_groups(b)
    if not groups:
        return []
    lo, hi = groups[-1]
    ports = []
    for frag in split_commas(b[lo:hi]):
        m = PORT.match(frag.strip())
        if not m:
            continue
        for n in port_names(m.group('names')):
            ports.append({'name': n, 'dir': m.group('dir'), 'net': m.group('net') or '',
                          'width': (m.group('width') or '').strip(),
                          'group': 'Ports', 'comment': '', 'line': hline})
    return ports



def parse(path):
    src = open(path, encoding='utf-8', errors='replace').read()
    name, header, hline, hend = split_header(src)
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
            for n in port_names(q.group('names')):
                ports.append({'name': n,
                              'dir': q.group('dir'),
                              'net': q.group('net') or '',
                              'width': (q.group('width') or '').strip(),
                              'group': group or 'Ports',
                              'comment': clean(cmt or ' '.join(note)),
                              'line': lineno})
            note = []
            continue
        note = []

    # Stop at this module's end, so a second module in the same file cannot
    # contribute its declarations, localparams or instantiations to this one.
    body = src[hend:]
    end = re.search(r'\bendmodule\b', blank(body))
    if end:
        body = body[:end.start()]
    bline = src[:hend].count('\n') + 1

    if not ports:
        ports = inline_ports(header, hline)
    if not ports:
        order = header_port_order(header)
        if order:
            ports = nonansi_ports(order, body, bline)
        if not params:
            # Verilog-95, or a module with no port list: parameters are declared
            # inside the module rather than in its header.
            params = nonansi_params(body, bline)

    bb = blank(body)
    locals_ = [{'name': m.group('name'), 'value': m.group('value').strip()}
               for m in LOCALPARAM.finditer(bb)]
    insts = sorted({m.group('type') for m in INST.finditer(bb)
                    if m.group('type') not in NOT_A_MODULE})

    return {'module': name, 'file': path, 'params': params, 'ports': ports,
            'localparams': locals_, 'instantiates': insts}


if __name__ == '__main__':
    print(json.dumps([o for o in (parse(p) for p in sys.argv[1:]) if o],
                     indent=1, ensure_ascii=False))
