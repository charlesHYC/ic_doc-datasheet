# Editable RTL schematic mode

Use this mode for a standalone block diagram, a Verdi-like schematic, or an operator-level
pipeline expansion. Draw a technical schematic with real connections, not an illustration.
Verdi-like describes the visual grammar; do not claim the output came from Verdi or synthesis.

## Read the accepted reference before choosing detail

When asked to learn a drawing style, inspect the actual latest drawing and its editable
source. Compare the generated version with any later user-edited version; filenames and
modification times identify candidates, but do not by themselves prove user approval.
Use the user's stated preference to choose the reference. Extract visual rules, not the
reference circuit. Do not regenerate or overwrite a hand-edited drawing while studying it.

Choose the view before placing symbols:

| Requested view | Drawing approach |
|---|---|
| Overall architecture or stage overview | Compact horizontal chain, meaningful logic groups, visible register boundaries and interfaces |
| Operator-level detail | Expand the requested logic into actual MUXes, adders, comparisons and registers while retaining the connected main path |
| Overview plus detail | Keep a readable overview; expand selected groups on linked detail pages using consistent interface names |

An overview is not a testbench wiring map: avoid isolated named-input islands, stimulus
boxes, or long lists of signals detached from their sources. An operator diagram is not
automatically a better overview. Keep the chosen abstraction level consistent and do not
expand every arithmetic expression merely because its RTL is available.

## Compact stage overview layout

Place the input structures on the left, the ordered processing stages across one horizontal
band, and the outputs on the right. Align repeated units in rows with the same port heights,
symbol sizes and spacing. A many-input MUX may span those rows, with numbered input pins;
its select enters separately from below. Keep repeated units separate unless the requested
abstraction explicitly permits an annotated repeated group.

Within a stage, draw its combinational group followed by the register that captures the
result. Enclose them in a thin dashed stage frame, with a short bold title at its upper-left
corner. A stage frame describes a clock boundary, not necessarily a Verilog module; infer
membership from actual register assignments. Do not blindly copy frame boundaries from a
reference. The logic between registers must meet that clock period, but the drawing alone
does not establish that timing has passed.

Keep the record/data path across the middle of the stage chain. Route accompanying metadata
on a nearby parallel track; route ready/free feedback backward along a separate lower track.
Put supporting counters and time calculations close below the stage that uses them, with
visible connections into the main path. Avoid tall register bars and large empty regions
that make a short pipeline occupy a wall-sized canvas.

Use the following visual vocabulary consistently within this overview style:

| Element | Appearance and meaning |
|---|---|
| Combinational group | Modestly rounded rectangle with a short function name; no clock marker |
| Register or sequential block | Square rectangle with a clock-edge triangle; do not add a triangle to combinational logic |
| FIFO | Queue-like rectangle with parallel inset lines or a small row of storage slots; label width and depth with units |
| MUX | Trapezoid with numbered inputs and a separate select pin; not a generic rectangle |
| Expanded adder | Circle with `+` and attached operand/result pins; use an equivalent expression grouping only when identified as such |
| Stage boundary | Thin dashed, unfilled enclosure behind its contents; title clear of all wires |
| Forward data path | Solid orthogonal line, arrow toward the receiver; compact width labels or bus slash where useful |
| Backward ready/free path | Dashed orthogonal line, arrow toward the upstream recipient; distinct from the stage enclosure |
| FSM-containing module | Append `{F}` only after confirming an actual state machine in the RTL; valid bits and counters alone do not justify it |

An approved reference may use pale fills to distinguish component families. If so, use a
small consistent palette, preserve black text and legible strokes, and keep shape semantics
readable in grayscale. Use monochrome when requested. Color never substitutes for identifying
whether a block is combinational, registered, a FIFO or an FSM. Do not impose one palette
or one corner style on all future diagrams regardless of the reference.

Size blocks around their names and ports. Use one short title plus a few essential fields;
move full descriptions and equations to a detail page when they obscure the overview.
Wrap at meaningful boundaries, widen the block before reducing the font, and keep labels
outside narrow routing channels. Port labels must not collide with the block's central
text. Keep the main stages readable at the intended viewing size, not only at extreme zoom.
A compact legend can explain the clock marker, stage frame and dashed feedback once.

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

For an operator-level pipeline request, expand arithmetic, carry folds, masks, comparisons, counters,
field replacement and selection inside modules. Show the whole pipeline with register
boundaries, adding detail pages for crowded logic. A page containing only one opaque module
does not satisfy an operator-level request. Preserve an already approved surrounding diagram.

An equivalent addition tree may explain an RTL expression, but is not proof of the synthesized
adder topology. Record that distinction outside the circuit figure. Do not infer a DSP,
memory primitive, timing result, or throughput guarantee from a behavioral expression.

## Symbol and wire grammar

- White background, thin legible strokes and restrained serif typography. Use the selected
  view's symbol vocabulary; the overview may distinguish rounded combinational blocks from
  square registered blocks and use an approved reference's pale fills.
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

## Extending an accepted drawing

