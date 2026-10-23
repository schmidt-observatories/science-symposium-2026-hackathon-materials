"""Chronoscope (time-domain) checks against the design documents and independent calculations.

Run:  python3 -m pytest tests/test_chr.py
"""
import json
import math
import os
import re
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "python"))

from dsa_etc import engine as E  # noqa: E402
from dsa_etc import DSACalculator  # noqa: E402

GP = E.lb_to_radec(40.0, 0.0)          # Galactic plane, l = 40
HIGH = (180.0, 60.0)                   # high latitude


@pytest.fixture(scope="module")
def default_run():
    return DSACalculator().calculate("targeted", *GP, products=("pulsar", "frb", "pta"))


def _band(td_calc, lo, hi, fc, bw_hz, sefd):
    """Fake one sub-band so that psr_band sees exactly (fc, bw, SEFD)."""
    td = {"_sub": {"%.6f-%.6f" % (lo, hi): [{"fc": fc, "bw_hz": bw_hz, "tsys_K": 0.0, "sefd": sefd}]}, "tau_c_s": 10.0,
          "psr_dm": 0.0, "track_s": 1260.0}
    return td


# 1. radiometer equation (DSA-00212): 10 sigma, array SEFD 1.7 Jy, 200 MHz, 1260 s, W/(P-W) = 1 -> 23.9 uJy
def test_radiometer_dsa00212():
    c = DSACalculator(td_confusion_uJy=0.0, psr_width_ms=15.0, psr_flux_mJy=1.0, psr_alpha=0.0, psr_snr=10.0)
    n = 1650.0
    td = _band(c, 1300.0, 1500.0, 1400.0, 200e6, 1.7 * n)
    r = c.psr_band(td, 1300.0, 1500.0, n, 1.0, 0.0, None, 1.0, 0.0, -4.4, 0.030)
    smin_uJy = 10.0 * 1e3 / r["snr"]
    assert smin_uJy == pytest.approx(23.9, rel=0.01)


# 2. untargeted-beam taper (DSA-00212, DSA-00213)
def test_taper_930_matches_ravi_memo():
    # Ravi et al. (2026b) Sec. 2.3: a 13.5" taper costs 1.9-2.6 between Dec -20 and +60, 2.3 at Dec 0
    assert E.chr_taper("B1", 0.0, 13.5)["f_taper"] == pytest.approx(2.3, abs=0.05)
    for d in (-20.0, 0.0, 30.0, 60.0):
        assert 1.85 < E.chr_taper("B1", d, 13.5)["f_taper"] < 2.65


def test_untargeted_beams_tile_unique_area():
    # 2e5 beams on a hexagonal grid at FWHM spacing tile the 2.42 deg^2 unique area with a 13.5" FWHM (Ravi et al. 2026b)
    area = 200000 * math.sqrt(3) / 2 * (13.5 / 3600.0) ** 2
    assert area == pytest.approx(2.42, rel=0.01)
    assert E.CHR_UNIQUE_AREA_DEG2 == pytest.approx(2.42, rel=0.01)
    r = DSACalculator().calculate("targeted", *HIGH, products=("pulsar",))
    row = r["pulsar"]["untargeted"][0]
    assert row["beam_arcsec"] == pytest.approx(13.5)
    assert row["area_deg2"] == pytest.approx(area, rel=1e-6)


@pytest.mark.parametrize("broaden, loss", [(2.0, 1.56), (3.0, 2.26)])
def test_taper_broadening_at_1p35ghz(broaden, loss):
    # the noise factor at a fixed broadening ratio is independent of frequency (u in wavelengths scales with nu).
    # Values computed from the configuration (Fig. 5 reads 1.45 and 2.0; the PI adopted the computed values).
    nat = E.chr_taper("B2", 0.0, 0.0)["natural_fwhm_arcsec"]
    assert E.chr_taper("B2", 0.0, broaden * nat)["f_taper"] == pytest.approx(loss, rel=0.02)


