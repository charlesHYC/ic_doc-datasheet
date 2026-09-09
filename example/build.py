#!/usr/bin/env python3
"""Assemble the datasheet from modules.json plus the prose kept here.

WORKED EXAMPLE. This is the real assembly script for a 29-page datasheet of
a fictional example design. Copy it into your own project directory
alongside the skill's scripts/ and edit the project-specific constants:

    DESIGN, PROSE, LIB, FULL, CSR, TIMING, and the cover page text

Everything else - the CSS, symbol(), the table builders, resolve_params() and
the pagination - carries over to any Verilog project unchanged.

Facts (parameters, ports, groups, instantiation) come from extract.py and are
never edited by hand. Prose is authored, and lives in PROSE below so a re-run
cannot overwrite it.

Run it from a directory holding modules.json and the skill's scripts:
    python3 build.py
"""
import json
import re
from collections import OrderedDict
import blocks as blockfig
import wave as wavefig
import paginate as pg

# Output is named after the design, the way a compiler-generated datasheet is.
DESIGN = 'example'
OUT = 'datasheet_manual.html' if not DESIGN else '%s_datasheet_manual.html' % DESIGN

MODS = {m['module']: m for m in json.load(open('modules.json'))}

# Placeholder prose. Real entries are two paragraphs per module and say *why*,
# not what: "these register slices are not decoration - without them the path
# from the controller to the write engine misses timing" beats restating the
# port list. Replace all of this with your own; a re-run never touches it.
PROSE = {
 'read_path': (
   "Reads stored records back out of memory and turns them into an output stream. "
   "Describe here what the block is for and what it owns, in the terms someone "
   "reviewing the design would use.",
   "Second paragraph is for the part that is not obvious from the port list: the "
   "structural decision, and the reason behind it. Say what would go wrong if it "
   "were done the other way."),
 'write_path': (
   "The register face of the write side: control and status registers, and the "
   "hand-off to the engine that does the transfer.",
   "Explain the modes or the sequencing the registers imply, and anything about "
   "the order operations have to be issued in."),
 'dma_engine': (
   "Moves data from host memory into on-card memory. Takes a descriptor and "
   "returns a status pulse.",
   "Say what is inside and why that shape was chosen - what is being overlapped, "
   "what latency is being hidden, where the buffering sits."),
 'axi_demux': (
   "Routes one wide write master to several channel-local masters.",
   "Describe the routing rule and its consequences; if there is no decode table "
   "because the address already carries the channel number, that is worth saying."),
 'axi_downsize': (
   "Converts an AXI write channel to half its width.",
   "If the module exists because a library equivalent could not be used, say so "
   "and why - that is exactly the kind of thing a reader cannot recover from the "
   "code."),
 'soc_app_top': (
   "The framework application block: the shell the design lives in. Its port list "
   "is defined by the framework, which is why it is large.",
   "Say what this level adds on top of the framework - which submodules it wires "
   "together, what the register map decodes, and any per-port structure that "
   "exists for timing rather than for function."),
}

LIB = [
 ('axi_wr_master', 'framework', 'Drives one AXI write master from segmented RAM. '
  'Note any width relationship it imposes on the rest of the design.'),
 ('stage_ram', 'framework', 'Segmented pseudo dual-port RAM, used here as a private '
  'staging buffer.'),
 ('axis_fifo', 'verilog-axis', 'Record FIFO in the read path. With KEEP_ENABLE, DEPTH is '
  'counted in bytes rather than words - a real trap worth writing down.'),
 ('axi_reg_rd', 'verilog-axi', 'Read-channel register slice, one per memory port.'),
 ('axi_reg_wr', 'verilog-axi', 'Write-channel register slice, one per memory port.'),
]

FULL = ['read_path', 'write_path', 'dma_engine',
        'axi_demux', 'axi_downsize']