Once the user has hand-edited a diagram, it is theirs. When asked to add a subsystem
(for example a write path beside an approved read path), produce a new file built on a
copy; never write to the accepted file, and confirm afterwards that its checksum did not
change. `scripts/drawio_extend.py` supports this:

```sh
python3 drawio_extend.py shift accepted.drawio room.drawio --dx 1600   # make room on the left
python3 drawio_extend.py diff  before.drawio   after.drawio            # what did the user change?
```

`shift` moves only root-layer cells. Child cells (pins, clock markers, inner labels) are
parent-relative and must stay put; edge source/target points and waypoints move; label
offsets do not. Then append the new section's cells to the copy.

**Re-saves are not edits.** draw.io rewrites the whole file on save: newline entities
(`&#10;` and `&#xa;`), attribute order and compression all change. A different checksum
therefore says nothing. Before regenerating a derived drawing, run `diff` against the
version the generator was written for, and carry over the user's real moves (a port moved
left, a block resized) instead of assuming the old coordinates.

Keep the user's own text untouched. Adding a line to their block shifts the vertically
centred text and can push it into decorations they placed inside the block, such as a small
arrow between two file names. Put an added annotation in a separate text cell above or
beside the block.

**Layering.** draw.io paints cells in document order. A filled frame or block created after
an edge or label hides it, with no warning in the XML. Emit enclosures first and new
content last; append new cells at the end of the root so they are not covered by existing
filled blocks. After export, look for arrows that stop at a frame border and labels missing
from inside filled blocks.

## Composing a system view

**One memory, two directions.** When a memory has a write path and a read path, draw the
writer entering one side and the reader leaving the other, each through its own interface
block, with one wire per channel lined up with the memory's channel rows on both sides.
If both sides are the same physical port (for example one AXI port per channel carrying
AW/W/B and AR/R), label the two blocks with their channel sets and add a single sentence
saying so, so nobody reads them as two sets of hardware.

**Stage names follow registers.** Combinational logic after a stage's register, with no
register of its own, belongs to that stage and shares its frame. If a block that used to
define a stage (an output FIFO, say) is left out of the view, remove its stage name and
rename signals labelled after it rather than keeping an empty stage name. When a comparison
happens in one stage, write the condition in that stage's block and route the inputs it
compares (counter, mode bit) into that block, not into a downstream block.

**Functional view by default.** Blocks that exist only to close timing (register slices,
isolation FIFOs, clock-domain crossings that do not change the data) usually do not
belong in a functional explanation. Follow the user's choice; do not re-introduce such
blocks into the drawing or the narrative unless asked about them.

**Variants from one generator.** Overview, detailed, and with/without a planned design
are often all wanted. Build them from one generator with switches rather than editing
exports by hand. When a variant drops a section, also remove every mention of it elsewhere
(host-side notes, legends, captions, frame titles).

**Notation.** Use the audience's notation in labels: arithmetic such as `(addr ÷ N) mod M`
where they prefer it over bit slices, and `×`, `÷`, `→` symbols. Replace symbols only in
contexts you can match exactly: a blanket `" / "` → `÷` also rewrites alternatives such
as `port a / port b`.

## Export and review

Export using the installed draw.io desktop CLI. Typical headless Linux commands:

```sh
xvfb-run -a drawio --export --format png --page-index 1 --scale 1.5 --border 30 --output example.png example.drawio
xvfb-run -a drawio --export --format pdf --all-pages --crop --output example.pdf example.drawio
```

Use the local executable path when it is not on PATH. An AppImage that cannot mount
(no FUSE) runs after `--appimage-extract`, from `squashfs-root/drawio`; Chromium may also
need `--no-sandbox`. Crop dense regions of a large export with Pillow and inspect them at
full resolution; a whole wall-sized sheet scaled to a screen hides collisions. Respect environment approval rules;
check the installed CLI's options if they differ. Verify the resulting file exists and can
be read even if the process reports an Xvfb cleanup error. Do not confuse that error with
proof that export succeeded. Export every page, not only the first page.

Iterate until both checks pass:

1. **Structural check:** valid XML, unique cell IDs within each page, all edge endpoints
   resolve to pins, expected pages present, orthogonal wires, and no unrelated block
   penetration. `Page.check()` catches diagonal segments, wire/block intersections and
   partial label/block overlap. It does not prove RTL correctness, text legibility,
   net separation, or absence of label/label collisions.
2. **Visual check:** inspect the whole sheet at its intended viewing size, then zoom into
   dense regions. Check wire
   alignment, MUX select attachment, crossings, text wrapping, clipping, and register port
   placement. Fix the source and regenerate; do not paint over errors in the preview.

For a compact overview, additionally trace one complete input-to-output route without
jumping between repeated signal names. Trace ready/free in the opposite direction and
verify where buffering stops or continues that dependency. Check that each stage enclosure
matches the intended capture boundary. Inspect label/wire and label/label collisions as well
as block collisions; the geometry helper does not catch all of these. A readable reference's
composition is worth reusing, but its circuit-specific claims still need independent RTL
evidence in each new project.

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
