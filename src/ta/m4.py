"""M4 (docs/03 §2, §4): Stage A research results, the candidate selection rule, and the internal walk-forward.

Per config (all 7 pairs pooled, 2010-2019): trades, win rate, EV (mean net R), profit factor, pairs positive.
Neighbourhood score = median EV of the config and its ±1-step neighbours in N, m, b, K (same entry_at, target).
Eligible: every one of those neighbours EV > 0, >= MIN_TRADES trades, EV > 0 on >= 5/7 pairs.
Walk-forward: train 4 years -> test the next, 2014..2019; the rule picks on train only (trade minimum pro rata).
S5 (docs/13 §8): each instrument alone, 2014-2020, positive years (>= 5/7; 3/4 in a fold) replace positive pairs.
"""
import json
import math

import numpy as np
import pandas as pd

from ta.config import REPORTS, ROOT
from ta.registry import rows

GRID = {"N": (2, 3, 5), "m": (1.0, 1.5), "b": (0.05, 0.10, 0.20), "K": (48, 96, 192)}
STAGES = {"A": (GRID, 216, "m4_stage_a"), "S2": ({"W": (8, 24)}, 4, "m4_s2"), "S3": ({"W": (4, 8)}, 8, "m4_s3"),
          "S4": ({"b": (0.1, 0.25, 0.5)}, 12, "m4_s4"), "S5": ({"orb": (5, 15, 30)}, 12, "m4_s5")}
TARGETS = {"A": ("T1", "T2"), "S2": ("T1",), "S3": ("T1", "Tasia"), "S4": ("T1", "time"), "S5": ("T1", "close")}  # numeric grid, configs, report name
MIN_TRADES, MIN_PAIRS, YEARS = 300, 5, 10