def _num(tok):
    """Verilog literal -> int, or None."""
    t = tok.strip().replace('_', '')
    m = re.fullmatch(r"(?:(\d+)\')?([hdbo])?([0-9a-fA-F]+)", t)
    if m and m.group(2):
        return int(m.group(3), {'h': 16, 'd': 10, 'b': 2, 'o': 8}[m.group(2)])
    return int(t) if re.fullmatch(r'\d+', t) else None


def resolve_params(mod):
    """Parameter name -> integer value, following references between them."""
    vals, raw = {}, {p['name']: p['value'] for p in mod['params']}
    for _ in range(6):
        for k, v in raw.items():
            if k in vals:
                continue
            e = v
            e = re.sub(r'\$clog2\s*\(([^)]*)\)', r'__clog2(\1)', e)
            for name, val in vals.items():
                e = re.sub(r'\b%s\b' % re.escape(name), str(val), e)
            e = re.sub(r"(\d+)'[hH]([0-9a-fA-F]+)", lambda m: str(int(m.group(2), 16)), e)
            e = re.sub(r"(\d+)'[dD](\d+)", lambda m: m.group(2), e)
            e = re.sub(r"(\d+)'[bB]([01]+)", lambda m: str(int(m.group(2), 2)), e)
            if re.fullmatch(r'[\d\s+\-*/()]+|__clog2\([\d\s+\-*/()]+\)', e.strip()):
                try:
                    import math
                    vals[k] = int(eval(e, {'__clog2': lambda x: max(1, math.ceil(math.log2(x))),
                                           '__builtins__': {}}))
                except Exception:
                    pass
    return vals


def concrete_width(width, vals):
    """[MEM_CH*ID-1:0] -> [95:0] when every name in it is known."""
    if not width:
        return ''
    inner = width.strip()[1:-1]
    if ':' not in inner:
        return width
    hi, lo = inner.rsplit(':', 1)
    out = []
    for part in (hi, lo):
        e = part
        for name, val in sorted(vals.items(), key=lambda kv: -len(kv[0])):
            e = re.sub(r'\b%s\b' % re.escape(name), str(val), e)
        if not re.fullmatch(r'[\d\s+\-*/()]+', e.strip()):
            return width
        try:
            out.append(str(int(eval(e, {'__builtins__': {}}))))
        except Exception:
            return width
    return '[%s:%s]' % (out[0], out[1])


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')



# Read off the AXI-Lite case decode in soc_app_top.v; the byte offset is the
# 6-bit selector shifted left by two.
# Placeholder register map. Read the real offsets off the AXI-Lite decode rather
# than transcribing them, and keep the three access semantics distinct: a bit
# that self-clears, a bit that is held for the duration, and a bit cleared by
# the act of reading it. That distinction is the point of the table.
CSR = [
 ('0x00', 'src_addr_lo', 'R/W', 'Source address, bits [31:0]'),
 ('0x04', 'src_addr_hi', 'R/W', 'Source address, bits [63:32]'),
 ('0x08', 'length', 'R/W', 'Transfer length'),
 ('0x0C', 'wr_ctrl', 'W', 'bit[0] go, self-clearing; bit[1] mode, held'),
 ('0x10', 'wr_status', 'R', 'bit[0] busy; bit[1] done, cleared on read'),
 ('0x14', 'rd_ctrl', 'W', 'bit[0] go, self-clearing; bit[1] free_run, held'),
 ('0x18', 'rd_status', 'R', 'bit[0] busy; bit[1] done, cleared on read; '
                            'bit[2] config_unsupported'),
 ('0x1C', 'debug_state', 'R', 'Per-source stall flags, one bit each'),
 ('0x20', 'cap_count', 'R', 'Records captured this run, at most CAP_DEPTH'),
 ('0x24', 'cap_word_addr', 'R/W', 'Readback word index: record = addr &gt;&gt; 4'),
 ('0x28', 'cap_rdata', 'R', 'The word at cap_word_addr, registered'),
 ('0x2C', 'run_cycles', 'R', 'Measured run length, in clock cycles'),
]


