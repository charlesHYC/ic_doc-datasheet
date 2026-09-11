#!/usr/bin/env python3
"""Turn the built datasheet HTML into an A4 PDF.

Firefox ESR has no --print-to-pdf, so each .page is rendered on its own at a
CSS transform scale and the pages are stitched into a PDF. Scaling with a
transform rather than a zoom keeps the layout byte-identical to what was
verified on screen; only the rasteriser runs at a higher resolution.

Every render also measures its page. `min-height:297mm` on .page is a
*minimum*: a page with too much content silently grows taller and looks
perfectly fine stacked on screen, but will not fit a sheet of paper. The page
is drawn on the document's grey background in a window a little taller than
A4, so the white page box ends where the grey begins, and that row is its
height. One Firefox launch therefore both measures a page and draws it.

Each Firefox runs headless in a private, throw-away profile with --no-remote.
Without that, a browser the user already has open can lock the default profile
or take the request over, and the run fails with no screenshot and no reason.
Private profiles are also what lets several pages render at once (--jobs).

`--png` writes individual pages as PNGs instead, for the visual check. Each
page is rendered on its own with its margins removed, so there is nothing to
crop and no page-pitch arithmetic to get wrong.

    python3 topdf.py <design>_datasheet_manual.html [--scale 3] [--out x.pdf]
    python3 topdf.py <design>_datasheet_manual.html --check       # measure only
    python3 topdf.py <design>_datasheet_manual.html --png 3,7-9   # PNGs to look at
"""
import argparse
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

CSS_PX_MM = 96 / 25.4                      # 1 mm in CSS pixels
A4_W, A4_H = 210 * CSS_PX_MM, 297 * CSS_PX_MM
SLACK = 64                                 # grey shown below an A4 page, CSS px
SHOT_MAX = 32000                           # Firefox cannot capture much taller
WHITE = 245                                # page is white; the body is #eceae6


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


