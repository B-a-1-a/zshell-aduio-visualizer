# termviz

`termviz` turns a macOS terminal into a live system-audio visualizer.

## Requirements

- macOS 14.2 or newer
- Python 3.10+
- A terminal with ANSI color support
- Xcode command line tools for source installs and local packaging

## Install

Released package:

```bash
pipx install termviz
```

Local development:

```bash
uv sync --extra dev
```

The published macOS wheel bundles the Swift helper. Source builds still compile the helper locally. If you need to skip that during local packaging work, set `TERMVIZ_SKIP_HELPER_BUILD=1`.

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

## License

`termviz` is licensed under the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`). See [`LICENSE`](LICENSE).

## Releasing

Maintainers publish by pushing a version tag such as `v0.1.0`. The GitHub Actions release workflow builds the macOS arm64 wheel and sdist, publishes them to TestPyPI, verifies a clean install on `macos-14`, and then waits for approval on the GitHub `pypi` environment before publishing the exact same artifacts to PyPI.

Before the first release, configure Trusted Publishers for the `termviz` project on both TestPyPI and PyPI, and create GitHub environments named `testpypi` and `pypi`.