def csr_tbl():
    r = ['<table><thead><tr><th>Offset</th><th class="l">Name</th><th>Access</th>'
         '<th class="l">Description</th></tr></thead><tbody>']
    for off, name, acc, desc in CSR:
        r.append('<tr><td class="c mono">%s</td><td class="mono">%s</td>'
                 '<td class="c">%s</td><td>%s</td></tr>' % (off, name, acc, desc))
    return "\n".join(r) + '</tbody></table>'


def bundle(ports):
    """Collapse a family of related ports into one symbol line.

    An AXI channel is the natural unit: aw, w, b, ar and r each become one line,
    which keeps the structure of the interface visible. Anything else falls back
    to a common prefix, and only collapses when there are enough of them to be
    worth it.
    """
    CHAN = re.compile(r'^(.*_(?:aw|ar|w|r|b))([a-z]+)$')

    def stem(name):
        m = CHAN.match(name)
        if m:
            return m.group(1), True
        return name.rsplit('_', 1)[0], False

    def really_a_channel(run):
        """The prefix rule alone is not enough: cpu_wdata and cpu_we end in _w
        plus letters and are not a channel. Every AXI channel has both a valid
        and a ready, so ask for those."""
        sufs = {CHAN.match(q['name']).group(2) for q in run if CHAN.match(q['name'])}
        return {'valid', 'ready'} <= sufs

    out, i = [], 0
    while i < len(ports):
        p = ports[i]
        st, is_chan = stem(p['name'])
        run, j = [p], i + 1
        while j < len(ports) and ports[j]['dir'] == p['dir'] and stem(ports[j]['name'])[0] == st:
            run.append(ports[j]); j += 1
        if is_chan and not really_a_channel(run):
            is_chan = False
        if len(run) >= (2 if is_chan else 4):
            out.append((st + '*', '%d signals' % len(run), p['dir']))
        else:
            for q in run:
                out.append((q['name'], q['width'], q['dir']))
        i = j
    return out


def fit(name, width, limit=26):
    """Name plus width if it fits; the name alone if not. The pin table carries
    the width either way, so dropping it here loses nothing."""
    full = name + (' ' + width if width else '')
    return full if len(full) <= limit else name


def by_group(ports):
    """One line per interface group, for modules too wide to draw signal by signal."""
    out, seen = [], OrderedDict()
    for p in ports:
        seen.setdefault(p['group'], []).append(p)
    for g, ps in seen.items():
        # the banner's first clause is the interface name; the rest is prose
        head = re.split(r'[(:.]', g, 1)[0].strip().rstrip(',')
        if len(head) > 24:
            words, head = head.split(), ''
            for w in words:
                if len(head) + len(w) + 1 > 23:
                    head += '\u2026'
                    break
                head = (head + ' ' + w).strip()
        out.append((head, '', ps[0]['dir']))
    return out


# Drawn on the underside of the symbol rather than as inputs on the left.
# rst_n is the common spelling and was being drawn as an ordinary input.
BOTTOM_PINS = {'clk', 'clock', 'aclk', 'rst', 'rstn', 'rst_n', 'reset', 'reset_n',
               'resetn', 'areset', 'aresetn', 'areset_n'}


def is_bottom(name):
    return name.lower() in BOTTOM_PINS


