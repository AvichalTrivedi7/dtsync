"""
dtsync: in-silico testbed for synchronising an imaging-driven tumour digital twin.

Physical twin  : 2D Fisher-KPP glioma on a 1 mm grid, heterogeneous proliferation (model-form error).
Imaging        : block-averaged to 2 mm, smooth segmentation noise, FLAIR (c>=0.16) and T1Gd (c>=0.80) masks.
Digital twin   : homogeneous-proliferation Fisher-KPP on a 2 mm grid, parameters (Dw, rho, k, gamma)
                 inferred by a sequential importance-resampling particle filter with a Dice-based kernel.
Policies       : static (no updates), fixed-interval imaging, uncertainty/risk-triggered imaging.
"""
import time
import zlib
import numpy as np
from scipy.ndimage import gaussian_filter

# ---------------- clinical timeline (days from diagnosis) ----------------
T_PRE = 30           # pre-treatment planning scan
T_RT0, T_RT1 = 35, 77   # 6-week chemoradiation window
T_FU1 = 105          # first follow-up scan (standard of care for every policy)
EVAL_END = 420       # progression events and tracking skill are evaluated up to here
SIM_END = 540        # simulation continues so every policy can still detect events that occur before EVAL_END
HORIZON = SIM_END
TH_FLAIR, TH_T1 = 0.16, 0.80
PROG = 1.25          # 2D analogue of RANO: >=25% area increase over nadir
A_MIN = 100.0        # and an absolute increase of at least 100 mm^2 (~11 mm lesion)


def is_prog(area, nadir):
    return (area >= PROG * nadir) & (area - nadir >= A_MIN)

# ---------------- priors (also used to draw virtual patients) ----------------
PRIOR = dict(Dw=(0.05, 0.30), rho=(0.008, 0.030), k=(0.2, 1.4), gamma=(0.30, 1.50))  # k: net log-kill over RT window; gamma: post-RT growth multiplier


def sample_params(rng, n):
    lo, hi = np.log(PRIOR["Dw"]); Dw = np.exp(rng.uniform(lo, hi, n))
    lo, hi = np.log(PRIOR["rho"]); rho = np.exp(rng.uniform(lo, hi, n))
    k = rng.uniform(*PRIOR["k"], n)
    lo, hi = np.log(PRIOR["gamma"]); gamma = np.exp(rng.uniform(lo, hi, n))
    return np.stack([np.log(Dw), np.log(rho), k, np.log(gamma)], axis=1)  # theta in unconstrained-ish space


def clip_theta(th):
    th[:, 0] = np.clip(th[:, 0], *np.log(PRIOR["Dw"]))
    th[:, 1] = np.clip(th[:, 1], *np.log(PRIOR["rho"]))
    th[:, 2] = np.clip(th[:, 2], *PRIOR["k"])
    th[:, 3] = np.clip(th[:, 3], *np.log(PRIOR["gamma"]))
    return th


# ---------------- anatomy ----------------
def make_brain(n, dx):
    L = n * dx
    yy, xx = np.mgrid[0:n, 0:n]
    X = (xx + 0.5) * dx - L / 2
    Y = (yy + 0.5) * dx - L / 2
    brain = (X / 60) ** 2 + (Y / 52) ** 2 <= 1
    wm = ((X + 21) / 29) ** 2 + (Y / 36) ** 2 <= 1
    wm |= ((X - 21) / 29) ** 2 + (Y / 36) ** 2 <= 1
    wm |= (np.abs(Y + 2) <= 5) & (np.abs(X) <= 30)
    deep_gm = ((X + 17) / 7) ** 2 + ((Y - 9) / 9) ** 2 <= 1
    deep_gm |= ((X - 17) / 7) ** 2 + ((Y - 9) / 9) ** 2 <= 1
    vent = ((X + 8) / 5) ** 2 + ((Y + 6) / 13) ** 2 <= 1
    vent |= ((X - 8) / 5) ** 2 + ((Y + 6) / 13) ** 2 <= 1
    brain &= ~vent
    wm &= brain & ~deep_gm
    m = np.zeros((n, n), np.float32)
    m[brain] = 0.2          # grey matter: D_g = 0.2 D_w
    m[wm] = 1.0
    return m, brain.astype(np.float32), wm


