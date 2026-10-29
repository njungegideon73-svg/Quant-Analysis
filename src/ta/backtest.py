"""M3 backtest engine (docs/02 §4-7): S1 episodes -> M1 fills and exits -> one setup per pair + portfolio limits.

resolve() works per pair and treats every episode as if it were the only order (its fill minute, exit and R do
not depend on anything else). portfolio() then replays all pairs on one clock and decides which of those fills
actually happen: one pending order or position per pair (the newest zone replaces a pending order), at most
`max_open` positions, and at most `max_ccy` positions with the same directional exposure to one currency.
"""
import heapq
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat

import numpy as np
import pandas as pd

from ta import s2, s4, s5
from ta.broker import M1, Costs, exit_trade, first_fill, trade_r
from ta.config import CFDS, DATA, PAIRS, pip_size
from ta.data.store import read_m1
from ta.registry import guard
from ta.strategy import Config, episodes, prepare_frames

PERIODS = {"research": (2010, 2019), "validation": (2020, 2023), "holdout": (2024, 2100)}  # docs/03 §1
CFD_PERIODS = {"research": (2014, 2020), "validation": (2021, 2023), "holdout": (2024, 2100)}  # docs/13 §8


def span(pair: str, period: str) -> tuple[int, int]:
    return (CFD_PERIODS if pair in CFDS else PERIODS)[period]

M15_NS = 15 * 60 * 10**9


def costs(pair: str, cfg: Config) -> Costs:
    return Costs.for_pair(pair, cfg.fill_through_pips, cfg.slip_pips, cfg.commission_per_lot, cfg.swap_pips)


def resolve(f: dict, m1: M1, cfg: Config) -> pd.DataFrame:
    """episodes() plus, for those that touch, the fill minute, exit and net R (standalone)."""
    minute = isinstance(cfg, (s2.S2Config, s5.S5Config))  # orders on M1: the episode carries times and fill minute
    if minute:
        ep = (s5 if isinstance(cfg, s5.S5Config) else s2).episodes(f, m1, cfg)
    else:
        ep = s4.episodes(f, cfg) if isinstance(cfg, s4.S4Config) else episodes(f, cfg)
    bar_ns = f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    c, recs = costs(f["pair"], cfg), []
    for r in ep.itertuples(index=False):
        rec = {"pair": f["pair"], "zone_ts": bar_ns[r.zone_t] + M15_NS, "place_ts": bar_ns[r.place_bar] + M15_NS,
               "end_ts": bar_ns[r.end_bar] + M15_NS, "fill_ts": -1, "exit_ts": -1, "reason": "no_fill"}
        if minute:
            rec |= {"zone_ts": r.zone_ns, "place_ts": r.place_ns, "end_ts": r.end_ns}
        if r.fill_bar >= 0:
            if minute:
                i = r.fill_min
            else:
                lo, hi = np.searchsorted(m1.ts, [bar_ns[r.fill_bar], bar_ns[r.fill_bar] + M15_NS])
                i = first_fill(m1, lo, hi, r.dir, r.entry, c)
            assert i >= 0, "M15 touch without an M1 fill: M15 and M1 data disagree"
            rec |= {"fill_ts": m1.ts[i], "reason": "open"}
            x = exit_trade(m1, i, r.dir, r.entry, r.stop, r.target, c, getattr(r, "flat_ns", 0))  # S3/S4: 17:00 UK
            if x is not None:
                j, reason, px = x
                rec |= {"exit_ts": m1.ts[j], "reason": reason, "exit_px": px} | trade_r(m1, i, j, r.dir, r.entry, r.stop, px, c)
        recs.append(rec)
    return pd.concat([ep, pd.DataFrame(recs, index=ep.index)], axis=1)