def symbol(mod):
    vals = resolve_params(mod)
    live = [p for p in mod['ports'] if not is_bottom(p['name'])]
    ins = bundle([p for p in live if p['dir'] == 'input'])
    outs = bundle([p for p in live if p['dir'] == 'output'])
    # a symbol taller than a page helps nobody; step up to interface granularity
    if max(len(ins), len(outs)) > 13:
        ins = by_group([p for p in live if p['dir'] == 'input'])
        outs = by_group([p for p in live if p['dir'] == 'output'])
    clks = [p['name'] for p in mod['ports'] if is_bottom(p['name'])]
    pitch, pad, bx, bw = 27, 24, 226, 200
    rows = max(len(ins), len(outs))
    bh = rows * pitch + 2 * pad
    W, H = 668, bh + 40 + 62
    top = 30
    o = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="Symbol for %s">'
         % (W, H, mod['module']),
         '<g font-family="Times New Roman, Times, serif" font-size="13.5">',
         '<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#000" '
         'stroke-width="1.6"/>' % (bx, top, bw, bh)]
    for i, (n, w, _) in enumerate(ins):
        yy = top + pad + i * pitch
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#000" stroke-width="0.9"/>'
                 % (bx - 30, yy, bx, yy))
        lab = fit(n, concrete_width(w, vals) if w else '')
        o.append('<text x="%d" y="%d" text-anchor="end">%s</text>'
                 % (bx - 36, yy + 4.5, esc(lab)))
    for i, (n, w, _) in enumerate(outs):
        yy = top + pad + i * pitch
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#000" stroke-width="0.9"/>'
                 % (bx + bw, yy, bx + bw + 30, yy))
        lab = fit(n, concrete_width(w, vals) if w else '')
        o.append('<text x="%d" y="%d">%s</text>'
                 % (bx + bw + 36, yy + 4.5, esc(lab)))
    for i, n in enumerate(clks):
        xx = bx + bw / (len(clks) + 1) * (i + 1)
        o.append('<line x1="%.0f" y1="%d" x2="%.0f" y2="%d" stroke="#000" stroke-width="0.9"/>'
                 % (xx, top + bh, xx, top + bh + 26))
        o.append('<text x="%.0f" y="%d" text-anchor="middle">%s</text>'
                 % (xx, top + bh + 42, n))
    o.append('<text x="%d" y="%d" text-anchor="middle" font-size="15" font-weight="bold">%s</text>'
             % (bx + bw / 2, top + bh / 2 + 5, mod['module']))
    o += ['</g>', '</svg>']
    return "\n".join(o)


def params_rows(mod):
    thead = ('<table><thead><tr><th class="l">Parameter</th><th>Default</th>'
             '<th class="l">Description</th></tr></thead><tbody>')
    rows = []
    for p in mod['params']:
        rows.append(('<tr><td class="mono">%s</td><td class="c mono">%s</td><td>%s</td></tr>'
                     % (esc(p['name']), esc(p['value']), esc(p['comment'])),
                     pg.rows_px(p['comment'], pg.CPL_PARAMS)))
    return thead, rows


def pins_rows(mod):
    vals = resolve_params(mod)
    groups = OrderedDict()
    for p in mod['ports']:
        groups.setdefault(p['group'], []).append(p)
    thead = ('<table><thead><tr><th class="l">Pin</th><th>Dir</th><th class="l">Width</th>'
             '<th class="l">Description</th></tr></thead><tbody>')
    rows = []
    for g, ps in groups.items():
        rows.append(('<tr class="grp"><td colspan="4">%s</td></tr>' % esc(g), pg.GRP_PX))
        for p in ps:
            rows.append(('<tr><td class="mono">%s</td><td class="c">%s</td>'
                         '<td class="mono">%s</td><td>%s</td></tr>'
                         % (esc(p['name']), p['dir'][:3],
                            esc(concrete_width(p['width'], vals) or '1'), esc(p['comment'])),
                         pg.rows_px(p['comment'], pg.CPL_PINS)))
    return thead, rows


def wrap_rows(thead, rows):
    return thead + "\n".join(rows) + '</tbody></table>'


