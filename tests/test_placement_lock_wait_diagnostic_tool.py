from tools.placement_lock_wait_diagnostic import classify


def _report(*, modes, transaction=0, tuples=0, depth=1, timeout=0, wait_ms=100):
    return {
        "queueObservation": {
            "pgrowlocksModes": modes,
            "maxBlockingChainDepth": depth,
        },
        "serverLockWaits": {
            "transactionSegmentCount": transaction,
            "tupleSegmentCount": tuples,
            "events": [{"reportedWaitMs": wait_ms}],
        },
        "errorsBySqlstate": {"55P03": timeout} if timeout else {},
    }


def test_classify_supported_requires_baseline_and_fk_dropped_counterfactual():
    legacy = _report(
        modes=["For Key Share", "For No Key Update"], transaction=4, depth=1
    )
    control = _report(modes=[], tuples=2, depth=3, timeout=2, wait_ms=504)
    verdict, reasons = classify(legacy, control)
    assert verdict == "HYPOTHESIS_SUPPORTED"
    assert "fkDroppedControlSignature=True" in reasons


def test_classify_contradicted_when_fk_drop_keeps_depth_one_without_tuple_timeout():
    legacy = _report(
        modes=["For Key Share", "For No Key Update"], transaction=4, depth=1
    )
    control = _report(modes=[], transaction=4, depth=1)
    assert classify(legacy, control)[0] == "HYPOTHESIS_CONTRADICTED"


def test_classify_not_observed_for_incomplete_baseline():
    legacy = _report(modes=["For Key Share"], transaction=0)
    control = _report(modes=[], tuples=2, depth=3, timeout=1, wait_ms=504)
    assert classify(legacy, control)[0] == "NOT_OBSERVED"
