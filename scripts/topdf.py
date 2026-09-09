#!/usr/bin/env python3
"""Turn the built datasheet HTML into an A4 PDF.

Run with the default python3 (3.6.8): Pillow lives there, not in 3.11.

Firefox ESR has no --print-to-pdf, so each .page is rendered on its own at a
CSS transform scale and the pages are stitched into a PDF. Scaling with a
transform rather than a zoom keeps the layout byte-identical to what was
verified on screen; only the rasteriser runs at a higher resolution.

`--png` writes individual pages as PNGs instead, for the visual check. Each
page is rendered on its own with its margins removed, so there is nothing to
crop and no page-pitch arithmetic to get wrong.

Before converting, every page is measured against A4. `min-height:297mm` on
.page is a *minimum*: a page with too much content silently grows taller and
looks perfectly fine stacked on screen, but will not fit a sheet of paper.
Converting such a page would crop it, so the run stops instead.

    python3 topdf.py <design>_datasheet_manual.html [--scale 3] [--out x.pdf]
    python3 topdf.py <design>_datasheet_manual.html --check    # measure only
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

CSS_PX_MM = 96 / 25.4                      # 1 mm in CSS pixels
A4_W, A4_H = 210 * CSS_PX_MM, 297 * CSS_PX_MM
PROBE_H = 6000                             # tall enough for any single page


def split_pages(html):
    """(prelude, [page html, ...]) — prelude carries the <style> block."""
    open_tag = re.compile(r'<div class="page"[^>]*>')
    m = open_tag.search(html)
    if not m:
        sys.exit('no <div class="page"> found; is this a built datasheet?')
    prelude, pages, pos = html[:m.start()], [], m.start()

    div = re.compile(r'<div\b|</div>')
    while True:
        m = open_tag.search(html, pos)
        if not m:
            return prelude, pages
        depth, i = 0, m.start()
        for t in div.finditer(html, m.start()):
            depth += 1 if t.group() == '<div' else -1
            if depth == 0:
                i = t.end()
                break
        else:
            sys.exit('unbalanced <div> around page %d' % (len(pages) + 1))
        pages.append(html[m.start():i])
        pos = i


def firefox(src, png, w, h):
    subprocess.run(['firefox', '--headless',
                    # --screenshot silently writes nothing for a relative path
                    '--screenshot', os.path.abspath(png),
                    '--window-size=%d,%d' % (w, h), src],
                   env=dict(os.environ, MOZ_HEADLESS='1'), timeout=300,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(png):
        sys.exit('firefox produced no screenshot: ' + png)


def write_tmp(work, doc):
    path = os.path.join(work, 'page.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return 'file://' + path


def measure(page_html, prelude, work):
    """Natural height of one page in CSS px.

    The page keeps its own min-height and the body keeps its grey background,
    so the white rectangle in the screenshot is exactly the page box.
    """
    src = write_tmp(work, prelude +
                    '<style>html,body{margin:0;padding:0}'
                    '.page{margin:0;box-shadow:none}</style>' + page_html)
    png = os.path.join(work, 'probe.png')
    if os.path.exists(png):
        os.remove(png)
    firefox(src, png, round(A4_W), PROBE_H)

    px = Image.open(png).convert('RGB').load()
    x = 4                                   # inside the page, outside its padding
    h = 0
    for y in range(PROBE_H):
        if px[x, y][0] > 245:
            h = y + 1
        elif h:
            break                           # first grey row after the page ends
    return h


def shoot(page_html, prelude, scale, out_png, work):
    """Render one page to PNG at `scale` times its CSS size."""
    src = write_tmp(work, prelude +
                    '<style>html,body{margin:0;padding:0;background:#fff}'
                    '.zoom{transform:scale(%g);transform-origin:top left}'
                    '.page{margin:0;box-shadow:none}</style>'
                    '<div class="zoom">%s</div>' % (scale, page_html))
    firefox(src, out_png, round(A4_W * scale), round(A4_H * scale))


def to_a4(png, scale):
    """Pad to exactly A4 at this scale so every sheet is the same size."""
    w, h = round(A4_W * scale), round(A4_H * scale)
    im = Image.open(png).convert('RGB')
    if im.size == (w, h):
        return im
    sheet = Image.new('RGB', (w, h), '#ffffff')
    sheet.paste(im.crop((0, 0, min(w, im.width), min(h, im.height))), (0, 0))
    return sheet


def page_numbers(spec, total):
    """Parse "1,3,7-9" into page numbers, or all of them for "all"/empty."""
    if not spec or spec == 'all':
        return list(range(1, total + 1))
    out = []
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    bad = [n for n in out if not 1 <= n <= total]
    if bad:
        sys.exit('no such page: %s (the document has %d)'
                 % (', '.join(map(str, bad)), total))
    return sorted(set(out))



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html')
    ap.add_argument('--scale', type=float, default=3.0,
                    help='3 gives 288 dpi; 2 gives 192 dpi and a smaller file')
    ap.add_argument('--out', help='default: the HTML name with a .pdf suffix')
    ap.add_argument('--check', action='store_true', help='measure the pages and stop')
    ap.add_argument('--force', action='store_true',
                    help='convert even if a page overflows; the overflow is cropped')
    ap.add_argument('--png', nargs='?', const='all', metavar='PAGES',
                    help='write PNGs instead of a PDF: "all", or "1,3,7-9". '
                         'Each page is rendered on its own, so nothing has to be cropped')
    a = ap.parse_args()

    out = a.out or re.sub(r'\.html?$', '', a.html) + '.pdf'
    with open(a.html, encoding='utf-8') as f:
        prelude, pages = split_pages(f.read())
    print('%s: %d pages' % (os.path.basename(a.html), len(pages)))

    work = tempfile.mkdtemp(prefix='topdf_')
    try:
        limit, over = round(A4_H), []
        for n, page in enumerate(pages, 1):
            h = measure(page, prelude, work)
            if h > limit + 2:
                over.append((n, h))
                print('  page %2d  %4d px  OVER A4 by %d px (%.1f mm)'
                      % (n, h, h - limit, (h - limit) / CSS_PX_MM))
            elif a.check:
                print('  page %2d  %4d px  fits' % (n, h))
        if over:
            print('\n%d of %d pages do not fit A4 (%d px).' % (len(over), len(pages), limit))
            print('min-height on .page is a minimum, so these look fine stacked on screen '
                  'but will not print. Split them in build.py.')
            if not (a.force or a.check):
                sys.exit(1)
        elif not a.check:
            print('  all %d pages fit A4' % len(pages))
        if a.check:
            return

        if a.png:
            stem = re.sub(r'\.html?$', '', a.html)
            for n in page_numbers(a.png, len(pages)):
                png = '%s_page%02d.png' % (stem, n)
                shoot(pages[n - 1], prelude, a.scale, png, work)
                print('  %s' % png)
            return

        print('rendering at %gx (%d dpi)' % (a.scale, round(96 * a.scale)))
        sheets = []
        for n, page in enumerate(pages, 1):
            png = os.path.join(work, 'p%02d.png' % n)
            shoot(page, prelude, a.scale, png, work)
            sheets.append(to_a4(png, a.scale))
            sys.stdout.write('\r  page %d/%d' % (n, len(pages)))
            sys.stdout.flush()
        print()
        sheets[0].save(out, 'PDF', save_all=True, append_images=sheets[1:],
                       resolution=96 * a.scale)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('%s: %d pages, %.1f MB' % (out, len(pages), os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