def face_coeffs(m):
    a, b = m[:, :-1], m[:, 1:]
    fx = np.where(a + b > 0, 2 * a * b / np.maximum(a + b, 1e-9), 0.0).astype(np.float32)
    a, b = m[:-1, :], m[1:, :]
    fy = np.where(a + b > 0, 2 * a * b / np.maximum(a + b, 1e-9), 0.0).astype(np.float32)
    return fx, fy


class Grid:
    def __init__(self, n, dx):
        self.n, self.dx = n, dx
        self.m, self.brain, self.wm = make_brain(n, dx)
        self.fx, self.fy = face_coeffs(self.m)

    def div(self, c, Dw):
        gx = (c[..., :, 1:] - c[..., :, :-1]) * self.fx
        gy = (c[..., 1:, :] - c[..., :-1, :]) * self.fy
        d = np.zeros_like(c)
        d[..., :, :-1] += gx
        d[..., :, 1:] -= gx
        d[..., :-1, :] += gy
        d[..., 1:, :] -= gy
        return Dw * d / self.dx ** 2


def smooth_noise(rng, shape, sigma_px):
    z = gaussian_filter(rng.standard_normal(shape), sigma_px)
    return (z / (z.std() + 1e-12)).astype(np.float32)


def dice(a, b):
    sa, sb = a.sum(), b.sum()
    if sa + sb == 0:
        return 1.0
    return 2.0 * np.logical_and(a, b).sum() / (sa + sb)


def dice_batch(P, o):
    """P: (N,n,n) bool, o: (n,n) bool"""
    inter = np.logical_and(P, o[None]).sum(axis=(1, 2))
    s = P.sum(axis=(1, 2)) + o.sum()
    out = np.where(s > 0, 2.0 * inter / np.maximum(s, 1), 1.0)
    return out


