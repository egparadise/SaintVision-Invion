"""One local file sampler for the CLI and challenge-bound Node observation."""

import os
from pathlib import Path
from saintvision.errors import InvError
from saintvision.services.verification import hash_file
from .readroot import ReadRoot


def check_sample(
    contribution, locations, sample, *, allowed_root, hash_reader=hash_file, max_bytes=None
):
    """Inspect only a configured root. Returning bytes is not Node attestation."""
    if type(sample) is not int or not 1 <= sample <= 1000:
        raise ValueError("invalid sample limit")
    if not isinstance(allowed_root, ReadRoot):
        raise ValueError("configured read root required")
    if Path(contribution.normalized_path) != allowed_root.path:
        raise ValueError("contribution differs from configured root")
    observations = []
    sampled = 0
    mismatches = []
    unverifiable = []
    for location in locations[:sample]:
        measured = {"locationId": location.location_id, "sha256": None, "byteSize": None}
        observations.append(measured)
        if not location.checksum_sha256:
            unverifiable.append(
                {"locationId": location.location_id, "reason": "no recorded checksum"}
            )
            continue
        sampled += 1
        relative = Path(location.relative_path)
        try:
            if relative.is_absolute() or relative.drive or ".." in relative.parts:
                raise ValueError("invalid relative path")
            observation = hash_reader(
                allowed_root.path / relative,
                allowed_root=allowed_root,
                os_type="windows" if os.name == "nt" else "linux",
                **({"max_bytes": max_bytes} if max_bytes is not None else {}),
            )
        except (InvError, OSError, ValueError):
            mismatches.append(
                {"locationId": location.location_id, "reason": "file unavailable or unsafe"}
            )
            continue
        measured.update(sha256=observation.sha256, byteSize=observation.byte_size)
        if not observation.matches(
            expected_sha256=location.checksum_sha256, expected_size=location.byte_size
        ):
            mismatches.append(
                {"locationId": location.location_id, "reason": "checksum or byte size differs"}
            )
    return {
        "observations": observations,
        "sampled": sampled,
        "mismatches": len(mismatches),
        "sampleHealthy": bool(sampled and not mismatches and not unverifiable),
        "detail": {
            "sampleLimit": sample,
            "mismatchDetail": mismatches,
            "unverifiable": unverifiable,
        },
    }