def hierarchy():
    """Containment, not an indented list. Notes sit on a second line inside each
    box, so box width never has to shrink the type."""
    OWN, LIB_F = '#e6e4e0', '#ffffff'
    o = []
    W = 720

    def box(x, y, w, h, name, note='', own=True, ns=15, nt=11.5):
        o.append('<rect x="%g" y="%g" width="%g" height="%g" fill="%s" stroke="#000" '
                 'stroke-width="%s" rx="2"/>'
                 % (x, y, w, h, OWN if own else LIB_F, '1.6' if own else '0.9'))
        o.append('<text x="%g" y="%g" font-size="%g">%s</text>'
                 % (x + 10, y + ns + 5, ns, name))
        if note:
            o.append('<text x="%g" y="%g" font-size="%g" fill="#3a3a3a">%s</text>'
                     % (x + 10, y + ns + nt + 9, nt, note))

    # ---- outer shell -------------------------------------------------
    box(6, 6, W - 12, 342, 'soc_app_top', 'framework application shell', True, 18, 12)

    # ---- write path -> dma_engine -> four children ---------------------
    box(20, 54, 308, 280, 'write_path', 'control and status registers',
        True, 15, 11.5)
    box(34, 102, 280, 220, 'dma_engine', 'host memory to on-card memory', True, 14, 11)
    kids = [('stage_ram', 'staging RAM', False),
            ('axi_wr_master', 'AXI write master', False),
            ('axi_demux', 'one master to N channels', True),
            ('axi_downsize', 'width conversion, one per channel', True)]
    for i, (n, note, own) in enumerate(kids):
        box(48, 148 + i * 42, 252, 36, n, note, own, 12.5, 10)

    # ---- read path -----------------------------------------------------
    box(342, 54, 196, 152, 'read_path', 'memory to the output stream', True, 15, 11.5)
    box(356, 108, 168, 36, 'axis_fifo', 'record FIFO, one per lane', False, 12.5, 10)
    o.append('<text x="356" y="172" font-size="11" fill="#3a3a3a">8 read masters,</text>')
    o.append('<text x="356" y="188" font-size="11" fill="#3a3a3a">2 channels each</text>')

    # ---- register slices: a grouping, so no fill -----------------------
    o.append('<rect x="552" y="54" width="152" height="152" fill="none" stroke="#000" '
             'stroke-width="0.9" stroke-dasharray="6 4" rx="2"/>')
    o.append('<text x="564" y="76" font-size="12.5" font-style="italic">per-channel</text>')
    o.append('<text x="564" y="92" font-size="12.5" font-style="italic">register slices</text>')
    box(564, 104, 128, 36, 'axi_reg_wr', 'x16', False, 12, 10)
    box(564, 150, 128, 36, 'axi_reg_rd', 'x16', False, 12, 10)

    # ---- data in and out ------------------------------------------------
    o.append('<defs><marker id="hh" markerWidth="9" markerHeight="8" refX="8" refY="4" '
             'orient="auto"><polygon points="0 0, 9 4, 0 8" fill="#000"/></marker></defs>')
    o.append('<line x1="140" y1="380" x2="140" y2="354" stroke="#000" stroke-width="1.5" '
             'marker-end="url(#hh)"/>')
    o.append('<text x="154" y="376" font-size="13">data in, from the host</text>')
    o.append('<line x1="440" y1="354" x2="440" y2="380" stroke="#000" stroke-width="1.5" '
             'marker-end="url(#hh)"/>')
    o.append('<text x="454" y="376" font-size="13">records out, to the sink</text>')

    return ('<svg viewBox="0 0 %d 394" width="100%%" role="img" '
            'aria-label="Module hierarchy drawn by containment">'
            '<g font-family="Times New Roman, Times, serif">%s</g></svg>'
            % (W, "\n".join(o)))


