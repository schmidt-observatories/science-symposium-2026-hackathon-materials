# Methods

<p class="doc-meta">DSA Sensitivity Calculator, version 3.1 (October 2026)</p>

This document describes how the DSA Sensitivity Calculator computes noise, resolution and detection limits for the data products of the Deep Synoptic Array (DSA). Two implementations of the model exist, a Python package and a JavaScript engine for the web page; they apply identical equations and agree to a relative precision of 2 × 10⁻⁵.

The instrument parameters assume the DSA project baseline at the Final Design Review (Hallinan et al. 2026).

Conventions: frequencies are in MHz and angles in degrees unless stated otherwise; flux densities are per beam; all noise values are 1σ; beam sizes are full widths at half maximum (FWHM).

## 1. Instrument

### 1.1 Array

The DSA consists of N = 1650 antennas of diameter D = 6.155 m (geometric area A = πD²/4 = 29.75 m²) at Spring Valley, Nevada (latitude φ = +39.554°), observing from 0.70 to 2.00 GHz in two linear polarizations. The antenna configuration provides 1,360,425 baselines from 10.2 m to 20.3 km. The primary beam is modeled as a Gaussian of FWHM θ_P = 3.36°/ν_GHz.

### 1.2 Data products

| Product | Backend | Description |
|---|---|---|
| Continuum | Radio Camera | ten 130.2-MHz windows (Stokes I, V), the full-band image, and 6-s snapshot images |
| HI | Radio Camera | three cubes: Zoom B, Zoom A and Narrow Line (Section 7.2) |
| Polarization | Radio Camera | 500 × 2.604-MHz full-Stokes cubes |
| FRB search | Chronoscope | three bands, visibility beams on a hexagonal grid at the center of the primary beam (Section 13) |
| Pulsar search | Chronoscope | untargeted (tapered visibility beams) and targeted (voltage beams) searches (Section 12) |
| Pulsar timing | Chronoscope; Pulsar Timing subsystem | targeted voltage beams; four full-band coherently dedispersed beams |

Sections 2–7 describe the imaging products and Sections 8–13 the time-domain (Chronoscope) products. All products use the system temperature, aperture efficiency and RFI profile of Sections 2 and 3, and the quantization efficiencies of Section 8.4.

## 2. System temperature and SEFD

### 2.1 System equivalent flux density

The system temperature at zenith on cold sky, T_sys(ν), is the measured bandpass (700–2000 MHz in 2-MHz steps, August 2025, 30 °C) with interference removed: points raised by RFI, identified with the Spring Valley occupancy, are replaced by interpolation (`tools/build_tsys.py`). Its median is 21.4 K. The aperture efficiency is η = 0.67. The system equivalent flux density (SEFD) of one antenna is

    SEFD = 2k (T_sys + ΔT_spill(ν, ZA) + ΔT_atm(ν, ZA) + T_gal) / (ηA)

which is 2817 Jy at zenith on cold sky at 1.35 GHz. Over a window, T_sys is averaged with the weights of the unflagged channels.

### 2.2 Spillover and atmosphere

The measured T_sys includes the ground spillover and the atmosphere at zenith. Both rise with zenith angle (ZA), and the calculator adds their increase over zenith, each a function of frequency and ZA (`tools/build_tsys_za.py`):

- Spillover: the simulated spillover temperature of the 6.15-m dish with the v3 feed (Jonas 2026), smoothed in frequency to remove a point-to-point ripple.
- Atmosphere: oxygen and water-vapor emission (ITU-R P.676) through the mid-latitude reference atmospheres (ITU-R P.835), with the median water vapor at the site (8.4 mm; ITU-R P.836), above 1746 m. It is 1.2–1.4 K at zenith across the band, almost all from oxygen, and grows roughly as sec ZA.

Averaged over the band, the increase is +2.5 K at ZA 40° (declination 0° at transit) and +7.3 K at ZA 70° (declination −30°). Together the two terms reproduce the earlier tabulation of total T_sys/η against zenith angle to 0.2 K up to ZA 75°.

### 2.3 Galactic synchrotron emission

Sky brightness is taken from the Global Sky Model (GSM2008; de Oliveira-Costa et al. 2008), without the cosmic microwave background. Planes at 700, 1000, 1400 and 2000 MHz on a 1° equatorial grid are each smoothed with the primary beam at their frequency and interpolated logarithmically in frequency and bilinearly in position. Because the measured T_sys already includes a typical cold sky, the calculator adds only the excess over a cold-sky reference, defined as the median brightness at |b| > 30°. Toward the Galactic Center the excess is about 100 K at 0.7 GHz and 25 K at 1.35 GHz; cold fields lie slightly below the reference.

## 3. Usable bandwidth

The usable bandwidth over a frequency range is

    Δν_usable = ∫ (1 − p(ν)) dν × (1 − f_extra)

where p(ν) is the RFI occupancy, treated as the fraction of data lost, and f_extra an optional additional loss. Three occupancy profiles are provided on a 0.8-MHz grid, and users can supply their own.

| Profile | Band-averaged loss | Description |
|---|---|---|
| Spring Valley model extrapolated (default) | 15.0% | the measured pattern scaled to DSA sensitivity |
| Spring Valley measured | 2.8% | occupancy from a site interference survey |
| None | 0 | no flagging |

The DSA is far more sensitive than the site survey and will detect weaker and more distant transmitters in the same bands. The default profile therefore treats each channel as having k times as many independent transmitters above the flagging threshold as the survey recorded, so its clean fraction becomes (1 − p)^k. Quiet channels then have occupancy ≈ k p, while busy channels saturate at 100%. A value k = 24.4 gives a band-averaged loss of 15%. Channels clean in the survey, including the 1400–1427 MHz HI band, remain clean; the loss concentrates at 1150–1300 MHz and 1540–1630 MHz (navigation satellites, aviation and radar).

