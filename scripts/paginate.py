"""Height estimates for packing datasheet content onto A4 pages.

`min-height:297mm` on .page is only a minimum, so a page with too much content
grows silently: it looks right stacked on screen and is wrong on paper. These
estimates let build.py split tables and figures before that happens; the real
check is still `topdf.py --check`, which measures the built document.

All figures are CSS pixels at the type scale in SKILL.md. They are deliberately
a little pessimistic - a page that comes out short is fine, one that overflows
is not.
"""
import math
import re

MM = 96 / 25.4

CONTENT_PX = round((297 - 15 - 12) * MM)   # A4 less the top and bottom margins
FOOTER_PX = 26                             # rule, padding, one 8.6pt line
TITLE_PX = 62                              # .titles + .rule on a module page
BAND_PX = 48                               # h2, its margin, band padding, border
CAPTION_PX = 24                            # one line of figcaption plus its margin

SAFETY_PX = 40                             # slack against estimate error

THEAD_PX = 25
ROW_PX = 28                                # a one-line table row
LINE_PX = 21                               # each additional wrapped line
GRP_PX = 36                                # a group sub-heading row

# Characters that fit on one line of the description column, by table.
CPL_PINS = 52
CPL_PARAMS = 50
CPL_BODY = 95                              # 11pt body across the full text column
CPL_CAP = 108                              # 9.4pt figcaption

PARA_LH = 22                               # one line of 11pt body
PARA_GAP = 9                               # space between paragraphs


def body_px(extra=0):
    """Height available for content on one page.

    Deliberately pessimistic: overshooting the estimate costs a page break in a
    slightly early place, undershooting silently pushes content off the sheet.
    """
    return CONTENT_PX - FOOTER_PX - SAFETY_PX - extra


def rows_px(text, cpl, base=ROW_PX):
    """Height of a table row whose description may wrap."""
    return base + LINE_PX * (max(1, math.ceil(len(text or '') / cpl)) - 1)


def svg_px(svg, width_mm=None):
    """Rendered height of an SVG, from its viewBox aspect and its width.

    Pass width_mm for a figure sized by CSS rather than by its own attribute -
    a symbol carries width="100%" and is capped by `.fig-sym svg{max-width}`,
    so its rendered width comes from the stylesheet, not the markup.
    """
    vb = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg)
    if not vb:
        return 0
    if width_mm is None:
        w = re.search(r'width="([\d.]+)mm"', svg)
        if not w:
            return 0
        width_mm = float(w.group(1))
    return width_mm * MM * float(vb.group(2)) / float(vb.group(1))


def chunk(items, budget, first=None):
    """Pack (html, px) items into lists that stay inside the budget.

    `first` overrides the budget of the opening chunk, for a page that also
    carries a title or a preceding band.
    """
    out, cur, used, cap = [], [], 0, first if first is not None else budget
    for html, px in items:
        if cur and used + px > cap:
            out.append(cur)
            cur, used, cap = [], 0, budget
        cur.append(html)
        used += px
    if cur:
        out.append(cur)
    return out


def pack(items, budget):
    """Greedily group whole blocks (html, px) onto pages."""
    return chunk(items, budget)


def para_px(text, cpl=CPL_BODY, lh=PARA_LH, gap=PARA_GAP):
    """Height of one paragraph of body text."""
    return lh * max(1, math.ceil(len(text or '') / cpl)) + gap


def caption_px(text):
    """Height of a figcaption, which wraps at a smaller size."""
    return 5 + 17 * max(1, math.ceil(len(text or '') / CPL_CAP))
