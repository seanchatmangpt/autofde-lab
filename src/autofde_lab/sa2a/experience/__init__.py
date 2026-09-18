"""MachineExperience compilation, admission, qualification and known-route lookup.

v26.9.17 PRD §6.7-6.10, ARD §5.7-5.8, §12, §17-19: the layer that turns an admitted
Episode 1 solution into reusable, admitted, qualified machinery a fresh Episode 2 can
route to via semantic classification -- never via prompt/string similarity, and never
via "successful Episode 1 -> automatically KNOWN" (that shortcut is the one this
package exists to refuse; see compiler.py and admission.py docstrings).
"""

from __future__ import annotations

from autofde_lab.sa2a.experience.types import ExperienceState, MachineExperience

__all__ = ["ExperienceState", "MachineExperience"]