## 4. Thermal noise

### 4.1 Radiometer equation

For an image formed from the cross-correlations,

    σ = SEFD / (η_v4 √(N(N−1) n_pol Δν_usable t_eff))

with n_pol = 2 and η_v4 = 0.988, the efficiency of correlating 4-bit voltages (Section 8.4), which applies to every imaging product. For a beam formed from the voltages of all antennas, N(N−1) is replaced by N², with the quantization efficiency of that beam (Section 8.4). For example, SEFD = 3318 Jy, Δν = 845 MHz and t = 10 min give σ = 2.00 μJy without the quantization loss, as in the Survey Implementation Plan (SIP; Myers et al. 2026), and 2.02 μJy with it.

### 4.2 Survey mosaics

The survey observes 21-minute pointings on the hexagonal grid of the SIP with spacings θ_hex = 1.667° along a row and θ_row = 1.45° between rows, so that each pointing represents A_hex = 2.417 deg². A linear mosaic weights each pointing by the square of the primary beam, B². The effective integration time at a position is

    t_eff(ν) = 21 min × Z(ν) × N_eff(ν)

- Z(ν), the mean mosaic weight, is ∫B² dΩ / A_hex, with the Gaussian primary beam truncated where B = 0.1 (radius 0.911 θ_P): ∫B² dΩ = π θ_P² / (8 ln 2) × (1 − 0.1²) = 0.5665 θ_P² × 0.990. Z is 5.35 at 0.7 GHz, 1.44 at 1.35 GHz and 0.65 at 2.0 GHz. Across the hexagonal pattern it varies by 2% at 0.7 GHz, 6% at 1.35 GHz and a factor of two at 2.0 GHz (0.48 to 1.00); the mean is used.
- N_eff(ν), the beam-weighted number of epochs, averages the planned epochs of the survey tiles under the squared primary beam, sampled on a 21 × 21 grid to 3.3σ at eight frequencies. The depth therefore varies smoothly across tile boundaries, falls to about half at the southern edge of the survey (δ = −30.45°), and is well defined at the pole. For example, RA 0°, Dec 0° lies on the boundary between a 7-epoch and a 3-epoch tile and has N_eff = 5.3 at 1.35 GHz.

The system temperature of survey products is evaluated at transit.

### 4.3 Targeted observations

A targeted observation is a single pointing, with noise quoted at the primary-beam center. Tracks are centered on transit and limited to |HA| ≤ 2 h and elevation ≥ 20°. A request longer than one transit window is divided evenly over several transits; near the southern limit the window shrinks (at δ = −30° the elevation limit allows ±0.57 h). Along a track the SEFD is combined as SEFD_eff = ⟨SEFD⁻²⟩^(−1/2) over up to 17 hour-angle samples.

## 5. Resolution and weighting

### 5.1 Natural weighting

The natural-weighted snapshot point-spread function (PSF) at zenith and 1.35 GHz, from a fit to the half-power contour of the configuration's PSF, is 3.03″ (east–west) × 2.31″ (north–south), position angle 90.6°. It scales as 1/ν, and away from zenith the north–south axis grows as 1/cos ZA. For a track, the inverse covariances of the projected snapshot PSFs are averaged:

    K = Σ_h w_h M_h K₀ M_hᵀ / Σ_h w_h,
    M_h = [[cos h, −sin φ sin h], [sin δ sin h, sin φ sin δ cos h + cos φ cos δ]]

with weights w_h = SEFD⁻². This agrees with a Fourier transform of the full uv coverage to about 1%.

### 5.2 Robust weighting

Two robust-weighting schemes scale the beam size and the noise relative to natural weighting. The factors are from Rosero (2026, Fig. 19), computed from imaging simulations at seven frequencies and four declinations (+30°, −20°, −30° and −40°):

- Robust, R = 0.46–1.94: the robust parameter rises with frequency, R = 0.46, 0.71, 0.95, 1.20, 1.45, 1.69 and 1.94 at 0.75, 0.95, 1.15, 1.35, 1.55, 1.75 and 1.95 GHz;
- Robust, R = 0.4: R = 0.4 at all frequencies.

The factors are interpolated linearly in frequency and declination and held constant beyond the tabulated ranges; north of +30° the +30° values apply.

### 5.3 Full-band image

The full-band continuum image combines the ten windows with weights w_i, either optimal summation (w_i = 1/σ_i²) or equal summation (w_i = 1):

    σ_FC = √(Σ w_i² σ_i²) / Σ w_i,    ν_eff = Σ w_i ν_i / Σ w_i,    K_FC = Σ w_i K_i / Σ w_i

where K_i is the inverse covariance of the beam of window i. Optimal summation in a mosaic favors the low-frequency windows, which have the largest mosaic weight, so the full-band beam is larger than the 1.35-GHz beam; equal summation keeps it close to monochromatic.

## 6. Confusion

### 6.1 Confusion noise

The confusion noise of Stokes I continuum images follows Condon's Universal Confusion Calculator, as tabulated by Rosero (2026), with the β_min criterion of Mauch et al. (2020):

    σ_c = f_β(θ) θ² (ν / 1.4 GHz)^−0.7 μJy beam⁻¹,    θ = √(b_maj b_min)

