"""M4 (docs/03 §2, §4): Stage A research results, the candidate selection rule, and the internal walk-forward.

Per config (all 7 pairs pooled, 2010-2019): trades, win rate, EV (mean net R), profit factor, pairs positive.
Neighbourhood score = median EV of the config and its ±1-step neighbours in N, m, b, K (same entry_at, target).
Eligible: every one of those neighbours EV > 0, >= MIN_TRADES trades, EV > 0 on >= 5/7 pairs.
Walk-forward: train 4 years -> test the next, 2014..2019; the rule picks on train only (trade minimum pro rata).
"""
import json

import numpy as np
import pandas as pd

from ta.config import REPORTS, ROOT
from ta.registry import rows

GRID = {"N": (2, 3, 5), "m": (1.0, 1.5), "b": (0.05, 0.10, 0.20), "K": (48, 96, 192)}
MIN_TRADES, MIN_PAIRS, YEARS = 300, 5, 10


def load(note: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(configs, trades) for the registry rows with this note; trades carry a config `key` and fill `year`."""
    cfgs, out = [], []
    for r in rows():
        if r["note"] != note or r["period"] != "research":
            continue
        c = json.loads(r["config"])
        key = (c["N"], c["m"], c["b"], c["K"], c["entry_at"], c["target"])
        e = pd.read_parquet(ROOT / "runs" / r["run_id"] / "episodes.parquet", columns=["status", "exit_ts", "fill_ts", "pair", "R"])
        t = e[(e.status == "filled") & (e.exit_ts >= 0)]
        out.append(pd.DataFrame({"key": [key] * len(t), "pair": t.pair.to_numpy(), "R": t.R.to_numpy(),
                                 "year": pd.to_datetime(t.fill_ts, utc=True).dt.year.to_numpy()}))
        cfgs.append({"key": key, "run_id": r["run_id"], "config_hash": r["config_hash"]})
    if len(cfgs) != 216:
        raise SystemExit(f"expected the 216 Stage A configs for note {note!r}, found {len(cfgs)}")
    return pd.DataFrame(cfgs), pd.concat(out, ignore_index=True)


def stats(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby("key").R
    s = pd.DataFrame({"trades": g.size(), "win_rate": g.apply(lambda r: (r > 0).mean()), "ev": g.mean(),
                      "pf": g.apply(lambda r: r[r > 0].sum() / -r[r <= 0].sum() if (r <= 0).any() else np.inf)})
    s["pairs_pos"] = (t.groupby(["key", "pair"]).R.mean() > 0).groupby("key").sum()
    return s


def neighbours(key) -> list:
    """The config plus every grid point one step away in one numeric param (same entry_at, target)."""
    out = [key]
    for i, vals in enumerate(GRID.values()):
        k = vals.index(key[i])
        for j in (k - 1, k + 1):
            if 0 <= j < len(vals):
                out.append(key[:i] + (vals[j],) + key[i + 1:])
    return out


def select(s: pd.DataFrame, min_trades: int) -> pd.DataFrame:
    """Adds nbhd_score and eligible (docs/03 §4) to per-config stats."""
    s = s.copy()
    ev = s.ev.to_dict()
    nb = {k: [ev.get(n, np.nan) for n in neighbours(k)] for k in s.index}
    s["nbhd_score"] = [np.nanmedian(nb[k]) for k in s.index]
    s["nbhd_all_pos"] = [all(v > 0 for v in nb[k]) for k in s.index]  # a missing neighbour (no trades) is not > 0
    s["eligible"] = s.nbhd_all_pos & (s.trades >= min_trades) & (s.pairs_pos >= MIN_PAIRS)
    return s


def picks(s: pd.DataFrame) -> dict:
    """Highest neighbourhood score among eligible configs, per target type (None if nothing is eligible)."""
    out = {}
    for tgt in ("T1", "T2"):
        e = s[s.eligible & (s.index.map(lambda k: k[5]) == tgt)]
        out[tgt] = e.nbhd_score.idxmax() if len(e) else None
    return out


def walk_forward(t: pd.DataFrame) -> pd.DataFrame:
    """Per test year and target type: the config picked on the 4 train years and its test-year trades."""
    rows_ = []
    for y in range(2014, 2020):
        train = t[t.year.between(y - 4, y - 1)]
        s = select(stats(train), round(MIN_TRADES * 4 / YEARS))
        for tgt, k in picks(s).items():
            test = t[(t.year == y) & (t.key == k)] if k is not None else t.iloc[:0]
            rows_.append({"test_year": y, "target": tgt, "pick": k, "test_trades": len(test), "test_R": test.R.sum(),
                          "test_ev": test.R.mean() if len(test) else np.nan})
    return pd.DataFrame(rows_)


def run(note: str) -> str:
    cfgs, t = load(note)
    s = select(stats(t), MIN_TRADES)
    s.join(cfgs.set_index("key")).sort_values("nbhd_score", ascending=False).to_csv(REPORTS / "m4_stage_a.csv")
    wf = walk_forward(t)
    wf.to_csv(REPORTS / "m4_walk_forward.csv", index=False)
    p = picks(s)
    lines = [f"{len(s)} configs, {len(t)} research trades (2010-2019, 7 pairs)",
             f"configs with EV > 0: {(s.ev > 0).sum()}  eligible (§4): {s.eligible.sum()}",
             f"EV across configs: median {s.ev.median():+.3f}R, best {s.ev.max():+.3f}R, worst {s.ev.min():+.3f}R"]
    for tgt, k in p.items():
        lines.append(f"pick {tgt}: " + ("none eligible" if k is None else
                     f"{k} -> {s.loc[[k], ['trades', 'win_rate', 'ev', 'pf', 'pairs_pos', 'nbhd_score']].round(3).to_dict('records')[0]}"))
    for tgt in ("T1", "T2"):
        w = wf[wf.target == tgt]
        n = w.test_trades.sum()
        lines.append(f"walk-forward {tgt}: {n} test trades, EV {w.test_R.sum() / n if n else float('nan'):+.3f}R "
                     f"({(w.pick.isna()).sum()} of 6 folds had no eligible config)")
    return "\n".join(lines + [f"-> {REPORTS / 'm4_stage_a.csv'}, {REPORTS / 'm4_walk_forward.csv'}"])
