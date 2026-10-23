# DSA Sensitivity Calculator: notes for Claude

This repository holds the sensitivity and exposure-time calculator of the Deep Synoptic Array (DSA): a static web page and a Python package that implement the same noise model. `docs/model.md` describes the model.

## Answering questions with it

Run the Python engine rather than estimating by hand:

```bash
cd python && python3 -m dsa_etc.cli --ra 150.12 --dec 2.21            # survey position
python3 -m dsa_etc.cli --mode targeted --ra 150.12 --dec 2.21 --hours 10 --json
```

`skill/dsa-sensitivity/SKILL.md` explains the options, where each answer sits in the output, and recipes (time needed to reach a noise level, HI mass limits, smoothing).

## Changing the model

- `python/dsa_etc/engine.py` is the reference. `web/js/dsa-engine.js` is a line-by-line port. Change both together, keeping names and order of operations the same.
- After any change, run:

  ```bash
  python3 -m pytest tests/test_engine.py tests/test_chr.py          # model checks
  python3 tests/make_reference.py && node tests/parity.test.js      # JS must match Python to 2e-5
  python3 tools/build_web.py && python3 tools/build_skill.py        # rebuild dist/
  ```
- Model data lives only in `python/dsa_etc/data/`; `tools/build_web.py` copies it to `web/data/`. Never edit `web/data/` or `dist/` by hand.
- Time-domain (Chronoscope) tables, each rebuilt by its script: `chr_taper.json` (`tools/build_chr_taper.py`, ~15 min on 8 cores), `psf_uniform.json` (`tools/build_psf_uniform.py`, uniformly weighted localization PSF), `ne2025_grid.json` (`tools/build_ne2025_grid.py`; needs `mwprop`, `mpmath`, `astropy`, which the engine itself never imports). The T_sys bandpass `tsys_bandpass.json` (`tools/build_tsys.py`, from the PI's T_sys measurement in `tools/inputs/`), its zenith-angle increase `tsys_za.json` (`tools/build_tsys_za.py`, spillover simulation in `tools/inputs/` plus the ITU-R atmosphere; needs `itur`) and the RFI profile apply to every product. The 4-bit correlator efficiency (`correlator_efficiency` = 0.988) applies to the imaging products; quantization (`td_eta_*`), sidelobe confusion and scattering apply to the Chronoscope pulsar and FRB products. The Pulsar Timing subsystem has no quantization loss (`pt_eta` = 1); confusion and scattering apply to it as well.
- The 200,000-beam pulsar search is the "untargeted" search everywhere (code, keys, UI, docs); never use the older name for it. `tests/test_chr.py` checks the vocabulary.
- Output keys carry their units (`sigma_uJy`, `t_eff_s`, `psf` in arcsec). Keep that convention.
- Spelling is American throughout.
- Rounding must match between the engines: use `floor(x + 0.5)`, not Python's `round`, wherever an index is computed.
- The survey plan (`allocation.json`) is produced by `tools/allocation.py`; re-run it after changes that affect survey noise, then rebuild the reference outputs.

## Page

- `web/index.html`, `web/css/app.css` (color tokens for light and dark themes) and `web/js/app.js` (UI: inputs, sky map, SVG charts, result cards).
- `tools/build_web.py` inlines CSS and JS into `dist/site/index.html` for the DSA website, and writes `dist/artifact/` for the hosted preview.
- Charts are hand-written SVG. Colors come from CSS tokens; series colors are fixed (blue, orange, green) and epochs use a single blue ramp.