# 3. quantization per product
def test_quantization_per_product(default_run):
    # voltages enter a correlation (beamforming): S/N efficiency 0.988 (Thompson et al. 2017, Sec. 8.3).
    # Intensities are one quantized stream: S/N factor = sqrt(Fisher efficiency), sqrt(0.8825) and sqrt(0.988)
    v4, i2, i4 = 0.988, 0.939, 0.994
    pu = default_run["pulsar"]
    for row in pu["untargeted"] + pu["targeted"]:
        assert row["losses"]["quantization"] == pytest.approx(v4 * i2)
    # PTA beams are formed before the antenna voltages are requantized to 4 bits: no digitization loss
    assert default_run["pta"]["losses"]["quantization"] == 1.0
    for b in default_run["frb"]["bands"]:
        assert b["losses"]["quantization"] == pytest.approx(v4 * i4)


def test_quantization_efficiency_numbers():
    """Optimum 4-level quantizer: Fisher efficiency for a weak signal in Gaussian noise."""
    from math import erf, exp, pi, sqrt
    cdf = lambda x: 0.5 * (1 + erf(x / sqrt(2)))                                     # noqa: E731
    pdf = lambda x: exp(-x * x / 2) / sqrt(2 * pi)                                   # noqa: E731

    def eff(th):
        th = [-1e9] + sorted([-t for t in th] + [0.0] + list(th)) + [1e9]
        return sum((pdf(a) - pdf(b)) ** 2 / (cdf(b) - cdf(a)) for a, b in zip(th[:-1], th[1:]))
    assert eff([0.9816]) == pytest.approx(0.8825, abs=2e-4)
    assert math.sqrt(eff([0.9816])) == pytest.approx(0.939, abs=1e-3)


# 4. DM smearing and channel summing
def test_dm_smearing_and_channel_summing(default_run):
    assert E.t_dm_s(500.0, 0.12268, 1000.0) == pytest.approx(8.3e-6 * 500 * 0.12268)
    assert [r["chan_kHz"] for r in default_run["pulsar"]["untargeted"]] == pytest.approx([122.68, 245.36, 368.04])
    assert all(b["chan_kHz"] == pytest.approx(122.68) for b in default_run["frb"]["bands"])


# 5. Cordes et al. 2022
@pytest.mark.parametrize("dm, tau", [(250.0, 0.42), (1000.0, 213.0)])
def test_cordes22(dm, tau):
    assert E.tau_cordes22_ms(dm, 1000.0) == pytest.approx(tau, rel=0.02)


# 6. NE2025 grid against direct mwprop (reference values recorded at build time, tests/data/ne2025_reference.json)
def _ne_errors():
    ref = json.load(open(os.path.join(HERE, "data", "ne2025_reference.json")))["points"]
    err = {"dist": [], "tau": [], "tau_x": [], "dm_max": []}
    for q in ref:
        r = E.ne2025_at(q["l"], q["b"], q["dm"])
        assert r["saturated"] == (q["dm"] > r["dm_max"])
        err["tau_x"].append(abs(r["tau_x_1GHz_ms"] / q["tau_x_1GHz_ms"] - 1))
        err["dm_max"].append(abs(r["dm_max"] / q["dm_max"] - 1))
        if q["dm"] < q["dm_max"]:
            err["dist"].append(abs(r["dist_kpc"] / q["dist_kpc"] - 1))
            err["tau"].append(abs(r["tau_1GHz_ms"] / q["tau_1GHz_ms"] - 1))
    return {k: np.asarray(v) for k, v in err.items()}


def test_ne2025_grid_against_recorded_mwprop():
    e = _ne_errors()
    assert np.median(e["dist"]) < 0.05 and np.median(e["tau"]) < 0.05
    assert e["tau_x"].max() < 0.20 and e["dm_max"].max() < 0.10


@pytest.mark.slow
def test_ne2025_grid_against_live_mwprop():
    pytest.importorskip("mwprop")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from build_ne2025_grid import mwprop_direct
    for l, b, dm in ((40.0, 20.0, 50.0), (150.0, 45.0, 20.0), (300.0, -40.0, 30.0)):
        q = mwprop_direct((l, b, dm))
        r = E.ne2025_at(l, b, dm)
        assert r["dist_kpc"] == pytest.approx(q["dist"], rel=0.2)
        assert r["tau_1GHz_ms"] == pytest.approx(q["tau"], rel=0.2)


