"""Command-line interface:  dsa-etc --ra 150.12 --dec 2.21 [--mode targeted --hours 10] [--json]"""
import argparse
import json
import math
import sys

from .engine import DSACalculator, make_rfi_profile, rfi_measured, rfi_none, SCHEMES, SCHEME_LABEL, SUM_LABEL


def parse_angle(s, is_ra):
    s = str(s).strip().replace("−", "-")
    if any(c in s for c in ":hmsd") or len(s.split()) > 1:
        sign = -1.0 if s.startswith("-") else 1.0
        parts = [float(p) for p in "".join(ch if (ch.isdigit() or ch == ".") else " " for ch in s.lstrip("+-")).split()]
        v = parts[0] + (parts[1] if len(parts) > 1 else 0) / 60 + (parts[2] if len(parts) > 2 else 0) / 3600
        return sign * (v * 15 if is_ra else v)
    return float(s)


def load_rfi(arg):
    if arg in (None, "default", "extrapolated"):
        return None
    if arg == "measured":
        return rfi_measured()
    if arg == "none":
        return rfi_none()
    f, o = [], []
    with open(arg) as fh:
        for line in fh:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            p = line.replace(",", " ").replace(";", " ").split()
            try:
                f.append(float(p[0])); o.append(float(p[1]))
            except (ValueError, IndexError):
                continue
    return make_rfi_profile(f, o, "file: " + arg)


