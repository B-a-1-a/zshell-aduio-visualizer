from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import click

from termviz import __version__
from termviz.app import UnsupportedPlatformError, VisualizerApp
from termviz.capture import CaptureError
from termviz.config import AppConfig


def _version() -> str:
    try:
        return version("termviz")
    except PackageNotFoundError:
        return __version__


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--fps", type=click.IntRange(10, 60), default=30, show_default=True, help="Target framerate.")
@click.option("--bars", type=click.IntRange(1, 400), default=None, help="Explicit number of bars.")
@click.option(
    "--color",
    "color_scheme",
    type=click.Choice(["spectrum", "mono", "fire", "ice"], case_sensitive=False),
    default="spectrum",
    show_default=True,
    help="Color scheme.",
)
@click.option(
    "--sensitivity",
    type=click.FloatRange(min=0.1, min_open=False),
    default=1.0,
    show_default=True,
    help="Audio sensitivity multiplier.",
)
@click.option("--no-color", is_flag=True, help="Disable color output.")
@click.option("--check", "check_only", is_flag=True, help="Run backend diagnostics and exit.")
@click.version_option(version=_version(), prog_name="termviz")
def main(
    fps: int,
    bars: int | None,
    color_scheme: str,
    sensitivity: float,
    no_color: bool,
    check_only: bool,
) -> None:
    """Render a live macOS system-audio visualizer in the terminal."""

    config = AppConfig(
        fps=fps,
        bars=bars,
        color=color_scheme.lower(),
        sensitivity=sensitivity,
        no_color=no_color,
    )
    app = VisualizerApp(config)
    try:
        if check_only:
            diagnostic = app.check()
            click.echo(f"backend: {diagnostic.backend}")
            click.echo(f"supported: {'yes' if diagnostic.supported else 'no'}")
            click.echo(f"permission: {diagnostic.permission}")
            click.echo(f"terminal colors: {diagnostic.color_depth}")
            if diagnostic.sample_rate is not None:
                click.echo(f"sample rate: {diagnostic.sample_rate}")
            click.echo(diagnostic.message)
            raise SystemExit(0 if diagnostic.supported else 1)
        app.run()
    except UnsupportedPlatformError as exc:
        raise click.ClickException(str(exc)) from exc
    except CaptureError as exc:
        raise click.ClickException(
            f"{exc}\nEnable your terminal in System Settings > Privacy & Security > Screen & System Audio Recording."
        ) from exc