# ---------------------------------------------------------------- page shell
CSS = """
  @page { size: A4; margin: 15mm 14mm 12mm; }
  * { box-sizing: border-box; margin: 0; padding: 0; }

  /* One serif family for the document. Identifiers keep a monospace face so a
     signal name can be told apart from prose; the symbol figure keeps its own. */
  body { background:#eceae6; color:#000;
         font:10pt/1.46 "Times New Roman", Times, "Noto Serif TC", serif; }
  /* identifiers share the document face, by request */
  .mono, code { font-family:"Times New Roman", Times, serif; }

  .page { width:210mm; min-height:297mm; margin:10mm auto; padding:15mm 14mm 12mm;
          background:#fff; box-shadow:0 1px 6px rgba(0,0,0,.18); display:flex; flex-direction:column; }

  /* --- type scale: title 18 / subtitle 11.5 / section 12 / sub-head 10 / body 10 / table 8.6 --- */
  .titles div:first-child { font-size:19pt; font-weight:700; line-height:1.2; }
  .titles div { font-size:12pt; font-weight:400; white-space:nowrap; margin-top:2.2mm; }
  .rule { border-top:1.4pt solid #000; margin-top:3.5mm; }

  /* The heading sits on its own line and the text runs flush left under it. */
  .band { padding:4.5mm 0; border-top:0.9pt solid #000; }
  .band:first-of-type { border-top:0; }
  .band > h2 { font-size:13pt; font-weight:700; line-height:1.25; margin-bottom:3mm; }
  .band > h2 small { display:inline; font-weight:400; font-size:9.2pt; color:#444;
                     margin-left:3mm; }

  .band p { font-size:11pt; }
  .band p + p { margin-top:2.4mm; }
  .note { font-size:9.6pt; color:#444; margin-top:2.6mm; }

  .wide { display:block; }
  .wide > h2 { margin-bottom:3.5mm; }

  table { border-collapse:collapse; width:100%; font-size:9.6pt; }
  th { background:#6f6f6f; color:#fff; font-weight:700; text-align:center;
       border:0.7pt solid #000; padding:1.1mm 1.4mm; font-size:9.8pt; }
  th.l { text-align:left; }
  td { border:0.7pt solid #000; padding:0.9mm 1.4mm; vertical-align:top; }
  td.c { text-align:center; }
  .mono { font-size:9.4pt; }
  /* sub-heading inside a table sits above body size, as a heading should */
  tr.grp td { background:#e2e0dc; font-weight:700; font-size:10.6pt; padding:1.4mm 1.4mm; }

  figure { margin:0; }
  .fig-center { text-align:center; }
  .fig-center svg { max-width:152mm; margin:0 auto; }
  .fig-wide svg { max-width:100%; margin:0 auto; }
  .fig-wave svg { max-width:100%; height:auto; margin:0 auto; }
  .fig-sym svg { max-width:158mm; margin:0 auto; }
  figcaption { font-size:9.4pt; margin-top:2.4mm; color:#333; }

  footer { margin-top:auto; padding-top:4mm; border-top:0.7pt solid #000;
           display:grid; grid-template-columns:1fr auto 1fr; font-size:8.6pt; }
  footer .c { text-align:center; } footer .r { text-align:right; }
  @media print { body{background:#fff} .page{margin:0;padding:0;width:auto;min-height:0;box-shadow:none} }
"""

pages = []


def page(inner, num):
    pages.append('<div class="page">\n%s\n<footer><div>Example Design</div>'
                 '<div class="c">rev. 1.0</div><div class="r">%d</div></footer>\n</div>'
                 % (inner, num))


# --- page 1: overview + hierarchy ---
idx = ['<table><thead><tr><th class="l">Module</th><th>Params</th><th>Ports</th>'
       '<th class="l">Role</th></tr></thead><tbody>']
for n in FULL + ['soc_app_top']:
    m = MODS[n]
    idx.append('<tr><td class="mono">%s</td><td class="c">%d</td><td class="c">%d</td>'
               '<td>%s</td></tr>' % (n, len(m['params']), len(m['ports']),
                                     esc(PROSE[n][0].split('.')[0] + '.')))
idx.append('</tbody></table>')

