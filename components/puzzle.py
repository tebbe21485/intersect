"""Local React puzzle components compiled by the existing Reflex frontend."""

from pathlib import Path

import reflex as rx


class PuzzleWidget(rx.Component):
    tag = "PuzzleWidget"
    mode: rx.Var[str]

    def add_imports(self):
        return {"react": [rx.ImportVar(tag="React", is_default=True, alias="PuzzleReact")]}

    def add_custom_code(self):
        source = Path(__file__).resolve().parents[1] / "assets" / "shared-puzzle.jsx"
        tools = source.with_name("connection-tools.jsx")
        return [source.read_text(encoding="utf-8") + "\n" + tools.read_text(encoding="utf-8")]


puzzle_widget = PuzzleWidget.create
