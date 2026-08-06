# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Session-wide pytest fixtures/setup.

Import numpy for real before anything else in the test session can import
`dspy`: dspy's `dspy.utils.lazy_import.require("numpy")` only returns the
real numpy module if numpy is already present in `sys.modules` at the exact
moment it is called; otherwise it installs a `_LazyModule` proxy whose first
attribute access re-execs numpy's own `__init__.py` in a second module
object, which recurses infinitely (`RecursionError`) under numpy 2.x. This
is a real, reproduced dspy/numpy interaction bug, not a defect in any
scikit-decide code -- conftest.py is loaded before any test module is
collected, so this import ordering guarantee holds regardless of which test
file first happens to import dspy.
"""

import numpy  # noqa: F401