page("""
  <div class="titles">
    <div>Example Design Module Reference</div>
    <div>Module Reference &mdash; 6 RTL modules, 5 library modules</div>
    <div>Example FPGA &middot; on-card memory &middot; single clock domain</div>
  </div>
  <div class="rule"></div>

  <div class="band"><h2>Overview</h2><div>
    <p>Placeholder overview. Say what the design does in two or three sentences,
    in the terms someone deciding whether to read further would use, and be
    specific about what is and is not in the datapath.</p>
    <p>Then the one structural fact that shapes everything else - a single clock
    domain, a fixed latency, a width that everything is built around. Parameters
    and ports in this document are read from the sources, not transcribed.</p>
  </div></div>

  <div class="band wide"><h2>Hierarchy</h2>
    <figure><div class="fig-center fig-wide">%s</div>
    <figcaption>Shaded blocks are modules of this design; unshaded are library modules
    instantiated unmodified.</figcaption></figure>
  </div>
""" % hierarchy(), 1)

page('  <div class="band wide"><h2>Module index</h2>%s</div>' % "\n".join(idx), 2)

# --- page 2: block diagram ---
page("""
  <div class="band wide"><h2>Block diagram</h2>
    <figure><div class="fig-center fig-wide">%s</div>
    <figcaption>How the modules are wired to one another, following the data rather than the
    hierarchy. Shaded frames are the two engines; the column on the left is the control path
    from CSR. The memory channels appear once, between the write path above and the
    read path below.</figcaption></figure>
  </div>
""" % blockfig.render(), 3)

def paged_table(lead, lead_px, title, thead, rows, n):
    """Put `lead` on a page and as much of the table under it as fits.

    pg.chunk hands back an empty opening list when nothing fits beside the lead;
    that means the lead gets the page to itself and the table starts on the next
    one, rather than being forced on top and pushing the page over A4.
    """
    head_px = pg.BAND_PX + pg.THEAD_PX
    parts = pg.chunk(rows, pg.body_px(head_px), first=pg.body_px(lead_px + head_px))
    total, k = sum(1 for p in parts if p), 0
    for i, part in enumerate(parts):
        band = ''
        if part:
            k += 1
            t = title if total < 2 else '%s (%d of %d)' % (title, k, total)
            band = '  <div class="band wide"><h2>%s</h2>%s</div>' % (t, wrap_rows(thead, part))
        page(((lead + "\n\n") if i == 0 else '') + band, n)
        n += 1
    return n


# --- one page per full module, split whenever a page would not fit A4 ---
n_page = 4
SYM_CAP = ('Families of related AXI signals are drawn as one bundle; the pin table below '
           'lists every signal.')

for name in FULL:
    m = MODS[name]
    p = PROSE[name]
    inst = ', '.join(m['instantiates']) or 'none'

    desc = ("""  <div class="titles"><div>%s</div></div>
  <div class="rule"></div>

  <div class="band"><h2>Description<small>%s</small></h2><div>
    <p>%s</p><p>%s</p>
    <p class="note">Instantiates: %s</p>
  </div></div>""" % (name, m['file'].split('/')[-1], p[0], p[1], inst))
    desc_px = (pg.TITLE_PX + pg.BAND_PX + pg.para_px(p[0]) + pg.para_px(p[1])
               + pg.para_px(inst, lh=19))

    # Parameters: as much as fits under the description, the rest on its own page
    thead, rows = params_rows(m)
    n_page = paged_table(desc, desc_px, 'Parameters', thead, rows, n_page)

    # Symbol: never split, so it opens a page and the pin table fills the rest
    sym = symbol(m)
    sym_html = """  <div class="band wide"><h2>%s &mdash; symbol</h2>
    <figure><div class="fig-center fig-sym">%s</div>
    <figcaption>%s</figcaption></figure>
  </div>""" % (name, sym, SYM_CAP)
    sym_px = pg.BAND_PX + pg.svg_px(sym, width_mm=158) + pg.caption_px(SYM_CAP)

    thead, rows = pins_rows(m)
    n_page = paged_table(sym_html, sym_px, '%s &mdash; pins' % name, thead, rows, n_page)

