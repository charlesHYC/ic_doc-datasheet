#!/usr/bin/env python3
"""Timing figures, drawn from the VCD captures in sim/wave_extract/.

One renderer, three specs. A spec lists the visible cycle segments (anything
between them is elided with a break), the signals, the phase bands across the
top and the markers underneath.

Buses follow the datasheet convention rather than being drawn as boxes: two
rails with an X crossover wherever the value changes, a chain of crossovers
where the value is a don't care, and no vertical cap where the waveform meets
the edge of the figure - a bus does not begin or end there, the drawing does.
"""
CW, LBL, GAP, ROW = 40, 94, 34, 54   # LBL must clear the longest signal name
HI, LO = 0, 28
TOP, FOOT = 60, 46
XW, CELL = 5, 14        # crossover half-width; don't-care repeat pitch
SLEW = 1.5              # clock rise and fall; a hint of it, no more - at this
                        # cell width a real slew reads as a triangle wave
UNIT_MM = 0.252         # mm per viewBox unit, the same in every figure: that is
                        # what makes one cycle the same width on any two pages
COL_MM = 178            # the content column a figure has to fit inside


def _mk(segments):
    """Return (x(cycle), segment pixel bounds, total width)."""
    starts, xs = [], LBL
    for seg in segments:
        starts.append((seg[0], seg[-1], xs))
        xs += len(seg) * CW + GAP
    W = xs - GAP + 34

    def x(c):
        for lo, hi, x0 in starts:
            if lo <= c <= hi + 1:
                return x0 + (c - lo) * CW
        return starts[-1][2] + (c - starts[-1][0]) * CW
    return x, [(s[2], s[2] + (s[1] - s[0] + 1) * CW) for s in starts], W


