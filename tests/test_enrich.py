"""Offline test for the liquidity math — no network."""

from letf.enrich import compute_adv

DAY1 = {"NVDL": (50.0, 1_000_000), "TQQQ": (60.0, 2_000_000)}
DAY2 = {"NVDL": (55.0, 2_000_000)}  # TQQQ didn't trade / missing this day


def test_average_over_days_present():
    adv = compute_adv([DAY1, DAY2], {"NVDL", "TQQQ", "GHOST"})
    # NVDL: (50*1M + 55*2M)/2 = 80M
    assert adv["NVDL"] == 80_000_000
    # TQQQ: only day1 -> 120M (averaged over days it actually traded)
    assert adv["TQQQ"] == 120_000_000
    # never seen -> None, not zero (no data is not the same as no volume)
    assert adv["GHOST"] is None


def test_empty_days():
    assert compute_adv([], {"NVDL"}) == {"NVDL": None}
