"""Advanced chunking strategies.

Select via ``CHUNK_STRATEGY`` in ``.env``:

``fixed``           character windows (baseline / control)
``recursive``       heading > paragraph > line > sentence > char cascade
``semantic``        embedding-similarity breakpoints
``metadata_aware``  structure preserving: atomic tables, breadcrumbs, code tags
"""

from .base import ChunkStrategy, available_strategies, build_strategy

__all__ = ["ChunkStrategy", "build_strategy", "available_strategies"]
