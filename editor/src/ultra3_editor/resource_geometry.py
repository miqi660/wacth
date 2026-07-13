from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceCanvasSpec:
    name: str
    label: str
    width: int
    height: int

    @property
    def aspect_ratio(self) -> tuple[int, int]:
        return (5, 6)


MAIN_RESOURCE = ResourceCanvasSpec("main", "主图", 320, 384)
THUMBNAIL_RESOURCE = ResourceCanvasSpec("thumbnail", "缩略图", 210, 252)