# ---------------- physical twin (virtual patient) ----------------
class Patient:
    FINE_N, FINE_DX, FINE_DT = 128, 1.0, 0.25

    def __init__(self, rng, coarse):
        self.rng = rng
        self.fine = Grid(self.FINE_N, self.FINE_DX)
        self.coarse = coarse
        while True:
            th = sample_params(rng, 1)[0]
            self.Dw, self.rho, self.k, self.gamma = np.exp(th[0]), np.exp(th[1]), th[2], np.exp(th[3])
            self.theta = th
            if self._grow_to_diagnosis():
                break
        self._simulate_course()

    def _grow_to_diagnosis(self):
        g, rng = self.fine, self.rng
        n = g.n
        wm_idx = np.argwhere(g.wm)
        seed = wm_idx[rng.integers(len(wm_idx))]
        self.rho_field = np.exp(0.2 * smooth_noise(rng, (n, n), 8.0)) * g.brain   # +/-20% heterogeneity
        yy, xx = np.mgrid[0:n, 0:n]
        r = np.sqrt((yy - seed[0]) ** 2 + (xx - seed[1]) ** 2) * g.dx
        c = (1.0 / (1.0 + np.exp((r - 9.0) / 0.7))).astype(np.float32) * g.brain   # saturated 9 mm seed
        d_eq = rng.uniform(28, 42)                        # equivalent FLAIR diameter at diagnosis (mm)
        self.A_diag = np.pi * d_eq ** 2 / 4
        steps = int(3000 / self.FINE_DT)
        for _ in range(steps):
            c = self._step(c, 0.0, 1.0)
            if (c >= TH_FLAIR).sum() * g.dx ** 2 >= self.A_diag:
                self.c0 = c
                return True
        return False

    def _step(self, c, kill, rho_mult):
        g = self.fine
        dc = g.div(c, self.Dw) + self.rho * rho_mult * self.rho_field * c * (1 - c) - kill * c
        c = np.clip(c + self.FINE_DT * dc, 0, 1) * g.brain
        return c.astype(np.float32)

    def _simulate_course(self):
        c = self.c0
        spd = int(round(1 / self.FINE_DT))
        n2 = self.coarse.n
        self.coarse_fields = np.zeros((HORIZON + 1, n2, n2), np.float32)
        self.fine_area = np.zeros(HORIZON + 1)
        for day in range(HORIZON + 1):
            self.coarse_fields[day] = c.reshape(n2, 2, n2, 2).mean(axis=(1, 3))
            self.fine_area[day] = (c >= TH_FLAIR).sum() * self.fine.dx ** 2
            kill = self.rho + self.k / (T_RT1 - T_RT0) if T_RT0 <= day < T_RT1 else 0.0
            mult = self.gamma if day >= T_RT1 else 1.0
            for _ in range(spd):
                c = self._step(c, kill, mult)
        self.true_flair = (self.coarse_fields >= TH_FLAIR).sum(axis=(1, 2)) * self.coarse.dx ** 2
        self.true_area = (self.coarse_fields >= TH_T1).sum(axis=(1, 2)) * self.coarse.dx ** 2   # enhancing (measurable) disease
        a = self.true_area
        nadir_val = a[T_PRE]
        self.t_prog = None
        for d in range(T_PRE + 1, HORIZON + 1):
            if is_prog(a[d], nadir_val):
                self.t_prog = d
                break
            nadir_val = min(nadir_val, a[d])

    def observe(self, day, noise=0.05):
        # common random numbers: the image acquired on a given day is identical whichever policy requested it
        r = np.random.default_rng([self.seed, day])
        f = self.coarse_fields[day] + noise * smooth_noise(r, self.coarse_fields[day].shape, 1.0) * self.coarse.brain
        return f >= TH_FLAIR, f >= TH_T1

    def true_masks(self, day):
        f = self.coarse_fields[day]
        return f >= TH_FLAIR, f >= TH_T1