class Renderer:
    """A fixed set of Firefox slots, each with its own profile and scratch files.

    A slot is taken for the length of one render, so no two Firefox processes
    ever share a profile or overwrite each other's page and screenshot.
    """

    def __init__(self, work, slots):
        self.free = queue.Queue()
        for k in range(slots):
            d = os.path.join(work, 'slot%d' % k)
            os.makedirs(os.path.join(d, 'profile'))
            self.free.put(d)

    @staticmethod
    def _firefox(slot, doc, w, h):
        src = os.path.join(slot, 'page.html')
        png = os.path.join(slot, 'shot.png')     # absolute: a relative path writes nothing
        with open(src, 'w', encoding='utf-8') as f:
            f.write(doc)
        if os.path.exists(png):
            os.remove(png)
        try:
            subprocess.run(['firefox', '--headless', '--no-remote',
                            '--profile', os.path.join(slot, 'profile'),
                            '--screenshot', png,
                            '--window-size=%d,%d' % (w, h), 'file://' + src],
                           env=dict(os.environ, MOZ_HEADLESS='1'), timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise RuntimeError('firefox timed out after 300 s; is the page enormous?')
        except FileNotFoundError:
            raise RuntimeError('firefox is not on PATH, and topdf.py needs it to render')
        if not os.path.exists(png):
            raise RuntimeError('firefox produced no screenshot for ' + src)
        return Image.open(png).convert('RGB')

    def render(self, page_html, prelude, scale, keep=True):
        """(image of the page or None, page height in CSS px).

        The window starts a little taller than A4. If the page is still white at
        its bottom edge the page is longer than the window, so it is drawn again
        in a taller one rather than reporting the window as the page height.
        """
        doc = (prelude +
               '<style>html,body{margin:0;padding:0}'
               '.zoom{transform:scale(%g);transform-origin:top left}'
               '.page{margin:0;box-shadow:none}</style>'
               '<div class="zoom">%s</div>' % (scale, page_html))
        w = round(A4_W * scale)
        h = min(round((A4_H + SLACK) * scale), SHOT_MAX)
        x = max(1, round(4 * scale))            # inside the page, outside its padding
        slot = self.free.get()
        try:
            while True:
                im = self._firefox(slot, doc, w, h)
                px, end = im.load(), 0
                for y in range(im.height):
                    if px[x, y][0] > WHITE:
                        end = y + 1
                    elif end:
                        break                   # first grey row after the page
                if end >= im.height and h < SHOT_MAX:
                    h = min(h * 4, SHOT_MAX)
                    continue
                return (im.crop((0, 0, w, end)) if keep else None), end / scale
        finally:
            self.free.put(slot)


def to_a4(im, scale):
    """Pad or crop to exactly A4 at this scale, so every sheet is the same size."""
    w, h = round(A4_W * scale), round(A4_H * scale)
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


def render_all(r, pages, prelude, nums, scale, jobs, keep, progress):
    """Render the listed pages `jobs` at a time; {page number: (image, height)}."""
    out = {}
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(r.render, pages[n - 1], prelude, scale, keep): n for n in nums}
        for k, f in enumerate(as_completed(futs), 1):
            out[futs[f]] = f.result()
            if progress:
                sys.stdout.write('\r  page %d/%d' % (k, len(nums)))
                sys.stdout.flush()
    if progress:
        print()
    return out


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
    ap.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1),
                    help='pages rendered at once, each in its own Firefox (default %(default)s)')
    a = ap.parse_args()

    out = a.out or re.sub(r'\.html?$', '', a.html) + '.pdf'
    with open(a.html, encoding='utf-8') as f:
        prelude, pages = split_pages(f.read())
    print('%s: %d pages' % (os.path.basename(a.html), len(pages)))

    if a.check:
        nums, scale, keep = list(range(1, len(pages) + 1)), 1.0, False
    elif a.png:
        nums, scale, keep = page_numbers(a.png, len(pages)), a.scale, True
    else:
        nums, scale, keep = list(range(1, len(pages) + 1)), a.scale, True
    jobs = max(1, min(a.jobs, len(nums)))
    if not a.check:
        print('rendering %d page%s at %gx (%d dpi), %d at a time'
              % (len(nums), '' if len(nums) == 1 else 's', scale, round(96 * scale), jobs))

    work = tempfile.mkdtemp(prefix='topdf_')
    try:
        r = Renderer(work, jobs)
        try:
            res = render_all(r, pages, prelude, nums, scale, jobs, keep,
                             progress=not a.check and not a.png)
        except RuntimeError as e:
            sys.exit(str(e))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    limit = round(A4_H)
    over = [(n, res[n][1]) for n in nums if res[n][1] > limit + 2]
    for n in nums:
        h = res[n][1]
        if h > limit + 2:
            print('  page %2d  %4d px  OVER A4 by %d px (%.1f mm)'
                  % (n, round(h), round(h - limit), (h - limit) / CSS_PX_MM))
        elif a.check:
            print('  page %2d  %4d px  fits' % (n, round(h)))

    if a.png:
        # An overflowing page is exactly the one worth looking at, so --png is
        # not blocked by an overflow and shows the page at its real height.
        stem = re.sub(r'\.html?$', '', a.html)
        for n in nums:
            png = '%s_page%02d.png' % (stem, n)
            res[n][0].save(png)
            print('  %s' % png)
        if over:
            print('%d of the pages shown do not fit A4; they are drawn in full.' % len(over))
        return

    if over:
        print('\n%d of %d pages do not fit A4 (%d px).' % (len(over), len(nums), limit))
        print('min-height on .page is a minimum, so these look fine stacked on screen '
              'but will not print. Split them in build.py.')
        if a.check or not a.force:
            sys.exit(1)
    elif a.check:
        print('  all %d pages fit A4' % len(pages))
    if a.check:
        return

    sheets = [to_a4(res[n][0], scale) for n in nums]
    sheets[0].save(out, 'PDF', save_all=True, append_images=sheets[1:],
                   resolution=96 * scale)
    print('%s: %d pages, %.1f MB' % (out, len(sheets), os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