where f_β(θ) is the confusion curve for β_min = 16 beam areas per source (β_min = 25 is also available), computed from the 1.4-GHz source counts of Matthews et al. (2021). The total noise is √(σ² + σ_c²). Continuum-subtracted HI cubes and Stokes Q, U and V images are taken to be thermal-noise limited.

### 6.2 Choice of weighting

For each position the calculator evaluates the six combinations of imaging weighting (Natural; Robust, R = 0.46–1.94; Robust, R = 0.4) and window summation (optimal or equal). In survey mode each tile uses the combination that minimizes the total noise of its final full-depth image, and single-epoch results use the same choice. In targeted mode the combination with the lowest total noise for the requested observation is used unless the user selects one.

## 7. Imaging products

### 7.1 Continuum

The continuum products are the ten 130.2-MHz windows (700–2002 MHz) and the full-band image, each with thermal, confusion and total noise, PSF and brightness temperature. Survey mode also gives the noise of a single 21-minute pointing at the beam center. Snapshot images of 6 s (Stokes I and V) are made in four 325.5-MHz sub-bands and the full band, at the beam center.

### 7.2 HI

| Cube | Channels | Channel width | Velocity width at 1420 MHz | Coverage |
|---|---|---|---|---|
| Zoom B (Galactic HI) | 960 | 1.017 kHz | 0.215 km s⁻¹ | −106 to +100 km s⁻¹ |
| Zoom A (HI to ~100 Mpc) | 4192 | 8.138 kHz | 1.718 km s⁻¹ | −358 to +6840 km s⁻¹ |
| Narrow Line (HI to z ≈ 1) | 5600 | 130.2 kHz | 27.5 km s⁻¹ | 700–1429 MHz, z ≤ 1.03 |

The noise per channel uses the channel's RFI occupancy, natural weighting and the mosaic or track time at that frequency. Narrow Line results are given at z = 0, 0.1, 0.25, 0.5, 0.75 and 1.0. Doppler tracking is assumed to be ideal: every epoch is taken to contribute to the same channel in a common velocity frame, with no loss or correlation between channels from regridding.

- Column density (5σ, optically thin, over Δv_line = 20 km s⁻¹): N_HI = 1.8224 × 10¹⁸ × 5 T_b,σ (1+z) √n Δv cm⁻², with n = Δv_line/Δv channels (at least one); the factor (1+z) converts observed to rest-frame brightness temperature.
- HI mass (5σ, unresolved source, boxcar line of width W): M_HI = 49.7 D_L² S_int (M_☉, Mpc, Jy Hz; Meyer et al. 2017), with S_int = 5 σ_ch √n Δν_ch. Zoom A uses D = 10, 50 and 100 Mpc; Narrow Line uses the luminosity distance of each redshift for a flat ΛCDM cosmology (H₀ = 67.66 km s⁻¹ Mpc⁻¹, Ω_m = 0.3097; Planck Collaboration 2020). Line widths are 50, 200 and 500 km s⁻¹ by default and can be set.

### 7.3 Polarization

The polarization cubes have 500 channels of 2.604 MHz across 700–2002 MHz in Stokes I, Q, U and V. The band-averaged noise, σ_band = (Σ σ_i⁻²)^(−1/2), is the noise of a Stokes Q or U image averaged over the band with inverse-variance weights; rotation-measure synthesis with the same weights has the same noise in its Faraday-depth spectrum (Brentjens & de Bruyn 2005). For rotation-measure synthesis:

- the resolution in Faraday depth (RMSF FWHM) is 2√3/Δλ² = 21.5 rad m⁻², with Δλ² the range of λ² across the band;
- the largest scale in Faraday depth, π/λ²_min = 140 rad m⁻², is the widest structure in Faraday depth (emission extended over a range of rotation measures) that can be recovered; it is not a limit on the rotation measure of a compact source;
- the largest measurable rotation measure, |RM|_max = √3/δλ² = 1269 rad m⁻², is set by the λ² width δλ² of the lowest-frequency channels, beyond which Faraday rotation within a channel depolarizes the signal (sensitivity falls to 50%).

### 7.4 Smoothing

Convolving an image with a Gaussian kernel of FWHM θ_k is equivalent to multiplying its visibilities by the uv taper

    T(u) = exp(−π² θ_k² |u|² / (4 ln 2))

exactly for the dirty image and very nearly for a deconvolved one. The noise per smoothed beam rises by

    f = √(Σ w T² · Σ w) / Σ w T

summed over the visibilities of the observation at up to five hour angles. The sum uses every baseline shorter than 1 km (15,758, weight 1) and every 13th longer baseline (weight 13), 119,128 in total, which reproduces the full set of 1,360,425 baselines to 0.3% at all scales and frequencies. The short spacings are well sampled: 12,983 baselines are shorter than 0.9 km, 238 shorter than 100 m and 72 shorter than 50 m.

The kernel is elliptical along the PSF axes (θ_k² = θ_target² − b²), so that the smoothed beam is the requested circular Gaussian, as for a restored image. If the dirty image is tapered instead, without deconvolution, the smoothed beam departs from the requested Gaussian as follows (1.35 GHz, 4-h track):

| Requested FWHM | Main lobe relative to request | Most negative sidelobe |
|---|---|---|
| 10″–1′ | within 2% | — |
| 2′ | +6 to +9% | — |
| 5′ | +13% | −7% |
| 10′ | −5 to +2% | −10 to −12% |
| 20′ | −15% | −11 to −22% |
| 30′ | −16 to −18% | −15 to −38% |

These scales grow with wavelength; at 0.7 GHz the main lobe stays within 2% up to 2′ and within 13% up to 20′. The calculator warns when the requested resolution exceeds 15′. Smoothed products use natural weighting and optimal summation.