# ---------------- digital twin (particle filter) ----------------
class Twin:
    DT = 1.0

    def __init__(self, grid, P, rng, eps_min=0.06, ess_frac=0.3, lw_a=0.97):
        self.g, self.P, self.rng = grid, P, rng
        self.eps_min, self.ess_frac, self.lw_a = eps_min, ess_frac, lw_a
        self.last_ess = None

    def copy(self):
        t = Twin(self.g, self.P, self.rng, self.eps_min, self.ess_frac, self.lw_a)
        t.theta, t.c = self.theta.copy(), self.c.copy()
        return t

    # ----- dynamics -----
    def step_day(self, day):
        th = self.theta
        Dw = np.exp(th[:, 0])[:, None, None].astype(np.float32)
        rho = np.exp(th[:, 1])[:, None, None].astype(np.float32)
        kill = (np.exp(th[:, 1]) + th[:, 2] / (T_RT1 - T_RT0) if T_RT0 <= day < T_RT1 else np.zeros(self.P))[:, None, None].astype(np.float32)
        mult = (np.exp(th[:, 3]) if day >= T_RT1 else np.ones(self.P))[:, None, None].astype(np.float32)
        c = self.c
        dc = self.g.div(c, Dw) + rho * mult * c * (1 - c) - kill * c
        self.c = (np.clip(c + self.DT * dc, 0, 1) * self.g.brain).astype(np.float32)

    def areas(self, th=TH_T1):
        return (self.c >= th).sum(axis=(1, 2)) * self.g.dx ** 2

    # ----- inference -----
    def _distance(self, obs):
        fo, to = obs
        dF = 1 - dice_batch(self.c >= TH_FLAIR, fo)
        dT = 1 - dice_batch(self.c >= TH_T1, to)
        return np.sqrt(dF ** 2 + dT ** 2)

    def assimilate(self, obs, valid=None):
        d = self._distance(obs)
        if valid is not None:
            d = np.where(valid, d, np.inf)

        def ess(eps):
            lw = -0.5 * (d / eps) ** 2
            lw -= lw[np.isfinite(lw)].max()
            w = np.exp(lw); w[~np.isfinite(lw)] = 0
            w /= w.sum()
            return 1.0 / (w ** 2).sum(), w

        eps = self.eps_min
        e, w = ess(eps)
        while e < self.ess_frac * self.P and eps < 2.0:   # widen kernel only if the filter would collapse
            eps *= 1.25
            e, w = ess(eps)
        self.last_eps, self.last_ess = eps, e
        # systematic resampling
        u = (self.rng.random() + np.arange(self.P)) / self.P
        idx = np.minimum(np.searchsorted(np.cumsum(w), u), self.P - 1)
        th = self.theta[idx].copy()
        self.c = self.c[idx].copy()
        # Liu-West kernel shrinkage jitter
        a = self.lw_a
        mean = th.mean(axis=0)
        cov = np.cov(th.T) + 1e-10 * np.eye(th.shape[1])
        th = a * th + (1 - a) * mean + self.rng.multivariate_normal(np.zeros(th.shape[1]), (1 - a ** 2) * cov, self.P)
        self.theta = clip_theta(th)

    def initialise(self, obs0, max_days=2500):
        """Grow each particle from a seed at the observed FLAIR centroid until its FLAIR area matches the scan."""
        g, P = self.g, self.P
        fo, _ = obs0
        A_obs = fo.sum() * g.dx ** 2
        cy, cx = np.argwhere(fo).mean(axis=0)
        brain_idx = np.argwhere(g.brain > 0)
        j = np.argmin((brain_idx[:, 0] - cy) ** 2 + (brain_idx[:, 1] - cx) ** 2)
        sy, sx = brain_idx[j]
        n = g.n
        yy, xx = np.mgrid[0:n, 0:n]
        r = np.sqrt((yy - sy) ** 2 + (xx - sx) ** 2) * g.dx
        seed = (1.0 / (1.0 + np.exp((r - 9.0) / 0.7))).astype(np.float32) * g.brain
        self.theta = sample_params(self.rng, P)
        self.c = np.repeat(seed[None], P, axis=0)
        captured = np.zeros(P, bool)
        store = np.zeros_like(self.c)
        for day in range(max_days):
            self.step_day(-1)          # untreated growth before diagnosis
            hit = (~captured) & (self.areas(TH_FLAIR) >= A_obs)
            store[hit] = self.c[hit]
            captured |= hit
            if captured.all():
                break
        self.c = store
        self.assimilate(obs0, valid=captured)
        return captured.mean()

    def summary(self):
        qt = np.percentile(self.areas(TH_T1), [5, 50, 95])
        qf = np.percentile(self.areas(TH_FLAIR), [5, 50, 95])
        return np.concatenate([qt, qf])

    def predicted_mask(self, th=TH_FLAIR):
        return (self.c >= th).mean(axis=0) >= 0.5


