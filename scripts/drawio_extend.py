"""Extend an accepted draw.io diagram without editing it, and tell real edits from re-saves.

    python3 drawio_extend.py shift accepted.drawio room.drawio --dx 1600 [--dy 0] [--page 0]
    python3 drawio_extend.py diff before.drawio after.drawio [--page 0]

shift: move every cell on the root layer(s) by (dx, dy) so new content fits beside it.
Child cells keep their parent-relative geometry; edge waypoints, source and target points
move with the page; label offsets (as="offset") stay relative.  The input is not modified.

diff: compare two saves cell by cell (value, parent, style, geometry, waypoints).  draw.io
rewrites a file when it is saved -- attribute order, &#10; vs &#xa;, compression -- so a
byte or md5 difference does not mean the drawing changed.  Exit status 1 if it did.

Standard library only.
"""
import argparse
import base64
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


def _inflate(text):
    raw = base64.b64decode(text)
    xml = zlib.decompress(raw, -15).decode('utf-8')
    return ET.fromstring(urllib.parse.unquote(xml))


def models(tree):
    """[(diagram element, mxGraphModel)] for every page; compressed pages are expanded in place."""
    out = []
    for diagram in tree.getroot().iter('diagram'):
        model = diagram.find('mxGraphModel')
        if model is None and (diagram.text or '').strip():
            model = _inflate(diagram.text.strip())
            diagram.text = None
            diagram.append(model)
        if model is not None:
            out.append((diagram, model))
    return out


def layer_ids(model):
    cells = model.find('root').findall('mxCell')
    roots = {c.get('id') for c in cells if c.get('parent') is None}
    return {c.get('id') for c in cells if c.get('parent') in roots}


def _num(v):
    f = float(v)
    return str(int(f)) if f == int(f) else repr(f)


def shift(model, dx, dy=0.0):
    """Move root-layer cells by (dx, dy).  Returns the number of cells moved."""
    layers = layer_ids(model)
    moved = 0
    for cell in model.find('root').findall('mxCell'):
        if cell.get('parent') not in layers:
            continue
        geo = cell.find('mxGeometry')
        if geo is None:
            continue
        if cell.get('edge') == '1':
            points = [p for p in geo.iter('mxPoint') if p.get('as') != 'offset']
        else:
            points = [geo]
        for p in points:
            p.set('x', _num(float(p.get('x', 0)) + dx))
            p.set('y', _num(float(p.get('y', 0)) + dy))
        moved += 1
    return moved


def snapshot(model):
    """id -> normalized description of a cell, independent of how draw.io serialized it."""
    snap = {}
    for cell in model.find('root').findall('mxCell'):
        geo = cell.find('mxGeometry')
        g = ()
        pts = ()
        if geo is not None:
            g = tuple(sorted((k, float(v)) for k, v in geo.attrib.items()
                             if k in ('x', 'y', 'width', 'height')))
            pts = tuple(sorted((p.get('as', ''), float(p.get('x', 0)), float(p.get('y', 0)))
                               for p in geo.iter('mxPoint')))
        style = ';'.join(sorted(s for s in (cell.get('style') or '').split(';') if s))
        snap[cell.get('id')] = (cell.get('value') or '', cell.get('parent'), style, g, pts)
    return snap


FIELDS = ('value', 'parent', 'style', 'geometry', 'points')


def diff(model_a, model_b):
    """List of (id, field, before, after); added/removed cells use field 'cell'."""
    a, b = snapshot(model_a), snapshot(model_b)
    out = [(i, 'cell', a[i][0], None) for i in a if i not in b]
    out += [(i, 'cell', None, b[i][0]) for i in b if i not in a]
    for i in a:
        if i in b:
            for n, (x, y) in enumerate(zip(a[i], b[i])):
                if x != y:
                    out.append((i, FIELDS[n], x, y))
    return out


def _page(tree, index):
    pages = models(tree)
    if not 0 <= index < len(pages):
        sys.exit(f'page {index} not found ({len(pages)} pages)')
    return pages[index]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('shift')
    s.add_argument('src')
    s.add_argument('out')
    s.add_argument('--dx', type=float, required=True)
    s.add_argument('--dy', type=float, default=0.0)
    s.add_argument('--page', type=int, default=0)
    d = sub.add_parser('diff')
    d.add_argument('before')
    d.add_argument('after')
    d.add_argument('--page', type=int, default=0)
    args = ap.parse_args(argv)

    if args.cmd == 'shift':
        if args.src == args.out:
            sys.exit('refusing to overwrite the accepted diagram; write a new file')
        tree = ET.parse(args.src)
        _, model = _page(tree, args.page)
        n = shift(model, args.dx, args.dy)
        for key, delta in (('pageWidth', args.dx), ('pageHeight', args.dy)):
            if model.get(key):
                model.set(key, _num(float(model.get(key)) + max(delta, 0)))
        tree.write(args.out, encoding='utf-8', xml_declaration=False)
        print(f'{args.out}: moved {n} cells by ({_num(args.dx)}, {_num(args.dy)})')
        return 0
    if args.cmd == 'diff':
        _, a = _page(ET.parse(args.before), args.page)
        _, b = _page(ET.parse(args.after), args.page)
        changes = diff(a, b)
        for i, field, x, y in changes:
            print(f'{i}\t{field}\t{x!r}\t->\t{y!r}')
        print(f'{len(changes)} semantic change(s)')
        return 1 if changes else 0
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
