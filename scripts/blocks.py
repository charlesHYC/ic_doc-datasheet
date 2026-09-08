#!/usr/bin/env python3
"""Connectivity diagram: how the modules are wired to each other.

Distinct from the hierarchy figure, which shows containment. This one follows
the data: host memory down through the write path into memory, back up through the
read path and out to the MAC, with the CSR control bus off to the side.

Layout runs in two passes: place the blocks, then draw the group frames around
whatever they turned out to occupy, so a frame can never miss its contents.
"""
W = 640
BX, BW = 176, 250
CX, CW_ = 0, 108
GAP_IN, GAP_OUT = 16, 26     # arrow length inside a group, and between groups


class Layout:
    def __init__(self):
        self.o, self.y = [], 10

    # ---- primitives ----
    def rect(self, x, y, w, h, fill='#fff', sw='1.1', dash=False):
        self.o.append('<rect x="%g" y="%g" width="%g" height="%g" fill="%s" stroke="#000" '
                      'stroke-width="%s"%s rx="2"/>'
                      % (x, y, w, h, fill, sw, ' stroke-dasharray="5 3"' if dash else ''))

    def txt(self, x, y, s, size=13, anchor='middle', weight='normal', fill='#000'):
        self.o.append('<text x="%g" y="%g" text-anchor="%s" font-size="%g" font-weight="%s" '
                      'fill="%s">%s</text>' % (x, y, anchor, size, weight, fill, s))

    # ---- flow ----
    def block(self, name, sub='', fill='#fff', sw='1.1', h=40, inset=0):
        x, w = BX + inset, BW - 2 * inset
        self.rect(x, self.y, w, h, fill, sw)
        if sub:
            self.txt(x + w / 2, self.y + h / 2 - 2, name, 13.5, weight='bold')
            self.txt(x + w / 2, self.y + h / 2 + 14, sub, 11, fill='#3a3a3a')
        else:
            self.txt(x + w / 2, self.y + h / 2 + 5, name, 13.5, weight='bold')
        self.y += h

    def arrow(self, label='', length=GAP_OUT):
        cx = BX + BW / 2
        self.o.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#000" stroke-width="1.4" '
                      'marker-end="url(#a)"/>' % (cx, self.y, cx, self.y + length))
        if label:
            self.txt(BX + BW + 26, self.y + length / 2 + 4, label, 11,
                     anchor='start', fill='#3a3a3a')
        self.y += length

    def group(self, y0, y1, title, sub=''):
        """Frame drawn after the fact, so it always encloses its contents."""
        self.o.insert(0, '<rect x="%g" y="%g" width="%g" height="%g" fill="#eeece8" '
                         'stroke="#000" stroke-width="1.5" rx="3"/>'
                      % (BX - 16, y0, BW + 32, y1 - y0))
        self.txt(BX - 8, y0 + 17, title, 12.5, anchor='start', weight='bold')
        if sub:
            self.txt(BX - 8, y0 + 31, sub, 10.5, anchor='start', fill='#3a3a3a')


def render():
    L = Layout()

    L.block('host memory', '', '#f4f2ee', h=34)
    L.arrow('PCIe')

    # ---- write path ----------------------------------------------------
    g0 = L.y
    L.y += 36                                    # room for the group title
    L.block('stage_ram', 'private staging RAM', inset=8)
    L.arrow('completions', GAP_IN)
    L.block('axi_wr_master', 'one 512-bit AXI master', inset=8)
    L.arrow('512-bit', GAP_IN)
    L.block('axi_demux', 'awaddr[12:9] picks the channel', inset=8)
    L.arrow('16 x 512-bit', GAP_IN)
    L.block('axi_downsize', 'x16, 512 to 256 bit', inset=8)
    L.y += 12
    g1 = L.y
    L.group(g0, g1, 'dma_engine', 'ring scheduler, 32 slots in flight')

    L.arrow('16 x 256-bit')
    L.block('axi_reg_wr', 'x16, cuts the path to the memory controller', h=38)
    L.arrow()

    L.block('Memory, 16 channels', 'batch N lands in channel N mod 16', '#ddd9d2', '1.8')
    L.arrow()
    L.block('axi_reg_rd', 'x16', h=38)
    L.arrow('16 x 256-bit')

    # ---- read path -------------------------------------------------------
    g2 = L.y
    L.y += 30
    L.block('8 AXI read masters', 'two channels each, no arbitration', inset=8)
    L.arrow('', GAP_IN)
    L.block('axis_fifo x8', 'one 64-byte record per word', inset=8)
    L.arrow('', GAP_IN)
    L.block('Fetch / Pace / TX', 'three-stage pipeline', inset=8)
    L.y += 12
    g3 = L.y
    L.group(g2, g3, 'read_path')

    L.arrow('512-bit AXIS')
    L.block('100G MAC', '', '#f4f2ee', h=34)
    H = L.y + 12

    # ---- control column ---------------------------------------------------
    L.rect(CX, 108, CW_, 32)
    L.txt(CX + CW_ / 2, 128, 'CSR AXI-Lite', 12)
    L.rect(CX, 166, CW_, 48, '#eeece8', '1.3')
    L.txt(CX + CW_ / 2, 186, 'write', 11.5, weight='bold')
    L.txt(CX + CW_ / 2, 201, '_path_v2', 11.5, weight='bold')
    cx = CX + CW_ / 2
    L.o.append('<line x1="%g" y1="140" x2="%g" y2="166" stroke="#000" stroke-width="1.2" '
               'marker-end="url(#a)"/>' % (cx, cx))
    L.o.append('<line x1="%g" y1="190" x2="%g" y2="190" stroke="#000" stroke-width="1.2" '
               'marker-end="url(#a)"/>' % (CX + CW_, BX - 16))
    # the label sits above the arrow, centred on the span it describes
    mid = (CX + CW_ + BX - 16) / 2
    L.txt(mid, 173, 'copy', 10, fill='#3a3a3a')
    L.txt(mid, 184, 'descriptor', 10, fill='#3a3a3a')
    # CSR path down to the read path
    L.o.append('<path d="M %g 124 L %g 124 L %g %g L %g %g" fill="none" stroke="#000" '
               'stroke-width="1.2" stroke-dasharray="4 3" marker-end="url(#a)"/>'
               % (CX, CX - 6, CX - 6, g2 + 46, BX - 16, g2 + 46))
    L.txt(CX + 26, g2 + 40, 'status and control', 10, anchor='start', fill='#3a3a3a')

    body = ('<defs><marker id="a" markerWidth="9" markerHeight="8" refX="8" refY="4" '
            'orient="auto"><polygon points="0 0, 9 4, 0 8" fill="#000"/></marker></defs>'
            + "\n".join(L.o))
    return ('<svg viewBox="-14 0 %d %d" width="%dmm" role="img" '
            'aria-label="Block diagram: how the modules connect">'
            '<g font-family="Times New Roman, Times, serif">%s</g></svg>'
            % (W, H, min(174, round(W * 0.285)), body))


if __name__ == '__main__':
    svg = render()
    open('blocks.svg', 'w').write(svg)
    print('blocks.svg', svg.split('viewBox="')[1].split('"')[0])