By default, every source brighter than 5σ in the full-resolution full-band image is subtracted before smoothing. The fainter sources left behind form a Poisson population, whose noise in a Gaussian beam is

    σ_res² = Ω_e ∫₀^S_lim S² n(S) dS,    Ω_e = π b_maj b_min / (8 ln 2)

with the counts n(S) recovered by inverting the confusion curve, N(> 5σ_c) = 1/(β Ω_beam), and a spectral index of −0.7. At full resolution this residual matches the confusion curve to within 8%. Because the remainder is Poisson, its noise grows only linearly with beam size, so its brightness temperature falls as 1/θ. Without subtraction, the confusion of the smoothed image is that of the confusion curve at the smoothed beam. Both are reported.

### 7.5 Brightness temperature

    T_b = σ λ² / (2 k Ω),    Ω = π b_maj b_min / (4 ln 2)

## 8. Chronoscope: observation and system

The pulsar and FRB products of the Chronoscope and the Pulsar Timing subsystem (Sections 8–13; DSA-00207, Ravi et al. 2026a) use the SEFD of Section 2 (the measured T_sys bandpass, its increase with zenith angle, the Galactic synchrotron excess and η = 0.67) and the usable bandwidth of Section 3, evaluated in their own bands. The losses of Sections 8–13 apply only to them, except the 4-bit correlator efficiency η_v4 (Section 8.4), which also applies to the imaging products (Section 4.1).

### 8.1 Observation

Every time-domain product is evaluated for a track of length t_track centered on transit at the position. For a targeted observation t_track is the on-source time, divided over transits as in Section 4.3; in survey mode it is set separately (default 1260 s, one survey pointing). Hour angles are sampled as for targeted observations (Section 4.3), and the noise is weighted by 1/SEFD² along the track.

### 8.2 Sub-bands

Every time-domain sensitivity is evaluated in n = ⌈B / 10 MHz⌉ equal sub-bands, each with its own mean T_sys, SEFD, usable bandwidth, center frequency, source flux density and pulse width. Detection signal-to-noise ratios add in quadrature, S/N = √(Σ S/N_i²), and timing precision combines as σ_TOA = [Σ (S/N_i / W_eff,i)²]^(−1/2). With the default RFI profile the usable fractions are 0.990 (B1), 0.998 (B2) and 0.976 (B3) for the search bands, and 0.931 and 0.977 for the targeted bands centered on 953.35 and 1800 MHz.

### 8.3 Self-noise

While a source is on, its flux density adds to the system noise of the beam, which rises by the factor 1 + x, with x = S_on / SEFD_beam. For an on-minus-off detection in which a fraction δ of the samples is on-source, the S/N in each sub-band is multiplied by

    f_self = [(1 + x)² (1 − δ) + δ]^(−1/2)

For pulsars, S_on = S_i P / W_eff,i is the on-pulse flux density and δ = W_eff,i / P. For FRBs, S_on = F / W_eff,i and δ = W_eff,i / (W_eff,i + T_b), with T_b = max(1 s, 10 W_eff,i) the running-mean window of Section 11.4. Because the S/N is then no longer proportional to the flux density, S_min and the fluence limits are found by solving S/N(S) = S/N_min numerically. For a very bright source the S/N tends to √(n_pol Δν t_on), set by the number of independent on-source samples; a threshold above this cannot be reached. With the default inputs self-noise costs less than 0.1% for the search pulsar, 1.4–2% for the PTA pulsar, and 1–2% at the FRB fluence limit.

### 8.4 Quantization

Digitization reduces the S/N by an efficiency that depends on the number of bits (Kassam 1977; Thompson et al. 2017).

- **4-bit voltages**, η_v4 = 0.988. A visibility is the product of two quantized voltages, and η_v4 is the correlator efficiency at 4 bits; it applies to everything formed from the cross-correlations: the imaging products (Section 4.1), the FRB search beams and the untargeted pulsar-search beams. A voltage beam is instead a sum of quantized voltages. Quantization adds to each antenna voltage a noise that is uncorrelated between antennas, so a beam formed from 4-bit voltages loses the same factor, η_v4. Among the voltage beams this correction applies only to the targeted pulsar beams. The Pulsar Timing subsystem forms its beams before the antenna voltages are requantized, so its products carry no digitization loss.
- **Requantized intensities.** A detected intensity requantized to a few bits is a single quantized stream, whose S/N factor is the square root of the corresponding correlator efficiency: η_i2 = √0.8825 = 0.939 for 2-bit intensities (pulsar searches and targeted timing) and η_i4 = √0.988 = 0.994 for 4-bit intensities (FRB search). This is the analog of the √(2/π) loss of surveys that one-bit digitize the detected filterbank output (Manchester et al. 2001).

The targeted beams are assumed to be formed and detected, and the Pulsar Timing beams formed and coherently dedispersed, at 8 bits or more, so that no further loss arises; requantizing a beam voltage to 4 bits would cost another factor of 0.988. The quantization levels are assumed to follow the noise level.

| Product | Quantization efficiency |
|---|---|
| Imaging: continuum, HI, polarization | η_v4 = 0.988 |
| FRB search | η_v4 η_i4 = 0.982 |
| Untargeted pulsar search | η_v4 η_i2 = 0.928 |
| Targeted pulsar search and timing | η_v4 η_i2 = 0.928 |
| Pulsar Timing subsystem | 1 |

## 9. Chronoscope beams

### 9.1 Targeted beams

Targeted beams are formed from the voltages of all antennas, combined coherently and without tapering: SEFD_beam = SEFD/N.

### 9.2 FRB search beams

