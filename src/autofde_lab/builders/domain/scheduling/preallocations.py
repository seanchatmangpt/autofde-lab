# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

from autofde_lab.core import HookNotImplementedError

__all__ = ["WithPreallocations", "WithoutPreallocations"]


class WithPreallocations:
    """A domain must inherit this class if there are some pre-allocations to consider."""

    def _get_preallocations(
        self,
    ) -> dict[int, list[str]]:  # Enforced by the domain when it builds applicable actions.
        """
        Return a dictionary where the key is the id of a task (int)
        and the value indicates the pre-allocated resources for this task (as a list of str)"""
        raise HookNotImplementedError(self, "_get_preallocations")

    def get_preallocations(
        self,
    ) -> dict[int, list[str]]:  # Enforced by the domain when it builds applicable actions.
        """
        Return a dictionary where the key is the id of a task (int)
        and the value indicates the pre-allocated resources for this task (as a list of str)"""
        return self._get_preallocations()


class WithoutPreallocations(WithPreallocations):
    """A domain must inherit this class if there are no pre-allocations to consider."""

    def _get_preallocations(self) -> dict[int, list[str]]:
        return {}
