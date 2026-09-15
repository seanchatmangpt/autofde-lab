"""CMCA (Chatman Multifractal Cascade Allocation) module for AutoFDE Lab Vision 2030."""

from .atomvm_schedule import generate_atomvm_cmca_module
from .cascade import MultifractalCascadeAllocator
from .contracts import (
    AllocationReceipt,
    AllocationStanding,
    BranchAllocation,
    CandidateBranch,
    CascadeAllocationPlan,
    ResourceBudget,
)
from .dfcm_bridge import (
    build_candidate_branches_from_dfcm,
    compute_option_entropy,
)
from .scheduler import CMCAScheduler

__all__ = [
    "AllocationReceipt",
    "AllocationStanding",
    "BranchAllocation",
    "CMCAScheduler",
    "CandidateBranch",
    "CascadeAllocationPlan",
    "MultifractalCascadeAllocator",
    "ResourceBudget",
    "build_candidate_branches_from_dfcm",
    "compute_option_entropy",
    "generate_atomvm_cmca_module",
]
