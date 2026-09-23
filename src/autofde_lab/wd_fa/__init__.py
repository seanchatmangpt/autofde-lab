"""WD failure-analysis candidate reasoning surface.

This package computes candidate hypotheses, process evidence and replayable
analytical state. It has no production actuation path.
"""

from .domain import CandidateTriage, FailureCase, FailureModeRule, Standing, WorkOrder
from .triage import triage

__all__ = [
    "CandidateTriage",
    "FailureCase",
    "FailureModeRule",
    "Standing",
    "WorkOrder",
    "triage",
]