# 7. data loss follows the RFI profile (no separate T_sys flagging)
def test_band_loss_from_rfi_profile():
    c = DSACalculator()
    r = c.calculate("targeted", *HIGH, products=("frb",))
    for name, lo, hi, _ in E.CHR_BANDS:
        assert r["time_domain"]["usable_fraction"][name] == pytest.approx(
            E.usable_bw_hz(c.rfi, lo, hi) / ((hi - lo) * 1e6))
    full = E.usable_bw_hz(c.rfi, 700.0, 2002.0) / 1302e6
    assert full == pytest.approx(0.85, abs=0.005)                                   # Spring Valley extrapolated


# 8. sidelobe confusion
def test_parallactic_rate_matches_finite_difference():
    lat = E.site_lat()
    for ha, dec in ((10.0, 0.0), (-30.0, 60.0), (5.0, -20.0)):
        def q(h):
            hr, d, p = math.radians(h), math.radians(dec), math.radians(lat)
            return math.atan2(math.sin(hr), math.tan(p) * math.cos(d) - math.sin(d) * math.cos(hr))
        fd = (q(ha + 1e-4) - q(ha - 1e-4)) / math.radians(2e-4)
        assert E.dq_dh(ha, dec, lat) == pytest.approx(fd, rel=1e-4)


def test_confusion_penalties():
    def tgt(P_ms, width_ms):
        r = DSACalculator(psr_period_ms=P_ms, psr_width_ms=width_ms, psr_dm=50.0).calculate(
            "targeted", *HIGH, products=("pulsar",))
        return r["pulsar"]["targeted"][0]["losses"]["confusion"]
    assert 1 - tgt(3.0, 0.3) < 0.01
    assert 1 - tgt(2000.0, 15.0) > 0.01

    def frb(w):
        r = DSACalculator(frb_width_ms=w).calculate("targeted", *HIGH, products=("frb",))
        return r["frb"]["bands"][1]["losses"]["confusion"]
    assert 1 - frb(1.0) < 0.01
    assert frb(1.0) > frb(10.0) > frb(100.0)


# 9. period ranges
@pytest.mark.parametrize("period_ms", [5.0, 20000.0])
def test_untargeted_period_range(period_ms):
    r = DSACalculator(psr_period_ms=period_ms).calculate("targeted", *HIGH, products=("pulsar",))
    for row in r["pulsar"]["untargeted"]:
        assert row["searched"] is False and math.isinf(row["smin_uJy"])


# 10. FRB host model and Macquart relation
def test_frb_host_at_z0():
    c = DSACalculator()
    td = c.td_setup(*HIGH)
    b0 = c.frb_dm_budget(td, 100.0)
    dm = b0["dm_mw"] + b0["dm_halo"] + math.exp(5.49)
    b = c.frb_dm_budget(td, dm)
    assert b["z"] == pytest.approx(0.0, abs=1e-6)
    assert b["dm_host"] == pytest.approx(242.2, rel=1e-3)
    assert b["tau_host_1GHz_ms"] == pytest.approx(3 * E.tau_cordes22_ms(242.2, 1000.0), rel=1e-2)


def test_macquart_relation():
    from scipy.integrate import quad
    h0 = E.H0_KMS_MPC * 1e5 / E.MPC_CM
    k = 3 * 2.99792458e10 * h0 * E.OMEGA_B * 0.84 * E.CHI_E / (8 * math.pi * E.G_CGS * E.M_P_G) / E.PC_CM
    zs = [0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 3.0]
    vals = [E.dm_cosmic(z) for z in zs]
    assert all(b > a for a, b in zip(vals, vals[1:]))
    for z, v in zip(zs, vals):
        ref = k * quad(lambda x: (1 + x) / math.sqrt(E.OMEGA_M * (1 + x) ** 3 + 1 - E.OMEGA_M), 0, z)[0]
        assert v == pytest.approx(ref, rel=0.01)


