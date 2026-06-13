"""Pluggable screening layers.

Each module in this package defines a ScreeningLayer subclass and registers an
instance with the shared `registry`. The pipeline runs every registered layer
independently (in parallel) for each PaymentInstruction and hands the results to
the VerdictComposer.

To add a new layer:
    1. Create `layers/my_layer.py` with a class implementing `ScreeningLayer`.
    2. Call `registry.register(MyLayer())` at module import time.
    3. Import the module here so registration happens on package import.

Importing the built-in layers registers them with `registry`.
"""

from app.payments.layers import behavioral, jurisdiction, sanctions  # noqa: F401
from app.payments.layers.registry import registry

__all__ = ["registry"]
