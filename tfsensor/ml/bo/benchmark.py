"""P1 kill-switch: leave-one-POSITION-out grouped-CV on the 84-variant scan.

Can a GP on transferable physchem features rediscover the known wet-lab leads
under an honest position-held-out split, beat an additive baseline, and stay
calibrated? If not, STOP — the surrogate can't rank multi-mutants (panel must-fix #1).

Run with an env that has scikit-learn (e.g. ~/.conda/envs/TF_agent_env):
    PYTHONPATH=. ~/.conda/envs/TF_agent_env/bin/python -m tfsensor.ml.bo.benchmark
"""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from tfsensor.ml.bo import seed, physchem


def _gp():
    k = ConstantKernel(1.0) * Matern(length_scale=1.0, nu=2.5) + WhiteKernel(0.1)
    return GaussianProcessRegressor(kernel=k, normalize_y=True, alpha=1e-6,
                                    n_restarts_optimizer=2, random_state=0)


def _build_X(variants, muts, mode):
    """mode: 'physchem' | 'esm' | 'concat'. Returns (X, keep_idx) — keep_idx drops
    variants missing an ESM embedding (esm/concat only)."""
    Xp = physchem.featurize_many(muts)
    keep = list(range(len(variants)))
    if mode == "physchem":
        return Xp, keep
    from tfsensor.ml.features.esm_embed import load_cache
    cache = load_cache()
    keep = [i for i, v in enumerate(variants) if v in cache]
    Xe = np.vstack([cache[variants[i]] for i in keep])
    if mode == "esm":
        return Xe, keep
    return np.hstack([Xp[keep], Xe]), keep      # concat


def lopo(target, offtargets=None, mode="physchem"):
    variants, muts, y = seed.objective_table(target, offtargets)
    X, keep = _build_X(variants, muts, mode)
    variants = [variants[i] for i in keep]; muts = [muts[i] for i in keep]
    y = np.array([y[i] for i in keep])
    pos = [m[0][1] if m else None for m in muts]            # held-out group key
    groups = sorted({p for p in pos if p is not None})

    gp_pred = np.full(len(y), np.nan); gp_std = np.full(len(y), np.nan)
    add_pred = np.full(len(y), np.nan)
    for g in groups:
        te = [i for i, p in enumerate(pos) if p == g]
        tr = [i for i, p in enumerate(pos) if p != g]
        sc = StandardScaler().fit(X[tr])
        Xtr, Xte = sc.transform(X[tr]), sc.transform(X[te])
        gp = _gp().fit(Xtr, y[tr])
        mu, sd = gp.predict(Xte, return_std=True)
        gp_pred[te], gp_std[te] = mu, sd
        add_pred[te] = Ridge(alpha=1.0).fit(Xtr, y[tr]).predict(Xte)

    m = ~np.isnan(gp_pred)
    rng = np.random.default_rng(0)
    rho_gp = spearmanr(y[m], gp_pred[m]).statistic
    rho_add = spearmanr(y[m], add_pred[m]).statistic
    rho_rnd = np.mean([spearmanr(y[m], rng.permutation(y[m])).statistic
                       for _ in range(50)])
    # calibration: held-out coverage of GP intervals
    z = np.abs(y[m] - gp_pred[m]) / np.maximum(gp_std[m], 1e-6)
    cov80, cov95 = np.mean(z <= 1.28), np.mean(z <= 1.96)
    # rediscovery: predicted percentile of each known lead among held-out variants
    order = {v: r / (m.sum() - 1) for r, v in
             enumerate(np.array(variants)[m][np.argsort(gp_pred[m])])}
    leads = {lead: round(order.get(lead, float("nan")), 3)
             for lead in seed.KNOWN_LEADS.get(target, [])}
    return {"target": target, "n": int(m.sum()), "n_positions": len(groups),
            "rho_gp": round(float(rho_gp), 3), "rho_additive": round(float(rho_add), 3),
            "rho_random": round(float(rho_rnd), 3),
            "cov80": round(float(cov80), 2), "cov95": round(float(cov95), 2),
            "lead_percentiles": leads}


def _main():
    print("=== P1 leave-one-position-out grouped-CV — feature ablation ===")
    for tgt in ("testosterone", "cortisol"):
        print(f"\n## {tgt}")
        for mode in ("physchem", "esm", "concat"):
            r = lopo(tgt, mode=mode)
            print(f"  [{mode:8s}] n={r['n']:2d}  GP_rho={r['rho_gp']:+.2f}  "
                  f"add={r['rho_additive']:+.2f}  rnd={r['rho_random']:+.2f}  "
                  f"cov80={r['cov80']}  leads={r['lead_percentiles']}")
    print("\nPASS: a mode's GP_rho clearly >0 and > additive, leads near 1.0. "
          "Else no learned surrogate is viable -> oracles + wet-lab diagnostic only.")


if __name__ == "__main__":
    _main()
