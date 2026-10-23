"""Checks of the engine against the DSA design documents.  Run: python3 -m pytest tests/test_engine.py"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import pytest
from dsa_etc import DSACalculator, confusion_uJy
from dsa_etc.engine import mosaic_z, DATA_DIR, K_B, JY

calc = DSACalculator()


def test_sefd_zenith():
    # SIP value with the flat 21.4 K option; the default is the measured bandpass (one T_sys for every product)
    c = DSACalculator(galactic_noise=False, tsys_zenith_K=21.4)
    area = math.pi * (6.155 / 2) ** 2
    assert c.sefd_jy(1350, 0.0, 0, 0) == pytest.approx(2 * K_B * 21.4 / 0.67 / area / JY, rel=1e-9)
    assert c.sefd_jy(1350, 0.0, 0, 0) == pytest.approx(2964, rel=1e-3)
    d = DSACalculator(galactic_noise=False)
    from dsa_etc.engine import tsys_bandpass_K
    assert d.sefd_jy(1350, 0.0, 0, 0) == pytest.approx(2 * K_B * tsys_bandpass_K(1350) / 0.67 / area / JY, rel=1e-9)


def test_tsys_bandpass_separates_rfi():
    """The bandpass is the measurement with RFI removed: never above it, equal where clean, and close to the clean median."""
    import numpy as np
    d = json.load(open(os.path.join(DATA_DIR, "tsys_bandpass.json")))
    T, M, m = (np.asarray(d[k], float) for k in ("tsys_zenith_K", "tsys_measured_K", "rfi_masked"))
    clean = m == 0
    dev = np.abs(T[clean] - M[clean])
    assert np.median(dev) < 0.1 and dev.max() < 1.5               # light smoothing only where the data are clean
    assert d["median_K"] == pytest.approx(21.4, abs=0.3)
    assert 0.2 < m.mean() < 0.4
    assert T.min() > 15.0 and T.max() < 30.0                      # no RFI spikes or drop-outs left
    lo = DSACalculator(rfi=None)
    # band-averaged T_sys excludes flagged channels: 1200-1300 MHz is dominated by RFI in the raw file
    assert lo.tz_K(1200.0, 1300.0) < 23.0


def test_one_tsys_for_all_products():
    c = DSACalculator(galactic_noise=False)
    r = c.calculate("targeted", 150.0, 30.0, hours=1.0, products=("continuum", "frb"))
    td = c.td_setup(150.0, 30.0, 3600.0)
    s = c.td_subbands(td, 1310.0, 1320.0)[0]
    assert s["tsys_K"] == pytest.approx(c.tz_K(1310.0, 1320.0))
    w = r["continuum"]["windows"][0]
    assert w["sefd_Jy"] == pytest.approx(c.sefd_eff(c.setup("targeted", 150.0, 30.0, hours=1.0), w["f_center_MHz"],
                                                    (w["f_lo_MHz"], w["f_hi_MHz"])))


# Version 1 spillover table (total T_sys/eta vs ZA, 6.15-m dish with cylindrical shield; band average)
V1_ZA = list(range(0, 85, 5))
V1_TOVERETA = [28.4402991408795, 28.5193373928180, 28.7595943656126, 29.1409699630969, 29.6184482113807,
               30.1442670930362, 30.6922101502842, 31.2571154083086, 31.8775062604304, 32.6024366119219,
               33.4397720555654, 34.4045056919293, 35.5353224055825, 37.0667895644841, 39.2670157941557,
               42.5294414716481, 48.2998097835121]


def test_za_spillover_plus_atmosphere_reproduce_version_1():
    """Spillover (Jonas) + ITU-R atmosphere, band-averaged, match the version 1 total T_sys/eta curve (eta 0.67)."""
    from dsa_etc.engine import za_increase_K, _tsys_za
    fs = _tsys_za()["freq_MHz"]
    for za, t in zip(V1_ZA, V1_TOVERETA):
        new = sum(sum(za_increase_K(f, za)) for f in fs) / len(fs)
        assert new == pytest.approx((t - V1_TOVERETA[0]) * 0.67, abs=0.25 if za <= 75 else 0.6)


def test_za_terms():
    from dsa_etc.engine import za_increase_K, _tsys_za
    d = _tsys_za()
    assert za_increase_K(1350.0, 0.0) == (0.0, 0.0)                    # zenith values are in the bandpass
    assert 1.1 < min(d["atm_zenith_K"]) and max(d["atm_zenith_K"]) < 1.5   # ITU-R zenith atmosphere at 1.75 km
    s60, a60 = za_increase_K(1350.0, 60.0)
    assert a60 == pytest.approx(min(d["atm_zenith_K"][20:24]), rel=0.15)   # ~sec(ZA) - 1 = 1 at 60 deg
    s85, a85 = za_increase_K(1350.0, 85.0)
    assert s85 > za_increase_K(1350.0, 80.0)[0] and a85 > za_increase_K(1350.0, 80.0)[1]   # extrapolated beyond 80
    c = DSACalculator(galactic_noise=False)
    area = math.pi * (6.155 / 2) ** 2
    assert c.sefd_jy(1350, 60.0, 0, 0) == pytest.approx(2 * K_B * (c.tz_K(1350) + s60 + a60) / 0.67 / area / JY)
    b = c.tsys_breakdown(1350.0, 60.0, 0, 0)
    assert b["tsys_K"] == pytest.approx(b["tsys_zenith_K"] + s60 + a60)


def test_sip_radiometer_statement():
    # SIP: SEFD 3318 Jy, N=1650, 845 MHz, 10 min -> 2.00 uJy/beam (no quantization loss)
    ideal = DSACalculator(correlator_efficiency=1.0)
    assert ideal.radiometer_jy(3318.0, 845e6, 600.0) * 1e6 == pytest.approx(2.00, abs=0.01)
    # imaging products carry the 4-bit correlator efficiency 0.988 by default
    assert calc.radiometer_jy(3318.0, 845e6, 600.0) == pytest.approx(ideal.radiometer_jy(3318.0, 845e6, 600.0) / 0.988)


def test_imaging_quantization_applies_to_imaging_only():
    kw = dict(products=("continuum", "line", "polarization", "frb", "pulsar", "pta"))
    a = calc.calculate("targeted", 150.12, 2.21, hours=1, weighting="natural:optimal", **kw)
    b = DSACalculator(correlator_efficiency=1.0).calculate("targeted", 150.12, 2.21, hours=1, weighting="natural:optimal", **kw)
    for x, y in ((a["continuum"]["fc"]["thermal_uJy"], b["continuum"]["fc"]["thermal_uJy"]),
                 (a["continuum"]["snapshots_6s"][4]["thermal_uJy"], b["continuum"]["snapshots_6s"][4]["thermal_uJy"]),
                 (a["line"]["ZA"]["channels"][0]["sigma_mJy"], b["line"]["ZA"]["channels"][0]["sigma_mJy"]),
                 (a["polarization"]["band_qu_sigma_uJy"], b["polarization"]["band_qu_sigma_uJy"])):
        assert x == pytest.approx(y / 0.988)
    assert a["frb"]["bands"][1]["fluence_min_Jyms"] == b["frb"]["bands"][1]["fluence_min_Jyms"]
    assert a["pulsar"]["targeted"][0]["smin_uJy"] == b["pulsar"]["targeted"][0]["smin_uJy"]
    assert a["pta"]["toa_us"] == b["pta"]["toa_us"]


@pytest.mark.parametrize("f,zmax,zmean,zmin", [(700, 5.38, 5.36, 5.28), (1350, 1.50, 1.44, 1.41), (2000, 1.00, 0.65, 0.48)])
def test_mosaic_weights_match_sip(f, zmax, zmean, zmin):
    z = mosaic_z(f)
    assert z["zmean"] == pytest.approx(zmean, abs=0.02)
    assert z["zmax"] == pytest.approx(zmax, abs=0.02)
    assert z["zmin"] == pytest.approx(zmin, abs=0.02)


@pytest.mark.parametrize("theta,nu,sigma", [(2.57, 1350, 0.154), (3.58, 1350, 0.463), (4.31, 1350, 0.764),
                                             (6.00, 1350, 1.65), (3.07, 1120, 0.329), (7.21, 1120, 2.704)])
def test_confusion_matches_rosero_tables(theta, nu, sigma):
    assert confusion_uJy(theta, nu, 16) == pytest.approx(sigma, rel=0.02)


def test_psf_from_configuration():
    r = calc.calculate("survey", 0.0, 39.55, products=("line",))
    b = r["line"]["ZA"]["channels"][0]["psf"]           # natural PSF at 1420.4 MHz
    s = 1420.405752 / 1350.0
    assert b["bmaj"] * s == pytest.approx(3.03, abs=0.02) and b["bmin"] * s == pytest.approx(2.31, abs=0.02)


def test_hi_channel_velocity_widths():
    r = calc.calculate("survey", 0.0, 30.0, products=("line",))
    assert r["line"]["ZB"]["dv_kms_at_1420"] == pytest.approx(0.2146, rel=1e-3)
    assert r["line"]["ZA"]["dv_kms_at_1420"] == pytest.approx(1.7176, rel=1e-3)
    assert r["line"]["NL"]["dv_kms_at_1420"] == pytest.approx(27.48, rel=1e-3)


def test_rm_synthesis():
    p = calc.calculate("survey", 0.0, 30.0, products=("polarization",))["polarization"]
    assert p["rmsf_fwhm_rad_m2"] == pytest.approx(21.5, abs=0.1)
    assert p["max_scale_rad_m2"] == pytest.approx(140.1, abs=0.2)


def test_allocation_budget():
    al = json.load(open(os.path.join(DATA_DIR, "allocation.json")))
    for v in al["variants"]:
        used = sum(t["n_ptg"] * t["epochs"][v] for t in al["tiles"].values())
        assert used <= 64250
        assert min(t["epochs"][v] for t in al["tiles"].values()) >= 2
    assert sum(t["n_ptg"] for t in al["tiles"].values()) == 12850
    assert len(al["tiles"]) == 429


def test_galactic_center_is_hot():
    gc = calc.calculate("survey", 266.405, -28.936, products=())["system"]["galactic_excess_K"]
    cold = calc.calculate("survey", 150.12, 2.21, products=())["system"]["galactic_excess_K"]
    assert gc > 20 and abs(cold) < 1


def test_survey_edge_and_pole_depth():
    edge = calc.calculate("survey", 30.0, -30.4, products=())["observation"]["effective_epochs_1350"]
    pole = calc.calculate("survey", 30.0, 89.9, products=())["observation"]["effective_epochs_1350"]
    assert 0.8 < edge < 1.4 and pole == pytest.approx(2.0, abs=0.05)


def test_targeted_splits_long_tracks():
    o = calc.calculate("targeted", 150.12, 2.21, hours=100.0, products=())["observation"]
    assert o["n_transits"] == 25 and o["ha_half_h"] == pytest.approx(2.0)


def test_effective_epochs_follow_requested_depth():
    one = calc.calculate("survey", 150.12, 2.21, depth="single", products=())["observation"]["effective_epochs_1350"]
    three = calc.calculate("survey", 0.0, 0.0, depth="custom", n_epochs=3, products=())["observation"]["effective_epochs_1350"]
    assert one == pytest.approx(1.0, abs=0.01) and three == pytest.approx(3.0, abs=0.01)


def test_rfi_default_is_extrapolated_spring_valley():
    from dsa_etc import rfi_default, rfi_measured
    from dsa_etc.engine import usable_bw_hz
    import numpy as np
    ext, mea = rfi_default(), rfi_measured()
    assert ext["name"] == "Spring Valley model extrapolated"
    loss = lambda p: 1 - usable_bw_hz(p, 700.0, 2002.0) / 1302e6
    assert loss(ext) == pytest.approx(0.15, abs=0.001) and loss(mea) == pytest.approx(0.028, abs=0.002)
    assert np.all(ext["occ"] >= mea["occ"] - 1e-9)                       # same pattern, only scaled up
    assert np.all(ext["occ"][mea["occ"] == 0] == 0)                      # clean channels stay clean
    hi = (ext["freq"] >= 1400) & (ext["freq"] <= 1427)
    assert ext["occ"][hi].max() == 0                                     # protected HI band
    usable = calc.calculate("survey", 150.12, 2.21, products=())["system"]["usable_band_fraction"]
    assert usable == pytest.approx(0.85, abs=0.001)


def test_default_survey_plan_is_plan_a():
    al = json.load(open(os.path.join(DATA_DIR, "allocation.json")))
    assert al["default_variant"] == "A" and al["variants"]["A"]["label"] == "Plan A: DSA-00264 corrected fill"
    o = calc.calculate("survey", 150.12, 2.21, products=())["observation"]
    assert o["tile"]["variant"] == "A" and o["n_epochs"] == 7                  # Euclid/HSC at 7 epochs


def test_default_position_transits_at_zenith():
    r = calc.calculate(products=())
    assert (r["inputs"]["ra"], r["inputs"]["dec"]) == (170.0, 39.57)
    assert r["observation"]["za_transit"] < 0.05 and r["system"]["spill_K"] < 0.01


def test_smoothing_noise_matches_all_baselines():
    """The smoothing noise uses every baseline under 1 km plus 1 in 13 longer ones; check it against all 1,360,425."""
    import math
    import numpy as np
    from dsa_etc import engine as eg
    a = eg._antennas()
    E, N, U = (np.asarray(a[k], float) for k in ("E", "N", "U"))
    i, j = np.triu_indices(len(E), 1)
    BE, BN, BU = E[j] - E[i], N[j] - N[i], U[j] - U[i]
    phi = math.radians(a["site_lat_deg"])
    Lx, Ly, Lz = -math.sin(phi) * BN + math.cos(phi) * BU, BE, math.cos(phi) * BN + math.sin(phi) * BU
    f, dec, lam = 1350.0, 39.57, eg.C_LIGHT / 1350e6
    u, v = Ly / lam, (-math.sin(math.radians(dec)) * Lx + math.cos(math.radians(dec)) * Lz) / lam   # transit
    for theta in (60.0, 1200.0):
        k = eg.smooth_plan({"bmaj": 3.03, "bmin": 2.31, "pa": 90.6}, theta)
        a_ = math.radians(k["pa"])
        pm, pn = u * math.sin(a_) + v * math.cos(a_), u * math.cos(a_) - v * math.sin(a_)
        T = np.exp(-(math.pi ** 2 / eg.FOUR_LN2) * ((k["k_maj"] * eg.ARCSEC) ** 2 * pm ** 2 + (k["k_min"] * eg.ARCSEC) ** 2 * pn ** 2))
        full = math.sqrt((T * T).sum() * len(T)) / T.sum()
        assert eg.taper_noise_factor(k, f, dec, [0.0], [1.0], a["site_lat_deg"]) == pytest.approx(full, rel=0.005)


def test_source_counts_from_both_confusion_curves_agree():
    import numpy as np
    from dsa_etc.engine import _counts
    S16, N16, _, _ = _counts(16)
    S25, N25, _, _ = _counts(25)
    for s in (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0):
        n16 = np.exp(np.interp(np.log(s), np.log(S16), np.log(N16)))
        n25 = np.exp(np.interp(np.log(s), np.log(S25), np.log(N25)))
        assert n16 == pytest.approx(n25, rel=0.05)


def test_source_subtraction_before_smoothing():
    from dsa_etc.engine import residual_confusion_uJy
    r = calc.calculate(products=("continuum",), smooth_arcsec=60)["continuum"]
    fc, sm = r["fc"], r["smoothed"]
    # at full resolution the Poisson remainder below 5 sigma matches the confusion curve's own value
    native = residual_confusion_uJy(5 * fc["total_uJy"], fc["nu_eff_MHz"], fc["psf"], fc["nu_eff_MHz"])
    assert native == pytest.approx(fc["confusion_uJy"], rel=0.15)
    sx = sm["subtraction"]
    assert sx["applied"] and sm["confusion_uJy"] == pytest.approx(sx["residual_confusion_uJy"])
    assert sx["limit_uJy"] == pytest.approx(5 * fc["total_uJy"])
    assert sm["tb_total_mK"] == pytest.approx(2.0, rel=0.1) and sx["tb_total_unsubtracted_mK"] > 10 * sm["tb_total_mK"]
    # the remainder is a Poisson population: its confusion grows linearly with beam size
    psf2 = {"bmaj": 2 * sm["psf"]["bmaj"], "bmin": 2 * sm["psf"]["bmin"], "pa": 0.0}
    r2 = residual_confusion_uJy(sx["limit_uJy"], sx["limit_nu_MHz"], psf2, sm["nu_eff_MHz"])
    assert r2 == pytest.approx(2 * sx["residual_confusion_uJy"], rel=1e-9)
    off = DSACalculator(smooth_subtract_sources=False).calculate(products=("continuum",), smooth_arcsec=60)
    assert off["continuum"]["smoothed"]["confusion_uJy"] == pytest.approx(sx["unsubtracted_confusion_uJy"])
