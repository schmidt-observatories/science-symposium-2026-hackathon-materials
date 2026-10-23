"""Single-pass NE2025 line-of-sight integration (wrapper around mwprop internals).

Used only by ``tools/build_ne2025_grid.py``. The physics is mwprop's, unchanged:
this module calls mwprop's own density components and reproduces the arithmetic
of ``mwprop.nemod.dmdsm.dmdsm_dm2d`` and ``mwprop.nemod.NE2025.ne2025``
(dmd_only=False). What differs is only the bookkeeping:

1. Each sightline is integrated ONCE, to mwprop's maximum integration distance
   (``dmax_ne2001p_integrate`` = 50 kpc) on mwprop's own coarse/fine grids
   (ds_coarse = 0.1 kpc for the smooth components, ds_fine = 0.0025 kpc for the
   small-scale ones). This is exactly the grid mwprop uses for any DM target
   that needs the full 50 kpc. From the cumulative DM(s) and the three
   cumulative SM moments every DM -> (D, tau) query, DM_max and tau_X come out
   of the same pass. (mwprop instead re-integrates every query on a grid
   ending at ~1.5x the estimated distance, up to three passes.)
2. ``nevoidN`` (voids; 45 % of mwprop's run time) is evaluated vectorised over
   all fine samples at once. Its result is identical to mwprop's scalar loop
   (last void in list order wins), checked by ``check_voids``.
3. The arm-center spline ``CubicSpline(th1[j], r1[j])`` that mwprop rebuilds
   for every sample is built once per arm (it depends only on model constants).

Everything else (ne_outer, ne_inner, ne_gc, ne_lism, neclumpN, the arm search,
the CubicSpline resampling of the smooth components, the trapezoid integrals,
the SM weightings and the scattering formulas) calls or copies mwprop verbatim.
"""

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.interpolate import CubicSpline

import mwprop.nemod.NE2025  # noqa: F401  (selects the NE2025 parameter set before config import)
from mwprop.nemod import config_nemod as cfg
from mwprop.nemod import ne_arms as _arms
from mwprop.nemod import nevoidN as _voids
from mwprop.nemod.density_components import ne_outer, ne_inner, ne_gc
from mwprop.nemod.ne_lism import ne_lism
from mwprop.nemod.neclumpN_fast import neclumpN, relevant_clumps
from mwprop.nemod.dmdsm import calc_galcentric_vecs
from mwprop.scattering_functions import scattering_functions2020 as sf

DMAX = cfg.dmax_ne2001p_integrate          # 50 kpc
DS_COARSE = cfg.ds_coarse                  # 0.1 kpc
DS_FINE = cfg.ds_fine                      # 0.0025 kpc
RF_REF = cfg.rf_ref                        # 1 GHz
SM_FACTOR = cfg.sm_factor
PC_IN_KPC = cfg.pc_in_kpc


# --------------------------------------------------------------------------
# Spiral arms: mwprop's ne_arms_ne2001p with the per-arm r(theta) spline cached.
# --------------------------------------------------------------------------
_ARM_R_SPLINES = None


def _arm_r_spline(j):
    global _ARM_R_SPLINES
    if _ARM_R_SPLINES is None:
        _ARM_R_SPLINES = [CubicSpline(_arms.th1[k, :], _arms.r1[k, :])
                          for k in range(np.shape(_arms.coarse_arms)[1])]
    return _ARM_R_SPLINES[j]