FRB search beams are formed from the cross-correlations without tapering: SEFD_beam = SEFD/√(N(N−1)). They lie on a hexagonal grid at the band-center natural-weighted beam FWHM, 6 × 10⁶ per band; the area they cover depends on declination (Section 13.7).

### 9.3 Untargeted pulsar-search beams

Untargeted pulsar-search beams are formed from the cross-correlations with a Gaussian uv taper, which broadens them so that fewer beams cover the sky: SEFD_beam = f_taper SEFD/√(N(N−1)). For each search band (centers 930, 1410 and 1800 MHz) and declinations from −30° to +90° at transit, the noise factor f_taper = √(Σ T² · N_bl)/Σ T, the beam FWHM (from the area of the half-power contour) and the rms PSF sidelobe level (over the annulus from 10 FWHM to the primary-beam half-power radius, from a direct Fourier sum at 4000 points) were computed from all baselines as functions of the taper scale. The calculator interpolates them linearly in declination and in beam FWHM. The default beam widths are 13.5″ × (930 MHz/ν_band): 13.5″, 8.90″ and 6.98″; 2 × 10⁵ beams of 13.5″ tile the unique area of a pointing at 930 MHz (Ravi et al. 2026b). At 930 MHz and δ = 0°, the 13.5″ beam has f_taper = 2.32; at 1.35 GHz, broadening the beam by factors of 2 and 3 costs 1.56 and 2.26.

### 9.4 Localization beams

FRBs are localized in images made from voltages recorded around each detection. These images use uniform weighting, with uv cells of 1/FOV for a 2′ field around the detection. From all baselines, the uniformly weighted snapshot PSF at zenith and 1.35 GHz is 2.03″ × 1.57″ (position angle 94°), compared with 3.03″ × 2.31″ for natural weighting; it is converged for fields smaller than a few arcminutes. It is projected to the declination of the source at transit as in Section 5.1 and scaled as 1/ν.

## 10. Pulse broadening and propagation

### 10.1 Effective width

In each sub-band,

    W_eff = √(W_int² + t_samp² + t_DM² + τ_sc²),    t_DM = 8.3 μs × DM × Δν_ch[MHz] / ν_GHz³

where Δν_ch is the channel width after any channel summing and τ_sc the scattering time. Pulsar searches assume the correct DM.

### 10.2 NE2025

The default scattering model is NE2025 (Ocker & Cordes 2026). A grid precomputed with the `mwprop` package gives, for each sightline, the total Galactic DM to the edge of the model, DM_max; the scattering time τ_X at 1 GHz of an extragalactic source; and, at 16 logarithmically spaced DMs from 10 to 5000 pc cm⁻³, the distance D(DM) and the scattering time τ(DM) at 1 GHz of a Galactic source. Sightlines are spaced by 1° in l and b for |b| ≤ 15° and by 5° elsewhere. The calculator interpolates log D and log τ trilinearly in (l, b, log DM) and log τ_X bilinearly in (l, b), and takes DM_max from the nearest sightline; DMs above DM_max are saturated and flagged. Scattering times scale as ν^−4.4. Compared with direct evaluation of the model at 46 random positions, the median interpolation error is 1.3% in D and 2.4% in τ; errors exceed 20% at four positions in D and three in τ, where compact clumps of the model fall between sightlines or the DM lies just below DM_max.

### 10.3 τ–DM relation

Alternatively, the τ–DM relation of Cordes et al. (2022) can be used: τ(DM, ν) = 1.90 × 10⁻⁷ ms × DM^1.5 (1 + 3.55 × 10⁻⁵ DM³) ν_GHz^−4, with an intrinsic scatter of 0.76 dex. This mode provides no distance and no Milky Way scattering of FRBs.

## 11. Sidelobe confusion

### 11.1 Amplitude and spectrum

Faint sources in the sidelobes of a beam add a slowly varying signal that behaves as red noise. Its rms is

    σ_c(ν) = 230 μJy × (ν / 1410 MHz)^−0.7 × s(θ)/s(0)

for an untapered beam, from simulations of the beam response to the extragalactic source population; s(θ)/s(0) is the increase of the rms sidelobe level of a tapered beam (Section 9.3). Its power spectrum is taken to be Lorentzian, P_c(f) = 4 σ_c² τ_c / [1 + (2π f τ_c)²], normalized so that ∫₀^∞ P_c df = σ_c². Thermal noise has the white spectrum P_th = 2 σ_1s², where σ_1s is the 1-s noise of the beam in the band. Because confusion is correlated across frequency, its effect is evaluated once per band (each Chronoscope band, each targeted band and each 100-MHz Pulsar Timing sub-band), at the band center.

### 11.2 Correlation time

The sidelobe pattern on the sky changes as the parallactic angle q rotates. The correlation time is τ_c = 10 s × ω_ref / ⟨|dq/dt|⟩, clamped to 1–1000 s, where

    dq/dH = cos φ (sin φ cos δ cos H − cos φ sin δ) / sin² z,

ω_ref is the rate for a source passing through the zenith at hour angle 1 h, and the average is taken over the track.

### 11.3 Pulsars

For matched folding of a Gaussian profile of FWHM W_eff, the S/N is multiplied by [Σ_k a_k² / (P_th + P_c(k/P)) ÷ Σ_k a_k² / P_th]^(1/2), with harmonic amplitudes a_k = exp(−π² k² W_eff² / (4 ln 2 P²)) up to a_k < 10⁻³ or k/P > 1/(2 t_samp). Confusion matters most for long periods.

### 11.4 FRBs

