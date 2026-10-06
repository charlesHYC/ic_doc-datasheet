"""Geometry and editable-XML regressions using invented circuits only."""
import base64
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import drawio_schematic as d


class SchematicTest(unittest.TestCase):
    def setUp(self):
        del d.FILE[:]

    def test_native_ports_and_multiline_roundtrip(self):
        p = d.Page('test', 'Test', 1000, 600)
        a = p.reg('input_q\n[15:0]', 100, 200, 180, 100)
        b = p.block('+ 1', 500, 210, 120, 80)
        d.connect(p, a, b)
        self.assertEqual(p.check(), [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.drawio'
            d.save_document(path)
            root = ET.parse(str(path)).getroot()
        cells = root.findall('.//mxCell')
        ids = {c.get('id'): c for c in cells}
        self.assertEqual(len(ids), len(cells))
        self.assertEqual(ids[a].get('value'), 'input_q\n[15:0]')
        edge = next(c for c in cells if c.get('edge') == '1')
        source = ids[edge.get('source')]
        target = ids[edge.get('target')]
        self.assertEqual(source.get('parent'), a)
        self.assertEqual(target.get('parent'), b)
        geometry = source.find('mxGeometry')
        self.assertEqual(float(geometry.get('x')) + 2.5 + 100, 280)
        self.assertEqual(float(geometry.get('y')) + 2.5 + 200, 250)

    def test_reject_obstructed_connection(self):
        p = d.Page('blocked', 'Blocked', 1000, 600)
        a = p.block('source', 100, 200, 100, 100)
        p.block('unrelated', 300, 200, 100, 100)
        b = p.block('sink', 500, 200, 100, 100)
        d.connect(p, a, b)
        self.assertTrue(any(i[1] == 'wire crosses block' for i in p.check()))

    def test_explicit_detour_avoids_obstacle(self):
        p = d.Page('route', 'Route', 1000, 600)
        a = p.block('source', 100, 200, 100, 100)
        p.block('unrelated', 300, 200, 100, 100)
        b = p.block('sink', 500, 200, 100, 100)
        d.connect(p, a, b, via=[(250, 250), (250, 150), (450, 150), (450, 250)])
        self.assertEqual(p.check(), [])

    def test_diagonal_and_label_collision(self):
        p = d.Page('bad', 'Bad', 1000, 600)
        a = p.block('a', 100, 200, 100, 100)
        b = p.block('b', 500, 300, 100, 100)
        p.edge(p.pin(a, 200, 250), p.pin(b, 500, 350))
        p.label('crossing label', 70, 190, 80, 30)
        kinds = {i[1] for i in p.check()}
        self.assertIn('non-orthogonal', kinds)
        self.assertIn('label crosses block', kinds)

    def test_custom_mux_is_native_vector_shape(self):
        compressed = base64.b64decode(d.MUX[len('stencil('):-1])
        xml = urllib.parse.unquote(zlib.decompress(compressed, -15).decode())
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, 'shape')
        self.assertEqual(len(root.findall('.//line')), 3)
        self.assertIsNotNone(root.find('.//close'))
        self.assertIsNone(root.find('.//image'))


if __name__ == '__main__':
    unittest.main()
