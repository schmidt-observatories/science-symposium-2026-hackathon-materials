# dsa-etc cookbook

Worked answers to common questions with the `dsa_etc` package (version 3.1). Installation, options and the output fields are in [`README.md`](README.md); the model is in [`../docs/model.md`](../docs/model.md).

Code blocks run in order in one session (IPython, notebook or script). Quoted values use the default model: Plan A, extrapolated RFI profile (15% of the band lost), measured T_sys bandpass, η = 0.67, 4-bit quantization efficiency 0.988 on the imaging products, β_min = 16. Noise is 1σ per beam. Positions: COSMOS (150.12°, +2.21°); a high-latitude field at (180°, +30°).

```python
import numpy as np
from dsa_etc import DSACalculator, rfi_measured
from dsa_etc.engine import SCHEMES

calc = DSACalculator()
```

## Contents

1. [Survey depth at a position](#1-survey-depth-at-a-position)
2. [Targeted time to reach a continuum noise](#2-targeted-time-to-reach-a-continuum-noise)
3. [Detectability and spectral index of a continuum source](#3-detectability-and-spectral-index-of-a-continuum-source)
4. [Extended emission: brightness temperature after smoothing](#4-extended-emission-brightness-temperature-after-smoothing)
5. [HI column density and mass limits](#5-hi-column-density-and-mass-limits)
6. [Polarization and RM synthesis](#6-polarization-and-rm-synthesis)
7. [Transient light curve observed at a given cadence](#7-transient-light-curve-observed-at-a-given-cadence)
8. [FRBs: fluence limit, DM, localization, rates](#8-frbs-fluence-limit-dm-localization-rates)
9. [Pulsars: detectability, S_min(P), timing](#9-pulsars-detectability-s_minp-timing)
10. [Sky maps and sweeps](#10-sky-maps-and-sweeps)
11. [Sensitivity to the assumptions](#11-sensitivity-to-the-assumptions)

## 1. Survey depth at a position

**Q.** What noise does the survey reach at a position: after all epochs, in one epoch, after N epochs?

```python
for depth, n in (("full", None), ("single", None), ("custom", 3)):
    r = calc.calculate("survey", 150.12, 2.21, depth=depth, n_epochs=n, products=("continuum",))
    fc, o = r["continuum"]["fc"], r["observation"]
    print(depth, n, "%.3f (%.3f, %.3f) uJy" % (fc["total_uJy"], fc["thermal_uJy"], fc["confusion_uJy"]),
          "N_eff %.2f of %d" % (o["effective_epochs_1350"], o["epochs_full"]))
```

COSMOS, tile N01_17 (7 epochs, Robust R = 0.4, optimal summation): full depth 0.449 μJy (thermal 0.369, confusion 0.256); one epoch 1.005 (0.971, 0.258). `continuum.single_pointing` gives one 21-min pointing at the beam center without mosaicking (1.34 μJy).

- Thermal noise scales as N^−1/2; confusion does not.
- N_eff (`effective_epochs_1350`) averages the epochs of the tiles under the squared primary beam, so it is non-integer near tile boundaries: 5.27 at (0°, 0°), between a 7- and a 3-epoch tile.
- Depth falls near the southern edge (δ = −30.45°); `warnings` says so.
- Survey T_sys is evaluated at transit.

## 2. Targeted time to reach a continuum noise

**Q.** How long must a targeted observation be to reach a full-band total noise σ?

Thermal noise falls as t^−1/2, confusion does not. Solve for t in each weighting and keep the shortest; if no weighting reaches σ, it is below the confusion floor at that resolution.

```python
def hours_for(target_uJy, ra, dec, hi=5000.0):
    """Shortest targeted time (h) for a full-band continuum total noise; (hours, weighting) or None."""
    best = None
    for im, su in SCHEMES:
        w = im + ":" + su
        total = lambda h: calc.calculate("targeted", ra, dec, hours=h, products=("continuum",),
                                         weighting=w)["continuum"]["fc"]["total_uJy"]
        if total(hi) > target_uJy:
            continue                                  # confusion floor, or more than `hi` hours
        lo, top = 0.01, hi
        for _ in range(40):                           # bisection in log(hours)
            mid = (lo * top) ** 0.5
            lo, top = (mid, top) if total(mid) > target_uJy else (lo, mid)
        if best is None or top < best[0]:
            best = (top, w)
    return best

for s in (1.0, 0.3, 0.2, 0.05):
    print(s, hours_for(s, 180.0, 30.0))
```

At (180°, +30°): 1 μJy in 0.43 h (Natural); 0.3 μJy in 6.3 h (Robust, R = 0.46–1.94); 0.2 μJy in 17.0 h (Robust, R = 0.4); 0.05 μJy is below the confusion floor (0.09 μJy with Robust, R = 0.4).

- Tracks are limited to |HA| ≤ 2 h and elevation ≥ 20°; longer requests are split evenly over transits (`observation.n_transits`). At δ = −30° only about ±0.6 h is available per transit.
- Near the floor the answer depends on small PSF changes: quote it as approximate, with the thermal and confusion parts.
- The same bisection applies to any other output, e.g. an HI channel noise or a pulsar S_min.

## 3. Detectability and spectral index of a continuum source

**Q.** Is a source of flux density S_ν detected, and how well is its spectral index measured?

The full-band image is the weighted sum of the ten 130.2-MHz windows, with weights `fc.window_weights` (normalized). A source of spectrum S(ν) therefore has full-band flux density Σ w_i S(ν_i).

```python
r = calc.calculate("survey", 150.12, 2.21, depth="single", products=("continuum",))
c = r["continuum"]
nu = np.array([w["f_center_MHz"] for w in c["windows"]])
sig = np.array([w["total_uJy"] for w in c["windows"]])
w = np.array(c["fc"]["window_weights"])

S = 5.0 * (nu / 1400.0) ** -0.7                       # uJy: 5 uJy at 1.4 GHz, alpha = -0.7
S_fc = w @ S
print("full band: %.2f uJy, S/N %.1f" % (S_fc, S_fc / c["fc"]["total_uJy"]))
print("per window S/N:", np.round(S / sig, 1))
```

One survey epoch at COSMOS: S_fc = 6.10 μJy at ν_eff = 1129 MHz, S/N = 6.1; per-window S/N 3.2 (765 MHz) to 0.7 (1937 MHz).

- Optimal summation weights the low-frequency windows in a mosaic (largest mosaic weight Z(ν)); with equal summation ν_eff is closer to the band center.
- Spectral-index uncertainty: see the Fisher estimate in Section 7 (not part of the engine; it assumes a power law and independent Gaussian window noise).

## 4. Extended emission: brightness temperature after smoothing

**Q.** What surface-brightness sensitivity does the survey reach on a scale θ?

```python
r = calc.calculate("survey", 150.12, 2.21, smooth_arcsec=60, products=("continuum",))
sm = r["continuum"]["smoothed"]
sx = sm["subtraction"]
print("thermal %.2f uJy/beam, T_b thermal %.2f mK, total %.2f mK (sources > %.2f uJy subtracted)"
      % (sm["thermal_uJy"], sm["tb_thermal_mK"], sm["tb_total_mK"], sx["limit_uJy"]))
print("without subtraction: confusion %.1f uJy/beam, T_b total %.1f mK"
      % (sx["unsubtracted_confusion_uJy"], sx["tb_total_unsubtracted_mK"]))
```

COSMOS, full depth, 60″: thermal 3.51 μJy/beam, T_b thermal 1.26 mK; total 2.16 mK after subtracting sources above 2.24 μJy (5σ of the full-resolution image); 34.2 mK without subtraction.

- Smoothing is a uv taper on the configuration's baselines; the smoothed beam is the requested circular Gaussian. Smoothed products use natural weighting and optimal summation.
- The main lobe of a tapered dirty beam is within 2% of the request to 1′ and within 13% to 10′ at 1.35 GHz. Requests beyond 15′ carry a warning; the limit scales with wavelength (about 30′ at 0.7 GHz).
- The subtracted residual includes neither source clustering nor subtraction errors. Always state which case is quoted.
- HI and polarization channels carry their own `smoothed` entries.

## 5. HI column density and mass limits

**Q.** What N_HI and M_HI limits does a cube reach, for chosen distances and line widths?

```python
c2 = DSACalculator(hi_distances_Mpc=[20.0, 40.0], hi_widths_kms=[100.0])
r = c2.calculate("survey", 150.12, 2.21, products=("line",))
za = r["line"]["ZA"]["channels"][0]
print("Zoom A: %.3f mJy per %.2f km/s, 5-sigma N_HI(20 km/s) %.2e cm^-2" % (za["sigma_mJy"], za["dv_kms"], za["nhi_5sigma_cm2"]))
for m in za["mhi_limits"]:
    print("  D %.0f Mpc, W %.0f km/s: M_HI(5 sigma) %.2e Msun" % (m["D_Mpc"], m["width_kms"], m["mhi_5sigma_Msun"]))
for ch in r["line"]["NL"]["channels"]:
    print("NL z %.2f: %.4f mJy" % (ch["z"], ch["sigma_mJy"]), ["%.2e" % m["mhi_5sigma_Msun"] for m in ch["mhi_limits"]])
```

COSMOS, full depth: Zoom A 0.147 mJy per 1.72 km/s channel, 5σ N_HI = 6.0 × 10²⁰ cm⁻² (emission filling the beam, over 20 km/s); 5σ M_HI (W = 100 km/s) = 9.0 × 10⁵ M_☉ at 20 Mpc, 3.6 × 10⁶ M_☉ at 40 Mpc. Narrow Line at z = 0.5 (D_L = 2921 Mpc): 0.020 mJy per channel, M_HI = 8.8 × 10⁹ M_☉.

- Cubes: Zoom B (960 × 1.017 kHz), Zoom A (4192 × 8.138 kHz), Narrow Line (5600 × 130.2 kHz, z ≤ 1.03). HI cubes are continuum subtracted; confusion does not apply.
- M_HI = 49.7 D_L² S_int (M_☉, Mpc, Jy Hz), S_int = 5σ_ch √n Δν_ch, unresolved source, boxcar line; Narrow Line uses D_L(z), flat ΛCDM (Planck 2018).
- N_HI is optically thin, rest-frame T_b, 5σ over 20 km/s (`nhi_width_kms`).
- Narrow Line noise varies with redshift through the RFI occupancy at 1420/(1+z) MHz (z = 0.1 lies in an RFI-affected range).
- Doppler tracking is assumed ideal.

## 6. Polarization and RM synthesis

**Q.** What polarized-intensity noise and Faraday-depth parameters does a polarization cube give?

```python
p = calc.calculate("survey", 150.12, 2.21, products=("polarization",))["polarization"]
print("Q/U band noise %.3f uJy; RMSF %.1f, max scale %.0f, max |RM| %.0f rad/m^2"
      % (p["band_qu_sigma_uJy"], p["rmsf_fwhm_rad_m2"], p["max_scale_rad_m2"], p["max_rm_rad_m2"]))
spec = np.array(p["spectrum"])                         # [MHz, sigma_uJy] for each 2.6-MHz channel
```

COSMOS, full depth: σ_Q,U = 0.368 μJy (band-averaged, inverse-variance weights; the same noise applies to the Faraday-depth spectrum of RM synthesis). RMSF FWHM 21.5 rad m⁻²; largest Faraday-depth scale 140 rad m⁻²; largest measurable |RM| 1269 rad m⁻² (50% depolarization within one 2.6-MHz channel at 700 MHz).

- Q, U and V are thermal-noise limited.
- The largest scale limits extended Faraday structure, not the RM of a compact source.

## 7. Transient light curve observed at a given cadence

**Q.** Given a model light curve S(t, ν) of a radio transient and a cadence of visits, what time-domain information does the DSA provide?

The calculator gives the noise of one visit; detections, spectral indices and stacked depths of the model follow from it (recipe below):

| Information | Noise in the output | Timescale |
|---|---|---|
| Detection and flux density | full-band `continuum.fc` (I) | one visit (one survey epoch of the mosaic, or the targeted track) |
| Spectrum, spectral index | `continuum.windows[]`, ten 130.2-MHz windows | one visit |
| Linear polarization, RM | `polarization` with `depth="single"` | one visit |
| Faint or late emission | stacked visits: `depth="custom"` (survey) or summed hours (targeted) | N visits |
| Quiescent counterpart, host | `depth="full"` | full survey |
| Periodic emission | `pulsar` products | track |

The visit times are an input. The survey plan fixes the number of epochs at a position (`observation.epochs_full`), not their dates; `dsa_view` warns if more survey visits are requested.

```python
def dsa_view(S, t_visit, ra, dec, mode="survey", hours=1.0, weighting="auto", nsig=5.0):
    """Per-visit view of a model transient. S(t_day, nu_MHz) -> uJy (vectorized in nu).

    mode="survey": each visit is one survey epoch; mode="targeted": each visit is a track of `hours`.
    """
    r = calc.calculate(mode, ra, dec, depth="single", hours=hours, weighting=weighting, products=("continuum",))
    for msg in r["warnings"]:
        print("warning:", msg)
    if mode == "survey" and len(t_visit) > r["observation"]["epochs_full"]:
        print("warning: %d visits requested, %d epochs planned here" % (len(t_visit), r["observation"]["epochs_full"]))
    c, fc = r["continuum"], r["continuum"]["fc"]
    win = [x for x in c["windows"] if 0 < x["thermal_uJy"] < np.inf]    # fully flagged windows carry no weight
    nu = np.array([x["f_center_MHz"] for x in win])
    sig_w = np.array([x["total_uJy"] for x in win])
    w = np.array(fc["window_weights"])                  # full-band image = sum(w * window)
    S_fc = np.array([w @ S(t, nu) for t in t_visit])
    rows = []
    for k, t in enumerate(t_visit):
        Sw = S(t, nu)
        J = np.vstack([Sw, Sw * np.log(nu / fc["nu_eff_MHz"])]).T / sig_w[:, None]
        sig_alpha = np.sqrt(np.linalg.pinv(J.T @ J)[1, 1])   # Fisher: power law, amplitude free
        sig_stack = np.hypot(fc["thermal_uJy"] / np.sqrt(k + 1), fc["confusion_uJy"])
        rows.append({"t_day": t, "S_uJy": S_fc[k], "snr": S_fc[k] / fc["total_uJy"],
                     "detected": S_fc[k] >= nsig * fc["total_uJy"], "sigma_alpha": sig_alpha,
                     "snr_stack": S_fc[:k + 1].mean() / sig_stack})
    per_visit = {"sigma_uJy": fc["total_uJy"], "thermal_uJy": fc["thermal_uJy"], "nu_eff_MHz": fc["nu_eff_MHz"],
                 "psf": fc["psf"], "weighting": r["weighting"]["imaging"] + ":" + r["weighting"]["summation"]}
    return rows, per_visit


def S(t, nu, S_pk=20.0, t_pk=30.0, alpha=-0.7):
    """Toy synchrotron transient (uJy): t^2 rise to t_pk (days), t^-1.5 decay, power-law spectrum."""
    f = (t / t_pk) ** 2 if t < t_pk else (t / t_pk) ** -1.5
    return S_pk * f * (nu / 1350.0) ** alpha


for mode, t_visit in (("survey", 10.0 + 60.0 * np.arange(7)),      # 7 epochs, 60 d apart (assumed)
                      ("targeted", 7.0 * np.arange(1, 13))):       # weekly 1-h tracks
    rows, v = dsa_view(S, t_visit, 150.12, 2.21, mode=mode, hours=1.0)
    print(mode, "sigma %.3f uJy at %.0f MHz, %s" % (v["sigma_uJy"], v["nu_eff_MHz"], v["weighting"]))
    for x in rows:
        print("  t %5.0f d  S %5.2f uJy  S/N %5.1f %s  sigma_alpha %4.2f  S/N(stack) %4.1f"
              % (x["t_day"], x["S_uJy"], x["snr"], "det" if x["detected"] else "   ", x["sigma_alpha"], x["snr_stack"]))
```

Model: 20 μJy peak at 1.35 GHz, day 30, α = −0.7, at COSMOS.

| | Survey, one epoch per visit, every 60 d (7 visits) | Targeted, 1 h per visit, weekly (12 visits) |
|---|---|---|
| σ per visit (full band, I) | 1.005 μJy at 1129 MHz (Robust, R = 0.4) | 0.738 μJy at 1338 MHz (Natural) |
| Visits with S ≥ 5σ | 1 (day 70, S/N 6.6) | 11 (days 14–84; peak S/N 25.0 on day 28) |
| σ_α at the best visit | 0.60 | 0.14 |
| Stacked S/N, all visits | 5.0 (7 epochs) | 28.3 (12 h) |

Reading the result: the survey samples this event once above 5σ and misses the peak; stacking recovers it at 5σ but only as a mean. Weekly 1-h tracks resolve the rise and decay and measure α to ±0.14–0.6 per visit.

Notes and assumptions:

- **Visit noise.** `depth="single"` is one survey epoch of the mosaic: all overlapping pointings at one epoch (mean mosaic weight Z(ν)). The calculator does not model when the overlapping pointings of an epoch are observed. `continuum.single_pointing` is one 21-min pointing at the primary-beam center (1.34 μJy at COSMOS), the best case for a single pointing; away from the center the noise rises as 1/B, with B the primary-beam response.
- **Flux in a visit.** S is evaluated at the visit mid-time; variability within a visit is averaged in the visit image.
- **Detection** uses the total (thermal + confusion) noise, as the calculator quotes it. Assumption (not modeled): if the confusing sources are constant, the flux difference of two equal visits has noise √2 σ_th; the calculator does not model image subtraction.
- **Stacking.** σ_N = √(σ_th²/N + σ_c²) reproduces `depth="custom", n_epochs=N` exactly (survey). For targeted visits it is approximate (12 × 1 h at COSMOS: 0.309 μJy, against 0.315 μJy for a 12-h request split over 3 transits); fix `weighting` so that every visit uses the same beam, since `weighting="auto"` chooses per observation.
- **σ_α** is a Fisher estimate (power law, amplitude marginalized, Gaussian window noise treated as independent, using the total window noise); it is not computed by the engine. Confusion is in fact common to all windows; in one epoch thermal noise dominates each window.
- **Targeted visits** must fit one transit window (|HA| ≤ 2 h, elevation ≥ 20°); longer requests are split over transits (`warnings`), and the visit noise then refers to the split track.
- **Inverse question.** To detect the event at its peak in one visit, require σ_visit ≤ S_fc,pk/5, with S_fc,pk the full-band flux density at the peak (Σ w_i S(ν_i), Section 3; it depends on the weighting through ν_eff), and solve for the track length with `hours_for(S_fc_pk / 5, ra, dec)` (Section 2).

## 8. FRBs: fluence limit, DM, localization, rates

**Q.** What is the fluence limit for a burst of width W and DM, where is it localized, and how many are expected?

```python
cf = DSACalculator(frb_dm=1000.0, frb_width_ms=5.0)
r = cf.calculate("survey", 180.0, 30.0, products=("frb",))
for b in r["frb"]["bands"]:
    print("%s: F_min %.3f Jy ms (beam peak %.3f), W_eff %.2f ms, losses x%.2f, loc %.2f\" x %.2f\", %.2g /yr"
          % (b["band"], b["fluence_min_Jyms"], b["fluence_peak_Jyms"], b["weff"]["weff_ms"], b["losses"]["total"],
             b["loc_ra_1sigma_arcsec"], b["loc_dec_1sigma_arcsec"], b["rate_per_yr"]))
print(r["frb"]["dm_budget"])
dm, F_B2 = r["frb"]["curves"]["dm"], r["frb"]["curves"]["B2"]        # fluence limit against DM
```

(180°, +30°), 10σ, defaults (DM 500, 1 ms): F_min = 0.105, 0.071, 0.061 Jy ms in B1, B2, B3; rates 3.9, 6.9, 5.3 × 10³ yr⁻¹. With DM 1000 and W = 5 ms: 0.184, 0.134, 0.115 Jy ms; z = 0.91 from the DM budget; 1σ localization 0.15″ × 0.12″ (B1) to 0.08″ × 0.06″ (B3).

- The headline limit includes quantization, beam straddle, primary-beam average, DM-trial, sidelobe-confusion and self-noise losses (`losses`); `fluence_peak_Jyms` is at a beam peak at the primary-beam center.
- W_eff combines intrinsic width, sampling, intra-channel smearing and scattering in the Milky Way (NE2025) and the host (`weff`).
- **Never add the band rates**: the bands observe overlapping sky. Quote each, or the highest. Rates are good to about a factor of two.
- The search beams cover 58–63% of the primary-beam FWHM area at δ = +15° to +50°, 75% at 0°, about 90% at the pole and 165% at −30° (`beam_coverage`); rates use the covered sky, weighted by the primary-beam response.

## 9. Pulsars: detectability, S_min(P), timing

**Q.** Is a given pulsar detected by the untargeted and targeted searches, and with what timing precision?

```python
cp = DSACalculator(psr_period_ms=3.0, psr_width_ms=0.3, psr_dm=150.0, psr_flux_mJy=0.05)
pu = cp.calculate("survey", 280.0, 0.0, products=("pulsar",))["pulsar"]
for x in pu["untargeted"]:
    print("untargeted %s: searched %s, S/N %.1f" % (x["band"], x["searched"], x["snr"]))
for x in pu["targeted"]:
    print("targeted %.2f MHz: S/N %.1f, S_min %.3g uJy, sigma_TOA %.3g us" % (x["center_MHz"], x["snr"], x["smin_uJy"], x["toa_us"]))
curves = pu["curves"]                         # period_s; smin_uJy per search (None = not searched)
```

3-ms pulsar, W = 0.3 ms, DM 150, 50 μJy at 1.4 GHz, at (280°, 0°) in a 1260-s survey track: untargeted search not run (periods 10 ms – 10 s only); targeted beams S/N 48 at 953.35 MHz and 35 at 1800 MHz, σ_TOA 10 and 9 μs; NE2025 distance 4.6 kpc.

- The untargeted search covers P = 10 ms – 10 s; the targeted search 1 ms – 10 s.
- `pulsar.curves` gives S_min against period at the input DM and duty cycle; a pulsar is detectable where its flux density exceeds the curve.
- At (180°, +30°), default pulsar, 1260 s: targeted S_min 3.7 μJy (953.35 MHz), untargeted B2 12 μJy at 1.4 GHz.
- Pulsar Timing subsystem (`products=("pta",)`, its own pulsar `pta_*`): default millisecond pulsar (1 mJy) σ_TOA = 35 ns in 1260 s at (180°, +30°).
- Track: 1260 s in survey mode (`td_track_s`), the on-source time in targeted mode.

## 10. Sky maps and sweeps

**Q.** How does the depth vary over the sky?

```python
ras, decs = np.arange(0, 360, 5.0), np.arange(-30, 90.1, 2.5)
noise = np.array([[calc.calculate("survey", a, d, products=("continuum",))["continuum"]["fc"]["total_uJy"]
                   for a in ras] for d in decs])
```

About 5 ms per position with `products=("continuum",)` (~0.1 s with all products): the 72 × 49 grid above takes about 20 s. Reuse one `DSACalculator`. For epochs alone, `calc.epochs_at(ra, dec)` returns the planned epochs and tile without computing noise.

## 11. Sensitivity to the assumptions

**Q.** How much do the defaults matter?

```python
cases = {"default": calc, "measured RFI": DSACalculator(rfi=rfi_measured()),
         "+24% loss": DSACalculator(extra_loss_percent=24), "T_sys 25 K": DSACalculator(tsys_zenith_K=25)}
for name, c in cases.items():
    r = c.calculate("survey", 150.12, 2.21, products=("continuum",))
    print("%-12s usable %.1f%%, total %.3f uJy" % (name, 100 * r["system"]["usable_band_fraction"], r["continuum"]["fc"]["total_uJy"]))
for v in ("A", "B", "C", "fig1"):
    r = calc.calculate("survey", 150.12, 2.21, products=("continuum",), variant=v)
    print("plan", v, r["observation"]["epochs_full"], "epochs, %.3f uJy" % r["continuum"]["fc"]["total_uJy"])
r = calc.calculate("targeted", 180.0, 30.0, hours=10, products=("continuum",))
for row in r["weighting"]["comparison"]:
    print("%s:%s total %.3f (thermal %.3f, confusion %.3f)" % (row["imaging"], row["summation"], row["total_uJy"], row["thermal_uJy"], row["confusion_uJy"]))
```

COSMOS, full depth, total noise: default 0.449 μJy (85.0% of the band usable); measured RFI 0.429 (97.2%); 24% extra loss 0.494 (64.6%); flat T_sys 25 K 0.497. Plans: A 7 epochs 0.449; B 8 epochs 0.429; C 5 epochs 0.505; reference plan 7 epochs 0.449. Targeted 10 h at (180°, +30°): Robust, R = 0.4 with optimal summation is lowest (0.250 μJy); Natural 0.263 μJy.

- `extra_loss_percent` is the simplest pessimistic case for unmeasured RFI.
- Survey tiles use the weighting planned for their final coadd; `weighting=` overrides it.
