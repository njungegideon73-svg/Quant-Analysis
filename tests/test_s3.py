from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
from test_s2 import bearish, build

from ta.backtest import resolve
from ta.s2 import episodes
from ta.s3 import S3Config, asia_sweeps, grid


def day(date, london=None):
    """One UTC day of M15 bars around 1.1000; Asia (01:00-07:00 UK) spans 1.0980-1.1020. london: {UK 'HH:MM': (h, l, c)}."""
    ts = pd.Series(pd.date_range(f"{date} 00:00", periods=96, freq="15min", tz="UTC"))
    h, l, c = np.full(96, 1.1005), np.full(96, 1.0995), np.full(96, 1.1000)
    uk = ts.dt.tz_convert("Europe/London")
    asia = ((uk.dt.hour >= 1) & (uk.dt.hour < 7)).to_numpy()
    h[np.flatnonzero(asia)[3]], l[np.flatnonzero(asia)[5]] = 1.1020, 1.0980
    for t, (hh, ll, cc) in (london or {}).items():
        i = int(np.flatnonzero(uk.dt.strftime("%H:%M") == t)[0])
        h[i], l[i], c[i] = hh, ll, cc
    return {"ts": ts, "h": h, "l": l, "c": c}


def test_asia_sweep_first_side_only_and_uk_clock():
    sw = asia_sweeps(day("2024-01-09", {"08:00": (1.1025, 1.1001, 1.1015)}))
    assert sw[["d", "opp"]].values.tolist() == [[-1, 1.0980]]
    assert sw.noon_ns[0] == pd.Timestamp("2024-01-09 12:00", tz="UTC").value  # GMT in winter
    summer = asia_sweeps(day("2024-07-09", {"08:00": (1.1025, 1.1001, 1.1015)}))
    assert summer.flat_ns[0] == pd.Timestamp("2024-07-09 16:00", tz="UTC").value  # 17:00 BST
    assert asia_sweeps(day("2024-01-09", {"08:00": (1.1025, 1.1001, 1.1022)})).empty  # close beyond: a break
    first_break = {"07:30": (1.1004, 1.0975, 1.0978), "08:00": (1.1025, 1.1001, 1.1015)}
    assert asia_sweeps(day("2024-01-09", first_break)).empty  # the low broke first: no trade that day
    assert asia_sweeps(day("2024-01-09", {"08:00": (1.1025, 1.0975, 1.1000)})).empty  # both sides in one bar
    assert asia_sweeps(day("2024-01-09", {"12:00": (1.1025, 1.1001, 1.1015)})).empty  # after the London window


def fixed(opp, noon_min, flat_min):
    """S3 on the S2 fixture (sweep bar 4, short at 1.1038, stop 1.1061, fill minute 200) with chosen S3 times."""
    f, m1 = build(*bearish())

    @dataclass(frozen=True)
    class Fixed(S3Config):
        def sweeps(self, f_):
            return pd.DataFrame({"s": [4], "d": [-1], "opp": [opp], "noon_ns": [m1.ts[noon_min]],
                                 "flat_ns": [m1.ts[flat_min] if flat_min else 0]})
    return f, m1, Fixed


def test_tasia_target_needs_3r():
    f, m1, C = fixed(1.0900, 400, 0)
    assert episodes(f, m1, C(target="Tasia")).target[0] == 1.0900
    f, m1, C = fixed(1.1000, 400, 0)  # 38 pips short of 3R (69)
    assert episodes(f, m1, C(target="Tasia")).empty
    assert episodes(f, m1, C(target="T1")).target[0] == pytest.approx(1.1038 - 3 * 0.0023)


def test_noon_deadline_cancels_and_late_zones_never_place():
    f, m1, C = fixed(1.0900, 150, 0)
    ep = episodes(f, m1, C())
    assert (ep.end_ns[0], ep.fill_min[0]) == (m1.ts[150], -1)
    f, m1, C = fixed(1.0900, 60, 0)  # deadline before the zone forms (minute 77)
    assert episodes(f, m1, C()).empty


def test_time_exit_at_17_uk():
    f, m1, C = fixed(1.0900, 400, 210)
    r = resolve(f, m1, C()).iloc[0]
    assert (r.fill_ts, r.exit_ts, r.reason) == (m1.ts[200], m1.ts[210], "flat")


def test_grid_is_the_frozen_8():
    g = grid()
    assert len(set(g)) == 8 and all(c.min_stop_pips == 5.0 and c.strategy == "S3" for c in g)
    assert {c.target for c in g} == {"T1", "Tasia"} and {c.W for c in g} == {4, 8}