For a boxcar of width W_eff minus a running mean over T_b = max(1 s, 10 W_eff), the S/N is multiplied by √(V_th / (V_th + V_c)), with V = ∫ P(f) |H(f)|² df and H(f) = sinc(f W_eff) − sinc(f T_b). V_th = σ_1s² (1/W_eff − 1/T_b) exactly; V_c is integrated numerically. Confusion matters most for wide bursts.

## 12. Pulsar search and timing

### 12.1 Input pulsar and S/N

A single pulsar, described by its period P, intrinsic FWHM W_int, DM, flux density S_ref at ν_ref and spectral index α, drives all pulsar products. If no DM is given, half the NE2025 DM_max along the line of sight is used. In each sub-band

    S/N_i = η f_self,i S_i / σ_1s,i × √t_track × √((P − W_eff,i) / W_eff,i),    σ_1s,i = SEFD_beam,i / √(n_pol Δν_i)

with S_i = S_ref (ν_i/ν_ref)^α, η the quantization efficiency (Section 8.4) and f_self,i the self-noise factor (Section 8.3). The minimum detectable flux density S_min is the S_ref at which S/N = S/N_min; it is reported at the band center and scaled to 1.4 GHz. Without self-noise, S_min = S/N_min × S_ref / (S/N). For example, an array SEFD of 1.7 Jy over 200 MHz for 1260 s, with W_eff/(P − W_eff) = 1 and no losses, gives S_min = 23.9 μJy at 10σ.

### 12.2 Products

| Product | Band | Channels, sampling | Beam | Quantization | Periods |
|---|---|---|---|---|---|
| Untargeted search | B1 880–980, B2 1310–1510, B3 1650–1950 MHz | 122.68 kHz summed ×1, ×2, ×3; 1 ms | tapered visibility, 2 × 10⁵ per band | η_v4 η_i2 | 10 ms – 10 s |
| Targeted search and timing | 306.7 MHz (2500 × 122.68 kHz) centered on 953.35 or 1800 MHz, or a custom center | 122.68 kHz; 0.1 ms | voltage | η_v4 η_i2 | 1 ms – 10 s |
| Pulsar Timing subsystem | 700–2000 MHz, 13 × 100 MHz; four full-band beams, which can be pointed in different directions | coherent dedispersion (no t_DM); 1 μs | voltage, formed before requantization | none | — |

Each untargeted beam is folded over the whole track. Outside its period range a search reports no detection. The Pulsar Timing subsystem times its own pulsar, by default a typical timing-array millisecond pulsar (P = 4 ms, W_int = 0.2 ms, DM 20, 1 mJy at 1.4 GHz, α = −1.6).

### 12.3 Sky coverage of the untargeted search

The untargeted beams lie on a hexagonal grid at FWHM spacing and cover N_b (√3/2) θ², 2.42 deg² for 2 × 10⁵ beams of 13.5″ in B1: the unique area of a survey pointing (Ravi et al. 2026b). The beams scale as 1/ν, so they cover 1.06 and 0.65 deg² in B2 and B3. The area is also reported as a fraction of the primary-beam FWHM area.

### 12.4 Sensitivity against period

S_min is also computed for 200 logarithmically spaced periods from 0.3 ms to 10 s, for each search within its period range, at the DM of the input pulsar and with its duty cycle W_int/P held fixed, so that the intrinsic width scales with period.

## 13. FRB search

### 13.1 Search configuration

The FRB search uses the three Chronoscope bands with native 122.68-kHz channels, 1-ms sampling and 6 × 10⁶ untapered visibility beams per band (Section 9.2), with quantization η_v4 η_i4. The bands are searched independently but observe overlapping fields (the primary beam is largest in B1), so a burst of sufficient fluence and spectral extent can be detected in more than one band; the event rates of the bands are therefore not additive.

### 13.2 DM budget

The observed DM is decomposed as

    DM_obs = DM_MW + DM_halo + ⟨DM_cosmic⟩(z) + DM_host / (1+z)

with DM_MW the NE2025 DM_max at the position, DM_halo = 20 pc cm⁻³, and the mean cosmic contribution (Macquart et al. 2020)

    ⟨DM_cosmic⟩(z) = (3 c H₀ Ω_b f_d χ_e / 8π G m_p) ∫₀^z (1+z′)/E(z′) dz′

for Planck 2018 parameters (Ω_b h² = 0.02242), a diffuse baryon fraction f_d = 0.84 and χ_e = 7/8 electrons per baryon mass. The host contribution is the median, 242.2 pc cm⁻³, of the lognormal distribution of Verdi et al. (2026) (μ = 5.49, σ = 0.62 in ln DM_host). The redshift is found by bisection. If the extragalactic excess is smaller than the median host DM, z = 0 and the host takes the excess (not below zero); a DM below DM_MW + DM_halo is flagged.

### 13.3 Scattering

The Milky Way contributes τ_X from NE2025 (none in the τ–DM mode). Following Verdi et al. (2026), host scattering follows the Galactic τ–DM relation with a plane-wave geometric factor of 3, τ_host(ν) = 3 τ_C22(DM_host, ν) (1+z)^−3, with an intrinsic scatter of about 1 dex.

### 13.4 Fluence limit and losses

For a burst at the peak of a search beam at the center of the primary beam, the fluence limit F solves

    S/N_min = η_v4 η_i4 C F √(Σ_i f_self,i(F)² / (σ_1s,i² W_eff,i))

