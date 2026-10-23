"""
DSA sensitivity / exposure-time calculator: reference engine.

Every number shown by the web calculator is produced by the same equations as this module
(the JavaScript port in web/js/dsa-engine.js is tested against it; see tests/).

Units: frequencies in MHz unless noted, angles in degrees unless noted, flux densities in Jy
internally; outputs carry their unit in the key name (e.g. ``sigma_uJy``).
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache

import numpy as np

_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")   # numpy >= 2 renamed trapz

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

C_LIGHT = 299792458.0          # m/s
K_B = 1.380649e-23             # J/K
JY = 1e-26                     # W m^-2 Hz^-1
HI_REST_MHZ = 1420.405752
FOUR_LN2 = 4.0 * math.log(2.0)
ARCSEC = math.pi / 180.0 / 3600.0

# ----------------------------------------------------------------------------- instrument defaults
DEFAULTS = {
    "n_ant": 1650,
    "dish_diameter_m": 6.155,
    "aperture_efficiency": 0.67,
    "tsys_zenith_K": None,            # None = measured bandpass T_sys(nu) (tsys_bandpass.json); a number = flat
    "correlator_efficiency": 0.988,   # imaging products: 4-bit voltages correlated (same factor as td_eta_v4)
    "n_pol": 2,
    "galactic_noise": True,           # add Galactic synchrotron (GSM2008) above the cold-sky reference
    "extra_loss_percent": 0.0,        # additional data loss on top of the RFI occupancy profile
    "pointing_s": 1260.0,             # 21-min survey pointings
    "el_min_deg": 20.0,               # targeted: minimum elevation
    "ha_max_h": 2.0,                  # targeted: max |hour angle| per transit
    "confusion_beta": 16,
    "smooth_subtract_sources": True,  # smoothed continuum: subtract sources detected at full resolution first
    "subtract_snr": 5.0,              # detection threshold (x total noise of the full-resolution image) for that
    # ---- time domain (Chronoscope pulsar and FRB products; independent of the survey/targeted mode)
    "td_track_s": 1260.0,             # track centered on transit
    "td_subband_MHz": 10.0,           # sensitivities are evaluated in sub-bands no wider than this
    "td_eta_v4": 0.988,               # 4-bit voltages: beams formed from the correlations, and targeted voltage beams
    "td_eta_i2": 0.939,               # 2-bit intensities (pulsar searches): sqrt(0.8825), one quantized stream
    "td_eta_i4": 0.994,               # 4-bit intensities (FRB search): sqrt(0.988)
    "td_scattering": "ne2025",        # "ne2025" (grid) or "cordes22" (tau-DM relation)
    "td_self_noise": True,            # on-pulse / on-burst source flux adds to the beam SEFD
    "td_confusion_uJy": 230.0,        # sidelobe confusion rms of an untapered beam at td_confusion_nu_MHz 
    "td_confusion_nu_MHz": 1410.0,
    "td_confusion_index": -0.7,
    "td_confusion_tau_s": 10.0,       # correlation time at HA 1 h for a source through the zenith
    # pulsar (one pulsar drives every pulsar product)
    "psr_period_ms": 500.0,
    "psr_width_ms": 15.0,             # intrinsic FWHM; does not scale with period
    "psr_dm": None,                   # None = half the NE2025 Galactic DM_max at the position
    "psr_flux_mJy": 0.02,             # at psr_nu_ref_MHz
    "psr_nu_ref_MHz": 1400.0,
    "psr_alpha": -1.6,
    "psr_snr": 10.0,
    "psr_untargeted_pmin_ms": 10.0, "psr_untargeted_pmax_ms": 10000.0,     
    "psr_targeted_pmin_ms": 1.0, "psr_targeted_pmax_ms": 10000.0,
    "psr_untargeted_beam_arcsec": None,   # per band [B1, B2, B3]; None = 13.5" x 930 MHz / band center
    "psr_untargeted_n_beams": 200000,
    "psr_targeted_center_MHz": 953.35,    # presets 953.35 and 1800; any center with the band inside 700-2002 MHz
    "pt_tsamp_us": 1.0,
    "pt_eta": 1.0,                    # PTA beams are formed before the antenna voltages are requantized: no loss
    # Pulsar Timing subsystem (PTA): its own pulsar, a typical timing-array millisecond pulsar
    "pta_period_ms": 4.0,
    "pta_width_ms": 0.2,              # intrinsic FWHM
    "pta_dm": 20.0,
    "pta_flux_mJy": 1.0,              # at pta_nu_ref_MHz
    "pta_nu_ref_MHz": 1400.0,
    "pta_alpha": -1.6,
    "pta_snr": 10.0,
    # FRB
    "frb_snr": 10.0,
    "frb_dm": 500.0,
    "frb_width_ms": 1.0,
    "frb_max_dm": 5000.0,
    "frb_dm_tolerance": 1.25,
    "frb_alpha_c": 1.5,               # source-count index
    "frb_gamma": 0.0,                 # rate spectral index (B3 extrapolation)
    "frb_dm_halo": 20.0,
    "frb_f_d": 0.84,                  # diffuse baryon fraction (Macquart relation)
    "frb_host_mu": 5.49, "frb_host_sigma": 0.62,     # lognormal DM_host, rest frame (Verdi et al. 2026)
    "frb_n_beams": 6000000,
    # HI mass limits
    "hi_widths_kms": [50.0, 200.0, 500.0],
    "hi_distances_Mpc": [10.0, 50.0, 100.0],
    "hi_redshifts": [0.1, 0.25, 0.5, 0.75, 1.0],
    "nhi_width_kms": 20.0,
}

# Survey geometry (Survey Implementation Plan, tiered-tile scheme 1)
THETA_HEX = 1.667
THETA_ROW = 1.45
A_HEX = THETA_HEX * THETA_ROW                 # deg^2 per pointing
PB_FWHM_1GHZ = 3.36                           # deg; Gaussian primary beam FWHM = 3.36 deg / nu[GHz]
SURVEY_DEC_EDGE = -30.45                      # southern edge of the tiling (last row center -29.725)
TIERS = [("S04", -30.45, -26.1, 19), ("S03", -26.1, -17.4, 40), ("S02", -17.4, -8.7, 42), ("S01", -8.7, 0.0, 43),
         ("N01", 0.0, 8.7, 43), ("N02", 8.7, 17.4, 42), ("N03", 17.4, 26.1, 40), ("N04", 26.1, 34.8, 37),
         ("N05", 34.8, 43.5, 33), ("N06", 43.5, 52.2, 29), ("N07", 52.2, 60.9, 24), ("N08", 60.9, 69.6, 18),
         ("N09", 69.6, 78.3, 12), ("N10", 78.3, 87.0, 6), ("N11", 87.0, 90.0, 1)]

# Natural-weighted snapshot PSF at zenith, 1.35 GHz, from dsa1650_P305_v2.5.6.8 (half-power contour fit)
PSF0_1350 = {"bmaj": 3.03, "bmin": 2.31, "pa": 90.6}

# Frequency plans
BAND_MHZ = (700.0, 2002.0)
WC_WIDTH = 130.2
WC_EDGES = [700.0 + WC_WIDTH * i for i in range(11)]
SNAP_EDGES = [700.0 + 325.5 * i for i in range(5)]
MP_WIDTH = 2.604
MP_N = 500
LINE_BANDS = {
    "ZB": {"label": "Galactic HI (Zoom B)", "f_lo": 1419.93, "f_hi": 1420.91, "nchan": 960, "chan_kHz": 1.017},
    "ZA": {"label": "HI to ~100 Mpc (Zoom A)", "f_lo": 1388.0, "f_hi": 1422.1, "nchan": 4192, "chan_kHz": 8.138},
    "NL": {"label": "HI to z~1 (Narrow Line)", "f_lo": 700.0, "f_hi": 1429.12, "nchan": 5600, "chan_kHz": 130.2},
}
# Chronoscope (Connor et al. 2026, Table 1): band, f_lo, f_hi, channel summing (untargeted)
CHR_BANDS = [("B1", 880.0, 980.0, 1), ("B2", 1310.0, 1510.0, 2), ("B3", 1650.0, 1950.0, 3)]
CHR_CHAN_MHZ = 0.12268
CHR_TARGETED_BW = 2500 * CHR_CHAN_MHZ            # 306.7 MHz
CHR_TARGETED_PRESETS = [953.35, 1800.0]
CHR_UNTARGETED_TSAMP_S = 1e-3
CHR_TARGETED_TSAMP_S = 1e-4
CHR_UNTARGETED_BEAM_1 = 13.5                     # arcsec at 930 MHz, scaled as 1/nu (Ravi et al. 2026b)
CHR_UNIQUE_AREA_DEG2 = A_HEX                     # unique sky area per pointing (2.42 deg^2; Ravi et al. 2026b)
HEX_CELL = math.sqrt(3.0) / 2.0                  # area of a hexagonal-grid cell / spacing^2
FRB_TSAMP_S = 1e-3
PT_BAND = (700.0, 2000.0)
PT_NSUB = 13
TD_LIMITS = (700.0, 2002.0)
KDM_S = 4.148808e-3                              # dispersion delay constant, s (GHz^2 / pc cm^-3)
YEAR_S = 365.25 * 86400.0
# FRB rate reference surveys (Connor et al. 2026 Sec. 3.1): rate /yr, SEFD Jy, solid angle deg^2, bandwidth MHz
FRB_RATE_REF = {"B1": ("CHIME/FRB", 1.0e3, 100.0, 200.0, 300.0), "B2": ("Parkes HTRU", 31.0, 40.0, 0.55, 340.0),
                "B3": ("Parkes HTRU", 31.0, 40.0, 0.55, 340.0)}
# Planck 2018 cosmology and baryons for the Macquart relation
H0_KMS_MPC, OMEGA_M, OMEGA_B = 67.66, 0.3097, 0.02242 / 0.6766 ** 2
MPC_CM, PC_CM, G_CGS, M_P_G = 3.0856775814913673e24, 3.0856775814913673e18, 6.6743e-8, 1.67262192e-24
CHI_E = 0.875                                    # electrons per baryon mass (Y_He = 0.25, fully ionised)
# J2000 equatorial -> Galactic rotation
GAL_ROT = [[-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
           [0.4941094278755837, -0.4448296299600112, 0.7469822444972189],
           [-0.8676661490190047, -0.1980763734312015, 0.4559837761750669]]

SCHEMES = [("natural", "optimal"), ("natural", "equal"), ("robust_freq", "optimal"), ("robust_freq", "equal"),
           ("robust_0p4", "optimal"), ("robust_0p4", "equal")]
SCHEME_LABEL = {"natural": "Natural", "robust_freq": "Robust, R = 0.46–1.94", "robust_0p4": "Robust, R = 0.4"}
SUM_LABEL = {"optimal": "optimal summation", "equal": "equal summation"}


# ============================================================================ data
@lru_cache(maxsize=None)
def _load(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)


def _rfi_file(name):
    d = _load(name)
    f = d["freq_start_MHz"] + d["freq_step_MHz"] * np.arange(len(d["occupancy_percent"]))
    return {"name": d["name"], "freq": f, "occ": np.asarray(d["occupancy_percent"], float) / 100.0}


@lru_cache(maxsize=None)
def rfi_default():
    """Default RFI profile: 'Spring Valley model extrapolated' (measured shape, 15% band-averaged loss)."""
    return _rfi_file("rfi_spring_valley_extrapolated.json")


@lru_cache(maxsize=None)
def rfi_measured():
    """Spring Valley occupancy as measured by the site RFI survey (digitized)."""
    return _rfi_file("rfi_spring_valley.json")


def make_rfi_profile(freq_mhz, occupancy, name="user profile"):
    """Build an RFI profile from arrays. Occupancy may be a fraction (0-1) or percent (0-100)."""
    f = np.asarray(freq_mhz, float)
    o = np.asarray(occupancy, float)
    if np.nanmax(o) > 1.0:
        o = o / 100.0
    s = np.argsort(f)
    return {"name": name, "freq": f[s], "occ": np.clip(o[s], 0.0, 1.0)}


def rfi_none():
    return {"name": "none (ideal)", "freq": np.array([600.0, 2100.0]), "occ": np.zeros(2)}


def occ_at(rfi, f):
    return np.interp(f, rfi["freq"], rfi["occ"], left=0.0, right=0.0)


def usable_bw_hz(rfi, f_lo, f_hi, extra_loss=0.0):
    """Unflagged bandwidth in Hz between f_lo and f_hi (MHz): integral of (1 - occupancy)."""
    width = f_hi - f_lo
    if width <= 0:
        return 0.0
    n = max(3, int(math.ceil(width / 0.1)) + 1)
    x = np.linspace(f_lo, f_hi, n)
    frac = 1.0 - _trapz(occ_at(rfi, x), x) / width
    return max(frac, 0.0) * width * 1e6 * (1.0 - extra_loss)


@lru_cache(maxsize=None)
def _ucc():
    d = _load("ucc_confusion.json")
    return (np.asarray(d["log10_theta_arcsec"]), np.asarray(d["log10_f_beta16"]), np.asarray(d["log10_f_beta25"]))


def confusion_uJy(theta_arcsec, freq_mhz, beta=16):
    """Condon UCC 'rms' confusion (uJy/beam) for a Gaussian beam of geometric-mean FWHM theta."""
    lt, f16, f25 = _ucc()
    lf = f16 if beta == 16 else f25
    x = math.log10(max(theta_arcsec, 1.0))
    f = 10 ** float(np.interp(x, lt, lf))
    return f * theta_arcsec ** 2 * (freq_mhz / 1400.0) ** -0.7


@lru_cache(maxsize=None)
def _counts(beta=16):
    """1.4-GHz source counts behind the confusion curve, and their second moment.

    The UCC curve is defined by N(>5 sigma_c) = 1 / (beta * Omega_beam) (Rosero 2026, Eq. 2), so inverting it returns
    the cumulative counts it was built from (Matthews et al. 2021); the beta = 16 and 25 curves give the same counts to
    3%. Returns S (uJy, ascending), N(>S) (per sr), the power-law index of N between table points, and
    M2(S) = integral_0^S S'^2 n(S') dS' (uJy^2 per sr), exact for power-law segments.
    """
    lt, f16, f25 = _ucc()
    lf = f16 if beta == 16 else f25
    th = 10.0 ** lt
    S = 5.0 * 10.0 ** lf * th ** 2
    N = FOUR_LN2 / (beta * math.pi * (th * ARCSEC) ** 2)
    alpha = -np.diff(np.log(N)) / np.diff(np.log(S))
    M2 = np.zeros(len(S))
    M2[0] = alpha[0] * N[0] * S[0] ** 2 / (2.0 - alpha[0])          # below the table: extend the first segment
    for k in range(len(S) - 1):
        M2[k + 1] = M2[k] + _seg_m2(N[k], S[k], alpha[k], S[k + 1])
    return S, N, alpha, M2


def _seg_m2(Nk, Sk, a, s):
    """integral_Sk^s S^2 n(S) dS for N(>S) = Nk (S/Sk)^-a."""
    if abs(2.0 - a) < 1e-9:
        return a * Nk * Sk * Sk * math.log(s / Sk)
    return a * Nk * Sk * Sk * ((s / Sk) ** (2.0 - a) - 1.0) / (2.0 - a)


def counts_m2(s_uJy, beta=16):
    """Second moment of the 1.4-GHz counts below s_uJy (uJy^2 per sr)."""
    S, N, alpha, M2 = _counts(beta)
    if s_uJy <= S[0]:
        return alpha[0] * N[0] * S[0] ** 2 * (s_uJy / S[0]) ** (2.0 - alpha[0]) / (2.0 - alpha[0])
    k = min(int(np.searchsorted(S, s_uJy, side="right")) - 1, len(S) - 2)
    return float(M2[k] + _seg_m2(N[k], S[k], alpha[k], s_uJy))


def residual_confusion_uJy(limit_uJy, limit_nu_mhz, beam, freq_mhz, beta=16):
    """Confusion (uJy/beam) left after subtracting every source brighter than limit_uJy at limit_nu_mhz.

    The remaining fainter sources are treated as a Poisson population: variance = Omega_e * M2(limit), with
    Omega_e = pi bmaj bmin / (8 ln 2) the solid angle of the squared Gaussian beam. Spectral index -0.7.
    Clustering of the faint sources and subtraction errors are not included.
    """
    s_1400 = limit_uJy * (limit_nu_mhz / 1400.0) ** 0.7
    omega_e = math.pi * beam["bmaj"] * beam["bmin"] * ARCSEC ** 2 / (2.0 * FOUR_LN2)
    return math.sqrt(omega_e * counts_m2(s_1400, beta)) * (freq_mhz / 1400.0) ** -0.7


@lru_cache(maxsize=None)
def _tsky():
    import base64
    d = _load("tsky_gsm2008.json")
    planes = []
    for s in d["log10T_milli_b64delta"]:
        a = np.frombuffer(base64.b64decode(s), dtype="<i2").reshape(d["ndec"], d["nra"]).astype(np.int64)
        planes.append(10 ** (np.cumsum(a, axis=1) / 1000.0))
    return {"f": np.asarray(d["planes_MHz"]), "T": np.asarray(planes), "Tref": np.asarray(d["Tref_K"]),
            "dec0": d["dec_start"], "ddec": d["dec_step"], "ra0": d["ra_start"], "dra": d["ra_step"],
            "ndec": d["ndec"], "nra": d["nra"]}


def tsky_K(freq_mhz, ra, dec):
    """Beam-smoothed Galactic sky temperature (K, no CMB) and cold-sky reference at freq (MHz)."""
    t = _tsky()
    y = (dec - t["dec0"]) / t["ddec"]
    y = min(max(y, 0.0), t["ndec"] - 1.000001)
    x = ((ra - t["ra0"]) / t["dra"]) % t["nra"]
    i0, j0 = int(math.floor(y)), int(math.floor(x))
    fy, fx = y - i0, x - j0
    j1 = (j0 + 1) % t["nra"]
    P = t["T"]
    v = (P[:, i0, j0] * (1 - fx) * (1 - fy) + P[:, i0, j1] * fx * (1 - fy)
         + P[:, i0 + 1, j0] * (1 - fx) * fy + P[:, i0 + 1, j1] * fx * fy)
    lf = np.log10(t["f"])
    x_f = math.log10(freq_mhz)
    T = 10 ** float(np.interp(x_f, lf, np.log10(v), left=None, right=None) if lf[0] <= x_f <= lf[-1]
                    else _extrap(x_f, lf, np.log10(v)))
    Tref = 10 ** float(np.interp(x_f, lf, np.log10(t["Tref"])) if lf[0] <= x_f <= lf[-1]
                       else _extrap(x_f, lf, np.log10(t["Tref"])))
    return T, Tref


def _extrap(x, xs, ys):
    if x < xs[0]:
        return ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
    return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])


@lru_cache(maxsize=None)
def _weighting():
    return _load("weighting_factors.json")


def robust_factors(scheme, freq_mhz, dec):
    """(beam factor, rms factor) relative to natural weighting (Rosero memo Fig. 19)."""
    if scheme == "natural":
        return 1.0, 1.0
    w = _weighting()
    key_b = "beam_robust_freq" if scheme == "robust_freq" else "beam_robust_0p4"
    key_r = "rms_robust_freq" if scheme == "robust_freq" else "rms_robust_0p4"
    decs = [30.0, -20.0, -30.0, -40.0]
    fr = np.asarray(w["freqs_MHz"], float)
    fq = min(max(freq_mhz, fr[0]), fr[-1])

    def at(dkey):
        f = w["factors"][str(int(dkey))]
        return float(np.interp(fq, fr, f[key_b])), float(np.interp(fq, fr, f[key_r]))

    d = min(max(dec, -40.0), 30.0)
    # interpolate linearly in declination between tabulated declinations (+30,-20,-30,-40)
    for hi, lo in ((30.0, -20.0), (-20.0, -30.0), (-30.0, -40.0)):
        if lo <= d <= hi:
            t = (hi - d) / (hi - lo)
            bh, rh = at(hi)
            bl, rl = at(lo)
            return bh + t * (bl - bh), rh + t * (rl - rh)
    return at(30.0)


@lru_cache(maxsize=None)
def _mosaic_z():
    return _load("mosaic_z.json")


def mosaic_z(freq_mhz, dec=None):
    """Mean mosaic weight Z (effective time / pointing time) and its min/max over the hex pattern."""
    d = _mosaic_z()
    fg = freq_mhz / 1000.0
    tp = PB_FWHM_1GHZ / fg
    zmean = 0.5665 * tp ** 2 * (1.0 - math.exp(-8.0 * math.log(2.0) * 0.911 ** 2)) / A_HEX
    zmin = float(np.interp(fg, d["freq_GHz"], d["zmin"]))
    zmax = float(np.interp(fg, d["freq_GHz"], d["zmax"]))
    edge = 1.0
    if dec is not None:
        sig = tp / (4.0 * math.sqrt(math.log(2.0)))        # row-direction sigma of the squared beam
        edge = 0.5 * math.erfc(-(dec - SURVEY_DEC_EDGE) / (sig * math.sqrt(2.0)))
    return {"zmean": zmean * edge, "zmin": zmin * edge, "zmax": zmax * edge, "edge_factor": edge}


@lru_cache(maxsize=None)
def _antennas():
    d = _load("antennas_enu.json")
    return d


BASELINE_EXACT_M = 1000.0      # baselines shorter than this are all used for the smoothing noise


@lru_cache(maxsize=None)
def baseline_sample(step=13, exact_m=BASELINE_EXACT_M):
    """Baselines for the smoothing (uv-taper) noise: equatorial-frame components (m) and count weights.

    Every baseline shorter than `exact_m` is kept with weight 1 (about 16,000), so large smoothing scales, which only
    short baselines reach, are exact. Of the longer baselines every `step`-th pair (i<j order) is kept with weight
    `step`. This agrees with all 1,360,425 baselines to within 0.3% at every scale and frequency.
    """
    a = _antennas()
    E, N, U = (np.asarray(a[k], float) for k in ("E", "N", "U"))
    i, j = np.triu_indices(len(E), 1)
    BE, BN, BU = E[j] - E[i], N[j] - N[i], U[j] - U[i]
    short = BE * BE + BN * BN + BU * BU < exact_m * exact_m
    keep = short | (np.arange(len(i)) % step == 0)
    BE, BN, BU, short = BE[keep], BN[keep], BU[keep], short[keep]
    phi = math.radians(a["site_lat_deg"])
    Lx = -math.sin(phi) * BN + math.cos(phi) * BU
    Ly = BE
    Lz = math.cos(phi) * BN + math.sin(phi) * BU
    return Lx, Ly, Lz, np.where(short, 1.0, float(step))


def site_lat():
    return _antennas()["site_lat_deg"]


# ============================================================================ geometry
def zenith_angle(ha_deg, dec, lat):
    h, d, p = math.radians(ha_deg), math.radians(dec), math.radians(lat)
    c = math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def track_plan(dec, hours, lat, el_min, ha_max_h):
    """Targeted observation: HA samples (deg) and number of transits.

    Observations are centered on transit and limited to |HA| <= ha_max_h and elevation >= el_min.
    If the requested time exceeds one transit window, it is split evenly over several transits.
    """
    p, d = math.radians(lat), math.radians(dec)
    s_el = math.sin(math.radians(el_min))
    denom = math.cos(p) * math.cos(d)
    if denom <= 1e-9:
        h_vis = 12.0 if math.sin(p) * math.sin(d) >= s_el else 0.0
    else:
        c = (s_el - math.sin(p) * math.sin(d)) / denom
        h_vis = 0.0 if c > 1 else (12.0 if c < -1 else math.degrees(math.acos(c)) / 15.0)
    if h_vis <= 0:
        return {"observable": False, "h_lim": 0.0, "n_transits": 0, "ha_half_h": 0.0, "ha_samples": []}
    h_lim = min(ha_max_h, h_vis)
    n_tr = max(1, int(math.ceil(hours / (2.0 * h_lim) - 1e-9)))
    half = hours / (2.0 * n_tr)
    ns = 1 if half < 1e-6 else max(3, min(17, 2 * int(math.ceil(half / 0.25)) + 1))
    has = [0.0] if ns == 1 else list(np.linspace(-half * 15.0, half * 15.0, ns))
    return {"observable": True, "h_lim": h_lim, "h_visible": h_vis, "n_transits": n_tr, "ha_half_h": half,
            "ha_samples": has}


def _M(ha_deg, dec, lat):
    h, d, p = math.radians(ha_deg), math.radians(dec), math.radians(lat)
    return np.array([[math.cos(h), -math.sin(p) * math.sin(h)],
                     [math.sin(d) * math.sin(h), math.sin(p) * math.sin(d) * math.cos(h) + math.cos(p) * math.cos(d)]])


def _cov_from_beam(bmaj, bmin, pa):
    a = math.radians(pa)
    vmaj = np.array([math.sin(a), math.cos(a)])
    vmin = np.array([math.cos(a), -math.sin(a)])
    return bmaj ** 2 * np.outer(vmaj, vmaj) + bmin ** 2 * np.outer(vmin, vmin)


def _beam_from_cov(P):
    ev, evec = np.linalg.eigh(P)
    v = evec[:, 1]
    return {"bmaj": math.sqrt(max(ev[1], 0)), "bmin": math.sqrt(max(ev[0], 0)),
            "pa": math.degrees(math.atan2(v[0], v[1])) % 180.0}


def psf_natural_1350(dec, ha_samples, weights, lat, psf0=None):
    """Natural-weighted (or, with psf0, any zenith snapshot) PSF at 1.35 GHz (arcsec) for a set of hour angles."""
    b0 = psf0 or PSF0_1350
    K0 = np.linalg.inv(_cov_from_beam(b0["bmaj"], b0["bmin"], b0["pa"]))
    K = np.zeros((2, 2))
    for h, w in zip(ha_samples, weights):
        M = _M(h, dec, lat)
        K += w * (M @ K0 @ M.T)
    K /= sum(weights)
    return _beam_from_cov(np.linalg.inv(K))


def scale_beam(b, factor):
    return {"bmaj": b["bmaj"] * factor, "bmin": b["bmin"] * factor, "pa": b["pa"]}


def beam_solid_angle_sr(b):
    return math.pi * (b["bmaj"] * ARCSEC) * (b["bmin"] * ARCSEC) / FOUR_LN2


def tb_K(sigma_jy, freq_mhz, b):
    lam = C_LIGHT / (freq_mhz * 1e6)
    return sigma_jy * JY * lam ** 2 / (2.0 * K_B * beam_solid_angle_sr(b))


def smooth_plan(b, target_arcsec):
    """Kernel (along PSF axes) that brings beam b to a circular target FWHM (quadrature approximation)."""
    if not target_arcsec or target_arcsec <= b["bmin"]:
        return None
    k_maj = math.sqrt(max(target_arcsec ** 2 - b["bmaj"] ** 2, 0.0))
    k_min = math.sqrt(target_arcsec ** 2 - b["bmin"] ** 2)
    out = {"bmaj": max(target_arcsec, b["bmaj"]), "bmin": target_arcsec, "pa": b["pa"],
           "k_maj": k_maj, "k_min": k_min}
    if out["bmaj"] < out["bmin"]:
        out["bmaj"], out["bmin"] = out["bmin"], out["bmaj"]
    return out


def taper_noise_factor(kernel, freq_mhz, dec, ha_samples, weights, lat):
    """Noise increase (Jy per smoothed beam) for image-plane Gaussian convolution == uv Gaussian taper.

    factor = sqrt(sum w T^2 * sum w) / sum w T over the visibilities of the observation (see baseline_sample).
    """
    if kernel is None:
        return 1.0
    Lx, Ly, Lz, cnt = baseline_sample()
    ctot = float(cnt.sum())
    if len(ha_samples) > 5:                      # the taper factor varies slowly along a track: 5 samples suffice
        idx = [int(math.floor(i * (len(ha_samples) - 1) / 4.0 + 0.5)) for i in range(5)]
        ha_samples = [ha_samples[i] for i in idx]
        weights = [weights[i] for i in idx]
    lam = C_LIGHT / (freq_mhz * 1e6)
    a = math.radians(kernel["pa"])
    emaj = (math.sin(a), math.cos(a))
    emin = (math.cos(a), -math.sin(a))
    cmaj = (math.pi ** 2 / FOUR_LN2) * (kernel["k_maj"] * ARCSEC) ** 2
    cmin = (math.pi ** 2 / FOUR_LN2) * (kernel["k_min"] * ARCSEC) ** 2
    d = math.radians(dec)
    s_wT = s_wT2 = s_w = 0.0
    for h, w in zip(ha_samples, weights):
        hr = math.radians(h)
        u = (math.sin(hr) * Lx + math.cos(hr) * Ly) / lam
        v = (-math.sin(d) * math.cos(hr) * Lx + math.sin(d) * math.sin(hr) * Ly + math.cos(d) * Lz) / lam
        pm = u * emaj[0] + v * emaj[1]
        pn = u * emin[0] + v * emin[1]
        T = np.exp(-(cmaj * pm * pm + cmin * pn * pn))
        s_wT += w * float((cnt * T).sum())
        s_wT2 += w * float((cnt * T * T).sum())
        s_w += w * ctot
    return math.sqrt(s_wT2 * s_w) / s_wT


# ============================================================================ time domain: data and helpers
@lru_cache(maxsize=None)
def _psf_uniform():
    """Uniformly weighted snapshot PSF at zenith, 1.35 GHz (2-arcmin localization image; tools/build_psf_uniform.py)."""
    return _load("psf_uniform.json")["uniform"]


@lru_cache(maxsize=None)
def _tsys_bp():
    """Zenith T_sys bandpass on its 2-MHz grid (RFI removed; tools/build_tsys.py)."""
    d = _load("tsys_bandpass.json")
    n = len(d["tsys_zenith_K"])
    f = [d["freq_start_MHz"] + d["freq_step_MHz"] * i for i in range(n)]
    return {"f": f, "T": d["tsys_zenith_K"], "meta": d}


@lru_cache(maxsize=None)
def _tsys_za():
    """Increase of T_sys over zenith, spillover and atmosphere, on a frequency x ZA grid (tools/build_tsys_za.py)."""
    return _load("tsys_za.json")


def tsys_bandpass_K(freq_mhz):
    """Zenith T_sys (K) of the measured bandpass at freq_mhz (linear interpolation, clamped at the ends)."""
    t = _tsys_bp()
    return float(np.interp(freq_mhz, t["f"], t["T"]))


def za_increase_K(freq_mhz, za):
    """(spillover, atmosphere): increase of T_sys over its zenith value (K) at freq_mhz and zenith angle za. Bilinear
    on the table; frequency clamped to 700-2000 MHz; linear in ZA beyond the last row (80 deg)."""
    d = _tsys_za()
    fs, zs = d["freq_MHz"], d["za_deg"]
    x = min(max(freq_mhz, fs[0]), fs[-1])
    j = 0
    while j < len(fs) - 2 and fs[j + 1] <= x:
        j += 1
    u = (x - fs[j]) / (fs[j + 1] - fs[j])
    i = 0
    while i < len(zs) - 2 and zs[i + 1] <= za:
        i += 1
    v = (za - zs[i]) / (zs[i + 1] - zs[i])

    def bil(t):
        a = t[i][j] + (t[i][j + 1] - t[i][j]) * u
        b = t[i + 1][j] + (t[i + 1][j + 1] - t[i + 1][j]) * u
        return a + (b - a) * v
    return bil(d["spill_K"]), bil(d["atm_K"])


def td_subband_edges(f_lo, f_hi, width):
    n = max(1, int(math.ceil((f_hi - f_lo) / width - 1e-9)))
    w = (f_hi - f_lo) / n
    return [(f_lo + w * i, f_lo + w * (i + 1)) for i in range(n)]


@lru_cache(maxsize=None)
def _chr_taper():
    return _load("chr_taper.json")


def chr_taper(band, dec, beam_arcsec):
    """Untargeted (tapered visibility) beam: noise factor, sidelobe-rms ratio s/s0 and actual FWHM for a band and Dec.

    The table is interpolated linearly in Dec, then in beam FWHM. A requested beam narrower than the natural beam is
    untapered (factor 1); one wider than the table is clamped to the widest entry.
    """
    t = _chr_taper()
    b = t["bands"][band]
    decs = t["dec_deg"]
    d = min(max(dec, decs[0]), decs[-1])
    j = min(int(math.floor((d - decs[0]) / (decs[1] - decs[0]))), len(decs) - 2)
    u = (d - decs[j]) / (decs[j + 1] - decs[j])

    def row(key):
        return [(1 - u) * a + u * c for a, c in zip(b[key][j], b[key][j + 1])]

    fw, ft, sl = row("fwhm_arcsec"), row("f_taper"), row("sidelobe_rms")
    note = None
    x = beam_arcsec
    if x <= fw[0]:
        x = fw[0]
        note = "narrower than the natural beam: untapered"
    elif x > fw[-1]:
        x = fw[-1]
        note = "wider than the taper table: clamped"
    return {"f_taper": float(np.interp(x, fw, ft)), "sidelobe_ratio": float(np.interp(x, fw, sl)) / sl[0],
            "fwhm_arcsec": x, "natural_fwhm_arcsec": fw[0], "sidelobe_rms0": sl[0], "note": note}


def radec_to_lb(ra, dec):
    a, d = math.radians(ra), math.radians(dec)
    v = [math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)]
    g = [sum(GAL_ROT[i][k] * v[k] for k in range(3)) for i in range(3)]
    return math.degrees(math.atan2(g[1], g[0])) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, g[2]))))


def lb_to_radec(l, b):
    a, d = math.radians(l), math.radians(b)
    g = [math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)]
    v = [sum(GAL_ROT[k][i] * g[k] for k in range(3)) for i in range(3)]
    return math.degrees(math.atan2(v[1], v[0])) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))


def _b64_int16(s):
    import base64
    return np.frombuffer(base64.b64decode(s), dtype="<i2").astype(np.int64)


@lru_cache(maxsize=None)
def _ne2025():
    d = _load("ne2025_grid.json")
    nd = len(d["dm_grid"])
    grids = {}
    for name, g in d["grids"].items():
        nb, nl = g["nb"], g["nl"]
        grids[name] = dict(g, dmmax=np.cumsum(_b64_int16(g["log_dmmax_b64"]).reshape(nb, nl), axis=-1) / 1000.0,
                           taux=np.cumsum(_b64_int16(g["log_taux_b64"]).reshape(nb, nl), axis=-1) / 1000.0,
                           dist=np.cumsum(_b64_int16(g["log_dist_b64"]).reshape(nb, nl, nd), axis=-1) / 1000.0,
                           tau=np.cumsum(_b64_int16(g["log_tau_b64"]).reshape(nb, nl, nd), axis=-1) / 1000.0)
    return {"ldm": [math.log10(x) for x in d["dm_grid"]], "grids": grids, "meta": d}


def ne2025_at(l, b, dm):
    """NE2025 grid: distance (kpc) and Galactic-source tau at 1 GHz (ms) for DM, DM_max and extragalactic tau_X (ms).

    Trilinear in (l, b, log DM) on log D and log tau; tau_X bilinear in (l, b) on log tau_X; DM_max from the nearest
    sightline. DM beyond the grid or beyond DM_max returns the clamped (saturated) values.
    """
    n = _ne2025()
    inner = n["grids"].get("inner")
    g = inner if inner is not None and inner["b0"] <= b <= inner["b0"] + inner["db"] * (inner["nb"] - 1) \
        else n["grids"]["outer"]
    nl, nb = g["nl"], g["nb"]
    x = ((l - g["l0"]) / g["dl"]) % nl
    y = min(max((b - g["b0"]) / g["db"], 0.0), nb - 1.0)
    ldm = n["ldm"]
    z = min(max(math.log10(max(dm, 1e-3)), ldm[0]), ldm[-1])
    k = min(int(np.searchsorted(ldm, z, side="right")) - 1, len(ldm) - 2)
    fz = (z - ldm[k]) / (ldm[k + 1] - ldm[k])
    i0 = min(int(math.floor(y)), nb - 2)
    fy = y - i0
    j0 = int(math.floor(x))
    fx = x - j0
    j1 = (j0 + 1) % nl

    def tri(A):
        s = 0.0
        for ii, wy in ((i0, 1 - fy), (i0 + 1, fy)):
            for jj, wx in ((j0, 1 - fx), (j1, fx)):
                s += wy * wx * ((1 - fz) * A[ii, jj, k] + fz * A[ii, jj, k + 1])
        return s

    ni = int(math.floor(y + 0.5))
    nj = int(math.floor(x + 0.5)) % nl
    dm_max = 10 ** float(g["dmmax"][ni, nj])
    T = g["taux"]
    ltx = ((1 - fy) * ((1 - fx) * T[i0, j0] + fx * T[i0, j1]) + fy * ((1 - fx) * T[i0 + 1, j0] + fx * T[i0 + 1, j1]))
    return {"dist_kpc": 10 ** tri(g["dist"]), "tau_1GHz_ms": 10 ** tri(g["tau"]), "dm_max": dm_max,
            "tau_x_1GHz_ms": 10 ** float(ltx), "saturated": dm > dm_max}


def tau_cordes22_ms(dm, freq_mhz):
    """Cordes et al. (2022) tau-DM relation (ms), nu^-4 scaling."""
    return 1.90e-7 * dm ** 1.5 * (1.0 + 3.55e-5 * dm ** 3) * (freq_mhz / 1000.0) ** -4.0


def t_dm_s(dm, chan_mhz, freq_mhz):
    """Intra-channel dispersion smearing (s): 8.3 us x DM x channel (MHz) / nu_GHz^3."""
    return 8.3e-6 * dm * chan_mhz / (freq_mhz / 1000.0) ** 3


def dq_dh(ha_deg, dec, lat):
    """Rate of change of parallactic angle with hour angle (rad / rad)."""
    h, d, p = math.radians(ha_deg), math.radians(dec), math.radians(lat)
    cz = math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h)
    s2 = max(1.0 - cz * cz, 1e-12)
    return math.cos(p) * (math.sin(p) * math.cos(d) * math.cos(h) - math.cos(p) * math.sin(d)) / s2


def confusion_tau_s(tau_ref, dec, half_h, lat):
    """Confusion correlation time: tau_ref x |dq/dt| at the reference (HA 1 h, Dec = latitude) / mean |dq/dt| over the
    track (midpoint rule, 32 samples over +-half_h hours), clamped to [1, 1000] s."""
    ref = abs(dq_dh(15.0, lat, lat))
    n = 32
    if half_h <= 0:
        mean = abs(dq_dh(0.0, dec, lat))
    else:
        mean = sum(abs(dq_dh(-half_h * 15.0 + (i + 0.5) * 2 * half_h * 15.0 / n, dec, lat)) for i in range(n)) / n
    return min(max(tau_ref * ref / max(mean, 1e-12), 1.0), 1000.0)


def lorentz_psd(f, sigma, tau):
    """One-sided Lorentzian power spectrum with integral sigma^2."""
    return 4.0 * sigma * sigma * tau / (1.0 + (2.0 * math.pi * f * tau) ** 2)


def psr_confusion_factor(period_s, weff_s, tsamp_s, sigma_1s, sigma_c, tau_c):
    """S/N factor from red sidelobe confusion for matched folding of a Gaussian profile (FWHM weff)."""
    if sigma_c <= 0 or not math.isfinite(sigma_1s) or weff_s >= period_s:
        return 1.0
    p_th = 2.0 * sigma_1s * sigma_1s
    c = math.pi ** 2 * weff_s ** 2 / (FOUR_LN2 * period_s ** 2)
    num = den = 0.0
    k = 1
    while k < 1000000:
        a = math.exp(-c * k * k)
        if a < 1e-3 or k / period_s > 0.5 / tsamp_s:
            break
        num += a * a / (p_th + lorentz_psd(k / period_s, sigma_c, tau_c))
        den += a * a / p_th
        k += 1
    return math.sqrt(num / den) if den > 0 else 1.0


def frb_confusion_factor(weff_s, sigma_1s, sigma_c, tau_c, n=4000):
    """S/N factor sqrt(V_th / (V_th + V_c)) for a boxcar of width W minus a running-mean baseline of max(1 s, 10 W).

    V_th = sigma_1s^2 (1/W - 1/T_b) exactly; V_c = int P_c |H|^2 df on a log grid (trapezoid in ln f).
    """
    if sigma_c <= 0 or not math.isfinite(sigma_1s):
        return 1.0
    tb = max(1.0, 10.0 * weff_s)
    v_th = sigma_1s * sigma_1s * (1.0 / weff_s - 1.0 / tb)
    lo, hi = math.log(1e-3 / max(tb, tau_c)), math.log(100.0 / weff_s)
    f = np.exp(lo + (hi - lo) * np.arange(n) / (n - 1))
    hh = np.sinc(f * weff_s) - np.sinc(f * tb)
    g = 4.0 * sigma_c * sigma_c * tau_c / (1.0 + (2.0 * math.pi * f * tau_c) ** 2) * hh * hh * f
    v_c = float(np.sum(0.5 * (g[1:] + g[:-1]))) * (hi - lo) / (n - 1)
    return math.sqrt(v_th / (v_th + v_c))


def self_noise_factor(x, delta):
    """S/N factor from self-noise: the source raises the on-pulse noise from SEFD to SEFD + S_on (x = S_on / SEFD).

    The pulse occupies a fraction delta of the data (on-pulse width / period, or burst width / (width + baseline));
    the S/N of the on-minus-off estimate then falls by [(1 + x)^2 (1 - delta) + delta]^(-1/2).
    """
    return ((1.0 + x) ** 2 * (1.0 - delta) + delta) ** -0.5


def solve_threshold(snr_of, flux0, thr, tol=1e-10, n_max=60):
    """Flux at which snr_of(flux)[0] = thr, given flux0, the solution without self-noise (a lower bound).

    The root is bracketed by stepping up from flux0 and refined by regula falsi (Illinois) on log S/N against log
    flux. Returns inf if self-noise caps the S/N below the threshold.
    """
    if not (flux0 > 0 and math.isfinite(flux0)):
        return float("inf")
    lo, s_lo = flux0, snr_of(flux0)[0]
    if not s_lo > 0:
        return float("inf")
    if s_lo >= thr * (1.0 - tol):
        return flux0 * thr / s_lo
    hi = lo * thr / s_lo
    s_hi = snr_of(hi)[0]
    k = 0
    while s_hi < thr * (1.0 - tol):
        k += 1
        if k > n_max or s_hi <= s_lo:
            return float("inf")                     # the S/N saturates below the threshold
        lo, s_lo = hi, s_hi
        hi = hi * 2.0 * thr / s_hi
        s_hi = snr_of(hi)[0]
    if s_hi <= thr * (1.0 + tol):
        return hi * thr / s_hi
    a, fa = math.log(lo), math.log(s_lo / thr)
    b, fb = math.log(hi), math.log(s_hi / thr)
    side = 0
    c = b
    for _ in range(n_max):
        c = (a * fb - b * fa) / (fb - fa)
        fc = math.log(snr_of(math.exp(c))[0] / thr)
        if abs(fc) < tol:
            break
        if fc * fb > 0:
            b, fb = c, fc
            if side == -1:
                fa *= 0.5
            side = -1
        else:
            a, fa = c, fc
            if side == 1:
                fb *= 0.5
            side = 1
    return math.exp(c)


def hex_straddle(beam, power=1.0):
    """Mean response of an elliptical Gaussian beam over a hexagonal cell whose spacing is its geometric-mean FWHM.

    With power p it returns <r^p>^(1/p): p = 1 for the fluence limit, p = alpha_c (the source-count index) for rates.
    Pointy-top hexagon (vertices N and S), circumradius a / sqrt(3), split into 6 triangles of 20^2 sub-triangles
    (centroid rule).
    """
    a = math.sqrt(beam["bmaj"] * beam["bmin"])
    R = a / math.sqrt(3.0)
    K = np.linalg.inv(_cov_from_beam(beam["bmaj"], beam["bmin"], beam["pa"]))
    m = 20
    s = 0.0
    cnt = 0
    for t in range(6):
        a0, a1 = math.radians(90.0 + 60.0 * t), math.radians(150.0 + 60.0 * t)
        P1 = (R * math.cos(a0), R * math.sin(a0))
        P2 = (R * math.cos(a1), R * math.sin(a1))
        for i in range(m):
            for j in range(m - i):
                for up in (0, 1):
                    if up and j == m - i - 1:
                        continue
                    if up == 0:
                        u, v = (i + 1.0 / 3.0) / m, (j + 1.0 / 3.0) / m
                    else:
                        u, v = (i + 2.0 / 3.0) / m, (j + 2.0 / 3.0) / m
                    x = u * P1[0] + v * P2[0]
                    y = u * P1[1] + v * P2[1]
                    q = K[0, 0] * x * x + 2 * K[0, 1] * x * y + K[1, 1] * y * y
                    s += math.exp(-FOUR_LN2 * q * power)
                    cnt += 1
    return (s / cnt) ** (1.0 / power)


def dm_trial_loss(tol, n=200):
    """Mean of sqrt(W / W(dDM)) over a uniform DM offset within +-half a trial step, with the smearing at half a step
    raising W by the factor tol: int_0^1 (1 + (tol^2 - 1) x^2)^(-1/4) dx (Simpson, n intervals)."""
    c = tol * tol - 1.0
    h = 1.0 / n
    s = 0.0
    for i in range(n + 1):
        x = i * h
        w = 1.0 if i in (0, n) else (4.0 if i % 2 else 2.0)
        s += w * (1.0 + c * x * x) ** -0.25
    return s * h / 3.0


@lru_cache(maxsize=None)
def _macquart_table(f_d):
    """<DM_cosmic>(z) on z = 0..10 (step 0.005), trapezoid cumulative integral of (1+z)/E(z) (Planck 2018)."""
    h0 = H0_KMS_MPC * 1e5 / MPC_CM
    kk = 3.0 * 2.99792458e10 * h0 * OMEGA_B * f_d * CHI_E / (8.0 * math.pi * G_CGS * M_P_G) / PC_CM
    n = 2000
    zs = [10.0 * i / n for i in range(n + 1)]
    g = [(1 + z) / math.sqrt(OMEGA_M * (1 + z) ** 3 + 1 - OMEGA_M) for z in zs]
    dm = [0.0]
    for i in range(1, n + 1):
        dm.append(dm[-1] + 0.5 * (g[i] + g[i - 1]) * (zs[i] - zs[i - 1]) * kk)
    return np.asarray(zs), np.asarray(dm)


def dm_cosmic(z, f_d=0.84):
    zs, dm = _macquart_table(f_d)
    return float(np.interp(z, zs, dm))


def frb_dm_trials(wint_s, tsamp_s, chan_mhz, fc, f_lo, f_hi, dm_max, tol):
    """Number of DM trials from 0 to dm_max, each step set so that the smearing across the band at half a step raises
    the width (intrinsic, sampling and intra-channel smearing at fc) by the factor tol."""
    k = KDM_S * ((f_lo / 1000.0) ** -2 - (f_hi / 1000.0) ** -2)          # s per pc cm^-3 across the band
    c = 2.0 * math.sqrt(tol * tol - 1.0) / k
    dm, n = 0.0, 0
    while dm < dm_max and n < 1000000:
        td = t_dm_s(dm, chan_mhz, fc)
        dm += c * math.sqrt(wint_s * wint_s + tsamp_s * tsamp_s + td * td)
        n += 1
    return n


def frb_rate_solid_angle(n_beams, beam_arcsec, pb_fwhm_deg, alpha):
    """Effective solid angle (deg^2) of the FRB search for rates, in units of a primary-beam FWHM area.

    The beams tile a hexagonal grid at their FWHM, so they cover A = N (sqrt3/2) theta^2, taken as a centered disk.
    Each position is weighted by r_PB^alpha (rate per solid angle at primary-beam response r_PB), normalized so that
    a search covering exactly the FWHM disk has the FWHM area, as the reference surveys are counted.
    """
    a_cov = n_beams * HEX_CELL * (beam_arcsec / 3600.0) ** 2
    rho2 = a_cov / math.pi
    w = (1.0 - math.exp(-FOUR_LN2 * alpha * rho2 / pb_fwhm_deg ** 2)) / (1.0 - 2.0 ** -alpha)
    return math.pi / 4.0 * pb_fwhm_deg ** 2 * w, a_cov


def frb_rate(r_ref, omega_ref, sefd_ref, bw_ref, omega, sefd, bw, expo):
    """Connor et al. (2026) eq. 2: R = R_i (Omega/Omega_i) [(SEFD_i/SEFD) sqrt(B/B_i)]^expo."""
    return r_ref * (omega / omega_ref) * ((sefd_ref / sefd) * math.sqrt(bw / bw_ref)) ** expo


# ============================================================================ calculator
class DSACalculator:
    """DSA sensitivity calculator: one model (instrument, RFI profile, parameters), any number of observations.

    DSACalculator(rfi=None, **params): params are keys of DEFAULTS (unknown keys are ignored); rfi is an RFI
    profile (None = Spring Valley model extrapolated; rfi_measured(), rfi_none(), make_rfi_profile(freq, occ)).
    calculate(...) returns every product for one observation. Documentation: README.md and COOKBOOK.md in the
    calculator's python/ folder.
    """

    def __init__(self, allocation="v2", rfi=None, **params):
        self.p = dict(DEFAULTS)
        self.p.update(params)
        self.rfi = rfi if rfi is not None else rfi_default()
        self.lat = site_lat()
        self.allocation_name = allocation
        self._alloc = None
        self._gcache = {}
        self._tzcache = {}

    # ---------------------------------------------------------------- basic instrument
    @property
    def extra_loss(self):
        return self.p["extra_loss_percent"] / 100.0

    def gal_excess_K(self, freq_mhz, ra, dec):
        if not self.p["galactic_noise"]:
            return 0.0
        key = (round(freq_mhz, 4), round(ra, 6), round(dec, 6))
        v = self._gcache.get(key)
        if v is None:
            T, Tref = tsky_K(freq_mhz, ra, dec)
            v = self._gcache[key] = T - Tref
        return v

    def tz_K(self, f_lo, f_hi=None):
        """Zenith T_sys (K) at f_lo, or the effective value over [f_lo, f_hi]: <(1 - occupancy) T^-2>^-1/2, the T_sys
        that gives the noise of the optimally weighted unflagged channels. A number in tsys_zenith_K is used flat."""
        flat = self.p["tsys_zenith_K"]
        if flat is not None:
            return float(flat)
        if f_hi is None or f_hi <= f_lo:
            return tsys_bandpass_K(f_lo)
        key = (round(f_lo, 6), round(f_hi, 6))
        v = self._tzcache.get(key)
        if v is None:
            n = max(3, int(math.ceil((f_hi - f_lo) / 0.5)) + 1)
            x = np.linspace(f_lo, f_hi, n)
            w = 1.0 - occ_at(self.rfi, x)
            T = np.interp(x, _tsys_bp()["f"], _tsys_bp()["T"])
            sw = float(w.sum())
            v = float((w * T ** -2).sum() / sw) ** -0.5 if sw > 0 else tsys_bandpass_K(0.5 * (f_lo + f_hi))
            self._tzcache[key] = v
        return v

    def sefd_jy(self, freq_mhz, za, ra, dec, f_band=None):
        """Per-antenna SEFD (Jy) at freq_mhz and zenith angle za; f_band = (lo, hi) averages T_sys over that band."""
        p = self.p
        area = math.pi * (p["dish_diameter_m"] / 2.0) ** 2
        tz = self.tz_K(*f_band) if f_band else self.tz_K(freq_mhz)
        gal = self.gal_excess_K(freq_mhz, ra, dec)
        spill, atm = za_increase_K(freq_mhz, za)
        return 2.0 * K_B * (tz + spill + atm + gal) / p["aperture_efficiency"] / area / JY

    def tsys_breakdown(self, freq_mhz, za, ra, dec):
        T, Tref = tsky_K(freq_mhz, ra, dec)
        tz = self.tz_K(freq_mhz)
        spill, atm = za_increase_K(freq_mhz, za)
        gal = (T - Tref) if self.p["galactic_noise"] else 0.0
        return {"tsys_K": tz + spill + atm + gal, "tsys_zenith_K": tz, "spill_K": spill, "atm_K": atm,
                "galactic_excess_K": gal, "tsky_gal_K": T, "tsky_ref_K": Tref}

    def tsys_band(self, za, ra, dec):
        """Full-band (0.70-2.00 GHz) T_sys and SEFD as used by the full-band products: zenith T_sys averaged over the
        unflagged channels, with spillover, atmosphere and Galactic excess at the band center."""
        lo, hi = BAND_MHZ
        fc = 0.5 * (lo + hi)
        tz = self.tz_K(lo, hi)
        spill, atm = za_increase_K(fc, za)
        gal = self.gal_excess_K(fc, ra, dec)
        return {"tsys_band_K": tz + spill + atm + gal, "tsys_band_zenith_K": tz, "spill_band_K": spill,
                "atm_band_K": atm, "galactic_band_K": gal, "sefd_band_Jy": self.sefd_jy(fc, za, ra, dec, (lo, hi))}

    def radiometer_jy(self, sefd, bw_hz, t_s, beam="image"):
        """Image (cross-correlation) or phased-array beam noise for bandwidth bw_hz and time t_s."""
        p = self.p
        n = p["n_ant"]
        if bw_hz <= 0 or t_s <= 0:
            return float("inf")
        nb = n * (n - 1) if beam == "image" else n * n
        return sefd / (p["correlator_efficiency"] * math.sqrt(nb * p["n_pol"] * bw_hz * t_s))

    # ---------------------------------------------------------------- survey allocation
    def allocation(self):
        if self._alloc is None:
            self._alloc = _load("allocation.json")
        return self._alloc

    def tile_of(self, ra, dec):
        if dec < SURVEY_DEC_EDGE:
            return None
        for name, d0, d1, n in TIERS:
            if d0 <= dec < d1 or (name == "N11" and dec >= d0):
                i = int((ra % 360.0) / (360.0 / n)) % n
                return name, i, d0, d1, n
        return None

    def epochs_at(self, ra, dec, variant=None):
        t = self.tile_of(ra, dec)
        if t is None:
            return 0, None
        al = self.allocation()
        v = variant or al["default_variant"]
        key = "%s_%d" % (t[0], t[1])
        tile = al["tiles"][key]
        return int(tile["epochs"][v]), {"tile": key, "tier": t[0], "index": t[1], "dec_lo": t[2], "dec_hi": t[3],
                                         "ra_lo": 360.0 / t[4] * t[1], "ra_hi": 360.0 / t[4] * (t[1] + 1),
                                         "class": tile["class"], "n_pointings": tile["n_ptg"], "variant": v}

    # ---------------------------------------------------------------- observation set-up
    def setup(self, mode, ra, dec, depth="full", n_epochs=None, hours=None, variant=None):
        lat = self.lat
        obs = {"mode": mode, "ra": ra, "dec": dec, "lat": lat}
        obs["za_transit"] = abs(lat - dec)
        obs["el_transit"] = 90.0 - obs["za_transit"]
        if mode == "survey":
            ne, tinfo = self.epochs_at(ra, dec, variant)
            obs["epochs_full"] = ne
            obs["tile"] = tinfo
            obs["in_survey"] = tinfo is not None
            if depth == "single":
                n = 1
            elif depth == "custom":
                n = max(1, int(round(n_epochs or 1)))
            else:
                n = ne
            obs["n_epochs"] = n
            obs["depth"] = depth
            obs["ha_samples"] = [0.0]
            obs["time_per_pointing_s"] = self.p["pointing_s"]
            obs["total_time_s"] = n * self.p["pointing_s"]
            obs["observable"] = obs["in_survey"] and n > 0
        else:
            hrs = float(hours or 1.0)
            tp = track_plan(dec, hrs, lat, self.p["el_min_deg"], self.p["ha_max_h"])
            obs.update(tp)
            obs["hours"] = hrs
            obs["total_time_s"] = hrs * 3600.0
        return obs

    def _ha_weights(self, obs, freq_mhz, f_band=None):
        """Sensitivity weights 1/SEFD^2 along the track (zenith-angle dependence + sky)."""
        ws = []
        for h in obs["ha_samples"]:
            za = zenith_angle(h, obs["dec"], self.lat)
            ws.append(self.sefd_jy(freq_mhz, za, obs["ra"], obs["dec"], f_band) ** -2)
        return ws

    def sefd_eff(self, obs, freq_mhz, f_band=None):
        if obs["mode"] == "survey":
            return self.sefd_jy(freq_mhz, obs["za_transit"], obs["ra"], obs["dec"], f_band)
        ws = self._ha_weights(obs, freq_mhz, f_band)
        return (sum(ws) / len(ws)) ** -0.5

    NEFF_FREQS = (700.0, 800.0, 950.0, 1100.0, 1300.0, 1500.0, 1750.0, 2002.0)

    def neff_table(self, obs, n_override=None):
        """Beam-weighted effective number of epochs at the reference frequencies.

        The squared primary beam (Gaussian, FWHM 3.36 deg / nu) is sampled on a 21 x 21 tangent-plane grid out to
        +-3.33 sigma around the position; each sample takes the epochs of the tile it falls in (0 outside the survey).
        This blends steps between tiles, includes the southern survey edge and works at the pole.
        """
        key = "_neff_%s" % (n_override,)
        if key in obs:
            return obs[key]
        al = self.allocation()
        v = obs["tile"]["variant"] if obs.get("tile") else al["default_variant"]
        a0, d0 = math.radians(obs["ra"]), math.radians(obs["dec"])
        sd0, cd0 = math.sin(d0), math.cos(d0)
        out = []
        for f in self.NEFF_FREQS:
            sig = (PB_FWHM_1GHZ / (f / 1000.0)) / (4.0 * math.sqrt(math.log(2.0)))
            steps = [i * sig / 3.0 for i in range(-10, 11)]
            sw = swn = 0.0
            for x in steps:
                for y in steps:
                    w = math.exp(-(x * x + y * y) / (2.0 * sig * sig))
                    xi, eta = math.radians(x), math.radians(y)
                    den = cd0 - eta * sd0
                    ra = math.degrees(a0 + math.atan2(xi, den)) % 360.0
                    dec = math.degrees(math.atan2(sd0 + eta * cd0, math.sqrt(xi * xi + den * den)))
                    t = self.tile_of(ra, dec)
                    if t is None:
                        n = 0.0
                    elif n_override is not None:
                        n = float(n_override)
                    else:
                        n = float(al["tiles"]["%s_%d" % (t[0], t[1])]["epochs"][v])
                    sw += w
                    swn += w * n
            out.append(swn / sw)
        obs[key] = out
        return out

    def survey_weight(self, obs, freq_mhz, n_override=None):
        """Effective time / pointing time: mean mosaic weight Z(nu) x beam-weighted effective epochs."""
        tab = self.neff_table(obs, n_override)
        neff = float(np.interp(math.log10(freq_mhz), [math.log10(v) for v in self.NEFF_FREQS], tab))
        return mosaic_z(freq_mhz)["zmean"] * neff

    def eff_time_s(self, obs, freq_mhz):
        """Effective integration time at freq. Survey: 21 min x sum over overlapping pointings of epochs x beam^2."""
        if obs["mode"] == "survey":
            n = None if obs.get("depth") == "full" else obs["n_epochs"]
            return self.p["pointing_s"] * self.survey_weight(obs, freq_mhz, n)
        return obs["total_time_s"]

    def psf_nat(self, obs, freq_mhz):
        """Natural-weighted PSF (arcsec) at freq for this observation."""
        key = (obs["mode"], obs["dec"], tuple(obs["ha_samples"]))
        b = self._pcache.get(key) if hasattr(self, "_pcache") else None
        if b is None:
            ws = self._ha_weights(obs, 1350.0) if obs["mode"] != "survey" else [1.0]
            b = psf_natural_1350(obs["dec"], obs["ha_samples"], ws, self.lat)
            if not hasattr(self, "_pcache"):
                self._pcache = {}
            self._pcache[key] = b
        return scale_beam(b, 1350.0 / freq_mhz)

    # ---------------------------------------------------------------- continuum
    def continuum_windows(self, obs, scheme):
        imaging, _ = scheme
        rows = []
        for i in range(10):
            f_lo, f_hi = WC_EDGES[i], WC_EDGES[i + 1]
            fc = 0.5 * (f_lo + f_hi)
            bw = usable_bw_hz(self.rfi, f_lo, f_hi, self.extra_loss)
            sefd = self.sefd_eff(obs, fc, (f_lo, f_hi))
            teff = self.eff_time_s(obs, fc)
            bfac, rfac = robust_factors(imaging, fc, obs["dec"])
            sig = rfac * self.radiometer_jy(sefd, bw, teff)
            psf = scale_beam(self.psf_nat(obs, fc), bfac)
            rows.append({"window": i + 1, "f_lo": f_lo, "f_hi": f_hi, "f_center": fc, "bw_usable_MHz": bw / 1e6,
                         "sefd_jy": sefd, "t_eff_s": teff, "sigma_jy": sig, "psf": psf, "rms_factor": rfac,
                         "beam_factor": bfac})
        return rows

    def combine_fc(self, rows, summation, beta):
        ok = [r for r in rows if math.isfinite(r["sigma_jy"]) and r["sigma_jy"] > 0]
        w = [1.0 / r["sigma_jy"] ** 2 if summation == "optimal" else 1.0 for r in ok]
        sw = sum(w)
        sig = math.sqrt(sum(wi ** 2 * r["sigma_jy"] ** 2 for wi, r in zip(w, ok))) / sw
        nu = sum(wi * r["f_center"] for wi, r in zip(w, ok)) / sw
        Kinv = sum(wi * np.linalg.inv(_cov_from_beam(r["psf"]["bmaj"], r["psf"]["bmin"], r["psf"]["pa"]))
                   for wi, r in zip(w, ok)) / sw
        psf = _beam_from_cov(np.linalg.inv(Kinv))
        theta = math.sqrt(psf["bmaj"] * psf["bmin"])
        conf = confusion_uJy(theta, nu, beta) * 1e-6
        return {"sigma_jy": sig, "nu_eff": nu, "psf": psf, "confusion_jy": conf,
                "total_jy": math.hypot(sig, conf), "weights": [wi / sw for wi in w]}

    def choose_scheme(self, obs_full, beta):
        """Weighting scheme minimizing the total (thermal + confusion) noise of the full-band image."""
        best, table = None, []
        for sc in SCHEMES:
            rows = self.continuum_windows(obs_full, sc)
            fc = self.combine_fc(rows, sc[1], beta)
            table.append({"imaging": sc[0], "summation": sc[1], "thermal_uJy": fc["sigma_jy"] * 1e6,
                          "confusion_uJy": fc["confusion_jy"] * 1e6, "total_uJy": fc["total_jy"] * 1e6,
                          "nu_eff_MHz": fc["nu_eff"], "psf": fc["psf"]})
            if best is None or fc["total_jy"] < best[1]:
                best = (sc, fc["total_jy"])
        return best[0], table

    def continuum(self, obs, scheme, smooth_arcsec=0.0):
        beta = self.p["confusion_beta"]
        rows = self.continuum_windows(obs, scheme)
        fc = self.combine_fc(rows, scheme[1], beta)
        out_rows = []
        for r in rows:
            th = math.sqrt(r["psf"]["bmaj"] * r["psf"]["bmin"])
            conf = confusion_uJy(th, r["f_center"], beta) * 1e-6
            out_rows.append({
                "window": r["window"], "f_lo_MHz": r["f_lo"], "f_hi_MHz": r["f_hi"], "f_center_MHz": r["f_center"],
                "bw_usable_MHz": r["bw_usable_MHz"], "sefd_Jy": r["sefd_jy"], "t_eff_s": r["t_eff_s"],
                "thermal_uJy": r["sigma_jy"] * 1e6, "confusion_uJy": conf * 1e6,
                "total_uJy": math.hypot(r["sigma_jy"], conf) * 1e6, "psf": r["psf"],
                "tb_thermal_mK": tb_K(r["sigma_jy"], r["f_center"], r["psf"]) * 1e3,
                "z_mosaic": mosaic_z(r["f_center"], obs["dec"]) if obs["mode"] == "survey" else None})
        fcd = {"thermal_uJy": fc["sigma_jy"] * 1e6, "confusion_uJy": fc["confusion_jy"] * 1e6,
               "total_uJy": fc["total_jy"] * 1e6, "nu_eff_MHz": fc["nu_eff"], "psf": fc["psf"],
               "tb_thermal_mK": tb_K(fc["sigma_jy"], fc["nu_eff"], fc["psf"]) * 1e3,
               "tb_total_mK": tb_K(fc["total_jy"], fc["nu_eff"], fc["psf"]) * 1e3,
               "window_weights": fc["weights"], "imaging": scheme[0], "summation": scheme[1]}
        res = {"windows": out_rows, "fc": fcd}
        if smooth_arcsec and smooth_arcsec > 0:
            res["smoothed"] = self.continuum_smoothed(obs, smooth_arcsec, fcd)
        return res

    def continuum_smoothed(self, obs, target, detect):
        """Full-band image convolved to a circular target resolution (natural weights, optimal summation).

        `detect` is the full-resolution full-band image. Sources above subtract_snr x its total noise can be subtracted
        before smoothing; the confusion is then that of the fainter sources left behind (residual_confusion_uJy).
        Without subtraction it is the UCC value for the smoothed beam.
        """
        beta = self.p["confusion_beta"]
        rows = self.continuum_windows(obs, ("natural", "optimal"))
        srows = []
        for r in rows:
            k = smooth_plan(r["psf"], target)
            if k is None:
                nf, psf = 1.0, r["psf"]
            else:
                ws = self._ha_weights(obs, r["f_center"]) if obs["mode"] != "survey" else [1.0]
                nf = taper_noise_factor(k, r["f_center"], obs["dec"], obs["ha_samples"], ws, self.lat)
                psf = {"bmaj": k["bmaj"], "bmin": k["bmin"], "pa": k["pa"]}
            srows.append(dict(r, sigma_jy=r["sigma_jy"] * nf, psf=psf, noise_factor=nf))
        fc = self.combine_fc(srows, "optimal", beta)
        sig, nu, psf = fc["sigma_jy"], fc["nu_eff"], fc["psf"]
        limit = self.p["subtract_snr"] * detect["total_uJy"]
        resid = residual_confusion_uJy(limit, detect["nu_eff_MHz"], psf, nu, beta) * 1e-6
        ucc = fc["confusion_jy"]
        applied = bool(self.p["smooth_subtract_sources"])
        conf = resid if applied else ucc
        return {"target_arcsec": target, "thermal_uJy": sig * 1e6, "confusion_uJy": conf * 1e6,
                "total_uJy": math.hypot(sig, conf) * 1e6, "nu_eff_MHz": nu, "psf": psf,
                "tb_thermal_mK": tb_K(sig, nu, psf) * 1e3,
                "tb_total_mK": tb_K(math.hypot(sig, conf), nu, psf) * 1e3,
                "noise_factors": [r["noise_factor"] for r in srows],
                "subtraction": {"applied": applied, "limit_uJy": limit, "limit_nu_MHz": detect["nu_eff_MHz"],
                                "residual_confusion_uJy": resid * 1e6,
                                "tb_total_subtracted_mK": tb_K(math.hypot(sig, resid), nu, psf) * 1e3,
                                "unsubtracted_confusion_uJy": ucc * 1e6,
                                "tb_total_unsubtracted_mK": tb_K(math.hypot(sig, ucc), nu, psf) * 1e3}}

    def snapshots(self, obs, scheme):
        """6-s intra-pointing images (Stokes I/V), 4 subbands + full band, primary-beam center."""
        beta = self.p["confusion_beta"]
        t = 6.0
        out = []
        bands = [(SNAP_EDGES[i], SNAP_EDGES[i + 1]) for i in range(4)] + [(BAND_MHZ[0], BAND_MHZ[1])]
        sub = []
        for k, (lo, hi) in enumerate(bands[:4]):
            fc = 0.5 * (lo + hi)
            za = obs["za_transit"]
            sefd = self.sefd_jy(fc, za, obs["ra"], obs["dec"], (lo, hi))
            bw = usable_bw_hz(self.rfi, lo, hi, self.extra_loss)
            bfac, rfac = robust_factors(scheme[0], fc, obs["dec"])
            obs_snap = dict(obs, ha_samples=[0.0], mode="survey")
            psf = scale_beam(self.psf_nat(obs_snap, fc), bfac)
            sig = rfac * self.radiometer_jy(sefd, bw, t)
            conf = confusion_uJy(math.sqrt(psf["bmaj"] * psf["bmin"]), fc, beta) * 1e-6
            row = {"label": "Subband %d" % (k + 1), "f_lo_MHz": lo, "f_hi_MHz": hi, "thermal_uJy": sig * 1e6,
                   "confusion_uJy": conf * 1e6, "total_uJy": math.hypot(sig, conf) * 1e6, "psf": psf,
                   "f_center": fc, "sigma_jy": sig}
            sub.append(row)
        # full band: optimal combination of the four subbands
        w = [1 / r["sigma_jy"] ** 2 for r in sub]
        sw = sum(w)
        sig = 1 / math.sqrt(sw)
        nu = sum(wi * r["f_center"] for wi, r in zip(w, sub)) / sw
        Kinv = sum(wi * np.linalg.inv(_cov_from_beam(r["psf"]["bmaj"], r["psf"]["bmin"], r["psf"]["pa"]))
                   for wi, r in zip(w, sub)) / sw
        psf = _beam_from_cov(np.linalg.inv(Kinv))
        conf = confusion_uJy(math.sqrt(psf["bmaj"] * psf["bmin"]), nu, beta) * 1e-6
        for r in sub:
            out.append({k: v for k, v in r.items() if k not in ("f_center", "sigma_jy")})
        out.append({"label": "Full band", "f_lo_MHz": BAND_MHZ[0], "f_hi_MHz": BAND_MHZ[1], "thermal_uJy": sig * 1e6,
                    "confusion_uJy": conf * 1e6, "total_uJy": math.hypot(sig, conf) * 1e6, "psf": psf})
        return out

    # ---------------------------------------------------------------- spectral line (HI)
    def line_channel(self, obs, freq_mhz, chan_hz, smooth_arcsec=0.0):
        bw = chan_hz * (1.0 - float(occ_at(self.rfi, freq_mhz))) * (1.0 - self.extra_loss)
        sefd = self.sefd_eff(obs, freq_mhz)
        teff = self.eff_time_s(obs, freq_mhz)
        sig = self.radiometer_jy(sefd, bw, teff)
        psf = self.psf_nat(obs, freq_mhz)
        res = {"freq_MHz": freq_mhz, "sigma_mJy": sig * 1e3, "psf": psf, "tb_K": tb_K(sig, freq_mhz, psf),
               "occupancy": float(occ_at(self.rfi, freq_mhz)), "sefd_Jy": sefd, "t_eff_s": teff}
        if smooth_arcsec and smooth_arcsec > 0:
            k = smooth_plan(psf, smooth_arcsec)
            if k is not None:
                ws = self._ha_weights(obs, freq_mhz) if obs["mode"] != "survey" else [1.0]
                nf = taper_noise_factor(k, freq_mhz, obs["dec"], obs["ha_samples"], ws, self.lat)
                sp = {"bmaj": k["bmaj"], "bmin": k["bmin"], "pa": k["pa"]}
                res["smoothed"] = {"target_arcsec": smooth_arcsec, "sigma_mJy": sig * nf * 1e3, "psf": sp,
                                   "tb_K": tb_K(sig * nf, freq_mhz, sp), "noise_factor": nf}
        return res

    def spectral_line(self, obs, smooth_arcsec=0.0):
        p = self.p
        out = {}
        for key, bd in LINE_BANDS.items():
            chan = bd["chan_kHz"] * 1e3
            if key == "NL":
                freqs = [HI_REST_MHZ / (1 + z) for z in [0.0] + list(p["hi_redshifts"])]
                freqs = [f for f in freqs if bd["f_lo"] <= f <= bd["f_hi"]]
            elif key == "ZA":
                freqs = [HI_REST_MHZ]
            else:
                freqs = [HI_REST_MHZ]
            chans = []
            for f in freqs:
                c = self.line_channel(obs, f, chan, smooth_arcsec)
                z = HI_REST_MHZ / f - 1.0
                dv = C_LIGHT / 1e3 * chan / (f * 1e6)
                c["z"] = z
                c["dv_kms"] = dv
                nch = max(1.0, p["nhi_width_kms"] / dv)
                # rest-frame brightness temperature is (1+z) x the observed one
                c["nhi_5sigma_cm2"] = 1.8224e18 * 5.0 * c["tb_K"] * (1 + z) * math.sqrt(nch) * dv
                if "smoothed" in c:
                    c["smoothed"]["nhi_5sigma_cm2"] = 1.8224e18 * 5.0 * c["smoothed"]["tb_K"] * (1 + z) * math.sqrt(nch) * dv
                # HI mass limits (point source, boxcar over the line width)
                ml = []
                if key == "ZA":
                    dists = list(p["hi_distances_Mpc"])
                elif key == "NL" and z > 0.01:
                    dists = [lum_dist_mpc(z)]
                else:
                    dists = []
                ml_s = []
                for D in dists:
                    for W in p["hi_widths_kms"]:
                        dnu = f * 1e6 * W / (C_LIGHT / 1e3)
                        n = max(1.0, dnu / chan)
                        sint = 5.0 * c["sigma_mJy"] * 1e-3 * math.sqrt(n) * chan      # Jy Hz
                        ml.append({"D_Mpc": D, "width_kms": W, "mhi_5sigma_Msun": 49.7 * D ** 2 * sint})
                        if "smoothed" in c:                                          # unresolved at the smoothed beam
                            sint_s = 5.0 * c["smoothed"]["sigma_mJy"] * 1e-3 * math.sqrt(n) * chan
                            ml_s.append({"D_Mpc": D, "width_kms": W, "mhi_5sigma_Msun": 49.7 * D ** 2 * sint_s})
                c["mhi_limits"] = ml
                if "smoothed" in c:
                    c["smoothed"]["mhi_limits"] = ml_s
                chans.append(c)
            dv0 = C_LIGHT / 1e3 * chan / (HI_REST_MHZ * 1e6)
            out[key] = {"label": bd["label"], "f_lo_MHz": bd["f_lo"], "f_hi_MHz": bd["f_hi"], "nchan": bd["nchan"],
                        "chan_kHz": bd["chan_kHz"], "dv_kms_at_1420": dv0,
                        "v_range_kms": [C_LIGHT / 1e3 * (1 - bd["f_hi"] / HI_REST_MHZ),
                                        C_LIGHT / 1e3 * (1 - bd["f_lo"] / HI_REST_MHZ)],
                        "z_range": [max(HI_REST_MHZ / bd["f_hi"] - 1, -1), HI_REST_MHZ / bd["f_lo"] - 1],
                        "channels": chans}
        return out

    # ---------------------------------------------------------------- polarization
    def polarization(self, obs, scheme, smooth_arcsec=0.0):
        imaging = scheme[0]
        chans = []
        inv_var = 0.0
        for k in range(MP_N):
            lo = BAND_MHZ[0] + MP_WIDTH * k
            fc = lo + 0.5 * MP_WIDTH
            bw = usable_bw_hz(self.rfi, lo, lo + MP_WIDTH, self.extra_loss)
            sefd = self.sefd_eff(obs, fc, (lo, lo + MP_WIDTH))
            teff = self.eff_time_s(obs, fc)
            _, rfac = robust_factors(imaging, fc, obs["dec"])
            sig = rfac * self.radiometer_jy(sefd, bw, teff)
            chans.append((fc, sig))
            if math.isfinite(sig):
                inv_var += 1.0 / sig ** 2
        sig_band = inv_var ** -0.5
        lam2_min = (C_LIGHT / (BAND_MHZ[1] * 1e6)) ** 2
        lam2_max = (C_LIGHT / (BAND_MHZ[0] * 1e6)) ** 2
        dlam2 = lam2_max - lam2_min
        dl2_ch = 2 * C_LIGHT ** 2 * MP_WIDTH * 1e6 / (BAND_MHZ[0] * 1e6) ** 3
        reps = []
        for f in (750.0, 1000.0, 1400.0, 1950.0):
            k = int((f - BAND_MHZ[0]) / MP_WIDTH)
            fc, sig = chans[k]
            bfac, _ = robust_factors(imaging, fc, obs["dec"])
            psf = scale_beam(self.psf_nat(obs, fc), bfac)
            row = {"freq_MHz": fc, "sigma_uJy": sig * 1e6, "psf": psf,
                   "confusion_I_uJy": confusion_uJy(math.sqrt(psf["bmaj"] * psf["bmin"]), fc,
                                                    self.p["confusion_beta"]),
                   "tb_mK": tb_K(sig, fc, psf) * 1e3}
            if smooth_arcsec and smooth_arcsec > 0:
                kk = smooth_plan(self.psf_nat(obs, fc), smooth_arcsec)
                if kk is not None:
                    ws = self._ha_weights(obs, fc) if obs["mode"] != "survey" else [1.0]
                    base = sig / robust_factors(imaging, fc, obs["dec"])[1]
                    nf = taper_noise_factor(kk, fc, obs["dec"], obs["ha_samples"], ws, self.lat)
                    sp = {"bmaj": kk["bmaj"], "bmin": kk["bmin"], "pa": kk["pa"]}
                    row["smoothed"] = {"target_arcsec": smooth_arcsec, "sigma_uJy": base * nf * 1e6, "psf": sp,
                                       "tb_mK": tb_K(base * nf, fc, sp) * 1e3, "noise_factor": nf}
            reps.append(row)
        return {"n_channels": MP_N, "chan_MHz": MP_WIDTH, "channels": reps,
                "band_qu_sigma_uJy": sig_band * 1e6,
                "rmsf_fwhm_rad_m2": 2 * math.sqrt(3) / dlam2, "max_scale_rad_m2": math.pi / lam2_min,
                "max_rm_rad_m2": math.sqrt(3) / dl2_ch, "lambda2_range_m2": [lam2_min, lam2_max],
                "spectrum": [[round(f, 3), s * 1e6] for f, s in chans]}

    # ---------------------------------------------------------------- time domain (Chronoscope pulsars and FRBs)
    def td_setup(self, ra, dec, track_s=None):
        """Time-domain observation: a track centered on transit, of td_track_s (survey mode) or the targeted time."""
        p = self.p
        t = p["td_track_s"] if track_s is None else track_s
        td = {"ra": ra, "dec": dec, "track_s": t}
        td.update(track_plan(dec, t / 3600.0, self.lat, p["el_min_deg"], p["ha_max_h"]))
        td["l_deg"], td["b_deg"] = radec_to_lb(ra, dec)
        td["za_transit"] = abs(self.lat - dec)
        td["tau_c_s"] = confusion_tau_s(p["td_confusion_tau_s"], dec, td["ha_half_h"], self.lat) \
            if td["observable"] else None
        ne, tinfo = self.epochs_at(ra, dec)
        td["survey"] = {"tile": tinfo["tile"] if tinfo else None, "class": tinfo["class"] if tinfo else None,
                        "epochs": ne, "in_7_epoch_tile": ne == 7}
        td["_sub"] = {}
        return td

    def td_sefd(self, td, f_lo, f_hi):
        """Per-antenna SEFD (Jy) over [f_lo, f_hi], combined along the track as <SEFD^-2>^-1/2 (same T_sys model as
        every other product)."""
        fc = 0.5 * (f_lo + f_hi)
        s = 0.0
        for h in td["ha_samples"]:
            za = zenith_angle(h, td["dec"], self.lat)
            s += self.sefd_jy(fc, za, td["ra"], td["dec"], (f_lo, f_hi)) ** -2
        return (s / len(td["ha_samples"])) ** -0.5

    def td_subbands(self, td, f_lo, f_hi):
        """Sub-bands of at most td_subband_MHz: center, usable bandwidth (Hz; RFI profile), effective zenith T_sys,
        SEFD."""
        key = "%.6f-%.6f" % (f_lo, f_hi)
        if key in td["_sub"]:
            return td["_sub"][key]
        rows = []
        for a, b in td_subband_edges(f_lo, f_hi, self.p["td_subband_MHz"]):
            bw = usable_bw_hz(self.rfi, a, b, self.extra_loss)
            fc = 0.5 * (a + b)
            rows.append({"fc": fc, "bw_hz": bw, "tsys_K": self.tz_K(a, b),
                         "sefd": self.td_sefd(td, a, b) if bw > 0 else float("inf")})
        td["_sub"][key] = rows
        return rows

    def td_sigma_c(self, fc, ratio=1.0):
        """Sidelobe-confusion rms (Jy) of a beam at fc; ratio = s(theta)/s(0) for a tapered beam."""
        p = self.p
        return p["td_confusion_uJy"] * 1e-6 * (fc / p["td_confusion_nu_MHz"]) ** p["td_confusion_index"] * ratio

    def psr_propagation(self, td, dm=None):
        """Scattering at 1 GHz (ms), its frequency index and the propagation block for a pulsar (default: the input
        search pulsar)."""
        p = self.p
        dm = td["psr_dm"] if dm is None else dm
        ne = ne2025_at(td["l_deg"], td["b_deg"], dm)
        if p["td_scattering"] == "cordes22":
            tau1, idx, dist = tau_cordes22_ms(dm, 1000.0), -4.0, None
        else:
            tau1, idx, dist = ne["tau_1GHz_ms"], -4.4, ne["dist_kpc"]
        prop = {"model": p["td_scattering"], "dm": dm, "dist_kpc": dist, "tau_1GHz_ms": tau1, "tau_index": idx,
                "tau_bands_ms": {name: tau1 * (0.5 * (lo + hi) / 1000.0) ** idx for name, lo, hi, _ in CHR_BANDS},
                "dm_max": ne["dm_max"], "tau_x_1GHz_ms": ne["tau_x_1GHz_ms"], "dm_above_max": dm > ne["dm_max"],
                "scatter_dex": 0.76 if p["td_scattering"] == "cordes22" else None}
        return tau1, idx, prop

    def _psr_weff(self, f, tsamp_s, chan_mhz, tau1, idx, dm, wint=None):
        p = self.p
        wint = p["psr_width_ms"] * 1e-3 if wint is None else wint
        tdm = t_dm_s(dm, chan_mhz, f) if chan_mhz else 0.0
        tau = tau1 * 1e-3 * (f / 1000.0) ** idx
        return math.sqrt(wint * wint + tsamp_s * tsamp_s + tdm * tdm + tau * tau), wint, tdm, tau

    def psr_band(self, td, f_lo, f_hi, beam_div, eta, tsamp_s, chan_mhz, conf_ratio, tau1, idx, period_s, wint=None,
                 src=None):
        """S/N and sigma_TOA of a pulsar in one band, summed over sub-bands, with the confusion factor.

        src (flux_mJy, nu_ref_MHz, alpha, dm, width_ms) describes the pulsar; default: the input search pulsar."""
        p = self.p
        if src is None:
            src = {"flux_mJy": p["psr_flux_mJy"], "nu_ref_MHz": p["psr_nu_ref_MHz"], "alpha": p["psr_alpha"],
                   "dm": td["psr_dm"], "width_ms": p["psr_width_ms"]}
        if wint is None:
            wint = src["width_ms"] * 1e-3
        npol, t, dm = p["n_pol"], td["track_s"], src["dm"]
        sref, nref, alpha = src["flux_mJy"] * 1e-3, src["nu_ref_MHz"], src["alpha"]
        snr2 = snr2_ns = toa2 = iv = bw = 0.0
        for s in self.td_subbands(td, f_lo, f_hi):
            if s["bw_hz"] <= 0 or not math.isfinite(s["sefd"]):
                continue
            sig = s["sefd"] / beam_div / math.sqrt(npol * s["bw_hz"])           # 1-s noise, Jy s^0.5
            iv += sig ** -2
            bw += s["bw_hz"]
            w = self._psr_weff(s["fc"], tsamp_s, chan_mhz, tau1, idx, dm, wint)[0]
            if w >= period_s:
                continue
            s_i = sref * (s["fc"] / nref) ** alpha
            snr_ns = eta * s_i / sig * math.sqrt(t) * math.sqrt((period_s - w) / w)
            # self-noise: on-pulse flux density S P / W adds to the beam SEFD for a fraction W / P of the data
            fs = self_noise_factor(s_i * period_s / w / (s["sefd"] / beam_div), w / period_s) if p["td_self_noise"] else 1.0
            snr = snr_ns * fs
            snr2 += snr * snr
            snr2_ns += snr_ns * snr_ns
            toa2 += (snr / w) ** 2
        fc = 0.5 * (f_lo + f_hi)
        wc, wint, tdm, tau = self._psr_weff(fc, tsamp_s, chan_mhz, tau1, idx, dm, wint)
        sig_band = iv ** -0.5 if iv > 0 else float("inf")
        conf = psr_confusion_factor(period_s, wc, tsamp_s, sig_band, self.td_sigma_c(fc, conf_ratio), td["tau_c_s"])
        snr = conf * math.sqrt(snr2)
        return {"snr": snr, "snr_thermal": math.sqrt(snr2), "snr_noself": conf * math.sqrt(snr2_ns),
                "self_noise": math.sqrt(snr2 / snr2_ns) if snr2_ns > 0 else 1.0,
                "toa_s": (conf * math.sqrt(toa2)) ** -1 if toa2 > 0
                else float("inf"), "f_center": fc, "bw_hz": bw, "sigma_1s": sig_band, "confusion": conf,
                "weff": {"weff_ms": wc * 1e3, "w_int_ms": wint * 1e3, "t_samp_ms": tsamp_s * 1e3, "t_dm_ms": tdm * 1e3,
                         "tau_ms": tau * 1e3}}

    def _psr_src(self, td, flux_mJy=None):
        p = self.p
        return {"flux_mJy": p["psr_flux_mJy"] if flux_mJy is None else flux_mJy, "nu_ref_MHz": p["psr_nu_ref_MHz"],
                "alpha": p["psr_alpha"], "dm": td["psr_dm"], "width_ms": p["psr_width_ms"]}

    def _psr_smin_mJy(self, args, period_s, wint, src, thr, r0=None):
        """Flux density at nu_ref (mJy) at which the pulsar of src reaches S/N thr in one band (self-noise included)."""
        if r0 is None:
            r0 = self.psr_band(*args, period_s, wint, src)
        if not r0["snr_noself"] > 0:
            return float("inf")
        f0 = thr * src["flux_mJy"] / r0["snr_noself"]
        def snr_of(f):
            r = self.psr_band(*args, period_s, wint, dict(src, flux_mJy=f))
            return r["snr"], r["snr_noself"]
        return solve_threshold(snr_of, f0, thr)

    def _psr_row(self, r, f_lo, f_hi, eta, searched, smin_mJy):
        """Output row of a pulsar product from psr_band and the solved threshold flux density."""
        p = self.p
        nref, alpha = p["psr_nu_ref_MHz"], p["psr_alpha"]
        snr = r["snr"] if searched else 0.0
        smin_ref = smin_mJy * 1e3 if searched else float("inf")                  # uJy at nu_ref
        return {"f_lo_MHz": f_lo, "f_hi_MHz": f_hi, "f_center_MHz": r["f_center"], "bw_usable_MHz": r["bw_hz"] / 1e6,
                "searched": searched, "snr": snr,
                "smin_uJy": smin_ref * (r["f_center"] / nref) ** alpha, "s1400_min_uJy": smin_ref * (1400.0 / nref) ** alpha,
                "sefd_beam_Jy": r["sigma_1s"] * math.sqrt(p["n_pol"] * r["bw_hz"]) if r["bw_hz"] > 0 else float("inf"),
                "weff": r["weff"], "losses": {"quantization": eta, "confusion": r["confusion"],
                                              "self_noise": r["self_noise"]}}

    def _psr_curve(self, td, f_lo, f_hi, beam_div, eta, tsamp_s, chan_mhz, conf_ratio, tau1, idx, pmin, pmax, periods):
        p = self.p
        duty = p["psr_width_ms"] / p["psr_period_ms"]          # curves keep the input pulsar's duty cycle
        out = []
        for P in periods:
            if P < pmin or P > pmax:
                out.append(None)
                continue
            args = (td, f_lo, f_hi, beam_div, eta, tsamp_s, chan_mhz, conf_ratio, tau1, idx)
            sref = self._psr_smin_mJy(args, P, duty * P, self._psr_src(td), p["psr_snr"]) * 1e3
            out.append(sref * (0.5 * (f_lo + f_hi) / p["psr_nu_ref_MHz"]) ** p["psr_alpha"])
        return out

    def pulsar(self, td, warnings):
        p = self.p
        n = p["n_ant"]
        P = p["psr_period_ms"] * 1e-3
        dm_default = p["psr_dm"] is None
        td["psr_dm"] = 0.5 * ne2025_at(td["l_deg"], td["b_deg"], 1.0)["dm_max"] if dm_default else p["psr_dm"]
        tau1, idx, prop = self.psr_propagation(td)
        if prop["dm_above_max"] and p["td_scattering"] != "cordes22":
            warnings.append("Pulsar DM %.0f exceeds the NE2025 Galactic maximum (%.0f) at this position: distance and "
                            "scattering are saturated." % (td["psr_dm"], prop["dm_max"]))
        eta_s = p["td_eta_v4"] * p["td_eta_i2"]
        nb_img = math.sqrt(n * (n - 1))
        periods = [10 ** (math.log10(3e-4) + i * (math.log10(10.0) - math.log10(3e-4)) / 199) for i in range(200)]
        curves = {"period_s": periods, "duty_cycle": p["psr_width_ms"] / p["psr_period_ms"]}
        # untargeted search: tapered visibility beams in B1-B3
        beams = p["psr_untargeted_beam_arcsec"]
        untargeted = []
        pmin, pmax = p["psr_untargeted_pmin_ms"] * 1e-3, p["psr_untargeted_pmax_ms"] * 1e-3
        for k, (name, lo, hi, nsum) in enumerate(CHR_BANDS):
            fc = 0.5 * (lo + hi)
            theta = beams[k] if beams else CHR_UNTARGETED_BEAM_1 * 930.0 / fc
            tp = chr_taper(name, td["dec"], theta)
            div = nb_img / tp["f_taper"]
            args = (td, lo, hi, div, eta_s, CHR_UNTARGETED_TSAMP_S, CHR_CHAN_MHZ * nsum, tp["sidelobe_ratio"], tau1, idx)
            r = self.psr_band(*args, P)
            row = self._psr_row(r, lo, hi, eta_s, pmin <= P <= pmax,
                                self._psr_smin_mJy(args, P, None, self._psr_src(td), p["psr_snr"], r))
            row["losses"]["taper"] = tp["f_taper"]
            area = p["psr_untargeted_n_beams"] * HEX_CELL * (tp["fwhm_arcsec"] / 3600.0) ** 2   # hexagonal grid
            fov = math.pi / 4 * (PB_FWHM_1GHZ / (fc / 1000.0)) ** 2
            row.update({"band": name, "chan_kHz": CHR_CHAN_MHZ * nsum * 1e3, "tsamp_ms": CHR_UNTARGETED_TSAMP_S * 1e3,
                        "beam_requested_arcsec": theta, "beam_arcsec": tp["fwhm_arcsec"],
                        "beam_natural_arcsec": tp["natural_fwhm_arcsec"], "beam_note": tp["note"],
                        "sidelobe_ratio": tp["sidelobe_ratio"], "n_beams": p["psr_untargeted_n_beams"],
                        "area_deg2": area, "frac_unique_area": area / CHR_UNIQUE_AREA_DEG2, "frac_pb_fwhm": area / fov,
                        "period_range_ms": [p["psr_untargeted_pmin_ms"], p["psr_untargeted_pmax_ms"]]})
            untargeted.append(row)
            curves["untargeted_" + name] = {"f_center_MHz": fc, "smin_uJy": self._psr_curve(*args, pmin, pmax, periods)}
        # targeted search and timing: voltage beams, 306.7 MHz
        centers = list(CHR_TARGETED_PRESETS)
        sel = p["psr_targeted_center_MHz"]
        if all(abs(sel - c) > 1e-6 for c in centers):
            centers.append(sel)
        targeted = []
        tmin, tmax = p["psr_targeted_pmin_ms"] * 1e-3, p["psr_targeted_pmax_ms"] * 1e-3
        half = 0.5 * CHR_TARGETED_BW
        for c in centers:
            lo, hi = max(c - half, TD_LIMITS[0]), min(c + half, TD_LIMITS[1])
            if lo > c - half or hi < c + half:
                warnings.append("Targeted band centered on %.2f MHz extends outside 700-2002 MHz; clipped to %.1f-%.1f MHz."
                                % (c, lo, hi))
            args = (td, lo, hi, float(n), eta_s, CHR_TARGETED_TSAMP_S, CHR_CHAN_MHZ, 1.0, tau1, idx)
            r = self.psr_band(*args, P)
            row = self._psr_row(r, lo, hi, eta_s, tmin <= P <= tmax,
                                self._psr_smin_mJy(args, P, None, self._psr_src(td), p["psr_snr"], r))
            row.update({"center_MHz": c, "selected": abs(c - sel) <= 1e-6, "preset": c in CHR_TARGETED_PRESETS,
                        "toa_us": r["toa_s"] * 1e6, "chan_kHz": CHR_CHAN_MHZ * 1e3,
                        "tsamp_ms": CHR_TARGETED_TSAMP_S * 1e3,
                        "period_range_ms": [p["psr_targeted_pmin_ms"], p["psr_targeted_pmax_ms"]]})
            targeted.append(row)
            if abs(c - sel) <= 1e-6:
                curves["targeted"] = {"f_center_MHz": r["f_center"],
                                      "smin_uJy": self._psr_curve(*args, tmin, tmax, periods)}
        return {"inputs": {"period_ms": p["psr_period_ms"], "width_ms": p["psr_width_ms"], "dm": td["psr_dm"],
                           "dm_default": dm_default,
                           "flux_mJy": p["psr_flux_mJy"], "nu_ref_MHz": p["psr_nu_ref_MHz"], "alpha": p["psr_alpha"],
                           "snr": p["psr_snr"]},
                "propagation": prop, "untargeted": untargeted, "targeted": targeted, "curves": curves}

    # ---------------------------------------------------------------- Pulsar Timing subsystem (PTA)
    def pta(self, td, warnings):
        """Four coherently dedispersed voltage beams over 700-2000 MHz (13 x 100 MHz), for the PTA pulsar."""
        p = self.p
        n = p["n_ant"]
        P = p["pta_period_ms"] * 1e-3
        src = {"flux_mJy": p["pta_flux_mJy"], "nu_ref_MHz": p["pta_nu_ref_MHz"], "alpha": p["pta_alpha"],
               "dm": p["pta_dm"], "width_ms": p["pta_width_ms"]}
        tau1, idx, prop = self.psr_propagation(td, src["dm"])
        if prop["dm_above_max"] and p["td_scattering"] != "cordes22":
            warnings.append("PTA pulsar DM %.0f exceeds the NE2025 Galactic maximum (%.0f) at this position: distance "
                            "and scattering are saturated." % (src["dm"], prop["dm_max"]))
        ts_pt = p["pt_tsamp_us"] * 1e-6
        edges = [PT_BAND[0] + (PT_BAND[1] - PT_BAND[0]) * i / PT_NSUB for i in range(PT_NSUB + 1)]

        def snr_all(f):
            s2 = s2n = 0.0
            for lo, hi in zip(edges[:-1], edges[1:]):
                rr = self.psr_band(td, lo, hi, float(n), p["pt_eta"], ts_pt, None, 1.0, tau1, idx, P, None,
                                   dict(src, flux_mJy=f))
                s2 += rr["snr"] ** 2
                s2n += rr["snr_noself"] ** 2
            return math.sqrt(s2), math.sqrt(s2n)
        subs = []
        snr2 = snr2_th = snr2_ns = toa_iv = 0.0
        for lo, hi in zip(edges[:-1], edges[1:]):
            r = self.psr_band(td, lo, hi, float(n), p["pt_eta"], ts_pt, None, 1.0, tau1, idx, P, None, src)
            snr2 += r["snr"] ** 2
            snr2_th += r["snr_thermal"] ** 2
            snr2_ns += r["snr_noself"] ** 2
            if math.isfinite(r["toa_s"]):
                toa_iv += r["toa_s"] ** -2
            subs.append({"f_center_MHz": r["f_center"], "bw_usable_MHz": r["bw_hz"] / 1e6, "snr": r["snr"],
                         "toa_us": r["toa_s"] * 1e6, "confusion": r["confusion"], "weff_ms": r["weff"]["weff_ms"],
                         "tau_ms": r["weff"]["tau_ms"]})
        snr_pt = math.sqrt(snr2)
        smin_ref = solve_threshold(snr_all, p["pta_snr"] * src["flux_mJy"] / math.sqrt(snr2_ns), p["pta_snr"]) * 1e3 \
            if snr2_ns > 0 else float("inf")
        wc = self._psr_weff(1350.0, ts_pt, None, tau1, idx, src["dm"], src["width_ms"] * 1e-3)
        return {"inputs": {"period_ms": p["pta_period_ms"], "width_ms": p["pta_width_ms"], "dm": src["dm"],
                           "flux_mJy": src["flux_mJy"], "nu_ref_MHz": src["nu_ref_MHz"], "alpha": src["alpha"],
                           "snr": p["pta_snr"]},
                "propagation": prop, "f_lo_MHz": PT_BAND[0], "f_hi_MHz": PT_BAND[1], "n_beams": 4,
                "tsamp_us": p["pt_tsamp_us"], "track_s": td["track_s"],
                "snr": snr_pt, "toa_us": toa_iv ** -0.5 * 1e6 if toa_iv > 0 else float("inf"),
                "smin_uJy": smin_ref * (1350.0 / src["nu_ref_MHz"]) ** src["alpha"],
                "s1400_min_uJy": smin_ref * (1400.0 / src["nu_ref_MHz"]) ** src["alpha"],
                "bw_usable_MHz": sum(s["bw_usable_MHz"] for s in subs),
                "weff": {"weff_ms": wc[0] * 1e3, "w_int_ms": wc[1] * 1e3, "t_samp_ms": ts_pt * 1e3, "t_dm_ms": 0.0,
                         "tau_ms": wc[3] * 1e3},
                "losses": {"quantization": p["pt_eta"],
                           "confusion": snr_pt / math.sqrt(snr2_th) if snr2_th > 0 else 1.0,
                           "self_noise": snr_pt / math.sqrt(snr2_ns) if snr2_ns > 0 else 1.0},
                "subbands": subs}

    # ---------------------------------------------------------------- FRB
    def frb_dm_budget(self, td, dm_obs):
        """DM_obs = DM_MW + DM_halo + <DM_cosmic>(z) + DM_host/(1+z), solved for z with the median DM_host."""
        p = self.p
        ne = ne2025_at(td["l_deg"], td["b_deg"], 1.0)
        dm_mw, halo = ne["dm_max"], p["frb_dm_halo"]
        host_med = math.exp(p["frb_host_mu"])
        ex = dm_obs - dm_mw - halo
        if ex < host_med:
            z, host = 0.0, max(ex, 0.0)
        else:
            lo, hi = 0.0, 10.0
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if dm_cosmic(mid, p["frb_f_d"]) + host_med / (1.0 + mid) < ex:
                    lo = mid
                else:
                    hi = mid
            z, host = 0.5 * (lo + hi), host_med
        tau_mw = ne["tau_x_1GHz_ms"] if p["td_scattering"] != "cordes22" else 0.0
        return {"dm_obs": dm_obs, "dm_mw": dm_mw, "dm_halo": halo, "z": z, "dm_cosmic": dm_cosmic(z, p["frb_f_d"]),
                "dm_host": host, "dm_host_median": host_med, "below_galactic": dm_obs < dm_mw + halo,
                "tau_mw_1GHz_ms": tau_mw, "tau_host_1GHz_ms": 3.0 * tau_cordes22_ms(host, 1000.0) * (1.0 + z) ** -3,
                "host_scatter_dex": 0.76}

    def _frb_weff(self, f, bud):
        p = self.p
        wint = p["frb_width_ms"] * 1e-3
        tdm = t_dm_s(bud["dm_obs"], CHR_CHAN_MHZ, f)
        tmw = bud["tau_mw_1GHz_ms"] * 1e-3 * (f / 1000.0) ** -4.4
        th = 3.0 * tau_cordes22_ms(bud["dm_host"], f) * (1.0 + bud["z"]) ** -3 * 1e-3
        return math.sqrt(wint * wint + FRB_TSAMP_S ** 2 + tdm * tdm + tmw * tmw + th * th), wint, tdm, tmw, th

    def frb_fluence(self, td, lo, hi, bud):
        """Fluence (Jy s) at the S/N threshold for a burst at the peak of a beam at the beam center (quantization,
        confusion and self-noise included), with the band-center width and confusion factor.

        Returns (fluence, fluence without self-noise, weff tuple, confusion factor, band 1-s noise, usable bw)."""
        p = self.p
        n = p["n_ant"]
        s2 = iv = bw = 0.0
        sub = []
        for s in self.td_subbands(td, lo, hi):
            if s["bw_hz"] <= 0 or not math.isfinite(s["sefd"]):
                continue
            sefd_b = s["sefd"] / math.sqrt(n * (n - 1))
            sig = sefd_b / math.sqrt(p["n_pol"] * s["bw_hz"])
            w = self._frb_weff(s["fc"], bud)[0]
            s2 += 1.0 / (sig * sig * w)
            iv += sig ** -2
            bw += s["bw_hz"]
            sub.append((sig, w, sefd_b))
        fc = 0.5 * (lo + hi)
        wc = self._frb_weff(fc, bud)
        sig_band = iv ** -0.5 if iv > 0 else float("inf")
        conf = frb_confusion_factor(wc[0], sig_band, self.td_sigma_c(fc), td["tau_c_s"])
        eta = p["td_eta_v4"] * p["td_eta_i4"]
        thr = p["frb_snr"]
        if s2 <= 0:
            return float("inf"), float("inf"), wc, conf, sig_band, bw
        fl0 = thr / (eta * conf * math.sqrt(s2))

        def snr_of(f):
            # self-noise: the burst's peak flux density f / W adds to the beam SEFD during the burst; the running-mean
            # baseline (T_b = max(1 s, 10 W)) is off-burst
            a = 0.0
            for sig, w, sefd_b in sub:
                fs = self_noise_factor(f / w / sefd_b, w / (w + max(1.0, 10.0 * w))) if p["td_self_noise"] else 1.0
                a += (f / (sig * math.sqrt(w)) * fs) ** 2
            return eta * conf * math.sqrt(a), f * eta * conf * math.sqrt(s2)
        fl = solve_threshold(snr_of, fl0, thr)
        return fl, fl0, wc, conf, sig_band, bw

    def frb(self, td, warnings):
        p = self.p
        bud = self.frb_dm_budget(td, p["frb_dm"])
        if bud["below_galactic"]:
            warnings.append("FRB DM %.0f is below the Galactic contribution (DM_MW %.0f + halo %.0f) at this position."
                            % (p["frb_dm"], bud["dm_mw"], bud["dm_halo"]))
        eta = p["td_eta_v4"] * p["td_eta_i4"]
        pb = 0.5 / math.log(2.0)
        dmt = dm_trial_loss(p["frb_dm_tolerance"])
        psf_obs = {"mode": "survey", "dec": td["dec"], "ha_samples": [0.0]}
        bands = []
        dm_lo = max(1.0, bud["dm_mw"] + bud["dm_halo"])
        dms = [10 ** (math.log10(dm_lo) + i * (math.log10(max(p["frb_max_dm"], dm_lo * 1.0001)) - math.log10(dm_lo)) / 59)
               for i in range(60)]
        curves = {"dm": dms}
        for name, lo, hi, _ in CHR_BANDS:
            fc = 0.5 * (lo + hi)
            fl, fl0, wc, conf, sig_band, bw = self.frb_fluence(td, lo, hi, bud)
            selfn = fl0 / fl if fl > 0 and math.isfinite(fl) else 1.0
            psf = self.psf_nat(psf_obs, fc)
            strad = hex_straddle(psf)
            strad_r = hex_straddle(psf, p["frb_alpha_c"])                       # count-weighted, for rates
            psf_u = scale_beam(psf_natural_1350(td["dec"], [0.0], [1.0], self.lat, _psf_uniform()), 1350.0 / fc)
            cov_u = _cov_from_beam(psf_u["bmaj"], psf_u["bmin"], psf_u["pa"])
            loss = strad * pb * dmt
            fl_all = fl / loss
            sefd_arr = sig_band * math.sqrt(p["n_pol"] * bw) if bw > 0 else float("inf")
            sefd_dsa = sefd_arr / (eta * strad_r * dmt * conf * selfn)
            ref_name, r_i, sefd_i, om_i, b_i = FRB_RATE_REF[name]
            fov = math.pi / 4 * (PB_FWHM_1GHZ / (fc / 1000.0)) ** 2
            om_rate, a_cov = frb_rate_solid_angle(p["frb_n_beams"], math.sqrt(psf["bmaj"] * psf["bmin"]),
                                                  PB_FWHM_1GHZ / (fc / 1000.0), p["frb_alpha_c"])
            expo = p["frb_alpha_c"] * ((1.0 + p["frb_gamma"]) if name == "B3" else 1.0)
            rate = frb_rate(r_i, om_i, sefd_i, b_i, om_rate, sefd_dsa, bw / 1e6, expo)
            bands.append({"band": name, "f_lo_MHz": lo, "f_hi_MHz": hi, "f_center_MHz": fc, "bw_usable_MHz": bw / 1e6,
                          "chan_kHz": CHR_CHAN_MHZ * 1e3, "tsamp_ms": FRB_TSAMP_S * 1e3, "sefd_beam_Jy": sefd_arr,
                          "fluence_peak_Jyms": fl * 1e3, "fluence_min_Jyms": fl_all * 1e3,
                          "speak_peak_mJy": fl / wc[0] * 1e3, "speak_min_mJy": fl_all / wc[0] * 1e3,
                          "weff": {"weff_ms": wc[0] * 1e3, "w_int_ms": wc[1] * 1e3, "t_samp_ms": FRB_TSAMP_S * 1e3,
                                   "t_dm_ms": wc[2] * 1e3, "tau_mw_ms": wc[3] * 1e3, "tau_host_ms": wc[4] * 1e3},
                          "losses": {"quantization": eta, "straddle": strad, "pb_average": pb, "dm_trial": dmt,
                                     "confusion": conf, "self_noise": selfn, "total": eta * conf * selfn * loss},
                          "fov_deg2": fov, "n_beams": p["frb_n_beams"], "psf": psf,
                          "beam_area_deg2": a_cov, "beam_coverage": a_cov / fov, "omega_rate_deg2": om_rate,
                          "straddle_rate": strad_r,
                          "dm_trials": frb_dm_trials(p["frb_width_ms"] * 1e-3, FRB_TSAMP_S, CHR_CHAN_MHZ, fc, lo, hi,
                                                     p["frb_max_dm"], p["frb_dm_tolerance"]),
                          "psf_uniform": psf_u,
                          "loc_1sigma_arcsec": math.sqrt(psf_u["bmaj"] * psf_u["bmin"]) / (2.0 * p["frb_snr"]),
                          "loc_ra_1sigma_arcsec": math.sqrt(cov_u[0, 0]) / (2.0 * p["frb_snr"]),
                          "loc_dec_1sigma_arcsec": math.sqrt(cov_u[1, 1]) / (2.0 * p["frb_snr"]),
                          "rate_ref": ref_name, "sefd_dsa_Jy": sefd_dsa, "rate_per_yr": rate,
                          "rate_in_track": rate * td["track_s"] / YEAR_S})
            curves[name] = [self.frb_fluence(td, lo, hi, self.frb_dm_budget(td, d))[0] / loss * 1e3 for d in dms]
        return {"inputs": {"dm": p["frb_dm"], "width_ms": p["frb_width_ms"], "snr": p["frb_snr"],
                           "max_dm": p["frb_max_dm"], "dm_tolerance": p["frb_dm_tolerance"],
                           "alpha_c": p["frb_alpha_c"], "gamma": p["frb_gamma"]},
                "dm_budget": bud, "bands": bands, "curves": curves}

    def time_domain(self, ra, dec, products, out, track_s=None):
        """Chronoscope pulsar and FRB products: fills out in place. track_s overrides td_track_s (targeted mode)."""
        p = self.p
        td = self.td_setup(ra, dec, track_s)
        meta = _tsys_bp()["meta"]
        out["time_domain"] = {"ra": ra, "dec": dec, "l_deg": td["l_deg"], "b_deg": td["b_deg"],
                              "track_s": td["track_s"], "observable": td["observable"],
                              "n_transits": td["n_transits"], "ha_half_h": td["ha_half_h"], "tau_c_s": td["tau_c_s"],
                              "survey": td["survey"], "aperture_efficiency": p["aperture_efficiency"],
                              "tsys_source": meta["source_file"],
                              "usable_fraction": {name: usable_bw_hz(self.rfi, lo, hi, self.extra_loss) /
                                                  ((hi - lo) * 1e6) for name, lo, hi, _ in CHR_BANDS},
                              "scattering": p["td_scattering"]}
        if not td["observable"]:
            out["warnings"].append("Time-domain track not observable: the position never rises above the elevation "
                                   "limit.")
            return
        if td["n_transits"] > 1:
            out["warnings"].append("Time-domain track exceeds one transit window; split over %d transits of %.2f h."
                                   % (td["n_transits"], 2 * td["ha_half_h"]))
        if "pulsar" in products:
            out["pulsar"] = self.pulsar(td, out["warnings"])
        if "frb" in products:
            out["frb"] = self.frb(td, out["warnings"])
        if "pta" in products:
            out["pta"] = self.pta(td, out["warnings"])

    # ---------------------------------------------------------------- top level
    def calculate(self, mode="survey", ra=170.0, dec=39.57, depth="full", n_epochs=None, hours=1.0,
                  products=("continuum", "line", "polarization", "frb", "pulsar", "pta"),
                  weighting="auto", smooth_arcsec=0.0, variant=None):
        """Noise, resolution and detection limits for one observation; returns a dict (as dsa-etc --json).

        mode: "survey" (survey mosaic at the position) or "targeted" (one pointing centered on it, tracked about
        transit). ra, dec: degrees. depth: survey "full", "single" or "custom" (n_epochs). hours: targeted
        on-source time, also the time-domain track in targeted mode (survey mode uses td_track_s).
        products: any of continuum, line, polarization, frb, pulsar, pta. weighting: "auto" or
        "imaging:summation" (natural, robust_freq, robust_0p4; optimal, equal). smooth_arcsec: also give image
        products at this circular resolution. variant: survey plan A (default), B, C or fig1.
        Noise values are 1 sigma per beam; keys carry their units. Read r["warnings"].
        """
        obs = self.setup(mode, ra, dec, depth, n_epochs, hours, variant)
        out = {"inputs": {"mode": mode, "ra": ra, "dec": dec, "depth": depth, "n_epochs": n_epochs, "hours": hours,
                          "weighting": weighting, "smooth_arcsec": smooth_arcsec,
                          "rfi_profile": self.rfi["name"], "params": {k: v for k, v in self.p.items()}},
               "observation": {k: v for k, v in obs.items() if k != "ha_samples" and not k.startswith("_")},
               "warnings": []}
        td_products = [k for k in ("pulsar", "frb", "pta") if k in products]
        td_track = obs["total_time_s"] if mode != "survey" else None     # targeted: the on-source time
        if not obs.get("observable", True):
            out["warnings"].append("Position is not observable with these settings (outside the survey footprint "
                                   "or below the elevation limit).")
            if td_products:
                self.time_domain(ra, dec, td_products, out, td_track)
            return out
        if mode == "survey":
            w = self.survey_weight(obs, 1350.0, None if depth == "full" else obs["n_epochs"])
            out["observation"]["effective_epochs_1350"] = w / mosaic_z(1350.0)["zmean"]
            out["observation"]["t_eff_1350_s"] = self.eff_time_s(obs, 1350.0)
        # system summary: full band, and at 1.35 GHz
        tb = self.tsys_breakdown(1350.0, obs["za_transit"], ra, dec)
        tb.update(self.tsys_band(obs["za_transit"], ra, dec))
        out["system"] = dict(tb, sefd_1350_Jy=self.sefd_jy(1350.0, obs["za_transit"], ra, dec),
                             sefd_700_Jy=self.sefd_jy(700.0, obs["za_transit"], ra, dec),
                             sefd_2000_Jy=self.sefd_jy(2000.0, obs["za_transit"], ra, dec),
                             tsys_700_K=self.tsys_breakdown(700.0, obs["za_transit"], ra, dec)["tsys_K"],
                             usable_band_fraction=usable_bw_hz(self.rfi, *BAND_MHZ, self.extra_loss) /
                             ((BAND_MHZ[1] - BAND_MHZ[0]) * 1e6))
        # weighting scheme
        beta = self.p["confusion_beta"]
        if weighting == "auto":
            obs_ref = obs
            if mode == "survey":
                obs_ref = dict(obs, n_epochs=max(obs["epochs_full"], 1), depth="full")
            scheme, table = self.choose_scheme(obs_ref, beta)
            basis = "this observation"
            if mode == "survey":
                # the survey pipeline uses one weighting per tile: the one minimizing the tile's final coadd noise
                al = self.allocation()
                tkey = obs["tile"]["tile"]
                sch = al["tiles"][tkey].get("scheme", {}).get(obs["tile"]["variant"])
                if sch:
                    scheme = tuple(sch.split(":"))
                basis = "tile %s final coadd (%d epochs)" % (tkey, obs["epochs_full"])
            out["weighting"] = {"imaging": scheme[0], "summation": scheme[1], "auto": True, "comparison": table,
                                "basis": basis}
        else:
            im, su = weighting.split(":")
            scheme = (im, su)
            out["weighting"] = {"imaging": im, "summation": su, "auto": False}
        if "continuum" in products:
            c = self.continuum(obs, scheme, smooth_arcsec)
            c["snapshots_6s"] = self.snapshots(obs, scheme)
            if mode == "survey":
                one = dict(obs, n_epochs=1)
                c["single_pointing"] = self._single_pointing(one, scheme)
            out["continuum"] = c
        if "line" in products:
            out["line"] = self.spectral_line(obs, smooth_arcsec)
        if "polarization" in products:
            out["polarization"] = self.polarization(obs, scheme, smooth_arcsec)
        if td_products:
            self.time_domain(ra, dec, td_products, out, td_track)
        if mode == "survey" and obs["dec"] < -27.0:
            out["warnings"].append("Near the southern survey edge (Dec -30.45): fewer overlapping pointings "
                                   "reduce the mosaic depth.")
        if smooth_arcsec and smooth_arcsec > 900.0:
            out["warnings"].append('Smoothing beyond 15′ is set by a few dozen short baselines (72 are shorter than 50 m): at 1.35 GHz the smoothed beam comes out 10–20% narrower than requested, with 10–40% sidelobes, so treat these T_b values as indicative. The limit scales with wavelength (about 30′ at 0.7 GHz).')
        if mode != "survey" and obs.get("n_transits", 1) > 1:
            out["warnings"].append("Requested time exceeds one transit window; split over %d transits of %.2f h."
                                   % (obs["n_transits"], 2 * obs["ha_half_h"]))
        return out

    def _single_pointing(self, obs, scheme):
        """One 21-min pointing image at the primary-beam center (no mosaicking), full band."""
        beta = self.p["confusion_beta"]
        o = dict(obs, mode="targeted", total_time_s=self.p["pointing_s"], ha_samples=[0.0])
        rows = self.continuum_windows(o, scheme)
        fc = self.combine_fc(rows, scheme[1], beta)
        return {"thermal_uJy": fc["sigma_jy"] * 1e6, "confusion_uJy": fc["confusion_jy"] * 1e6,
                "total_uJy": fc["total_jy"] * 1e6, "nu_eff_MHz": fc["nu_eff"], "psf": fc["psf"]}


def lum_dist_mpc(z, h0=67.66, om=0.3097):
    """Luminosity distance (Mpc), flat LCDM (Planck 2018)."""
    if z <= 0:
        return 0.0
    n = 400
    zs = np.linspace(0.0, z, n + 1)
    ez = np.sqrt(om * (1 + zs) ** 3 + (1 - om))
    dc = (C_LIGHT / 1e3 / h0) * _trapz(1.0 / ez, zs)
    return (1 + z) * dc
