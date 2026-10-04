"""SQLite-backed application services and Reflex-hosted routes."""

from pathlib import Path

# The merged layout keeps matching under the Reflex package and core services here.
__path__.append(str(Path(__file__).resolve().parents[1] / "mule_hacks" / "backend"))