def load(note: str, grid=GRID, expected=216) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(configs, trades) for the registry rows with this note; trades carry a config `key` and fill `year`."""
    cfgs, out = [], []
    latest = {r["config_hash"]: r for r in rows() if r["note"] == note and r["period"] == "research"}  # repeat runs: last
    for r in latest.values():
        c = json.loads(r["config"])
        extra = tuple(c[x] for x in ("h1", "instrument", "bias") if x in c)  # S4/S5 switches; target stays last
        key = tuple(c[p] for p in grid) + extra + (c.get("entry", c["entry_at"]), c["target"])  # S4 names its entry `entry`
        e = pd.read_parquet(ROOT / "runs" / r["run_id"] / "episodes.parquet", columns=["status", "exit_ts", "fill_ts", "pair", "R"])
        t = e[(e.status == "filled") & (e.exit_ts >= 0)]
        out.append(pd.DataFrame({"key": [key] * len(t), "pair": t.pair.to_numpy(), "R": t.R.to_numpy(),
                                 "year": pd.to_datetime(t.fill_ts, utc=True).dt.year.to_numpy()}))
        cfgs.append({"key": key, "run_id": r["run_id"], "config_hash": r["config_hash"]})
    if len(cfgs) != expected:
        raise SystemExit(f"expected {expected} configs for note {note!r}, found {len(cfgs)}")
    return pd.DataFrame(cfgs), pd.concat(out, ignore_index=True)


def stats(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby("key").R
    s = pd.DataFrame({"trades": g.size(), "win_rate": g.apply(lambda r: (r > 0).mean()), "ev": g.mean(),
                      "pf": g.apply(lambda r: r[r > 0].sum() / -r[r <= 0].sum() if (r <= 0).any() else np.inf)})
    s["pairs_pos"] = (t.groupby(["key", "pair"]).R.mean() > 0).groupby("key").sum()
    s["years_pos"] = (t.groupby(["key", "year"]).R.mean() > 0).groupby("key").sum()
    return s


def neighbours(key, grid=GRID) -> list:
    """The config plus every grid point one step away in one numeric param (same entry_at, target)."""
    out = [key]
    for i, vals in enumerate(grid.values()):
        k = vals.index(key[i])
        for j in (k - 1, k + 1):
            if 0 <= j < len(vals):
                out.append(key[:i] + (vals[j],) + key[i + 1:])
    return out


def select(s: pd.DataFrame, min_trades: int, grid=GRID, by="pairs_pos", min_pos=MIN_PAIRS) -> pd.DataFrame:
    """Adds nbhd_score and eligible (docs/03 §4) to per-config stats."""
    s = s.copy()
    ev = s.ev.to_dict()
    nb = {k: [ev.get(n, np.nan) for n in neighbours(k, grid)] for k in s.index}
    s["nbhd_score"] = [np.nanmedian(nb[k]) for k in s.index]
    s["nbhd_all_pos"] = [all(v > 0 for v in nb[k]) for k in s.index]  # a missing neighbour (no trades) is not > 0
    s["eligible"] = s.nbhd_all_pos & (s.trades >= min_trades) & (s[by] >= min_pos)
    return s


def picks(s: pd.DataFrame, targets=("T1", "T2")) -> dict:
    """Highest neighbourhood score among eligible configs, per target type (None if nothing is eligible)."""
    out = {}
    for tgt in targets:
        e = s[s.eligible & (s.index.map(lambda k: k[-1]) == tgt)]
        out[tgt] = e.nbhd_score.idxmax() if len(e) else None
    return out


def walk_forward(t: pd.DataFrame, grid=GRID, targets=("T1", "T2"), span=(2010, 2019), by="pairs_pos") -> pd.DataFrame:
    """Per test year and target type: the config picked on the 4 train years and its test-year trades."""
    rows_, years = [], span[1] - span[0] + 1
    min_pos = MIN_PAIRS if by == "pairs_pos" else math.ceil(MIN_PAIRS / 7 * 4)  # 5/7 years -> 3 of 4 train years
    for y in range(span[0] + 4, span[1] + 1):
        train = t[t.year.between(y - 4, y - 1)]
        s = select(stats(train), round(MIN_TRADES * 4 / years), grid, by, min_pos)
        for tgt, k in picks(s, targets).items():
            test = t[(t.year == y) & (t.key == k)] if k is not None else t.iloc[:0]
            rows_.append({"test_year": y, "target": tgt, "pick": k, "test_trades": len(test), "test_R": test.R.sum(),
                          "test_ev": test.R.mean() if len(test) else np.nan})
    return pd.DataFrame(rows_)


def run(note: str, stage: str = "A") -> str:
    grid, expected, name = STAGES[stage]
    cfgs, t = load(note, grid, expected)
    if stage != "S5":
        return report(cfgs, t, grid, TARGETS[stage], name, "2010-2019, 7 pairs", (2010, 2019), "pairs_pos")
    ins = len(grid)  # the key is (orb, instrument, bias, entry, target)
    return "\n\n".join(report(cfgs[cfgs.key.str[ins] == i], t[t.key.str[ins] == i], grid,
                               TARGETS[stage], f"{name}_{i}", i + ", 2014-2020", (2014, 2020), "years_pos")
                        for i in sorted({k[ins] for k in cfgs.key}))


def report(cfgs, t, grid, targets, name, what, span, by) -> str:
    s = select(stats(t), MIN_TRADES, grid, by)
    out, wf_out = REPORTS / f"{name}.csv", REPORTS / f"{name}_walk_forward.csv".replace("_stage_a", "")
    s.join(cfgs.set_index("key")).sort_values("nbhd_score", ascending=False).to_csv(out)
    wf = walk_forward(t, grid, targets, span, by)
    wf.to_csv(wf_out, index=False)
    p = picks(s, targets)
    lines = [f"{len(s)} configs, {len(t)} research trades ({what})",
             f"configs with EV > 0: {(s.ev > 0).sum()}  eligible (§4): {s.eligible.sum()}",
             f"EV across configs: median {s.ev.median():+.3f}R, best {s.ev.max():+.3f}R, worst {s.ev.min():+.3f}R"]
    for tgt, k in p.items():
        lines.append(f"pick {tgt}: " + ("none eligible" if k is None else
                     f"{k} -> {s.loc[[k], ['trades', 'win_rate', 'ev', 'pf', by, 'nbhd_score']].round(3).to_dict('records')[0]}"))
    for tgt in wf.target.unique():
        w = wf[wf.target == tgt]
        n = w.test_trades.sum()
        lines.append(f"walk-forward {tgt}: {n} test trades, EV {w.test_R.sum() / n if n else float('nan'):+.3f}R "
                     f"({(w.pick.isna()).sum()} of {len(w)} folds had no eligible config)")
    return "\n".join(lines + [f"-> {out}, {wf_out}"])
