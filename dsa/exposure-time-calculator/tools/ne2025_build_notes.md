# NE2025 grid build notes (2026-10-06)

Output: `python/dsa_etc/data/ne2025_grid.json` (1,255,123 bytes). Builder: `tools/build_ne2025_grid.py`
(`check` / `build` / `reference`). Fast path: `tools/ne2025_fast.py`. mwprop 2.0.5, NE2025 parameter set.

## Method
- One integration per sightline to mwprop's limit (`dmax_ne2001p_integrate` = 50 kpc) on mwprop's own
  grids (0.1 kpc coarse spline for the smooth disk and arm components, 0.0025 kpc fine sampling for the GC, LISM,
  clump and void components). The cumulative DM(s) and the dSM moments ∫dsm, ∫s dsm and ∫s² dsm give every DM→(D, tau),
  DM_max and tau_X from the same pass. The SM weightings, splines and scattering formulas are copied
  from `dmdsm_dm2d` / `ne2025`, and the density components are mwprop's own functions.
- Speed-ups: (1) a single pass instead of up to 3 passes per query, which removes 16x repeat work; (2) `nevoidN` vectorised
  over samples. The result is bit-identical to mwprop's loop at 20,000 test points (`check_voids`). (3) The arm r(θ) spline is
  built once rather than once per sample, also bit-identical. numba and f2py were not needed.
- Timing (h23): a direct `ne2025()` call takes 1 s (low DM) to 13 s (DM above DM_max, which integrates to 50 kpc in 3 passes). One full
  sightline on the fast path takes 0.9 s, including all 16 DMs, DM_max and tau_X.
  The full build of 13,824 sightlines took 1143 s (inner) + 244 s (outer) = 23 min on 12 processes.
- DM_max is the DM at 50 kpc. The model-edge distance is mwprop's lower-limit distance: the first sample where the
  cumulative DM reaches its final value. For DM > DM_max, dist and tau are clamped to their model-edge values, which is what
  mwprop returns for any DM above DM_max that makes it integrate to 50 kpc.
- tau_X is mwprop `TAU_X` (`taux_from_thetax`, plane-wave theta_X with D_eff = ∫s dsm / ∫dsm). tau and tau_X are in
  ms at 1 GHz (`rf_ref` = 1). Scale as nu^-4.4.

## Validation against unmodified mwprop (100 random points, Dec > -35°)
- 90 points with DM below DM_max: 89 agree to max 0.34% in D and 0.93% in tau (medians 0.03% and 0.12%).
- 10 points with DM ≥ 2000, above DM_max: bit-identical.
- 1 outlier, (358.005, 9.814, DM 157): mwprop D = 13.8 kpc vs 8.33 kpc here. This is a mwprop artifact.
  `dmdsm_dm2d` picks the relevant clumps only once, at the pass-0 distance (here 7.3 kpc), so clump 60 at 8.4 kpc is dropped
  when a later pass integrates past it. At DM = 200 mwprop includes the clump and agrees here to 0.2%. A first test run
  turned up the same effect at (78.4, -2.1, DM 17.4) with a clump at 1.35 kpc. The grid uses the self-consistent model, with all
  clumps included.
- When mwprop saturates on a short integration (DM above DM_max, but pass 0 stops before 50 kpc), its lower-limit
  distance depends on how far it integrated. The grid always uses the 50 kpc value.

## Layout and encoding
- inner: l 0..359 step 1, b -15..15 step 1. outer: l 0..355 step 5, b -90..90 step 5. All sightlines are computed, with no
  declination skip.
- dm_grid = geomspace(10, 5000, 16). Encoding follows the spec. Floors: tau and tau_X 1e-12 ms, which is never reached (min tau
  1.7e-8 ms); dist and DM_max 1e-3. The largest |delta| is 8063, well inside int16. The round trip was checked
  (quantisation is ≤ 0.12%).

## Interpolation accuracy (`tests/data/ne2025_reference.json`, 50 points, 32 with |b| ≤ 15, 4 saturated)
| quantity | median | max | n > 20% |
|---|---|---|---|
| tau (trilinear) | 2.3% | 77% | 3 |
| D (trilinear) | 1.1% | 82% | 4 |
| DM_max (nearest) | 2.1% | 7.3% | 0 |
| tau_X (nearest) | 8.0% | 41% | 8 |

- tau outliers are all in the plane: (68.8, -0.46) is off by x0.23, and two more points are about 22%. Model clumps (rc ~ 0.05 kpc,
  F_c up to 4500) and voids are smaller than the 1° cells.
- D outliers come from DM close to DM_max, where D(DM) is nearly vertical: (99.9, 56.5) at DM 26.6 with DM_max 30 is off by x1.8.
- Refinement was NOT done. A 0.5° inner grid would be about 3.8 MB and a 2.5° outer grid about 2.0 MB total, both over the 1.5 MB cap.
- Bilinear (log) interpolation of tau_X and DM_max instead of nearest would bring tau_X to median 0.5%, max 19.5%, 0 points
  over 20%, and DM_max to median 0.1%, max 2.4%. This is recommended for the engine.

## Sanity values (tau_X at 1 GHz)
- l=40: b=10 5.96e-3 ms, b=30 4.5e-4, b=60 9.6e-5, b=90 6.4e-5. l=180: b=10 5.5e-2, b=30 3.0e-4, b=60 1.0e-4.
- DM_max: (40, 0) 1002.7. North pole 21.7, south pole 26.3.
- Clump spikes are real mwprop output on the exact sightline: (358, 10) tau_X 4.3e6 ms and (356, -2) 1.8e7 ms, against neighbours
  at about 0.04 ms and 18 ms. Through interpolation they affect about 1° around them.

## Environment note
`dsa-etc` came with astropy 6.1.7, which fails to import under numpy 2.4 (`np.in1d`). It was upgraded to astropy 8.0.1.