# 11. FRB losses
def test_frb_losses(default_run):
    assert E.hex_straddle({"bmaj": 3.0, "bmin": 3.0, "pa": 0.0}) == pytest.approx(0.70, rel=0.05)
    for b in default_run["frb"]["bands"]:
        assert b["losses"]["pb_average"] == pytest.approx(0.5 / math.log(2), rel=1e-12)
        assert b["losses"]["pb_average"] == pytest.approx(0.721, abs=1e-3)
        assert 0.9 < b["losses"]["dm_trial"] < 1.0


# 12. rates: Connor et al. eq. 2 with the paper's nominal inputs
@pytest.mark.parametrize("band, nu, bw, expect", [("B1", 0.93, 100.0, 9.0e3), ("B2", 1.41, 200.0, 1.7e4),
                                                 ("B3", 1.80, 300.0, 1.4e4)])
def test_rates_eq2(band, nu, bw, expect):
    _, r, sefd, om, b = E.FRB_RATE_REF[band]
    assert E.frb_rate(r, om, sefd, b, 8.6 / nu ** 2, 1.8, bw, 1.5) == pytest.approx(expect, rel=0.02)


# 13. vocabulary
def test_no_blind_anywhere():
    hits = []
    paths = [os.path.join(ROOT, p) for p in ("python", "web", "docs", "skill")] + \
        [os.path.join(ROOT, "README.md"), os.path.join(ROOT, "CLAUDE.md")]
    for p in paths:
        files = [p] if os.path.isfile(p) else [os.path.join(d, f) for d, _, fs in os.walk(p) for f in fs]
        for f in files:
            if not f.endswith((".py", ".js", ".html", ".css", ".md", ".json", ".txt")):
                continue
            if re.search(r"blind", open(f, encoding="utf-8", errors="ignore").read(), re.I):
                hits.append(os.path.relpath(f, ROOT))
    assert not hits, hits


# outputs and propagation
def test_targeted_presets_and_custom():
    r = DSACalculator(psr_targeted_center_MHz=1400.0).calculate("targeted", *HIGH, products=("pulsar",))
    t = r["pulsar"]["targeted"]
    assert [x["center_MHz"] for x in t] == [953.35, 1800.0, 1400.0]
    assert [x["selected"] for x in t] == [False, False, True]
    assert t[0]["f_lo_MHz"] == pytest.approx(800.0) and t[0]["f_hi_MHz"] == pytest.approx(1106.7)
    r = DSACalculator(psr_targeted_center_MHz=1950.0).calculate("targeted", *HIGH, products=("pulsar",))
    assert r["pulsar"]["targeted"][2]["f_hi_MHz"] == 2002.0 and any("clipped" in w for w in r["warnings"])


def test_curves_shape_and_ranges(default_run):
    c = default_run["pulsar"]["curves"]
    assert len(c["period_s"]) == 200
    assert c["period_s"][0] == pytest.approx(3e-4) and c["period_s"][-1] == pytest.approx(10.0)
    for key in ("targeted", "untargeted_B1", "untargeted_B2", "untargeted_B3"):
        s = c[key]["smin_uJy"]
        assert len(s) == 200
        lo = 1e-3 if key == "targeted" else 1e-2
        for P, v in zip(c["period_s"], s):
            assert (v is None) == (P < lo or P > 10.0)
    f = default_run["frb"]["curves"]
    assert len(f["dm"]) == 60 and all(len(f[b]) == 60 for b in ("B1", "B2", "B3"))


def test_frb_peak_flux_uses_weff(default_run):
    for b in default_run["frb"]["bands"]:
        assert b["speak_min_mJy"] == pytest.approx(b["fluence_min_Jyms"] / b["weff"]["weff_ms"] * 1e3)


def test_cordes22_mode_has_no_distance():
    r = DSACalculator(td_scattering="cordes22").calculate("targeted", *GP, products=("pulsar", "frb"))
    assert r["pulsar"]["propagation"]["dist_kpc"] is None
    assert r["frb"]["dm_budget"]["tau_mw_1GHz_ms"] == 0.0


