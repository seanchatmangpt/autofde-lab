"""Re-export of the canonical PTD economics; the guarded implementation lives in ``autofde_lab.ptd.metrics``."""
from autofde_lab.ptd.metrics import ptd_advantage, ptd_efficiency, regeneration_advantage

__all__ = ["ptd_advantage", "ptd_efficiency", "regeneration_advantage"]