def _clean(o):
    """Replace inf/nan by None so the output is strict JSON (as JSON.stringify does on the web page)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _smin(d):
    return "%.3g uJy" % d["smin_uJy"] if d.get("searched", True) and math.isfinite(d["smin_uJy"]) else "not searched"


def _s1400(d):
    return "%.3g uJy" % d["s1400_min_uJy"] if d.get("searched", True) and math.isfinite(d["s1400_min_uJy"]) else "-"


def summary(r):
    o, lines = r["observation"], []
    lines.append("DSA %s at RA %.4f  Dec %+.4f" % ("survey products" if o["mode"] == "survey" else "targeted observation",
                                                    o["ra"], o["dec"]))
    for w in r.get("warnings", []):
        lines.append("  ! " + w)
    if "system" not in r:
        return "\n".join(lines)
    s = r["system"]
    if o["mode"] == "survey":
        lines.append("  tile %s (%s), %d of %d epochs; beam-weighted %.2f epochs at 1.35 GHz"
                     % (o["tile"]["tile"], o["tile"]["class"], o["n_epochs"], o["epochs_full"], o["effective_epochs_1350"]))
    else:
        lines.append("  %.2f h in %d transit(s), |HA| <= %.2f h" % (o["hours"], o["n_transits"], o["ha_half_h"]))
    lines.append("  Tsys(full band) %.1f K (zenith %.1f, spillover %+.1f, atmosphere %+.1f, Galactic %+.1f)  "
                 "SEFD %.0f Jy  usable band %.1f%%"
                 % (s["tsys_band_K"], s["tsys_band_zenith_K"], s["spill_band_K"], s["atm_band_K"],
                    s["galactic_band_K"], s["sefd_band_Jy"], 100 * s["usable_band_fraction"]))
    w = r["weighting"]
    lines.append("  weighting: %s · %s" % (SCHEME_LABEL[w["imaging"]], SUM_LABEL[w["summation"]]))
    if "continuum" in r:
        fc = r["continuum"]["fc"]
        lines.append("  Continuum full band: total %.3f uJy/beam (thermal %.3f, confusion %.3f) at %.0f MHz, beam %.2f\" x %.2f\", "
                     "Tb(1sig) %.1f mK" % (fc["total_uJy"], fc["thermal_uJy"], fc["confusion_uJy"], fc["nu_eff_MHz"],
                                           fc["psf"]["bmaj"], fc["psf"]["bmin"], fc["tb_thermal_mK"]))
        if "smoothed" in r["continuum"]:
            sm = r["continuum"]["smoothed"]
            sx = sm["subtraction"]
            how = ("after subtracting sources > %.2f uJy; %.3g uJy without" % (sx["limit_uJy"], sx["unsubtracted_confusion_uJy"])
                   if sx["applied"] else "no subtraction; %.3g uJy with" % sx["residual_confusion_uJy"])
            lines.append("    smoothed to %g\": thermal %.3f uJy/beam, confusion %.3g (%s); Tb thermal %.3f mK, total %.3f mK"
                         % (sm["target_arcsec"], sm["thermal_uJy"], sm["confusion_uJy"], how, sm["tb_thermal_mK"],
                            sm["tb_total_mK"]))
    if "line" in r:
        for k in ("ZB", "ZA", "NL"):
            c = r["line"][k]["channels"][0]
            lines.append("  HI %s: %.3f mJy/beam per %.2f km/s channel, Tb %.2f K, 5sig NHI(20 km/s) %.2e cm^-2"
                         % (k, c["sigma_mJy"], c["dv_kms"], c["tb_K"], c["nhi_5sigma_cm2"]))
    if "polarization" in r:
        p = r["polarization"]
        lines.append("  Polarization: band Q/U %.3f uJy/beam; RMSF %.1f rad/m2; max scale %.0f; max |RM| %.0f"
                     % (p["band_qu_sigma_uJy"], p["rmsf_fwhm_rad_m2"], p["max_scale_rad_m2"], p["max_rm_rad_m2"]))
    if "time_domain" in r:
        t = r["time_domain"]
        sv = t["survey"]
        lines.append("  Time domain: %.0f s track at l %.2f b %+.2f; tau_c %s; scattering %s; tile %s (%s, %d epochs)"
                     % (t["track_s"], t["l_deg"], t["b_deg"],
                        "%.1f s" % t["tau_c_s"] if t["tau_c_s"] is not None else "n/a", t["scattering"],
                        sv["tile"], sv["class"], sv["epochs"]))
    if "pulsar" in r:
        pu = r["pulsar"]
        i, pr = pu["inputs"], pu["propagation"]
        lines.append("  Pulsar P %g ms, W %g ms, DM %.4g, %g mJy at %g MHz (alpha %g): D %s, tau(1 GHz) %.3g ms, "
                     "DM_max %.0f" % (i["period_ms"], i["width_ms"], i["dm"], i["flux_mJy"], i["nu_ref_MHz"], i["alpha"],
                                      "%.2f kpc" % pr["dist_kpc"] if pr["dist_kpc"] is not None else "n/a",
                                      pr["tau_1GHz_ms"], pr["dm_max"]))
        for x in pu["untargeted"]:
            lines.append("    untargeted %s: S/N %.1f, Smin %s (s1400 %s), beam %.2f\", taper x%.2f, confusion x%.3f, "
                         "%.2f deg2" % (x["band"], x["snr"], _smin(x), _s1400(x), x["beam_arcsec"], x["losses"]["taper"],
                                        x["losses"]["confusion"], x["area_deg2"]))
        for x in pu["targeted"]:
            lines.append("    targeted %.2f MHz%s: S/N %.1f, Smin %s, sigma_TOA %.3g us"
                         % (x["center_MHz"], " (selected)" if x["selected"] else "", x["snr"], _smin(x), x["toa_us"]))
    if "frb" in r:
        f = r["frb"]
        bd = f["dm_budget"]
        lines.append("  FRB DM %g: DM_MW %.0f + halo %.0f + cosmic %.0f (z %.3f) + host %.0f/(1+z)"
                     % (bd["dm_obs"], bd["dm_mw"], bd["dm_halo"], bd["dm_cosmic"], bd["z"], bd["dm_host"]))
        for b in f["bands"]:
            lines.append("    %s: %g-sigma fluence %.3f Jy ms (%.3f at beam peak), W_eff %.2f ms, losses x%.2f, "
                         "%.3g /yr (%.2g in the track)" % (b["band"], f["inputs"]["snr"], b["fluence_min_Jyms"],
                                                           b["fluence_peak_Jyms"], b["weff"]["weff_ms"],
                                                           b["losses"]["total"], b["rate_per_yr"], b["rate_in_track"]))
    if "pta" in r:
        pt, i = r["pta"], r["pta"]["inputs"]
        lines.append("  Pulsar timing (PTA, 4 beams, 700-2000 MHz): P %g ms, W %g ms, DM %g, %g mJy at %g MHz: S/N %.1f, "
                     "sigma_TOA %.3g us, %g-sigma Smin(1400) %.3g uJy"
                     % (i["period_ms"], i["width_ms"], i["dm"], i["flux_mJy"], i["nu_ref_MHz"], pt["snr"], pt["toa_us"],
                        i["snr"], pt["s1400_min_uJy"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="DSA sensitivity and exposure-time calculator")
    ap.add_argument("--mode", choices=["survey", "targeted"], default="survey")
    ap.add_argument("--ra", default="170", help="degrees, or hours as hh:mm:ss (default 170)")
    ap.add_argument("--dec", default="39.57", help="degrees, or dd:mm:ss (default +39.57, which transits at the zenith)")
    ap.add_argument("--depth", choices=["full", "single", "custom"], default="full")
    ap.add_argument("--epochs", type=int, default=None, help="number of epochs for --depth custom")
    ap.add_argument("--hours", type=float, default=1.0, help="on-source time for --mode targeted")
    ap.add_argument("--weighting", default="auto", help="auto or imaging:summation, e.g. natural:optimal")
    ap.add_argument("--smooth", type=float, default=0.0, help="smooth images to this resolution (arcsec)")
    ap.add_argument("--no-subtract", action="store_true",
                    help="smoothed continuum: do not subtract the sources detected at full resolution first")
    ap.add_argument("--products", default="continuum,line,polarization,frb,pulsar,pta")
    ap.add_argument("--tsys", type=float, default=None, help="flat zenith T_sys in K (default: the measured bandpass)")
    ap.add_argument("--hi-widths", default=None, help="HI line widths for the mass limits, km/s (default 50,200,500)")
    td = ap.add_argument_group("time domain (pulsar and FRB products; a track centered on transit)")
    td.add_argument("--track-s", type=float, help="track length in seconds (default 1260)")
    td.add_argument("--psr-period-ms", type=float, help="pulsar period (default 500)")
    td.add_argument("--psr-width-ms", type=float, help="pulsar intrinsic FWHM (default 15)")
    td.add_argument("--psr-dm", type=float, help="pulsar DM (default: half the NE2025 Galactic DM)")
    td.add_argument("--psr-flux-mJy", type=float, help="pulsar flux density at --psr-nu-ref (default 0.02)")
    td.add_argument("--psr-nu-ref", type=float, help="reference frequency of the flux density, MHz (default 1400)")
    td.add_argument("--psr-alpha", type=float, help="pulsar spectral index (default -1.6)")
    td.add_argument("--targeted-center-MHz", type=float, help="targeted-beam band center (presets 953.35, 1800)")
    td.add_argument("--untargeted-beam-arcsec", help="untargeted beam FWHM per band, B1,B2,B3 (default 13.5\" x 930 MHz/nu)")
    td.add_argument("--pta-period-ms", type=float, help="PTA pulsar period (default 4)")
    td.add_argument("--pta-width-ms", type=float, help="PTA pulsar intrinsic FWHM (default 0.2)")
    td.add_argument("--pta-dm", type=float, help="PTA pulsar DM (default 20)")
    td.add_argument("--pta-flux-mJy", type=float, help="PTA pulsar flux density at --pta-nu-ref (default 1)")
    td.add_argument("--pta-nu-ref", type=float, help="reference frequency of the PTA flux density, MHz (default 1400)")
    td.add_argument("--pta-alpha", type=float, help="PTA pulsar spectral index (default -1.6)")
    td.add_argument("--scattering", choices=["ne2025", "cordes22"], help="scattering model (default ne2025)")
    td.add_argument("--frb-dm", type=float, help="FRB DM (default 500)")
    td.add_argument("--frb-width-ms", type=float, help="FRB intrinsic width (default 1)")
    td.add_argument("--frb-max-dm", type=float, help="maximum searched DM (default 5000)")
    ap.add_argument("--rfi", default="default",
                    help="default (Spring Valley model extrapolated, 15%% loss) | measured (Spring Valley measured) | "
                         "none | path to a CSV of MHz, occupancy")
    ap.add_argument("--variant", default=None, help="survey plan: A (default), B, C or fig1")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override an engine parameter, e.g. --set tsys_zenith_K=25 --set galactic_noise=false")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    argv = list(sys.argv[1:] if argv is None else argv)
    for i in range(len(argv) - 1):                      # let "--dec -28:56:10" through argparse
        if argv[i] in ("--ra", "--dec") and argv[i + 1][:1] in ("-", "\u2212"):
            argv[i], argv[i + 1] = argv[i] + "=" + argv[i + 1], ""
    a = ap.parse_args([t for t in argv if t != ""])
    params = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        params[k] = {"true": True, "false": False}.get(v.lower(), None)
        if params[k] is None:
            try:
                params[k] = json.loads(v)
            except ValueError:
                params[k] = v
    if a.weighting != "auto" and tuple(a.weighting.split(":")) not in SCHEMES:
        ap.error("weighting must be auto or one of " + ", ".join(":".join(s) for s in SCHEMES))
    if a.no_subtract:
        params["smooth_subtract_sources"] = False
    for opt, key in (("track_s", "td_track_s"), ("psr_period_ms", "psr_period_ms"), ("psr_width_ms", "psr_width_ms"),
                     ("psr_dm", "psr_dm"), ("psr_flux_mJy", "psr_flux_mJy"), ("psr_nu_ref", "psr_nu_ref_MHz"),
                     ("psr_alpha", "psr_alpha"), ("targeted_center_MHz", "psr_targeted_center_MHz"),
                     ("scattering", "td_scattering"), ("frb_dm", "frb_dm"), ("frb_width_ms", "frb_width_ms"),
                     ("frb_max_dm", "frb_max_dm"),
                     ("pta_period_ms", "pta_period_ms"), ("pta_width_ms", "pta_width_ms"), ("pta_dm", "pta_dm"),
                     ("pta_flux_mJy", "pta_flux_mJy"), ("pta_nu_ref", "pta_nu_ref_MHz"), ("pta_alpha", "pta_alpha")):
        if getattr(a, opt) is not None:
            params[key] = getattr(a, opt)
    if a.untargeted_beam_arcsec:
        params["psr_untargeted_beam_arcsec"] = [float(x) for x in a.untargeted_beam_arcsec.split(",")]
        if len(params["psr_untargeted_beam_arcsec"]) != 3:
            ap.error("--untargeted-beam-arcsec needs three values, B1,B2,B3")
    if a.tsys is not None:
        params["tsys_zenith_K"] = a.tsys
    if a.hi_widths:
        params["hi_widths_kms"] = [float(x) for x in a.hi_widths.split(",")]
    calc = DSACalculator(rfi=load_rfi(a.rfi), **params)
    r = calc.calculate(mode=a.mode, ra=parse_angle(a.ra, True) % 360.0, dec=parse_angle(a.dec, False), depth=a.depth,
                       n_epochs=a.epochs, hours=a.hours, products=tuple(a.products.split(",")), weighting=a.weighting,
                       smooth_arcsec=a.smooth, variant=a.variant)
    if a.json:
        json.dump(_clean(r), sys.stdout, indent=1, allow_nan=False)
        print()
    else:
        print(summary(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
