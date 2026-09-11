#!/usr/bin/env python3
"""Regression checks for the scripts that have no visible output of their own.

Each case is a way one of them once went wrong without saying so: extract.py
returning no ports or the wrong instances, paginate.chunk ignoring `first`,
wave.render quietly shrinking a figure. No test framework is needed:

    python3 tests/test_scripts.py

prints one line per check and exits non-zero if any fails.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import extract            # noqa: E402
import paginate as pg     # noqa: E402
import wave               # noqa: E402

FIX = os.path.join(HERE, 'fixtures')
failed, total = [], [0]


def check(what, got, want):
    total[0] += 1
    if got == want:
        print('  ok    ' + what)
    else:
        print('  FAIL  %s\n        got  %r\n        want %r' % (what, got, want))
        failed.append(what)


def raises(what, fn, exc=ValueError):
    try:
        fn()
    except exc:
        check(what, 'raised', 'raised')
        return
    check(what, 'returned normally', 'raised %s' % exc.__name__)


def ports(m):
    return [(p['name'], p['dir'], p['width']) for p in m['ports']]


print('extract.py')

m = extract.parse(os.path.join(FIX, 'ansi_banner.v'))
check('ANSI: module found after a leading banner comment', m['module'], 'ansi_top')
check('ANSI: parameters, including a typed one',
      [(p['name'], p['value']) for p in m['params']],
      [('DATA_W', '64'), ('ID_W', '4'), ('MAGIC', "8'hA5")])
check('ANSI: ports, several names per declaration, initialiser dropped', ports(m), [
    ('clk', 'input', ''), ('rst', 'input', ''),
    ('s_axi_wdata', 'input', '[DATA_W-1:0]'), ('s_axi_wvalid', 'input', ''),
    ('s_axi_wready', 'output', ''),
    ('count', 'output', '[7:0]'), ('busy', 'output', ''), ('done', 'output', ''),
    ('dbg', 'output', '[3:0]')])
check('ANSI: a heading padded with dashes inside a ruled block is cleaned',
      m['ports'][-1]['group'], 'Debug ports')
check('ANSI: a heading in the parameter list does not label the first ports',
      [m['ports'][0]['group'], m['ports'][1]['group']], ['Ports', 'Ports'])
check('ANSI: one-line banner "// ---- AXI write ----" names a group',
      [p['group'] for p in m['ports'] if p['name'].startswith('s_axi')], ['AXI write'] * 3)
check('ANSI: the one-line banner does not become a port description',
      m['ports'][2]['comment'], '')
check('ANSI: three-line banner names a group',
      [p['group'] for p in m['ports'] if p['name'] in ('count', 'busy')], ['Status'] * 2)
check('ANSI: trailing comment is the port description', m['ports'][5]['comment'],
      'the initialiser is not part of the name')
check('localparams are found, with or without a range (needs re.M)',
      [p['name'] for p in m['localparams']], ['DEPTH', 'MODE'])
check('instances: plain, #(...), multi-line #(...), arrays; not gates, task calls, '
      'comments, strings or the next module',
      m['instantiates'], ['child_a', 'child_b', 'child_c', 'child_d'])

m = extract.parse(os.path.join(FIX, 'v95.v'))
check('Verilog-95: ports in header order with body widths', ports(m), [
    ('Q', 'output', '[BITS-1:0]'), ('CLK', 'input', ''), ('CEN', 'input', ''),
    ('WEN', 'input', ''), ('A', 'input', '[7:0]'), ('D', 'input', '[BITS-1:0]')])
check('Verilog-95: parameters declared in the body',
      [(p['name'], p['value']) for p in m['params']], [('WORDS', '256'), ('BITS', '128')])
check('Verilog-95: a task input does not become a port',
      'addr' in [p['name'] for p in m['ports']], False)

m = extract.parse(os.path.join(FIX, 'inline.v'))
check('ANSI header on one line', ports(m),
      [('clk', 'input', ''), ('d', 'input', '[W-1:0]'), ('q', 'output', '[W-1:0]')])
check('ANSI header on one line: parameter', [p['name'] for p in m['params']], ['W'])

m = extract.parse(os.path.join(FIX, 'noports.v'))
check('no port list: no ports', m['ports'], [])
check('no port list: body parameter and localparam',
      ([p['name'] for p in m['params']], [p['name'] for p in m['localparams']]),
      (['N'], ['M']))
check('no port list: instance with an empty port list', m['instantiates'], ['dut'])

print('paginate.py')

check('chunk packs greedily', pg.chunk([('a', 200), ('b', 200), ('c', 50)], 300),
      [['a'], ['b', 'c']])
check('chunk: an item that misses only `first` moves on and leaves out[0] empty',
      pg.chunk([('a', 100), ('b', 100)], 300, first=50), [[], ['a', 'b']])
check('chunk: an item taller than the budget is still admitted, on its own',
      pg.chunk([('big', 500), ('s', 10)], 300), [['big'], ['s']])
raises('svg_px refuses an SVG with no width="Nmm" instead of returning 0',
       lambda: pg.svg_px('<svg viewBox="0 0 100 50" width="100%">'))
check('svg_px from viewBox and width',
      round(pg.svg_px('<svg viewBox="0 0 100 50" width="100mm">'), 1),
      round(50 * pg.MM, 1))

print('wave.py')

WIDE = {'id': 'wide', 'alt': 'x', 'segments': [list(range(200))],
        'signals': [{'name': 'clk', 'kind': 'clk'}]}
raises('render refuses a figure wider than the column', lambda: wave.render(WIDE))
check('render with shrink accepts it at the column width',
      'width="%dmm"' % wave.COL_MM in wave.render(dict(WIDE, shrink=True)), True)
check('render draws the bundled READ spec', wave.render(wave.READ).startswith('<svg'), True)

print('\n%d of %d checks passed' % (total[0] - len(failed), total[0]))
sys.exit(1 if failed else 0)