# --- shell + library ---
sh = MODS['soc_app_top']
libt = ['<table><thead><tr><th class="l">Module</th><th class="l">Origin</th>'
        '<th class="l">Role in this design</th></tr></thead><tbody>']
for n, org, role in LIB:
    libt.append('<tr><td class="mono">%s</td><td>%s</td><td>%s</td></tr>' % (n, org, esc(role)))
libt.append('</tbody></table>')

gcount = OrderedDict()
for pt in sh['ports']:
    gcount[pt['group']] = gcount.get(pt['group'], 0) + 1
page("""
  <div class="titles"><div>soc_app_top and library modules</div></div>
  <div class="rule"></div>

  <div class="band"><h2>Shell<small>soc_app_top.v</small></h2><div>
    <p>%s</p><p>%s</p>
    <p class="note">%d parameters, %d ports, all defined
    by the framework framework. The port table is omitted here for that reason; the register map
    below is the part this design defines.</p>
  </div></div>

  <div class="band wide"><h2>CSR register map</h2>%s</div>
""" % (PROSE['soc_app_top'][0], PROSE['soc_app_top'][1],
       len(sh['params']), len(sh['ports']), csr_tbl()), n_page)
n_page += 1

page("""
  <div class="band wide"><h2>Library modules</h2>%s</div>
""" % "\n".join(libt), n_page)
n_page += 1

# --- timing ---
# Placeholder captions. A caption says what the figure shows, what the reader
# should notice in it, and which capture it came from - the last part is not
# optional, because a waveform nobody can trace back to a run is decoration.
TIMING = [
 ('Read burst', 'read_path', wavefig.READ,
  'The master holds <span class="mono">araddr</span> while '
  '<span class="mono">arvalid</span> is asserted, waits out the fixed memory latency, then '
  'takes the burst back to back with <span class="mono">rready</span> already high. From '
  '<span class="mono">tb_read.vcd</span>; the idle cycles in the middle are elided.'),
 ('Write burst into one channel', 'axi_demux, axi_downsize', wavefig.WRITE,
  'The demux routes the address to one channel and W follows it. The beats go out, then '
  '<span class="mono">wlast</span>, and the response returns a few cycles later. From '
  '<span class="mono">tb_write.vcd</span>.'),
 ('Descriptor push', 'write_path', wavefig.DESC,
  'The host pushes one descriptor at a time and the engine takes the next only when the '
  'previous one has been copied. From <span class="mono">tb_write.vcd</span>.'),
 ('Descriptor accepted, data fetched', 'dma_engine', wavefig.CTRL,
  'A descriptor is accepted in one cycle, after which the engine issues its own read '
  'requests and data begins landing in the private RAM. Gaps in '
  '<span class="mono">rdd_ready</span> are the source pushing back. From '
  '<span class="mono">tb_dma.vcd</span>.'),
]


# pack as many waveforms per page as actually fit
blocks = []
for (title, owner, spec, cap) in TIMING:
    svg = wavefig.render(spec)
    html = """  <div class="band wide"><h2>%s<small>%s</small></h2>
    <figure><div class="fig-center fig-wave">%s</div>
    <figcaption>%s</figcaption></figure>
  </div>""" % (title, owner, svg, cap)
    plain = re.sub(r'<[^>]+>', '', cap)
    blocks.append((html, pg.BAND_PX + pg.svg_px(svg) + pg.caption_px(plain)))

for group in pg.pack(blocks, pg.body_px()):
    page("\n".join(group), n_page)
    n_page += 1

html = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        '<title>Example Design &mdash; module reference</title>\n'
        '<style>%s</style>\n</head>\n<body>\n%s\n</body>\n</html>\n'
        % (CSS, "\n\n".join(pages)))
open(OUT, 'w', encoding='utf-8').write(html)
print('%s: %d pages, %d bytes' % (OUT, len(pages), len(html)))