where C is the confusion factor (Section 11.4) and f_self,i the self-noise factor (Section 8.3); without self-noise, F = S/N_min / (η_v4 η_i4 C √(Σ_i 1/(σ_1s,i² W_eff,i))). The headline limit further divides by three losses: the beam straddle, the mean response of the band-center natural PSF over a hexagonal cell at FWHM spacing (≈ 0.70 for a circular beam); the mean Gaussian primary-beam response over the FWHM disk, 0.5/ln 2 = 0.721; and the DM-trial loss (Section 13.5). Peak flux-density limits are F/W_eff at the band center.

### 13.5 DM trials

A DM error ΔDM smears a burst across the band by t_ΔDM = 4.149 ms × ΔDM × (ν_lo⁻² − ν_hi⁻²), with ν in GHz, which adds in quadrature to the width W₀ = √(W_int² + t_samp² + t_DM²) at the band center (scattering is excluded). Successive trial DMs differ by a step δDM chosen so that the largest error, half a step (ΔDM = δDM/2), raises the width by a factor of 1.25:

    δDM = 2 √(1.25² − 1) W₀ / [4.149 ms × (ν_lo⁻² − ν_hi⁻²)]

Because t_DM grows with DM, so does the step; the number of trials counts the steps from DM = 0 to the maximum searched DM (default 5000 pc cm⁻³). The loss is the mean of √(W₀ / W(ΔDM)) for an error distributed uniformly within half a step, ∫₀¹ (1 + 0.5625 x²)^(−1/4) dx = 0.961.

### 13.6 Localization

The 1σ position uncertainty of a burst at the detection threshold is the localization beam (Section 9.4) divided by 2 S/N_min, along right ascension and declination separately: σ_α = √Σ_αα / (2 S/N_min) and σ_δ = √Σ_δδ / (2 S/N_min), where Σ is the beam covariance in FWHM². Because the beam scales as 1/ν, B3 localizes best.

### 13.7 Event rates

Rates are scaled from reference surveys with eq. 2 of Connor et al. (2026):

    R = R_i (Ω_DSA / Ω_i) [(SEFD_i / SEFD_DSA) √(B_DSA / B_i)]^α_c

with α_c = 1.5. The exponent is multiplied by (1 + γ) for B3 to allow for a rate spectral index γ (default 0). B1 is scaled from CHIME/FRB (R_i = 10³ yr⁻¹, SEFD 100 Jy, Ω_i = 200 deg², B_i = 300 MHz) and B2 and B3 from the Parkes high-latitude survey (31 yr⁻¹, 40 Jy, 0.55 deg², 340 MHz). B_DSA is the usable bandwidth of the band, and SEFD_DSA the effective array SEFD divided by the quantization, straddle, DM-trial, confusion and self-noise efficiencies (the last evaluated at the fluence limit). Ω_DSA is the solid angle searched, counted as the reference surveys count theirs:

- The 6 × 10⁶ beams lie on a hexagonal grid at FWHM spacing and cover A_cov = N_b (√3/2) θ_b², with θ_b the geometric mean of the band-center beam FWHM. Because the beams lengthen north–south as 1/cos ZA, A_cov is 58–63% of the primary-beam FWHM area for declinations from +15° to +50°, 75% at 0°, about 90% at the pole and 165% at −30°.
- The beams are taken to fill a disk of radius ρ = √(A_cov/π) centered on the primary beam. A position where the primary-beam response is B sees the limit raised by 1/B, so it contributes bursts in proportion to B^α_c. The solid angle is normalized so that a search of exactly the FWHM disk has the FWHM area, as for the reference surveys:

      Ω_DSA = (π θ_P² / 4) [1 − exp(−4 ln 2 α_c ρ² / θ_P²)] / (1 − 2^−α_c)

- For the same reason, the straddle efficiency in SEFD_DSA is the count-weighted mean response over a hexagonal cell, ⟨b^α_c⟩^(1/α_c) (0.702 at δ = +30°), rather than the mean response ⟨b⟩ (0.692) used for the fluence limit.

At (180°, +30°) in a survey pointing this gives 3.9 × 10³, 6.9 × 10³ and 5.3 × 10³ yr⁻¹ for B1, B2 and B3. As a check of the scaling relation, nominal inputs with full coverage of the FWHM area (SEFD 1.8 Jy, B = 100, 200 and 300 MHz, Ω = 8.6 ν_GHz⁻² deg²) give 9.0 × 10³, 1.7 × 10⁴ and 1.4 × 10⁴ yr⁻¹; Connor et al. (2026) quote 9 × 10³, 1.5 × 10⁴ and 9 × 10³ yr⁻¹ for these bands, and their posteriors span roughly a factor of two. The expected number in the track is R t_track / (1 yr).

The calculator also reports the field of view (π θ_P²/4), the area covered by the beams and Ω_DSA, the number of DM trials, and the fluence limit as a function of DM for 60 logarithmically spaced DMs from max(1, DM_MW + DM_halo) to the maximum searched DM.

## 14. Survey plan

The Cadenced All-Sky Survey covers δ > −30.45° with 12,850 pointings and a budget of 5 × 12,850 = 64,250 pointing-epochs of 21 minutes. Epochs are assigned per tile, in 429 tiles of 30 pointings (the polar tile has 10) arranged in 15 declination tiers mostly 8.7° wide. Each plan is evaluated with the noise model above; the figure of merit is the number of continuum sources above 5σ in the final full-band images.

