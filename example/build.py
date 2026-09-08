#!/usr/bin/env python3
"""Assemble the datasheet from modules.json plus the prose kept here.

WORKED EXAMPLE. This is the real assembly script for a 29-page datasheet of
a packet replay engine. Copy it into your own project directory
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
DESIGN = 'hbm_run'
OUT = 'datasheet_manual.html' if not DESIGN else '%s_datasheet_manual.html' % DESIGN

MODS = {m['module']: m for m in json.load(open('modules.json'))}

PROSE = {
 'read_path': (
   "Streams the stored trace out of memory and onto the MAC. It owns all sixteen "
   "channels and reads them through RD_LANES masters, each statically owning "
   "MEM_CH / RD_LANES channels, so no arbitration is needed and two masters can "
   "never drive the same channel.",
   "A three-stage pipeline rebuilds each Ethernet frame from the 64-byte metadata "
   "records. Pacing reproduces the recorded timestamps and gates only the final "
   "stage, so prefetch continues while the engine waits to transmit. Every "
   "runed record is copied to a capture buffer the host can read back."),
 'write_path': (
   "The CSR face of the write path. It holds the control and status registers, "
   "accepts placement descriptors from the host, and hands the actual transfer to "
   "dma_engine.",
   "Two modes share the same registers. Legacy mode issues one copy descriptor on "
   "go, reproducing the original single-shot behaviour byte for byte. Descriptor "
   "mode lets the host push a queue of segments first, each with its own address "
   "and stride, and then start them as one run."),
 'dma_engine': (
   "A self-contained engine that moves host memory into memory. It takes a copy "
   "descriptor of {host address, memory address, length, tag} and returns a status "
   "pulse; the data never passes through the application datapath.",
   "Inside, a 32-slot ring scheduler keeps several batches in flight so PCIe "
   "latency is hidden, a private psdpram stages the data, and axi_wr_master drives "
   "one wide AXI write master that is then split across the sixteen memory ports."),
 'axi_demux': (
   "Routes one wide AXI write master to CH channel-local masters by slicing the "
   "channel number straight out of the address. There is no address decode table: "
   "awaddr[CH_OFFSET +: CH_BITS] is the channel, and the bits either side are the "
   "local address.",
   "W follows AW through a small FIFO so write data cannot overtake its address, "
   "and B responses return round-robin with the ID passed through untouched."),
 'axi_downsize': (
   "Halves the width of an AXI write channel, converting AW length and size "
   "together and splitting each wide beat into RATIO narrow ones. B passes "
   "through.",
   "Written rather than taken from the library because the library's adapter "
   "computes its expansion inside a procedural branch; when the ratio makes it "
   "zero-copy, VCS rejects it outright while Vivado tolerates it. At RATIO = 1 "
   "this module degenerates to wires."),
 'soc_app_top': (
   "The framework application block: the shell the whole design lives in. Its port "
   "list is defined by the framework, which is why it is so large; only the CSR "
   "slave, the memory masters and the TX stream matter here.",
   "It instantiates the read and write paths, decodes the CSR register map, and "
   "puts a register slice on every one of the sixteen memory ports. Those slices are "
   "not cosmetic: without them the path from the memory controller to the write "
   "engine misses timing by 0.65 ns."),
}

LIB = [
 ('axi_wr_master', 'framework', 'Drives one AXI write master from segmented RAM. '
  'Requires RAM width = 2 x AXI width, which is what fixes the internal bus at 512 bits.'),
 ('stage_ram', 'framework', 'Segmented pseudo dual-port RAM used as the private staging '
  'buffer inside dma_engine.'),
 ('axis_fifo', 'verilog-axis', 'Per-lane record FIFO in the read path. With KEEP_ENABLE, '
  'DEPTH is counted in bytes, not words.'),
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
CSR = [
 ('0x00', 'host_meta_base_lo', 'R/W', 'Host physical address of the trace, bits [31:0]'),
 ('0x04', 'host_meta_base_hi', 'R/W', 'Host physical address, bits [63:32]'),
 ('0x08', 'batch_total', 'R/W', 'Number of packets to transfer'),
 ('0x0C', 'wr_ctrl', 'W', 'bit[0] wr_go, self-clearing; bit[1] desc_mode, held'),
 ('0x10', 'wr_status', 'R', 'bit[0] wr_busy; bit[1] wr_done, cleared on read'),
 ('0x14', 'rd_ctrl', 'W', 'bit[0] run_go, self-clearing; bit[1] max_rate, held'),
 ('0x18', 'rd_status', 'R', 'bit[0] run_busy; bit[1] run_done, cleared on read; '
                            'bit[2] placement_unsupported'),
 ('0x1C', 'debug_state', 'R', 'dbg_stall[5:0]: active, ring credit, NIC desc, PCIe fill, '
                              'op table full, engine busy'),
 ('0x20', 'cap_count', 'R', 'Records captured this run, at most CAP_DEPTH'),
 ('0x24', 'cap_word_addr', 'R/W', 'Readback word index: record = addr &gt;&gt; 4'),
 ('0x28', 'cap_rdata', 'R', 'The word at cap_word_addr, registered'),
 ('0x30', 'desc_dma_addr_lo', 'R/W', 'Descriptor: host source address, bits [31:0]'),
 ('0x34', 'desc_dma_addr_hi', 'R/W', 'Descriptor: host source address, bits [63:32]'),
 ('0x38', 'desc_hbm_addr', 'R/W', 'Descriptor: flat memory address of the first batch'),
 ('0x3C', 'desc_len', 'R/W', 'Descriptor: bytes covered, rounded up to whole batches'),
 ('0x40', 'desc_ctrl', 'W', 'bits[4:0] stride_log2; bit[8] push, a pulse; bit[9] clear, a pulse'),
 ('0x44', 'desc_status', 'R', 'bit[0] full; bit[1] empty; bits[23:16] queue level; '
                              'bits[31:24] descriptors completed this run'),
 ('0x48', 'rd_placement', 'R/W', 'bits[4:0] read-side stride_log2, resets to 9; '
                                 'on read bit[5] is placement_unsupported'),
 ('0x4C', 'run_cycles', 'R', 'Measured run length in 250 MHz cycles'),
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
    CHAN = re.compile(r'^(.*_(?:aw|ar|w|r|b))[a-z]+$')

    def stem(name):
        m = CHAN.match(name)
        if m:
            return m.group(1), True
        return name.rsplit('_', 1)[0], False

    out, i = [], 0
    while i < len(ports):
        p = ports[i]
        st, is_chan = stem(p['name'])
        run, j = [p], i + 1
        while j < len(ports) and ports[j]['dir'] == p['dir'] and stem(ports[j]['name'])[0] == st:
            run.append(ports[j]); j += 1
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


def symbol(mod):
    vals = resolve_params(mod)
    live = [p for p in mod['ports'] if p['name'] not in ('clk', 'rst')]
    ins = bundle([p for p in live if p['dir'] == 'input'])
    outs = bundle([p for p in live if p['dir'] == 'output'])
    # a symbol taller than a page helps nobody; step up to interface granularity
    if max(len(ins), len(outs)) > 13:
        ins = by_group([p for p in live if p['dir'] == 'input'])
        outs = by_group([p for p in live if p['dir'] == 'output'])
    clks = [p['name'] for p in mod['ports'] if p['name'] in ('clk', 'rst')]
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
    box(20, 54, 308, 280, 'write_path', 'CSR registers, placement descriptors',
        True, 15, 11.5)
    box(34, 102, 280, 220, 'dma_engine', 'host memory to memory, ring scheduler', True, 14, 11)
    kids = [('stage_ram', 'staging RAM', False),
            ('axi_wr_master', 'AXI write master', False),
            ('axi_demux', 'one master to 16 channels', True),
            ('axi_downsize', '512 to 256 bit, x16', True)]
    for i, (n, note, own) in enumerate(kids):
        box(48, 148 + i * 42, 252, 36, n, note, own, 12.5, 10)

    # ---- read path -----------------------------------------------------
    box(342, 54, 196, 152, 'read_path', 'memory to the MAC', True, 15, 11.5)
    box(356, 108, 168, 36, 'axis_fifo', 'record FIFO, x2', False, 12.5, 10)
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
    o.append('<text x="154" y="376" font-size="13">host memory in, over PCIe</text>')
    o.append('<line x1="440" y1="354" x2="440" y2="380" stroke="#000" stroke-width="1.5" '
             'marker-end="url(#hh)"/>')
    o.append('<text x="454" y="376" font-size="13">frames out, to the 100G MAC</text>')

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
    <div>Example FPGA &middot; external memory &middot; 250 MHz single clock domain</div>
  </div>
  <div class="rule"></div>

  <div class="band"><h2>Overview</h2><div>
    <p>The engine stores a recorded packet trace in external memory on the card and
    runs it onto a 100 Gbps MAC, either preserving the captured inter-packet timing or
    running as fast as the wire allows. The host is not in the transmit path.</p>
    <p>Everything runs in one 250 MHz domain, so there is no clock crossing anywhere in the
    design. This reference covers each RTL module in turn: what it does, its parameters, its
    symbol, and every port. Parameters and ports are read from the sources, not transcribed.</p>
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
    from CSR. The same sixteen memory channels appear once, between the write path above and the
    read path below.</figcaption></figure>
  </div>
""" % blockfig.render(), 3)

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
    head_px = pg.BAND_PX + pg.THEAD_PX
    parts = pg.chunk(rows, pg.body_px(head_px),
                     first=pg.body_px(desc_px + head_px))
    for k, part in enumerate(parts):
        title = 'Parameters' if k == 0 else 'Parameters (cont.)'
        band = '  <div class="band wide"><h2>%s</h2>%s</div>' % (title, wrap_rows(thead, part))
        page((desc + "\n\n" + band) if k == 0 else band, n_page)
        n_page += 1

    # Symbol: never split, so it opens a page and the pin table fills the rest
    sym = symbol(m)
    sym_html = """  <div class="band wide"><h2>%s &mdash; symbol</h2>
    <figure><div class="fig-center fig-sym">%s</div>
    <figcaption>%s</figcaption></figure>
  </div>""" % (name, sym, SYM_CAP)
    sym_px = pg.BAND_PX + pg.svg_px(sym, width_mm=158) + pg.caption_px(SYM_CAP)

    thead, rows = pins_rows(m)
    parts = pg.chunk(rows, pg.body_px(head_px),
                     first=pg.body_px(sym_px + head_px))
    for k, part in enumerate(parts):
        title = '%s &mdash; pins' % name
        if len(parts) > 1:
            title += ' (%d of %d)' % (k + 1, len(parts))
        band = '  <div class="band wide"><h2>%s</h2>%s</div>' % (title, wrap_rows(thead, part))
        page((sym_html + "\n\n" + band) if k == 0 else band, n_page)
        n_page += 1

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
TIMING = [
 ('Read burst', 'read_path', wavefig.READ,
  'One read master holds <span class="mono">araddr</span> while '
  '<span class="mono">arvalid</span> is asserted, waits out the fixed memory latency, then takes '
  'sixteen beats back to back with <span class="mono">rready</span> already high. From '
  '<span class="mono">tb_read_latency.vcd</span>; the twenty-six idle cycles are elided.'),
 ('Write burst into one channel', 'axi_demux, axi_downsize', wavefig.WRITE,
  'The demux routes the address to the channel named by <span class="mono">awaddr</span>, and W '
  'follows it. Sixteen beats then <span class="mono">wlast</span>, and the response comes back a '
  'few cycles later. From <span class="mono">tb_dma_engine.vcd</span>, channel 0.'),
 ('Placement descriptors', 'write_path', wavefig.DESC,
  'The host pushes its placement plan one segment at a time. Each descriptor carries the memory '
  'address the segment starts at and the stride between its 512-byte batches; the engine takes '
  'the next one only when the previous segment has been copied. From '
  '<span class="mono">tb_dma_engine.vcd</span>, the per-channel placement run, where stride '
  '13 keeps each segment inside one channel.'),
 ('Copy descriptor and host fetch', 'dma_engine', wavefig.CTRL,
  'A copy descriptor is accepted in one cycle, after which the engine issues read descriptors to '
  'the NIC and completions begin landing in the private RAM. '
  '<span class="mono">rdd_ready</span> gaps are the NIC pushing back. From '
  '<span class="mono">tb_dma_engine.vcd</span>.'),
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
