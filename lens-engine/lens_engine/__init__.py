"""CorpusMind Lens engine — a local-first visual & multimodal corpus-analysis service.

Own repository, own identity, own vocabulary (build brief §4/§5): this package
shares no source with the CorpusMind (Text) product. Logic that both products
legitimately need (the stable statistics formulas) is forked here with its own
tests rather than imported across the boundary.
"""

__version__ = "0.3.2"
PRODUCT_NAME = "CorpusMind Lens"
API_VERSION = "1"  # X-CorpusMind-API-Version advertised by Companion Mode (§5)
