"""shift / diff regressions on an invented two-block circuit."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import drawio_schematic as d
import drawio_extend as x


def build(tmp):
    del d.FILE[:]
    p = d.Page('demo', 'Demo', 800, 400)
    a = p.reg('count_q\n[7:0]', 100, 150, 160, 90)
    b = p.block('+ 1', 450, 160, 120, 70)
    d.connect(p, a, b, via=[(350, 195)])
    path = Path(tmp) / 'accepted.drawio'
    d.save_document(path)
    return path, a, b


class ExtendTest(unittest.TestCase):
    def test_shift_moves_root_cells_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, a, b = build(tmp)
            before = ET.parse(str(src))
            out = Path(tmp) / 'room.drawio'
            self.assertEqual(x.main(['shift', str(src), str(out), '--dx', '500']), 0)
            _, m0 = x.models(before)[0]
            _, m1 = x.models(ET.parse(str(out)))[0]
            s0, s1 = x.snapshot(m0), x.snapshot(m1)
            ga = dict(s0[a][3]); gb = dict(s1[a][3])
            self.assertEqual(gb['x'], ga['x'] + 500)
            self.assertEqual(gb['y'], ga['y'])
            for i, cell in s0.items():
                if cell[1] in (a, b):            # pins: parent-relative, must not move
                    self.assertEqual(cell[3], s1[i][3])
            edge = next(i for i, c in s0.items() if c[4])
            for p0, p1 in zip(s0[edge][4], s1[edge][4]):
                if p0[0] != 'offset':
                    self.assertEqual(p1[1], p0[1] + 500)

    def test_refuses_to_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, _, _ = build(tmp)
            with self.assertRaises(SystemExit):
                x.main(['shift', str(src), str(src), '--dx', '10'])

    def test_diff_ignores_resave_but_finds_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, a, _ = build(tmp)
            text = src.read_text()
            resaved = Path(tmp) / 'resaved.drawio'
            # what a draw.io re-save looks like: other newline entity, other attribute order
            resaved.write_text(text.replace('&#10;', '&#xa;').replace('x="350" y="195"', 'y="195" x="350"'))
            self.assertNotEqual(resaved.read_text(), text)
            self.assertEqual(x.main(['diff', str(src), str(resaved)]), 0)
            moved = Path(tmp) / 'moved.drawio'
            tree = ET.parse(str(src))
            _, model = x.models(tree)[0]
            cell = next(c for c in model.iter('mxCell') if c.get('id') == a)
            g = cell.find('mxGeometry')
            g.set('x', str(float(g.get('x')) - 40))
            tree.write(str(moved))
            changes = x.diff(x.models(ET.parse(str(src)))[0][1], x.models(ET.parse(str(moved)))[0][1])
            self.assertEqual([(i, f) for i, f, _, _ in changes], [(a, 'geometry')])


if __name__ == '__main__':
    unittest.main()
