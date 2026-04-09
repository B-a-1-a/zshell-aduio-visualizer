# termviz

`termviz` turns a macOS terminal into a live system-audio visualizer.

## Requirements

- macOS 14.2 or newer
- Python 3.10+
- Xcode command line tools for building the bundled Swift helper
- A terminal with ANSI color support

## Install

```bash
pipx install .
```

For editable local development:

```bash
uv sync --extra dev
```

The package build compiles a small Swift helper and bundles it into the wheel. If you need to skip that during local packaging work, set `TERMVIZ_SKIP_HELPER_BUILD=1`.

## Usage

```bash
termviz
termviz --fps 24 --color fire
termviz --check
```

On first run, macOS may ask for audio capture access. If playback stays silent or startup fails, enable your terminal app in:

`System Settings > Privacy & Security > Screen & System Audio Recording`

## CLI

```text
Usage: termviz [OPTIONS]

Options:
  --fps INTEGER
  --bars INTEGER
  --color [spectrum|mono|fire|ice]
  --sensitivity FLOAT
  --no-color
  --check
  --version
  --help
```

## Development

- Python application code lives in `src/termviz/`
- The Swift helper lives in `termviz_helper/`
- Python tests run with `pytest`
- Swift helper tests run with `swift test`

The Python host is responsible for CLI parsing, DSP, rendering, and subprocess supervision. The Swift helper is responsible for Core Audio tap setup and PCM capture.
