"""Typed errors for configurations the stable-baselines bindings do not support."""


class UnsupportedConfigurationError(NotImplementedError):
    """Raised when an unsupported configuration (vectorization, memory optimization,
    observation space...) is requested. Subclasses NotImplementedError for callers
    that already catch it, but is a distinct, typed contract."""