def test_default_pulsar_dm_is_half_galactic():
    r = DSACalculator().calculate("targeted", *GP, products=("pulsar",))
    pu = r["pulsar"]
    assert pu["inputs"]["dm_default"] is True
    assert pu["inputs"]["dm"] == pytest.approx(0.5 * pu["propagation"]["dm_max"])
    r = DSACalculator(psr_dm=123.0).calculate("targeted", *GP, products=("pulsar",))
    assert r["pulsar"]["inputs"]["dm"] == 123.0 and r["pulsar"]["inputs"]["dm_default"] is False


def test_time_domain_efficiency_follows_system_value():
    r = DSACalculator().calculate("targeted", *HIGH, products=("frb",))
    assert r["time_domain"]["aperture_efficiency"] == 0.67
    r = DSACalculator(aperture_efficiency=0.6).calculate("targeted", *HIGH, products=("frb",))
    assert r["time_domain"]["aperture_efficiency"] == 0.6


def test_frb_localization_uniform_beam():
    psf0 = json.load(open(os.path.join(ROOT, "python", "dsa_etc", "data", "psf_uniform.json")))
    assert psf0["natural_check"]["bmaj"] == pytest.approx(3.03, rel=0.01)       # method reproduces the natural PSF
    assert psf0["natural_check"]["bmin"] == pytest.approx(2.31, rel=0.01)
    r = DSACalculator().calculate("targeted", 180.0, 30.0, products=("frb",))
    loc = [(b["loc_ra_1sigma_arcsec"], b["loc_dec_1sigma_arcsec"]) for b in r["frb"]["bands"]]
    assert loc[0][0] > loc[1][0] > loc[2][0] and loc[0][1] > loc[1][1] > loc[2][1]   # higher bands localize better
    b2 = r["frb"]["bands"][1]
    assert b2["psf_uniform"]["bmaj"] < b2["psf"]["bmaj"]


def test_smin_curves_keep_duty_cycle():
    r = DSACalculator().calculate("targeted", *HIGH, products=("pulsar",))
    c = r["pulsar"]["curves"]
    assert c["duty_cycle"] == pytest.approx(15.0 / 500.0)
    i = min(range(200), key=lambda k: abs(c["period_s"][k] - 2e-3))
    assert c["targeted"]["smin_uJy"][i] is not None and math.isfinite(c["targeted"]["smin_uJy"][i])


def test_targeted_mode_sets_the_time_domain_track():
    r1 = DSACalculator().calculate("targeted", *HIGH, hours=4.0, products=("pulsar", "frb", "pta"))
    r0 = DSACalculator().calculate("survey", *HIGH, products=("pulsar", "frb", "pta"))
    assert r1["time_domain"]["track_s"] == pytest.approx(4 * 3600.0) and r0["time_domain"]["track_s"] == 1260.0
    snr1, snr0 = r1["pta"]["snr"], r0["pta"]["snr"]
    assert snr1 / snr0 == pytest.approx(math.sqrt(4 * 3600 / 1260.0), rel=0.05)      # S/N ~ sqrt(t), small confusion/elevation effects
    for r, t in ((r1, 4 * 3600.0), (r0, 1260.0)):
        b = r["frb"]["bands"][1]
        assert b["rate_in_track"] == pytest.approx(b["rate_per_yr"] * t / E.YEAR_S, rel=1e-12)



# self-noise: the source flux density raises the on-pulse (on-burst) noise
def test_self_noise_factor_limits():
    assert E.self_noise_factor(0.0, 0.03) == pytest.approx(1.0)
    d = 0.03
    # S/N (units of sqrt(n_pol B t), SEFD = 1) of the on-minus-off estimate for mean flux density S, on-pulse S / d,
    # equals the no-self-noise S/N, S sqrt((1 - d) / d), times the factor
    direct = lambda S: (S / d) / math.sqrt((1 + S / d) ** 2 / d + 1 / (1 - d))
    for S in (1e-4, 0.01, 1.0, 100.0):
        assert direct(S) == pytest.approx(S * math.sqrt((1 - d) / d) * E.self_noise_factor(S / d, d), rel=1e-12)
    # a very bright source: the S/N saturates at sqrt(d), whatever its flux density
    assert direct(1e7) == pytest.approx(math.sqrt(d), rel=1e-4)


