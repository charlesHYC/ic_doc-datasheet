# Editable RTL schematic mode

Use this mode for a standalone block diagram, a Verdi-like schematic, or an operator-level
pipeline expansion. Draw a technical schematic with real connections, not an illustration.
Verdi-like describes the visual grammar; do not claim the output came from Verdi or synthesis.

## Establish the circuit and scope

Read the project's instructions and active synthesis file list. Trace actual instantiations
and production RTL; similarly named archived modules are not evidence. Respect the requested
boundary: a pipeline-only view should terminate at its interfaces instead of redrawing the
surrounding memory and transmission subsystems.

Before drawing, record the following in a local working table:

| Item | Evidence to establish |
|---|---|
| Stage boundary | Register assignments, width, clock, enable, reset and update priority |
| Data transformation | Arithmetic width, signedness, truncation, concatenation and byte order |
| Selection | MUX input 0/1, exact select expression, default and bypass values |
| Transfer | valid/ready acceptance, hold, release, simultaneous set/clear priority |
| Output | Exact data and sideband sources, time gating and backpressure |

For a detailed pipeline, expand arithmetic, carry folds, masks, comparisons, counters,
field replacement and selection inside modules. Show the whole pipeline with register
boundaries, adding detail pages for crowded logic. A page containing only one opaque module
does not satisfy an operator-level request. Preserve an already approved surrounding diagram.

An equivalent addition tree may explain an RTL expression, but is not proof of the synthesized
adder topology. Record that distinction outside the circuit figure. Do not infer a DSP,
memory primitive, timing result, or throughput guarantee from a behavioral expression.

## Symbol and wire grammar

- White background, black thin strokes, square corners and restrained serif typography.
  Keep figure text to English identifiers, widths, operators and short technical labels;
  place explanatory prose in accompanying documentation.
- Use a trapezoid for a MUX, with visible 0/1 inputs and a separate select pin. Use a register
  rectangle with a clock-edge marker and label its enable/reset where relevant. Distinguish
  FIFOs/memories from arithmetic and ordinary module rectangles.
- Show arithmetic with the actual operator and necessary result width. Comparators and
  Boolean logic need their predicate or operator, not generic boxes named “processing.”
- Connect edges to explicit pin vertices with source/target IDs. Use off-page terminals
  for named continuations; repeat the same signal identifier at the other end. Terminals
  represent continuations, not hidden hardware. Avoid a diagram consisting solely of
  disconnected labeled inputs: keep each principal datapath and stage boundary connected.
- Align ports and operator centers. Route wires orthogonally through reserved channels.
  No wire may run through an unrelated block, port label or block title. Leave space for
  labels before placing blocks. Move symbols or enlarge the page instead of shrinking text.
- Separate unrelated nets. Collinear overlap must not imply a shared bus. Use a junction
  dot only for an electrical connection; use a bridge or clear spacing at other crossings.
  Fanout must retain a common source. Never combine different signals into one unlabeled wire.
- Reserve a lower or upper routing channel for enable/ready feedback. A data register
  does not advance just because its upstream stage is valid; show the actual transfer condition.

## Editable generation

Use draw.io directly or generate its native XML, then open/export it with draw.io.
`scripts/drawio_schematic.py` provides reusable symbols and explicit port-connected edges;
it is a geometry helper, not an RTL parser or automatic router. It requires only Python's
standard library. Keep project-specific generators and signal maps in the user's project.

Import the helper from the installed skill's `scripts` directory. A process builds one
document in `FILE`; use `del FILE[:]` before creating a separate document to remove its
pages while preserving document attributes. Page IDs must be unique. Example, using deliberately
abstract circuit names rather than an existing project's design:

```python
from drawio_schematic import Page, connect, save_document

p = Page('example', 'Example', 1000, 500)
a = p.reg('input_q[15:0]', 100, 180, 180, 100)
b = p.block('+ 1 / 16-bit', 430, 195, 180, 70)
c = p.reg('output_q[15:0]', 760, 180, 180, 100)
connect(p, a, b)
connect(p, b, c)
assert not p.check(), p.check()
save_document('example.drawio')
```

Coordinates passed to `pin()` are page coordinates, converted to coordinates relative to
the parent block. `vertex()` geometry is relative to its parent; keep obstacle blocks on
the root layer. `connect()` joins right-to-left ports, with a simple dogleg if heights differ;
supply explicit `via` waypoints for congested regions. `edge()` supports any pair of pins.
The `reg()` clock marker is symbolic; add actual clock/reset nets when the requested view
needs them. Do not invent a second data path for a decorative clock marker.

Write XML with ElementTree so newlines in label attributes survive a save/load round trip.
Retain custom stencils and native text/shapes; a bitmap embedded in `.drawio` is not editable
schematic content. Avoid external image references or online editors for confidential RTL.

## Export and review

Export using the installed draw.io desktop CLI. Typical headless Linux commands:

```sh
xvfb-run -a drawio --export --format png --page-index 1 --scale 1.5 --border 30 --output example.png example.drawio
xvfb-run -a drawio --export --format pdf --all-pages --crop --output example.pdf example.drawio
```

Use the local executable path when it is not on PATH. Respect environment approval rules;
check the installed CLI's options if they differ. Verify the resulting file exists and can
be read even if the process reports an Xvfb cleanup error. Do not confuse that error with
proof that export succeeded. Export every page, not only the first page.

Iterate until both checks pass:

1. **Structural check:** valid XML, unique cell IDs within each page, all edge endpoints
   resolve to pins, expected pages present, orthogonal wires, and no unrelated block
   penetration. `Page.check()` catches diagonal segments, wire/block intersections and
   partial label/block overlap. It does not prove RTL correctness, text legibility,
   net separation, or absence of label/label collisions.
2. **Visual check:** inspect each exported image and zoom into dense regions. Check wire
   alignment, MUX select attachment, crossings, text wrapping, clipping, and register port
   placement. Fix the source and regenerate; do not paint over errors in the preview.

Re-read RTL for every selection polarity, carry width, endian conversion and valid-state
priority after layout changes. Deliver editable source plus reviewed exports and a short
local provenance note identifying the source revision and abstraction level. Do not present
an unchecked draft as finished.

## Publication boundary

Keep reusable skill content independent of the source project. A confidential circuit must
not appear in screenshots, XML, PDF, generated examples, test fixtures, source paths, commit
messages or handoff documents included in a public commit. Renaming signals does not make
a real circuit safe to publish. Use invented minimal examples for tests. Inspect the exact
staged diff and file list before a requested commit/push; publication permission for a skill
does not publish the diagrams produced with it.
