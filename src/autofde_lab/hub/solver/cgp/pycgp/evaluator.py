# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from abc import ABC, abstractmethod


class Evaluator(ABC):
    """Contract for CGP fitness evaluators; subclasses must implement both methods."""

    @abstractmethod
    def evaluate(self, cgp, it):
        """Return the fitness of individual `cgp` at iteration `it`."""

    @abstractmethod
    def clone(self):
        """Return an independent copy usable from another worker."""