def portfolio(eps: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Replay every pair's episodes on one clock; returns eps with a `status` column (filled / rejected / ...)."""
    eps = eps.reset_index(drop=True)
    rank = {p: i for i, p in enumerate(PAIRS)}
    keys = list(zip(eps.zone_ts, eps.pair.map(rank)))  # ties: earliest-created zone, then fixed pair order
    q = []
    for k, r in enumerate(eps.itertuples(index=False)):
        q.append((r.end_ts, 0, keys[k], k, "end"))
        q.append((r.place_ts, 1, keys[k], k, "place"))
        if r.fill_ts >= 0:
            q.append((r.fill_ts, 2, keys[k], k, "fill"))  # a fill is processed before a same-minute exit (pessimistic)
    heapq.heapify(q)
    state = {p: {"pending": None, "position": None, "waiting": []} for p in eps.pair.unique()}
    status = np.full(len(eps), "not_placed", dtype=object)
    open_pos = {}
    while q:
        t, _, key, k, kind = heapq.heappop(q)
        r, P = eps.iloc[k], state[eps.pair.iat[k]]
        if kind == "end":
            if P["pending"] == k:
                P["pending"], status[k] = None, "cancelled"
        elif kind == "place":
            if P["position"] is not None:
                P["waiting"].append(k)
                status[k] = "blocked"
                continue
            old = P["pending"]
            if old is not None:
                if cfg.zone_pick == "extreme" and eps.leg.iat[old] == r.leg:
                    status[k] = "kept_older"
                    continue
                status[old] = "replaced"
            P["pending"], status[k] = k, "pending"
        elif kind == "fill":
            if P["pending"] != k:
                continue
            P["pending"] = None
            if _room(open_pos, r.pair, r.dir, cfg):
                open_pos[k] = (r.pair, r.dir)
                P["position"], status[k] = k, "filled"
                if r.exit_ts >= 0:
                    heapq.heappush(q, (r.exit_ts, 3, key, k, "exit"))
            else:
                status[k] = "rejected"
        elif kind == "exit":
            P["position"] = None
            del open_pos[k]
            close = (t // M15_NS + 1) * M15_NS  # waiting zones are re-placed at the close of the exit bar
            for w in P["waiting"]:
                if eps.end_ts.iat[w] > close and (eps.fill_ts.iat[w] < 0 or eps.fill_ts.iat[w] >= close):
                    heapq.heappush(q, (close, 1, keys[w], w, "place"))
            P["waiting"] = []
    return eps.assign(status=status)


def _room(open_pos: dict, pair: str, d: int, cfg: Config) -> bool:
    if len(open_pos) >= cfg.max_open:
        return False
    expo = [(p[:3], dd) for p, dd in open_pos.values()] + [(p[3:], -dd) for p, dd in open_pos.values()]
    return all(expo.count(x) < cfg.max_ccy for x in ((pair[:3], d), (pair[3:], -d)))


def load(pair: str, period: str, root=DATA):
    """M15, H4 and M1 for a period: everything from the first year (warm-up) up to the period's end, nothing after."""
    end = pd.Timestamp(f"{span(pair, period)[1] + 1}-01-01", tz="UTC")
    m15, h4 = (pd.read_parquet(root / "derived" / pair / f"{tf}.parquet") for tf in ("M15", "H4"))
    raw = read_m1(pair, years=range(2000, span(pair, period)[1] + 1), root=root)
    return m15[m15.close_ts <= end].reset_index(drop=True), h4[h4.close_ts <= end].reset_index(drop=True), \
        M1.from_frame(raw[raw.ts < end].sort_values("ts").reset_index(drop=True))


def pair_runs(pair: str, cfgs: list[Config], period: str) -> list[pd.DataFrame]:
    """resolve() for every config on one pair. Features only depend on a few params, so they are built once per
    distinct set (the Stage A grid needs 6 builds for 216 configs). Episodes are kept if their zone is in the period."""
    m15, h4, m1 = load(pair, period)
    start = pd.Timestamp(f"{span(pair, period)[0]}-01-01", tz="UTC").value
    feats, out = {}, []
    for cfg in cfgs:
        key = (cfg.N, cfg.k, cfg.m, cfg.zone_body, cfg.N_h4, cfg.session, cfg.liq_veto, cfg.pools, cfg.h1_bias)
        if key not in feats:
            feats[key] = prepare_frames(pair, m15, h4, cfg)
        r = resolve(feats[key], m1, cfg)
        out.append(r[r.zone_ts >= start].reset_index(drop=True))
    return out


def grid(cfgs: list[Config], pairs=PAIRS, period: str = "research", workers: int = 4, unlock_holdout=False):
    """All configs on all pairs, one worker per pair -> one portfolio-level episodes frame per config."""
    guard(period, [c.to_dict() for c in cfgs], unlock_holdout)
    with ProcessPoolExecutor(min(workers, len(pairs))) as ex:
        per_pair = list(ex.map(pair_runs, pairs, repeat(cfgs), repeat(period)))
    return [portfolio(pd.concat([pp[i] for pp in per_pair], ignore_index=True), c) for i, c in enumerate(cfgs)]


def run(cfg: Config, pairs=PAIRS, period: str = "research", unlock_holdout=False) -> pd.DataFrame:
    """Full S1 run: all episodes with their portfolio status. Trades are the rows with status == 'filled'."""
    return grid([cfg], pairs, period, unlock_holdout=unlock_holdout)[0]


def random_control(f: dict, m1: M1, cfg: Config, n: int = 3000, seed: int = 0, stop_atr: float = 1.5) -> pd.DataFrame:
    """docs/02 §6.6: market entries at random fillable M15 closes, random side, the same stop floor, rr target,
    exits and costs as S1. With no edge, mean R should be about -cost_R."""
    rng, pip, c = np.random.default_rng(seed), pip_size(f["pair"]), costs(f["pair"], cfg)
    bar_ns = f["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    ok = np.flatnonzero(f["fillable"][1:] & ~np.isnan(f["atr"][:-1]))  # entry in the next bar, which must be fillable
    rows = []
    for s in np.sort(rng.choice(ok, size=min(n, ok.size), replace=False)):
        d = int(rng.choice([1, -1]))
        i = int(np.searchsorted(m1.ts, bar_ns[s + 1]))
        if i >= len(m1.ts) - 1:
            continue
        entry = m1.ao[i] if d == 1 else m1.bo[i]
        dist = max(stop_atr * f["atr"][s], cfg.min_stop_pips * pip)
        stop, target = entry - d * dist, entry + d * cfg.rr * dist
        x = exit_trade(m1, i, d, entry, stop, target, c)
        if x is None:
            continue
        j, reason, px = x
        res = trade_r(m1, i, j, d, entry, stop, px, c)
        spread = m1.ao[i] - m1.bo[i]
        cost = spread + 2 * c.commission(entry) + ((stop - px) * d if reason == "stop" else c.slip if reason == "flat" else 0) + res["nights"] * c.swap
        rows.append({"bar": s, "dir": d, "reason": reason, "cost_R": cost / dist} | res)
    return pd.DataFrame(rows)
