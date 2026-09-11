# ic-datasheet

A [Claude Code](https://claude.com/claude-code) skill that turns a Verilog project into a
printable A4 datasheet — module symbols, pin tables, a connectivity block diagram, timing
waveforms and a register map, in the style of a foundry IP datasheet.

Output is two files: an **HTML** you can keep editing, and an **A4 PDF** you can print or mail.

<p align="center">
  <img src="example/sample-page.png" width="45%" alt="Cover page: overview and key figures">
  <img src="example/sample-blockdiagram.png" width="45%" alt="Connectivity block diagram">
</p>

<p align="center"><sub>Sample output. Module names are anonymised.</sub></p>

## What it actually does

Facts come out of the RTL; prose is written by hand. That split is the whole design:

| | Source | On a re-run |
|---|---|---|
| Parameters, ports, bit widths, instantiations | parsed from the Verilog | regenerated |
| Overview, per-module description, signal notes | written by you, in `build.py` | left alone |

Generating descriptions from RTL only ever produces `wr_go is the wr_go signal`, so the skill
does not try. What it does automate is everything tedious and error-prone: resolving
`[NUM_CH*ID_WIDTH-1:0]` into `[95:0]`, laying out symbols so no label is truncated, splitting a
63-pin table across pages, and refusing to emit a PDF when a page does not actually fit A4.

## Install

```sh
git clone https://github.com/charlesHYC/ic_doc-datasheet ~/.claude/skills/ic-datasheet
bash ~/.claude/skills/ic-datasheet/example/run.sh     # builds the example: proves the setup works
```

Then in Claude Code:

```
/ic-datasheet <your project>
```

Claude reads `SKILL.md` and drives the scripts. You can also run them by hand — see below.

## Requirements

- Python 3.6 or later (tested with 3.6.8, 3.9 and 3.11). Only the standard library, except:
- [Pillow](https://pypi.org/project/Pillow/) and Firefox for `topdf.py`

If your machine has several Pythons, Pillow may not be installed in the one that runs
`build.py`. That is normal; just spell out the interpreter paths.

## By hand

```sh
# 1. Parse the module headers. List the files explicitly - do NOT glob *.v,
#    because file names and module names do not always agree.
python3 scripts/extract.py rtl/a.v rtl/b.v > modules.json

# 2. Assemble the HTML (start from example/build.py and edit PROSE)
PYTHONPATH=scripts python3 build.py

# 3. Look at the pages. Each one is rendered on its own, so there is nothing
#    to crop; a page that overflows is shown at its real height.
python3 scripts/topdf.py my_design_datasheet_manual.html --png 1,3-5

# 4. Check every page really fits A4, then convert
python3 scripts/topdf.py my_design_datasheet_manual.html --check
python3 scripts/topdf.py my_design_datasheet_manual.html
```

Pages render in parallel, each in its own headless Firefox with a private profile, so a browser
you already have open does not get in the way. A 29-page datasheet converts in about 17 s at
192 dpi (`--scale 2`) and 19 s at 288 dpi; `--jobs N` sets how many pages render at once.

## What's in here

| Path | |
|---|---|
| `SKILL.md` | the skill: workflow, layout rules, and the traps worth knowing |
| `scripts/extract.py` | module header parser → JSON; Verilog-95 and Verilog-2001 headers |
| `scripts/paginate.py` | height estimates, so long tables split before they overflow |
| `scripts/topdf.py` | HTML → A4 PDF, the page-fits-A4 check, and per-page PNGs |
| `scripts/wave.py` | timing figure renderer, datasheet-style buses |
| `scripts/blocks.py` | connectivity block diagram layout |
| `example/build.py` | the example's assembly script — copy it and edit |
| `example/rtl/` | six stub modules, real interfaces and empty bodies, so the example runs |
| `example/run.sh` | extract → build → A4 check for the example, output in `example/out/` |
| `tests/test_scripts.py` | regression checks; run it after touching any script |

`extract.py`, `paginate.py` and `topdf.py` are project-independent. `wave.py` and `blocks.py`
have generic renderers but the content of each figure is written per project.

## Two traps that cost real time

**A page that does not fit A4 gives no warning.** `min-height: 297mm` on `.page` is a
*minimum* — too much content and the div simply grows. Stacked on screen it looks perfect,
footer and all, but printing repaginates it and converting crops it. The first version of the
example datasheet had 11 of 16 pages over, one by 310 mm, and nobody noticed. `topdf.py --check`
measures every page and refuses to convert until they all fit.

**Firefox has no `--print-to-pdf`.** Only `--screenshot`, which silently writes nothing if you
give it a relative path. `topdf.py` renders each page under `transform: scale(N)` and stitches
the results, so the PDF's layout is identical to the HTML you verified — at the cost of text
not being selectable.

## Example

`bash example/run.sh` builds a 24-page datasheet from the stubs in `example/rtl/`: six modules,
their symbols and pin tables, a register map, a block diagram and four waveforms. Add `--png` to
render every page, or `--pdf` for a 192 dpi PDF. Copying `example/build.py` and replacing the
`PROSE`, `CSR`, `LIB` and `FULL` constants is the fastest way to start on your own design; the
CSS, the symbol renderer, the table builders and the pagination all carry over unchanged.

## Tests

```sh
python3 tests/test_scripts.py
```

Each check is a way a script once went wrong without saying so: a Verilog-95 header coming back
with no ports, a task call counted as an instance, a heading in the parameter list labelling the
first ports, `paginate.chunk` ignoring `first`, a waveform quietly shrunk to fit.

## License

MIT — see [LICENSE](LICENSE).