def test_self_noise_in_products():
    on = DSACalculator().calculate("targeted", *HIGH, products=("pulsar", "frb", "pta"))
    off = DSACalculator(td_self_noise=False).calculate("targeted", *HIGH, products=("pulsar", "frb", "pta"))
    # a faint pulsar at the threshold: S_min barely changes; FRB limits rise by a percent or two
    assert on["pulsar"]["targeted"][0]["smin_uJy"] == pytest.approx(off["pulsar"]["targeted"][0]["smin_uJy"], rel=1e-3)
    for a, b in zip(on["frb"]["bands"], off["frb"]["bands"]):
        assert 1.0 < a["fluence_peak_Jyms"] / b["fluence_peak_Jyms"] < 1.05
        assert a["losses"]["self_noise"] == pytest.approx(b["fluence_peak_Jyms"] / a["fluence_peak_Jyms"])
    # a bright millisecond pulsar loses S/N to self-noise
    br = DSACalculator(pta_flux_mJy=100.0).calculate("targeted", *HIGH, products=("pta",))["pta"]
    assert br["losses"]["self_noise"] < 0.5
    assert on["pta"]["losses"]["self_noise"] < 1.0


def test_threshold_solver_reaches_threshold():
    c = DSACalculator(frb_snr=200.0)
    td = c.td_setup(*HIGH, 3600.0)
    bud = c.frb_dm_budget(td, 500.0)
    fl, fl0, wc, conf, sig_band, bw = c.frb_fluence(td, 880.0, 980.0, bud)
    assert fl > fl0
    # independent S/N at the solved fluence
    p, n = c.p, c.p["n_ant"]
    a = 0.0
    for s in c.td_subbands(td, 880.0, 980.0):
        if s["bw_hz"] <= 0:
            continue
        sb = s["sefd"] / math.sqrt(n * (n - 1))
        sig = sb / math.sqrt(p["n_pol"] * s["bw_hz"])
        w = c._frb_weff(s["fc"], bud)[0]
        a += (fl / (sig * math.sqrt(w)) * E.self_noise_factor(fl / w / sb, w / (w + max(1.0, 10 * w)))) ** 2
    assert p["td_eta_v4"] * p["td_eta_i4"] * conf * math.sqrt(a) == pytest.approx(200.0, rel=1e-8)


# FRB rates: actual beam coverage, source-count weighting
def test_rate_solid_angle():
    tp, al = 3.0, 1.5
    full = math.pi / 4 * tp ** 2
    # beams covering exactly the FWHM disk give the FWHM area
    nb = full / (E.HEX_CELL * (1.0 / 3600) ** 2)
    om, a = E.frb_rate_solid_angle(nb, 1.0, tp, al)
    assert a == pytest.approx(full) and om == pytest.approx(full)
    # half the area counts for more than half, since the center is the most sensitive
    om_h, _ = E.frb_rate_solid_angle(nb / 2, 1.0, tp, al)
    assert 0.5 * full < om_h < full


def test_rate_weighted_straddle():
    rng = np.random.default_rng(3)
    R = 1 / math.sqrt(3)
    x, y = rng.uniform(-R, R, 2_000_000), rng.uniform(-R, R, 2_000_000)
    m = (np.abs(x) <= R * math.sqrt(3) / 2) & (np.abs(y) <= R - np.abs(x) / math.sqrt(3))
    r = np.exp(-4 * math.log(2) * (x[m] ** 2 + y[m] ** 2))
    beam = {"bmaj": 1.0, "bmin": 1.0, "pa": 0.0}
    assert E.hex_straddle(beam) == pytest.approx(r.mean(), rel=2e-3)
    assert E.hex_straddle(beam, 1.5) == pytest.approx(np.mean(r ** 1.5) ** (1 / 1.5), rel=2e-3)
    b = DSACalculator().calculate("targeted", *HIGH, products=("frb",))["frb"]["bands"][1]
    assert b["straddle_rate"] > b["losses"]["straddle"]
    assert b["omega_rate_deg2"] < b["fov_deg2"] and b["beam_coverage"] < 1.0