def _fig_mm(W, spec):
    """Figure width in mm at the shared unit size, or a refusal.

    Clamping a too-wide figure to the column is the tempting fix and the wrong
    one: the figure survives, but at a smaller unit size than every other
    figure, so the same cycle is drawn two different widths in one document and
    nothing says why. Refuse, and name what to do about it.
    """
    mm = W * UNIT_MM
    if mm <= COL_MM:
        return round(mm)
    if spec.get('shrink'):
        return COL_MM
    drop = int(-(-(mm - COL_MM) // (CW * UNIT_MM)))
    raise ValueError(
        "waveform %r is %.0f mm wide at the shared unit size and the column is "
        "%d mm. Show %d fewer cycle%s, break the segments up further, or lower "
        "CW for every figure. Setting 'shrink': True in the spec accepts a "
        "smaller unit size for this one instead, at the cost of it no longer "
        "matching the others."
        % (spec.get('id', '?'), mm, COL_MM, drop, '' if drop == 1 else 's'))



def _rails(x0, x1, top, bot):
    """The two horizontal edges of a bus, with no cap at either end."""
    if x1 - x0 < 0.5:
        return []
    return ['<path d="M %.1f %.1f L %.1f %.1f M %.1f %.1f L %.1f %.1f" fill="none" '
            'stroke="#000" stroke-width="1.15"/>' % (x0, top, x1, top, x0, bot, x1, bot)]


def _cross(xc, top, bot):
    """One value changing to the next: the rails swap over."""
    return ['<path d="M %.1f %.1f L %.1f %.1f M %.1f %.1f L %.1f %.1f" fill="none" '
            'stroke="#000" stroke-width="1.15"/>'
            % (xc - XW, top, xc + XW, bot, xc - XW, bot, xc + XW, top)]


def _dontcare(x0, x1, top, bot):
    """A value that is not being relied on: rails filled with crossovers."""
    if x1 - x0 < 1:
        return []
    o = _rails(x0, x1, top, bot)
    n = max(1, int(round((x1 - x0) / CELL)))
    step = (x1 - x0) / n
    for k in range(n):
        a, b = x0 + k * step, x0 + (k + 1) * step
        o.append('<path d="M %.1f %.1f L %.1f %.1f M %.1f %.1f L %.1f %.1f" fill="none" '
                 'stroke="#000" stroke-width="1.0"/>' % (a, top, b, bot, a, bot, b, top))
    return o


def _bus(a, b, wins, top, bot):
    """One visible segment of a bus. `wins` is (x0, x1, text) in pixels.

    A crossover is drawn only where a value actually changes; where a window
    runs into the edge of the segment the rails simply continue, because the
    bus does not stop there.
    """
    o, cur = [], a
    for (wa, wb, txt) in sorted(wins):
        wa, wb = max(wa, a), min(wb, b)
        if wb <= wa:
            continue
        lcap, rcap = wa > a + 0.5, wb < b - 0.5
        if wa - (XW if lcap else 0) > cur:
            o += _dontcare(cur, wa - (XW if lcap else 0), top, bot)
        if lcap:
            o += _cross(wa, top, bot)
        o += _rails(wa + (XW if lcap else 0), wb - (XW if rcap else 0), top, bot)
        if rcap:
            o += _cross(wb, top, bot)
        if txt:
            # a white halo, so a value sitting on a guide line stays readable
            o.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="12" '
                     'stroke="#fff" stroke-width="3.2" paint-order="stroke">%s</text>'
                     % ((wa + wb) / 2, top + 20, txt))
        cur = wb + (XW if rcap else 0)
    if cur < b:
        o += _dontcare(cur, b, top, bot)
    return o



def render(spec):
    segs = spec['segments']
    x, bounds, W = _mk(segs)
    sig = spec['signals']
    H = TOP + len(sig) * ROW + FOOT

    def y(i):
        return TOP + i * ROW

    mm = _fig_mm(W, spec)
    o = ['<svg viewBox="0 0 %d %d" width="%dmm" role="img" aria-label="%s">'
         % (W, H, mm, spec['alt']),
         '<g font-family="Times New Roman, Times, serif" font-size="12">']

    for i, s in enumerate(sig):
        o.append('<text x="%d" y="%d" text-anchor="end" font-size="13">%s</text>'
                 % (LBL - 11, y(i) + LO - 8, s['name']))

    for (x0, x1, label, shade) in spec.get('bands', []):
        a, b = x(x0), x(x1)
        o.append('<rect x="%.0f" y="18" width="%.0f" height="21" fill="%s" stroke="#000" '
                 'stroke-width="0.9"/>' % (a, b - a, '#e6e4e0' if shade else '#fff'))
        o.append('<text x="%.0f" y="33" text-anchor="middle" font-size="12">%s</text>'
                 % ((a + b) / 2, label))
    for gx in spec.get('guides', []):
        o.append('<line x1="%.0f" y1="39" x2="%.0f" y2="%d" stroke="#000" stroke-width="0.7" '
                 'stroke-dasharray="3 3"/>' % (x(gx), x(gx), y(len(sig) - 1) + LO + 10))

    # breaks between segments
    for k in range(len(bounds) - 1):
        gx = bounds[k][1]
        o.append('<rect x="%.0f" y="42" width="%d" height="%d" fill="#fff" stroke="none"/>'
                 % (gx, GAP, y(len(sig) - 1) + LO + 4 - 42))
        for i in range(len(sig)):
            for dx in (8, 18):
                o.append('<path d="M %.0f %d l 10 -19" stroke="#000" stroke-width="1.1" '
                         'fill="none"/>' % (gx + dx, y(i) + LO + 7))

    for i, s in enumerate(sig):
        k = s['kind']
        if k == 'clk':
            d = []
            for seg in segs:
                for c in seg:
                    a, m, e = x(c), x(c) + CW / 2, x(c) + CW
                    # no trailing rise: the next cycle draws its own leading one,
                    # and the last cycle of a segment must not overhang the edge
                    d.append("M %.1f %d L %.1f %d L %.1f %d L %.1f %d L %.1f %d"
                             % (max(a - SLEW, x(seg[0])), y(i) + LO, a + SLEW, y(i) + HI,
                                m - SLEW, y(i) + HI, m + SLEW, y(i) + LO,
                                e, y(i) + LO))
            o.append('<path d="%s" fill="none" stroke="#000" stroke-width="1.3"/>' % " ".join(d))
        elif k == 'level':
            for group in s['spans']:
                d, prev = [], None
                for (c0, c1, v) in group:
                    yy = y(i) + (HI if v else LO)
                    if prev is not None and prev != v:
                        d.append("M %.1f %d L %.1f %d" % (x(c0), y(i) + HI, x(c0), y(i) + LO))
                    d.append("M %.1f %d L %.1f %d" % (x(c0), yy, x(c1), yy))
                    prev = v
                o.append('<path d="%s" fill="none" stroke="#000" stroke-width="1.3"/>'
                         % " ".join(d))
        elif k == 'bus':
            top, bot = y(i) + HI, y(i) + LO
            for (a, b) in bounds:
                o += _bus(a, b, [(x(c0), x(c1), t) for (c0, c1, t) in s['windows']],
                          top, bot)
        elif k == 'beats':
            c0, c1, lab = s['from'], s['to'], s.get('label', 'D%d')
            top, bot = y(i) + HI, y(i) + LO
            wins = [(x(c), x(c + 1), lab % n) for n, c in enumerate(range(c0, c1))]
            for (a, b) in bounds:
                o += _bus(a, b, wins, top, bot)

    yb = y(len(sig) - 1) + LO + 4
    for (c, txt) in spec.get('markers', []):
        o.append('<path d="M %.0f %d l -5 9 l 10 0 Z" fill="#000"/>' % (x(c), yb + 6))
        o.append('<text x="%.0f" y="%d" text-anchor="middle" font-size="12">%s</text>'
                 % (x(c), yb + 30, txt))
    o += ['</g>', '</svg>']
    return "\n".join(o)


# ---------------------------------------------------------------- specs
READ = {
 'id': 'r', 'alt': 'Read burst: address, elided memory latency, then the data beats',
 'segments': [list(range(0, 5)), list(range(26, 32))],
 'bands': [(0, 2, 'address', False), (2, 26, 'memory read latency', True),
           (26, 32, 'data burst, 16 beats', False)],
 'guides': [2, 26], 'markers': [(2, 'AR accepted'), (26, 'first beat')],
 'signals': [
   {'name': 'clk', 'kind': 'clk'},
   {'name': 'arvalid', 'kind': 'level', 'spans': [[(0, 1, 0), (1, 2, 1), (2, 5, 0)],
                                                  [(26, 32, 0)]]},
   {'name': 'arready', 'kind': 'level', 'spans': [[(0, 2, 1), (2, 5, 0)],
                                                  [(26, 31, 0), (31, 32, 1)]]},
   {'name': 'araddr', 'kind': 'bus', 'windows': [(1, 4, '0x10000')]},
   {'name': 'rvalid', 'kind': 'level', 'spans': [[(0, 5, 0)], [(26, 32, 1)]]},
   {'name': 'rready', 'kind': 'level', 'spans': [[(0, 2, 0), (2, 5, 1)], [(26, 32, 1)]]},
   {'name': 'rdata', 'kind': 'beats', 'from': 26, 'to': 32},
 ]}

WRITE = {
 'id': 'w', 'alt': 'Write burst into one memory channel, then the response',
 'segments': [list(range(0, 6)), list(range(17, 24))],
 'bands': [(0, 3, 'address', False), (3, 20, 'data beats', False),
           (20, 24, 'response', True)],
 'guides': [3, 20], 'markers': [(3, 'first beat'), (20, 'wlast')],
 'signals': [
   {'name': 'clk', 'kind': 'clk'},
   {'name': 'awvalid', 'kind': 'level', 'spans': [[(0, 1, 0), (1, 2, 1), (2, 6, 0)],
                                                  [(17, 24, 0)]]},
   {'name': 'awready', 'kind': 'level', 'spans': [[(0, 2, 1), (2, 6, 0)], [(17, 24, 0)]]},
   {'name': 'awaddr', 'kind': 'bus', 'windows': [(1, 3, '0x0000')]},
   {'name': 'wvalid', 'kind': 'level', 'spans': [[(0, 3, 0), (3, 6, 1)],
                                                 [(17, 20, 1), (20, 24, 0)]]},
   {'name': 'wready', 'kind': 'level', 'spans': [[(0, 2, 0), (2, 6, 1)],
                                                 [(17, 20, 1), (20, 24, 0)]]},
   {'name': 'wlast', 'kind': 'level', 'spans': [[(0, 6, 0)],
                                                [(17, 19, 0), (19, 20, 1), (20, 24, 0)]]},
   {'name': 'bvalid', 'kind': 'level', 'spans': [[(0, 6, 0)],
                                                 [(17, 22, 0), (22, 23, 1), (23, 24, 0)]]},
 ]}

CTRL = {
 'id': 'c', 'alt': 'Copy descriptor in, NIC read descriptor out, completions into RAM',
 'segments': [list(range(0, 12))],
 'bands': [(0, 3, 'descriptor accepted', False), (3, 12, 'fetch from host', True)],
 'guides': [3], 'markers': [(1, 'copy desc'), (3, 'first read desc')],
 'signals': [
   {'name': 'clk', 'kind': 'clk'},
   {'name': 'cd_valid', 'kind': 'level', 'spans': [[(0, 1, 0), (1, 2, 1), (2, 12, 0)]]},
   {'name': 'cd_ready', 'kind': 'level', 'spans': [[(0, 2, 1), (2, 12, 0)]]},
   {'name': 'rdd_valid', 'kind': 'level', 'spans': [[(0, 3, 0), (3, 12, 1)]]},
   {'name': 'rdd_ready', 'kind': 'level', 'spans': [[(0, 4, 1), (4, 5, 0), (5, 6, 1),
                                                     (6, 7, 0), (7, 9, 1), (9, 10, 0),
                                                     (10, 12, 1)]]},
   {'name': 'ram_wr_valid', 'kind': 'level', 'spans': [[(0, 6, 0), (6, 12, 1)]]},
 ]}


DESC = {
 'id': 'd', 'alt': 'Descriptors handed over one segment at a time',
 'segments': [list(range(0, 6)), list(range(260, 267))],
 'bands': [(0, 2, 'descriptor 0', False), (2, 260, 'segment copied', True),
           (260, 267, 'descriptor 1', False)],
 'guides': [2, 260], 'markers': [(2, 'accepted'), (262, 'accepted')],
 'signals': [
   {'name': 'clk', 'kind': 'clk'},
   {'name': 'desc_valid', 'kind': 'level',
    'spans': [[(0, 1, 0), (1, 2, 1), (2, 6, 0)],
              [(260, 261, 0), (261, 262, 1), (262, 267, 0)]]},
   {'name': 'desc_ready', 'kind': 'level',
    'spans': [[(0, 2, 1), (2, 6, 0)], [(260, 262, 1), (262, 267, 0)]]},
   {'name': 'mem_addr', 'kind': 'bus', 'windows': [(1, 3, '0x0000'), (261, 264, '0x0200')]},
   {'name': 'seg_stride', 'kind': 'bus', 'windows': [(1, 3, '0x200'), (261, 264, '0x200')]},
   {'name': 'wr_busy', 'kind': 'level', 'spans': [[(0, 1, 0), (1, 6, 1)], [(260, 267, 1)]]},
 ]}


def build():
    return render(READ)


if __name__ == '__main__':
    for name, spec in (('read', READ), ('write', WRITE), ('ctrl', CTRL), ('desc', DESC)):
        svg = render(spec)
        open('wave_%s.svg' % name, 'w').write(svg)
        print('wave_%s.svg' % name, svg.split('viewBox="')[1].split('"')[0])