# ---------------- policies ----------------
def run_policy(tw0, pat, policy, rng, eval_days, p_star=0.3, min_int=28, max_int=120, noise=0.05, snap_days=()):
    tw = tw0.copy()
    tw.rng = np.random.default_rng([pat.seed, zlib.crc32(policy.encode())])   # independent of policy order
    snaps = {}
    nadir = pat.obs_area_pre            # smallest enhancing area measured so far (RANO-style reference)
    prev_flair = pat.obs_flair_pre
    detected, n_scans, last_scan, next_scan = None, 0, T_PRE, T_FU1
    scan_days, daily = [], np.zeros((HORIZON + 1, 6))
    evals, assim_ms = {}, []
    for day in range(T_PRE, HORIZON):
        tw.step_day(day)
        t = day + 1
        q = tw.summary(); daily[t] = q
        if t in snap_days:      # twin forecast maps before any same-day update
            snaps[t] = ((tw.c >= TH_FLAIR).mean(axis=0), (tw.c >= TH_T1).mean(axis=0))
        if t in eval_days:      # forecast skill before any same-day update
            ft, tt = pat.true_masks(t)
            af = pat.true_flair[t]
            evals[t] = dict(dice=dice(tw.predicted_mask(), ft), dice_t1=dice(tw.predicted_mask(TH_T1), tt),
                            rel_err=abs(q[4] - af) / max(af, 1.0),
                            covered=float(q[3] <= af <= q[5]),
                            width=(q[5] - q[3]) / max(q[4], 1.0),
                            t1_abs_err=abs(q[1] - pat.true_area[t]))
        if detected is not None or policy == "static":
            continue
        scan = False
        if t == T_FU1:
            scan = True
        elif t > T_FU1 and policy.startswith("fixed"):
            scan = (t - T_FU1) % int(policy.split("_")[1]) == 0
        elif t > T_FU1 and policy == "reactive":      # clinician-style rule, no twin: 30 d if equivocal, else 90 d
            scan = t >= next_scan
        elif t > T_FU1 and policy.startswith("trig"):
            p_star = float(policy.split("_")[1]) if "_" in policy else p_star
            gap = t - last_scan
            if gap >= min_int:
                p_prog = is_prog(tw.areas(), nadir).mean()
                scan = p_prog >= p_star or gap >= max_int
        if scan:
            obs = pat.observe(t, noise)
            t0 = time.perf_counter()
            tw.assimilate(obs)
            assim_ms.append(1000 * (time.perf_counter() - t0))
            n_scans += 1; last_scan = t; scan_days.append(t)
            a_obs = obs[1].sum() * tw.g.dx ** 2
            a_fl = obs[0].sum() * tw.g.dx ** 2
            if is_prog(a_obs, nadir):
                detected = t
            equivocal = (a_obs - nadir >= 40.0) or (a_fl >= 1.10 * prev_flair)
            next_scan = t + (30 if equivocal else 90)
            nadir = min(nadir, a_obs)
            prev_flair = a_fl
    return dict(policy=policy, n_scans=n_scans, scan_days=scan_days, detected=detected,
                evals=evals, daily=daily, final_theta=np.median(tw.theta, axis=0),
                assim_ms=float(np.mean(assim_ms)) if assim_ms else None, snaps=snaps)


def run_patient(seed, P=192, policies=("static", "fixed_30", "fixed_60", "fixed_90", "triggered"),
                noise=0.05, eval_step=15, p_star=0.3):
    rng = np.random.default_rng(seed)
    coarse = Grid(64, 2.0)
    pat = Patient(rng, coarse)
    pat.seed = seed
    tw = Twin(coarse, P, rng)
    obs0 = pat.observe(0, noise)
    frac = tw.initialise(obs0)
    for day in range(0, T_PRE):
        tw.step_day(day)
    obs_pre = pat.observe(T_PRE, noise)
    pat.obs_area_pre = obs_pre[1].sum() * coarse.dx ** 2
    pat.obs_flair_pre = obs_pre[0].sum() * coarse.dx ** 2
    tw.assimilate(obs_pre)
    eval_days = set(range(T_FU1, EVAL_END + 1, eval_step))
    out = dict(seed=seed, theta=pat.theta.tolist(), t_prog=pat.t_prog, init_capture=frac,
               true_area=pat.true_area, true_flair=pat.true_flair.astype(np.float32),
               pre_theta=tw.theta.copy(), results={})
    for pol in policies:
        out["results"][pol] = run_policy(tw, pat, pol, rng, eval_days, p_star=p_star, noise=noise)
    return out
