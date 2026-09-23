"""Strict downgrade prevention (§76).

Raises UnsupportedProfileError / UNSUPPORTED_PROFILE when an agent attempts
to negotiate an unsupported, deprecated, or lower-security profile.
"""

from __future__ import annotations


class UnsupportedProfileError(ValueError):
    """Raised when an unsupported or downgraded profile is encountered (§76)."""

    def __init__(self, message: str, profile: str | None = None) -> None:
        super().__init__(message)
        self.profile = profile
        self.code = "UNSUPPORTED_PROFILE"


class DowngradeGuard:
    """Strict guard asserting admitted profile standards (§76)."""

    def __init__(
        self, admitted_profiles: tuple[str, ...] = ("SA2A-PROFILE-v26.9.16",)
    ) -> None:
        self.admitted_profiles = frozenset(admitted_profiles)

    def assert_supported_profile(self, profile: str) -> None:
        """Verify that the requested profile is among admitted profiles; fail closed on downgrade."""
        if profile not in self.admitted_profiles:
            raise UnsupportedProfileError(
                f"Requested profile '{profile}' is not admitted. "
                f"Strict downgrade prevention (§76) refusing execution. Expected one of: {sorted(self.admitted_profiles)}",
                profile=profile,
            )

    def check_downgrade(
        self, proposed_profile: str, minimum_profile: str = "SA2A-PROFILE-v26.9.16"
    ) -> None:
        """Disallow any downgrade below minimum required profile."""
        if (
            proposed_profile != minimum_profile
            and proposed_profile not in self.admitted_profiles
        ):
            raise UnsupportedProfileError(
                f"Profile downgrade to '{proposed_profile}' blocked (§76). Minimum required: '{minimum_profile}'.",
                profile=proposed_profile,
            )
