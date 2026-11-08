"""Urban-block morphology for the three-city and thirteen-city
sets: morphometric-only Track A (46 descriptors) on top of
the core package `urban-block-morphology` (import name `blockmorph`).

This package adds only what the international sets need and the core
v1.0.0 lacks: per-city building and height sources with automatic height
source selection, a per-city analysis CRS, the thirteen-city sampling-unit
refinement (built-envelope trimming and mega-block splitting) with the
partition-unit neutralisation of unit-dependent descriptors, and model
settings per set (PCA dimensionality, K range per model).
"""
__version__ = "1.0.0"
CORE_VERSION = "1.0.0"          # urban-block-morphology, pinned in pyproject.toml


def check_core():
    """Raise when the installed core is not the pinned version."""
    import blockmorph
    if blockmorph.__version__ != CORE_VERSION:
        raise RuntimeError(
            f"urban-block-morphology {blockmorph.__version__} is installed; "
            f"this release was verified with {CORE_VERSION}")
    return blockmorph.__version__