def ne_arms_cached(x, y, z, Ncoarse=20, dthfine=0.01, nfinespline=5):
    """Copy of mwprop.nemod.ne_arms.ne_arms_ne2001p (verbose prints removed,
    arm r(theta) spline cached). Same arithmetic, same return values."""
    A = _arms
    Dgal, Darmmap, sech2 = A.Dgal, A.Darmmap, A.sech2
    coarse_arms, th1 = A.coarse_arms, A.th1
    narms = np.shape(coarse_arms)[1]
    dsq_coarse = (coarse_arms[0] - x)**2 + (coarse_arms[1] - y)**2
    index_dsqmin = [dsq_coarse[j, :].argmin() for j in range(narms)]
    nspline2 = int((nfinespline-1)/2)
    nea = 0.
    ga = 0.
    whicharm = 0
    whicharm_spiralmodel = 0
    rr = np.sqrt(x**2 + y**2)
    thxydeg = np.rad2deg(np.arctan2(-x, y))
    for j in range(narms):
        ind1 = range(max(0, index_dsqmin[j]-nspline2-1),
                     min(index_dsqmin[j]+nspline2+1, Ncoarse), 1)
        dsqs = CubicSpline(th1[j, ind1], dsq_coarse[j, ind1])
        thjfine = np.arange(th1[j, ind1[0]], th1[j, ind1[-1]], dthfine)
        ind_min = dsqs(thjfine).argmin()
        thjmin = thjfine[ind_min]
        rjmin = _arm_r_spline(j)(thjmin)
        xjmin, yjmin = -rjmin*np.sin(thjmin), rjmin*np.cos(thjmin)
        dmin = np.sqrt((x-xjmin)**2 + (y-yjmin)**2)
        jj = Darmmap[str(j)]
        wa = Dgal['wa']
        if thxydeg < 0:
            thxydeg += 360
        if j == 0:
            dmin_min = dmin
        Wa = wa * Dgal['warm'+str(jj)]
        if dmin < 3.*wa:
            if dmin <= dmin_min:
                dmin_min = dmin
                whicharm_spiralmodel = j+1
            argxy = dmin / Wa
            ga = np.exp(-argxy**2)
            if rr > Dgal['Aa']:
                ga *= sech2((rr-Dgal['Aa'])/2.)
            Ha = Dgal['ha'] * Dgal['harm'+str(jj)]
            ga *= sech2(z/Ha)
            if jj == 3:
                th3adeg, th3bdeg = 290, 363
                test3 = thxydeg - th3adeg
                if test3 < 0:
                    test3 += 360
                if 0 <= test3 and test3 < th3bdeg-th3adeg:
                    arg = 2.*np.pi*test3 / (th3bdeg-th3adeg)
                    fac = ((1 + np.cos(arg))/2)**4
                    ga *= fac
            if jj == 2:
                th2adeg, th2bdeg = 340, 370
                test2 = thxydeg - th2adeg
                fac2min = 0.1
                if test2 < 0:
                    test2 += 360
                if 0 <= test2 and test2 < th2bdeg-th2adeg:
                    arg = 2.*np.pi*test2 / (th2bdeg-th2adeg)
                    fac = ((1 + fac2min + (1 - fac2min) * np.cos(arg))/2)**3.5
                    ga *= fac
            nea += ga * Dgal['narm'+str(jj)] * Dgal['na']
    if whicharm_spiralmodel == 0:
        whicharm = 0
        Farm = 0
    else:
        whicharm = Darmmap[str(whicharm_spiralmodel-1)]
        Farm = Dgal['Fa']
    return nea, Farm, whicharm


def smooth_comps(x, y, z):
    """mwprop.nemod.density.density_2001_smooth_comps with the cached arm spline."""
    ne1 = ne2 = nea = 0
    F1 = F2 = Fa = 0
    whicharm = 0
    if cfg.wg1 == 1:
        ne1, F1 = ne_outer(x, y, z)
    if cfg.wg2 == 1:
        ne2, F2 = ne_inner(x, y, z)
    if cfg.wga == 1:
        nea, Fa, whicharm = ne_arms_cached(x, y, z, Ncoarse=cfg.Ncoarse)
    wne1 = cfg.wg1*ne1
    wne2 = cfg.wg2*ne2
    wnea = cfg.wga*nea
    ne_smooth = wne1 + wne2 + wnea
    if ne_smooth > 0.:
        Fsmooth = (F1*(wne1)**2 + F2*wne2**2 + Fa*wnea**2) / ne_smooth**2
    else:
        Fsmooth = 0.
    return ne1, ne2, nea, F1, F2, Fa, whicharm, ne_smooth, Fsmooth


