"""S3 rules (docs/09): the first London bar (07:00-11:45 UK) that trades beyond the Asia range (01:00-06:45 UK)
and closes back inside is the sweep; the entry is S2's M1 BOS + zone + limit (s2.episodes), filled by 12:00 UK,
target 3R (T1) or the opposite side of Asia (Tasia, if >= 3R), flat at 17:00 UK.
"""
from dataclasses import dataclass
from itertools import product
from typing import ClassVar

import pandas as pd

from ta.s2 import S2Config
from ta.strategy import LDN


@dataclass(frozen=True)
class S3Config(S2Config):
    pools: ClassVar[bool] = False  # the liquidity is the Asia range, not equal highs/lows
    strategy: str = "S3"
    min_stop_pips: float = 5.0  # docs/09 §7: S1/S2's 15 pips skips 85% of S3 zones

    def sweeps(self, f: dict) -> pd.DataFrame:
        return asia_sweeps(f)


def grid() -> list[S3Config]:
    """The frozen S3 grid (docs/09 §5): 8 configs."""
    return [S3Config(W=w, entry_at=e, target=t) for w, e, t in product((4, 8), ("proximal", "mid"), ("T1", "Tasia"))]


def asia_sweeps(f: dict) -> pd.DataFrame:
    """docs/09 §1-2, one row per UK day with a sweep: bar `s`, trade dir `d`, `opp` (the other side of Asia),
    `noon_ns` (12:00 UK, fill deadline) and `flat_ns` (17:00 UK, time exit). A close beyond (break) or a bar
    beyond both sides gives nothing that day: only the first side taken counts."""
    ldn = f["ts"].dt.tz_convert(LDN)
    hr = ldn.dt.hour.to_numpy()
    bars = pd.DataFrame({"day": ldn.dt.date.to_numpy(), "h": f["h"], "l": f["l"], "c": f["c"]})
    asia = bars[(hr >= 1) & (hr < 7)].groupby("day").agg(hi=("h", "max"), lo=("l", "min"))
    lon = bars[(hr >= 7) & (hr < 12)].join(asia, on="day", how="inner")
    lon = lon[(lon.h > lon.hi) | (lon.l < lon.lo)]
    rows = []
    for s, r in lon[~lon.day.duplicated()].iterrows():
        up = r.h > r.hi
        if up and r.l < r.lo or (r.c > r.hi if up else r.c < r.lo):
            continue
        noon, flat = (pd.Timestamp(f"{r.day} {t}", tz=LDN).value for t in ("12:00", "17:00"))
        rows.append((s, -1 if up else 1, r.lo if up else r.hi, noon, flat))
    return pd.DataFrame(rows, columns=["s", "d", "opp", "noon_ns", "flat_ns"])
