"""The unit conversion, on its own.

These run without a database because the property they check is arithmetic, and
arithmetic that decides where work runs deserves to be checked where nothing
else can be blamed for the result.
"""

from __future__ import annotations

import pytest

from saintvision.errors import InvError
from saintvision.units import CANONICAL_UNIT, canonical_unit, format_quantity, to_canonical


def test_every_kind_has_exactly_one_canonical_unit():
    """The table is the contract. A kind missing from it has no comparable unit."""
    assert CANONICAL_UNIT == {
        "cpu": "millicores",
        "ram": "bytes",
        "disk": "bytes",
        "gpu": "devices",
    }


def test_binary_and_decimal_prefixes_are_not_the_same():
    """GB is 10^9 and GiB is 2^30 — a 7% gap that decides whether a shard fits."""
    assert to_canonical("ram", 1, "GB") == 1_000_000_000
    assert to_canonical("ram", 1, "GiB") == 1_073_741_824


def test_a_quarter_core_survives_conversion():
    """The reason CPU is stored in millicores rather than cores."""
    assert to_canonical("cpu", 0.25, "cores") == 250


def test_the_same_capacity_reported_two_ways_converges():
    """The whole point: two nodes measuring differently become comparable."""
    assert to_canonical("ram", 32, "GiB") == to_canonical("ram", 32768, "MiB")


def test_an_unrecognised_unit_is_refused_rather_than_guessed():
    with pytest.raises(InvError) as excinfo:
        to_canonical("ram", 4, "blocks")
    assert "not a recognised unit" in excinfo.value.message


def test_a_unit_from_the_wrong_kind_is_refused():
    """"cores" is a real unit, and it is not a real unit of memory."""
    with pytest.raises(InvError):
        to_canonical("ram", 4, "cores")


def test_a_quantity_finer_than_the_canonical_unit_is_refused():
    """Truncating here would turn a 1.5-core offer into 1 and never say so."""
    with pytest.raises(InvError):
        to_canonical("cpu", 0.0004, "cores")


def test_a_negative_quantity_is_refused():
    with pytest.raises(InvError):
        to_canonical("ram", -1, "bytes")


def test_an_unknown_kind_is_refused():
    with pytest.raises(InvError):
        to_canonical("quantum", 1, "qubits")
    with pytest.raises(InvError):
        canonical_unit("quantum")


def test_a_formatted_quantity_carries_its_unit():
    """A bare number in a response is a number a consumer has to guess about."""
    assert format_quantity("ram", 1024) == {"value": 1024, "unit": "bytes"}