| Plan | Rule | Euclid/HSC median | Galactic plane median | Wide-area median | Sources > 5σ |
|---|---|---|---|---|---|
| Plan A (default) | 7 epochs in the Euclid/HSC footprint and in the Galactic plane and bulge; the remaining pointings go to the wide area where they add the most detections, with at least 2 epochs everywhere | 0.40 μJy | 0.45 μJy | 0.66 μJy | 1.69 × 10⁹ |
| Plan B | as Plan A, but the Euclid/HSC time (7 epochs per tile on average) is divided so that the final noise is equal across those tiles (6 to 11 epochs) | 0.41 μJy | 0.45 μJy | 0.66 μJy | 1.68 × 10⁹ |
| Plan C | at least 2 epochs everywhere and 7 in the Galactic plane and bulge; the remaining time goes wherever it adds the most detections (4 to 6 epochs in the Euclid/HSC footprint) | 0.46 μJy | 0.45 μJy | 0.59 μJy | 1.71 × 10⁹ |
| Reference | DSA-00264 (Fig. 1): 7 epochs in the Euclid/HSC footprint and the Galactic plane and bulge; 4, 3 or 2 by declination elsewhere; 63,110 pointings | 0.40 μJy | 0.45 μJy | 0.67 μJy | 1.67 × 10⁹ |

Medians are of the final full-band total noise (thermal and confusion) per tile, with the default RFI model.

## 15. Implementation

Model data are stored as tables in the Python package (`python/dsa_etc/data/`) and shared by both engines.

| File | Contents |
|---|---|
| `rfi_spring_valley.json` | measured RFI occupancy, 700–2000 MHz at 0.8 MHz |
| `rfi_spring_valley_extrapolated.json` | default occupancy, extrapolated to DSA sensitivity |
| `ucc_confusion.json` | confusion curves f_β(θ) for β_min = 16 and 25 |
| `tsky_gsm2008.json` | beam-smoothed GSM2008 sky planes |
| `weighting_factors.json` | robust-weighting beam and noise factors |
| `mosaic_z.json` | minimum and maximum mosaic weight over the hexagonal grid |
| `antennas_enu.json` | antenna positions and site latitude |
| `allocation.json` | survey tiles, classes, epochs and weighting choices for each plan |
| `tsys_bandpass.json` | T_sys bandpass at zenith with RFI removed |
| `tsys_za.json` | increase of T_sys over zenith from spillover and atmosphere, against frequency and zenith angle |
| `chr_taper.json` | untargeted-beam noise factor, FWHM and sidelobe level against taper, band and declination |
| `psf_uniform.json` | uniformly weighted localization PSF at zenith and 1.35 GHz |
| `ne2025_grid.json` | NE2025 DM_max, τ_X, D(DM) and τ(DM) on the sightline grid |

Tables are rebuilt by the scripts in `tools/`. The Python engine depends only on NumPy.

## 16. Limitations

- The default RFI model is an extrapolation of a site survey; the loss at DSA sensitivity has not been measured.
- The T_sys bandpass is interpolated across ranges dominated by RFI (1170–1300 and 1540–1630 MHz), where it is not measured.
- The residual confusion after source subtraction includes neither source clustering nor subtraction errors.
- Robust-weighting factors north of +30° use the +30° values.
- HI cubes assume ideal Doppler tracking (Section 7.2).
- Targeted and Pulsar Timing beams are assumed to be formed and processed at 8 bits or more (Section 8.4).
- Scattering uses the mean of the chosen model; its intrinsic scatter is large. Pulse jitter and scintillation are not modeled.
- FRB rates inherit the uncertainties of the reference surveys and of the source-count index.

## References

- Brentjens, M. A., & de Bruyn, A. G. 2005, A&A, 441, 1217
- Connor, L., et al. 2026, arXiv:2608.30943
- Cordes, J. M., Ocker, S. K., & Chatterjee, S. 2022, ApJ, 931, 88
- DSA-00207: Ravi, V., et al. 2026a, Chronoscope high-level design (DSA document)
- DSA-00264: Hallinan, G., & Ravi, V. 2026, Survey Strategy and Coverage Goals (DSA document)
- de Oliveira-Costa, A., Tegmark, M., Gaensler, B. M., et al. 2008, MNRAS, 388, 247
- Hallinan, G., et al. 2026, DSA Overview at FDR
- ITU-R P.676-12 2019, Attenuation by atmospheric gases and related effects
- ITU-R P.835-6 2017, Reference standard atmospheres
- ITU-R P.836-6 2017, Water vapour: surface density and total columnar content
- Jonas, J. 2026, simulated spillover temperature of the 6.15-m dish with the v3 feed (DSA project data)
- Kassam, S. A. 1977, IEEE Trans. Commun., 25, 479
- Macquart, J.-P., Prochaska, J. X., McQuinn, M., et al. 2020, Nature, 581, 391
- Matthews, A. M., Condon, J. J., Cotton, W. D., & Mauch, T. 2021, ApJ, 909, 193
- Mauch, T., Cotton, W. D., Condon, J. J., et al. 2020, ApJ, 888, 61
- Manchester, R. N., Lyne, A. G., Camilo, F., et al. 2001, MNRAS, 328, 17
- Meyer, M., Robotham, A., Obreschkow, D., et al. 2017, PASA, 34, 52
- Myers et al. 2026, DSA Survey Implementation Plan (SIP), FDR version
- Ocker, S. K., & Cordes, J. M. 2026, NE2025 Galactic electron-density model, `mwprop`
- Planck Collaboration 2020, A&A, 641, A6
- Ravi, V., et al. 2026b, The DSA/Chronoscope pulsar survey: design and forecasts
- Rosero 2026, Confusion Noise and Image Weighting Analysis for DSA (DSA memo)
- Thompson, A. R., Moran, J. M., & Swenson, G. W. 2017, Interferometry and Synthesis in Radio Astronomy, 3rd ed. (Springer)
- Verdi, F., et al. 2026, arXiv:2609.30616
