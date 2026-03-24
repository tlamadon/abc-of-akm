"""
Calibrate the Model parameters to match Guvenen/Song (US) AKM variance decomposition.

Target moments:
  var(firm effect)       = 0.081
  var(worker effect)     = 0.476
  2 * cov(alpha, psi)    = 0.108
  var(residual)          = 0.136

Strategy:
  sigma is set analytically: sigma = sqrt(var_eps_target).
  We optimize over (lambda1, rho, scale_alpha, scale_psi) to match the remaining
  three targets (var_alpha, var_psi, 2*cov). The scale parameters multiply the
  N(0,1) quantiles used for both mobility and wages, so sorting is affected consistently.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize

# ── Targets from Guvenen/Song ──────────────────────────────────────────────
TARGET_VAR_PSI = 0.081
TARGET_VAR_ALPHA = 0.476
TARGET_2COV = 0.108
TARGET_VAR_EPS = 0.136
TARGET_SIGMA = np.sqrt(TARGET_VAR_EPS)

# ── Model code (extracted from jep.ipynb, with scale parameters) ───────────

def matrix_stationary_distribution(transition_matrix):
    eigvals, eigvecs = np.linalg.eig(transition_matrix.T)
    stationary_vec = eigvecs[:, np.isclose(eigvals, 1)]
    stationary_dist = stationary_vec[:, 0].real
    stationary_dist = np.maximum(0, np.sign(stationary_dist.sum()) * stationary_dist)
    stationary_dist /= stationary_dist.sum()
    return stationary_dist


class Param:
    def __init__(self, **kwds):
        self.__dict__.update({
            'rho': 1.0, 'lambda1': 0.1, 'sigma': 0.2,
            'ng': 10, 'nj': 20,
            'scale_alpha': 1.0, 'scale_psi': 1.0,
        })
        self.__dict__.update(kwds)


class Model:
    def __init__(self, p=None, **kwds):
        if p is None:
            p = Param(**kwds)
        else:
            p.__dict__.update(kwds)
        self.lambda1 = p.lambda1
        self.sigma = p.sigma
        self.rho = p.rho
        self.scale_alpha = p.scale_alpha
        self.scale_psi = p.scale_psi
        self.psi_j = p.scale_psi * norm.ppf(np.linspace(1/p.nj, 1-1/p.nj, p.nj), loc=0, scale=1.0)
        self.alpha_g = p.scale_alpha * norm.ppf(np.linspace(1/p.ng, 1-1/p.ng, p.ng), loc=0, scale=1.0)
        self.ng = p.ng
        self.nj = p.nj
        self.H = None

    def tr_pr(self, alpha, psi1, psi2):
        return self.lambda1 / (1 + np.exp(1/self.rho * ((psi2-alpha)**2 - (psi1-alpha)**2)))

    def construct_transition_matrix(self, alpha, psi):
        n = len(psi)
        T = np.zeros((n, n))
        for j in range(n):
            for jp in range(n):
                T[j, jp] = self.tr_pr(alpha, psi[j], psi[jp])
        row_sums = T.sum(axis=1, keepdims=True)
        T /= row_sums
        return T

    def stationary_distribution(self):
        H = np.zeros((self.ng, self.nj))
        for g in range(self.ng):
            T = self.construct_transition_matrix(self.alpha_g[g], self.psi_j)
            H[g, :] = matrix_stationary_distribution(T)
        self.H = H
        return H

    def simulate(self, ni, nt):
        if self.H is None:
            self.stationary_distribution()
        data = []
        for i in range(ni):
            g = np.random.choice(self.ng)
            j = np.random.choice(self.nj, p=self.H[g, :])
            alpha_i = self.alpha_g[g] + np.random.normal(0, self.scale_alpha)
            data.append({'i': i, 'j': j, 't': 0, 'alpha': alpha_i})
            for t in range(1, nt):
                j2 = np.random.choice(self.nj)
                pr_move = self.tr_pr(self.alpha_g[g], self.psi_j[j], self.psi_j[j2])
                if (j != j2) and (np.random.uniform() < pr_move):
                    j = j2
                data.append({'i': i, 'j': j, 't': t, 'alpha': alpha_i})
        dataset = pd.DataFrame(data)
        dataset['psi'] = self.psi_j[dataset['j']]
        dataset['epsilon'] = np.random.normal(0, 1, len(dataset)) * self.sigma
        dataset['y'] = dataset['alpha'] + dataset['psi'] + dataset['epsilon']
        return dataset


def variance_decomposition(data):
    va = data['alpha'].var()
    vp = data['psi'].var()
    cov_ap = data['alpha'].cov(data['psi'])
    eps = data['y'] - data['alpha'] - data['psi']
    ve = eps.var()
    return {'var_alpha': va, 'var_psi': vp, 'cov_alpha_psi': cov_ap, 'var_eps': ve}


# ── Calibration ────────────────────────────────────────────────────────────

def simulate_moments(lambda1, rho, scale_alpha, scale_psi, ng=10, nj=100, ni=5000, nt=10, seed=42):
    """Simulate data and return the variance decomposition."""
    np.random.seed(seed)
    m = Model(lambda1=lambda1, rho=rho, sigma=TARGET_SIGMA,
              ng=ng, nj=nj, scale_alpha=scale_alpha, scale_psi=scale_psi)
    data = m.simulate(ni, nt)
    return variance_decomposition(data)


def objective(params, ng=10, nj=100, ni=5000, nt=10):
    """Sum of squared differences between simulated and target moments."""
    lambda1, rho, scale_alpha, scale_psi = params
    if lambda1 <= 0 or lambda1 >= 1 or rho <= 0.01 or scale_alpha <= 0 or scale_psi <= 0:
        return 1e6

    errors = []
    for seed in [42, 123, 456]:
        vd = simulate_moments(lambda1, rho, scale_alpha, scale_psi, ng, nj, ni, nt, seed)
        errors.append([
            (vd['var_alpha'] - TARGET_VAR_ALPHA) / TARGET_VAR_ALPHA,
            (vd['var_psi'] - TARGET_VAR_PSI) / TARGET_VAR_PSI,
            (2*vd['cov_alpha_psi'] - TARGET_2COV) / TARGET_2COV,
        ])
    mean_errors = np.mean(errors, axis=0)
    return np.sum(mean_errors**2)


def calibrate(ng=10, nj=100, ni=5000, nt=10):
    """Find (lambda1, rho, scale_alpha, scale_psi) that match the target decomposition."""
    print(f"Target variance decomposition:")
    print(f"  var(alpha) = {TARGET_VAR_ALPHA}")
    print(f"  var(psi)   = {TARGET_VAR_PSI}")
    print(f"  2*cov      = {TARGET_2COV}")
    print(f"  var(eps)   = {TARGET_VAR_EPS}")
    print(f"  sigma      = {TARGET_SIGMA:.4f}")
    print()

    # Grid search for starting point (seeded near known good values)
    print("Grid search for starting point...")
    best_loss = 1e6
    best_params = (0.559, 0.351, 0.550, 0.317)
    for lam in [0.1, 0.2, 0.3, 0.5]:
        for rho in [0.3, 0.5, 1.0, 2.0, 3.0]:
            for sa in [0.3, 0.5, 0.7]:
                for sp in [0.2, 0.3, 0.5]:
                    loss = objective([lam, rho, sa, sp], ng, nj, ni, nt)
                    if loss < best_loss:
                        best_loss = loss
                        best_params = (lam, rho, sa, sp)
    print(f"  Best: lambda1={best_params[0]:.2f}, rho={best_params[1]:.2f}, "
          f"scale_alpha={best_params[2]:.2f}, scale_psi={best_params[3]:.2f}, loss={best_loss:.6f}")

    # Refine with Nelder-Mead
    print("Refining with Nelder-Mead...")
    result = minimize(
        objective, best_params, args=(ng, nj, ni, nt),
        method='Nelder-Mead',
        options={'xatol': 1e-4, 'fatol': 1e-8, 'maxiter': 500, 'disp': True}
    )
    lambda1_opt, rho_opt, sa_opt, sp_opt = result.x
    print(f"  Optimized: lambda1={lambda1_opt:.4f}, rho={rho_opt:.4f}, "
          f"scale_alpha={sa_opt:.4f}, scale_psi={sp_opt:.4f}")
    print()

    # Final verification with large sample
    print("Final simulation (large sample)...")
    np.random.seed(0)
    m = Model(lambda1=lambda1_opt, rho=rho_opt, sigma=TARGET_SIGMA,
              ng=ng, nj=nj, scale_alpha=sa_opt, scale_psi=sp_opt)
    data = m.simulate(ni=20000, nt=15)
    vd = variance_decomposition(data)
    total = vd['var_alpha'] + vd['var_psi'] + 2*vd['cov_alpha_psi'] + vd['var_eps']
    target_total = TARGET_VAR_ALPHA + TARGET_VAR_PSI + TARGET_2COV + TARGET_VAR_EPS

    print("Verification (large sample):")
    print(f"  var(alpha) = {vd['var_alpha']:.4f}  (target: {TARGET_VAR_ALPHA})")
    print(f"  var(psi)   = {vd['var_psi']:.4f}  (target: {TARGET_VAR_PSI})")
    print(f"  2*cov      = {2*vd['cov_alpha_psi']:.4f}  (target: {TARGET_2COV})")
    print(f"  var(eps)   = {vd['var_eps']:.4f}  (target: {TARGET_VAR_EPS})")
    print(f"  total var  = {total:.4f}  (target: {target_total})")
    print()

    print("=" * 60)
    print("CALIBRATED PARAMETERS")
    print("=" * 60)
    print(f"  Model(lambda1={lambda1_opt:.4f}, rho={rho_opt:.4f}, sigma={TARGET_SIGMA:.4f},")
    print(f"        ng={ng}, nj={nj},")
    print(f"        scale_alpha={sa_opt:.4f}, scale_psi={sp_opt:.4f})")

    return {
        'lambda1': lambda1_opt, 'rho': rho_opt, 'sigma': TARGET_SIGMA,
        'ng': ng, 'nj': nj,
        'scale_alpha': sa_opt, 'scale_psi': sp_opt,
    }


if __name__ == '__main__':
    result = calibrate()