# --------------------------------------------------------------------------
# Voids: vectorised nevoidN (same result as mwprop's scalar loop).
# --------------------------------------------------------------------------
def nevoidN_vec(x, y, z):
    V = _voids
    x = np.asarray(x, float)[:, None]
    y = np.asarray(y, float)[:, None]
    z = np.asarray(z, float)[:, None]
    dx = x - V.xv
    dy = y - V.yv
    dz = z - V.zv
    q = ((V.cc12*dx + V.s2*dy + V.cs21*dz)**2. / V.aav**2.
         + (-V.cs12*dx + V.c2*dy - V.ss12*dz)**2. / V.bbv**2.
         + (-V.s1*dx + V.c1*dz)**2. / V.ccv**2.)
    hit0 = (V.edgev == 0.) & (q < 3.)
    hit1 = (V.edgev == 1.) & (q <= 1.)
    hit = hit0 | hit1
    n = x.shape[0]
    nv = q.shape[1]
    anyhit = hit.any(axis=1)
    # last j in list order wins (mwprop overwrites in its j loop)
    jlast = nv - 1 - np.argmax(hit[:, ::-1], axis=1)
    rows = np.arange(n)
    nev_j = np.where(V.edgev[jlast] == 0., V.nev[jlast] * np.exp(-q[rows, jlast]), V.nev[jlast])
    nevN = np.where(anyhit, nev_j, 0.)
    FvN = np.where(anyhit, V.Fv[jlast], 0.)
    hitvoid = np.where(anyhit, jlast + 1, 0)
    wvoid = anyhit.astype(int)
    return nevN, FvN, hitvoid, wvoid


def check_voids(n=20000, seed=1):
    """Compare nevoidN_vec with mwprop's scalar nevoidN at random points,
    concentrated near the voids. Returns max |difference|."""
    rng = np.random.default_rng(seed)
    V = _voids
    j = rng.integers(0, V.nvoids, n)
    sc = np.maximum(np.maximum(V.aav, V.bbv), V.ccv)[j] * 1.5
    x = V.xv[j] + rng.uniform(-1, 1, n) * sc
    y = V.yv[j] + rng.uniform(-1, 1, n) * sc
    z = V.zv[j] + rng.uniform(-1, 1, n) * sc
    vec = np.array(nevoidN_vec(x, y, z), float).T
    ref = np.array([V.nevoidN(x[i], y[i], z[i]) for i in range(n)], float)
    return float(np.max(np.abs(vec - ref))), int(np.count_nonzero(ref[:, 2]))


# --------------------------------------------------------------------------
# Single-pass sightline integration.
# --------------------------------------------------------------------------
def integrate_sightline(ldeg, bdeg, dmax=DMAX):
    """Integrate NE2025 along (l, b) to dmax on mwprop's coarse/fine grids.

    Returns dict with s (kpc), cumulative DM (pc cm^-3) and the cumulative
    dSM moments C1 = int dsm, C2 = int s dsm, C3 = int s^2 dsm (unscaled, as
    in dmdsm_dm2d)."""
    l = np.deg2rad(ldeg)
    b = np.deg2rad(bdeg)
    Ns_coarse = int(dmax / DS_COARSE)
    Ns_fine = int(dmax / DS_FINE)
    rel = relevant_clumps(l, b, dmax, cfg.rcmult)

    sc_vec, xc_vec, yc_vec, zc_vec = calc_galcentric_vecs(l, b, dmax, Ns_coarse)
    sf_vec, xf_vec, yf_vec, zf_vec = calc_galcentric_vecs(l, b, dmax, Ns_fine)

    cne1, cne2, cnea, cF1, cF2, cFa, cwhicharm, cne_smooth, cFsmooth = np.array(
        [smooth_comps(xc_vec[j], yc_vec[j], zc_vec[j]) for j in range(Ns_coarse)]).T
    ne_smooth = CubicSpline(sc_vec, cne_smooth)(sf_vec)
    F_smooth = CubicSpline(sc_vec, cFsmooth)(sf_vec)

    # small-scale components: ne_gc, ne_lism, neclumpN scalar (mwprop); voids vectorised
    wggc, wglism, wgcN, wgvN = cfg.wggc, cfg.wglism, cfg.wgcN, cfg.wgvN
    out = np.zeros((Ns_fine, 7))
    for j in range(Ns_fine):
        x, y, z = xf_vec[j], yf_vec[j], zf_vec[j]
        negc = nelism = necN = 0
        Fgc = Flism = FcN = 0
        wlism = 0
        if wggc == 1:
            negc, Fgc = ne_gc(x, y, z)
        if wglism == 1:
            nelism, Flism, wlism, wldr, wlhb, wlsb, wloopI = ne_lism(x, y, z)
        if wgcN == 1:
            necN, FcN, hitclump, arg = neclumpN(x, y, z, inds_relevant=rel)
        else:
            necN = 0
            FcN = 0
        out[j] = (negc, nelism, necN, Fgc, Flism, FcN, wlism)
    negc, nelism, necN, Fgc, Flism, FcN, wlism = out.T
    if wgvN == 1:
        nevN, FvN, hitvoid, wvoid = nevoidN_vec(xf_vec, yf_vec, zf_vec)
    else:
        nevN = FvN = wvoid = np.zeros(Ns_fine)

    wtotal = (1-wgvN*wvoid)*(1-wglism*wlism)
    ne_ex = (1.-wglism*wlism) * (ne_smooth + wggc*negc) + wglism*wlism*nelism
    ne = (1-wgvN*wvoid)*ne_ex + wgvN*wvoid*nevN + wgcN*necN
    dm_cum = PC_IN_KPC * cumulative_trapezoid(ne, sf_vec, initial=0.0)

    dsm_smooth = wtotal * ne_smooth**2 * F_smooth
    dsmgc = wtotal*wggc*negc**2*Fgc
    dsmlism = (1.-wgvN*wvoid)*wglism*wlism*nelism**2*Flism
    dsmcN = wgcN*necN**2*FcN
    dsmvN = wgvN*wvoid*nevN**2*FvN
    dsm = dsm_smooth + dsmgc + dsmlism + dsmcN + dsmvN
    C1 = cumulative_trapezoid(dsm, sf_vec, initial=0.0)
    C2 = cumulative_trapezoid(sf_vec*dsm, sf_vec, initial=0.0)
    C3 = cumulative_trapezoid(sf_vec**2*dsm, sf_vec, initial=0.0)
    return dict(s=sf_vec, dm=dm_cum, C1=C1, C2=C2, C3=C3)


