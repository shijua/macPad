"""Versioned translation profiles for MacWS's AIR-to-AIR compiler layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metal2MetalProfile:
    name: str
    source_family: str
    target_triple: str
    container_target: str
    target_major: int
    target_minor: int


DEFAULT_PROFILE = "ventura13-ios19-macabi"
IOS17_QUARTZCORE_PROFILE = "ventura13-ios165-macabi"
SONOMA_IOS17_PROFILE = "sonoma14-ios17-macabi"

PROFILES = {
    SONOMA_IOS17_PROFILE: Metal2MetalProfile(
        name=SONOMA_IOS17_PROFILE,
        source_family="macOS 14.0 Apple AIR",
        # Runtime-confirmed on 21A329: fixed_frag_lph_cpf specialization
        # accepts Sonoma's AIR 2.6 at this deployment target. The 16.5
        # target admits the library but specialization requires AIR 2.5.
        # Keep the source AIR version and shader semantics unchanged.
        target_triple="air64-apple-ios17.0.0-macabi",
        container_target="macabi",
        target_major=17,
        target_minor=0,
    ),
    "sonoma14-ios165-macabi": Metal2MetalProfile(
        name="sonoma14-ios165-macabi",
        source_family="macOS 14.0 Apple AIR",
        # Retained for reproducing the AIR 2.6/2.5 specialization rejection.
        target_triple="air64-apple-ios16.5.0-macabi",
        container_target="macabi",
        target_major=16,
        target_minor=5,
    ),
    DEFAULT_PROFILE: Metal2MetalProfile(
        name=DEFAULT_PROFILE,
        source_family="macOS 13.4 Apple AIR",
        # This is the runtime-confirmed Catalyst target used by the existing
        # iOS 16.3 MTLCompilerService bridge. It is deliberately not inferred
        # from the device OS marketing version.
        target_triple="air64-apple-ios19.0.0-macabi",
        container_target="macabi",
        target_major=19,
        target_minor=0,
    ),
    IOS17_QUARTZCORE_PROFILE: Metal2MetalProfile(
        name=IOS17_QUARTZCORE_PROFILE,
        source_family="macOS 13.4 Apple AIR",
        # On iOS 17.0 build 21A329, QuartzCore's default desktop-effects
        # functions are rejected at deployment target 16.6 while the
        # Catalyst runtime reports 16.5. This is an experiment; the
        # translated AIR and MTLB still reproduce the rejection, so do not
        # treat this profile as a fix.
        target_triple="air64-apple-ios16.5.0-macabi",
        container_target="macabi",
        target_major=16,
        target_minor=5,
    ),
}


def get_profile(name: str) -> Metal2MetalProfile:
    try:
        return PROFILES[name]
    except KeyError as error:
        raise ValueError(f"unknown metal2metal profile: {name}") from error
