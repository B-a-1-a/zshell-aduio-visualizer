from __future__ import annotations

from click.testing import CliRunner

from termviz import cli
from termviz.capture import BackendDiagnostic


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "--fps" in result.output
    assert "--check" in result.output


def test_cli_validates_ranges() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--fps", "100"])
    assert result.exit_code != 0
    assert "100 is not in the range" in result.output


def test_check_outputs_diagnostics(monkeypatch: object) -> None:
    class FakeApp:
        def __init__(self, _config: object) -> None:
            pass

        def check(self) -> BackendDiagnostic:
            return BackendDiagnostic(
                backend="swift-coreaudio",
                supported=True,
                permission="granted",
                color_depth=256,
                sample_rate=48_000,
                message="audio capture backend is available",
            )

        def run(self) -> None:
            raise AssertionError("run should not be called for --check")

    monkeypatch.setattr(cli, "VisualizerApp", FakeApp)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["--check"])
    assert result.exit_code == 0
    assert "backend: swift-coreaudio" in result.output
    assert "permission: granted" in result.output