def _sm_at(I, dhat):
    """SM, SMtau, SMtheta at distance dhat exactly as dmdsm_dm2d does it
    (cumulative arrays weighted with dhat, then CubicSpline evaluated at dhat)."""
    ss, c1, c2, c3 = I['s'], I['C1'], I['C2'], I['C3']
    sm = CubicSpline(ss, SM_FACTOR * c1)(dhat)
    smtau = CubicSpline(ss, 6 * (SM_FACTOR/dhat) * (c2 - c3/dhat))(dhat)
    smtheta = CubicSpline(ss, 3 * SM_FACTOR * (c1 + c3/dhat**2 - 2*c2/dhat))(dhat)
    return float(sm), float(smtau), float(smtheta)


def edge(I):
    """DM_max and the model-edge distance (mwprop's 'lower limit' distance:
    first sample where the cumulative DM equals its final value)."""
    dm = I['dm']
    dm_max = float(dm[-1])
    ind = int(np.where(dm == dm[-1])[0][0])
    return dm_max, float(I['s'][ind])


def query(I, dm_target):
    """(D kpc, tau_1GHz ms, saturated) for a Galactic source at dm_target.
    Saturated (dm_target > DM_max): D and tau at the model edge, as mwprop."""
    dm_max, d_edge = edge(I)
    if dm_target > dm_max:
        dhat, sat = d_edge, True
    else:
        dhat, sat = float(np.interp(dm_target, I['dm'], I['s'])), False
    sm, smtau, smtheta = _sm_at(I, dhat)
    tau = sf.tauiss(dhat, smtau, RF_REF)
    return dhat, float(tau), sat


def tau_x(I):
    """Extragalactic (plane-wave) pulse broadening at 1 GHz (ms) for the full
    column: mwprop's TAU_X from a DM->D query beyond DM_max."""
    dm_max, d_edge = edge(I)
    sm, smtau, smtheta = _sm_at(I, d_edge)
    tau = sf.tauiss(d_edge, smtau, RF_REF)
    sbw = sf.scintbw(d_edge, smtau, RF_REF)
    theta_x = sf.theta_xgal(sm, RF_REF)
    tx, sbw_x, deffsm2 = sf.taux_from_thetax(d_edge, sm, smtau, smtheta, theta_x, tau, sbw)
    return float(tx)


def sightline_table(ldeg, bdeg, dm_grid):
    """Everything the grid needs for one sightline, from one integration."""
    I = integrate_sightline(ldeg, bdeg)
    dm_max, d_edge = edge(I)
    D = np.empty(len(dm_grid))
    T = np.empty(len(dm_grid))
    for k, dm in enumerate(dm_grid):
        D[k], T[k], _ = query(I, dm)
    return dict(dm_max=dm_max, d_edge=d_edge, tau_x=tau_x(I), dist=D, tau=T)
