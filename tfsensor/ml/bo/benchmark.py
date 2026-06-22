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


def lopo(target, offtargets=None):
    variants, muts, y = seed.objective_table(target, offtargets)
    X = physchem.featurize_many(muts)
    y = np.array(y)
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
    print("=== P1 leave-one-position-out grouped-CV (physchem features) ===")
    for tgt in ("testosterone", "cortisol"):
        r = loho = lopo(tgt)
        print(f"\n[{tgt}]  n={r['n']} positions={r['n_positions']}")
        print(f"  Spearman: GP={r['rho_gp']}  additive={r['rho_additive']}  random={r['rho_random']}")
        print(f"  calibration: 80%→{r['cov80']}  95%→{r['cov95']}")
        print(f"  lead rediscovery (predicted percentile, 1.0=top): {r['lead_percentiles']}")
    print("\nPASS bar: GP Spearman > additive & >> random; leads near percentile 1.0; "
          "cov80≈0.8/cov95≈0.95. Else STOP — features/objective can't rank.")


if __name__ == "__main__":
    _main()
