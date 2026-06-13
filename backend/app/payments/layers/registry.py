"""Registry of pluggable screening layers.

The pipeline asks the registry for "all layers" rather than importing them
individually, so new layers can be added by registering them in their own module
(see layers/__init__.py) without touching the pipeline.
"""

from __future__ import annotations

from app.payments.layers.base import ScreeningLayer


class LayerRegistry:
    def __init__(self) -> None:
        self._layers: dict[str, ScreeningLayer] = {}

    def register(self, layer: ScreeningLayer) -> None:
        if layer.name in self._layers:
            raise ValueError(f"Layer '{layer.name}' is already registered")
        self._layers[layer.name] = layer

    def all(self) -> list[ScreeningLayer]:
        return list(self._layers.values())

    def get(self, name: str) -> ScreeningLayer:
        return self._layers[name]


registry = LayerRegistry()
