# User guide

<p class="doc-meta">DSA Sensitivity Calculator, version 3.1</p>

The calculator gives the noise, resolution and detection limits of every Deep Synoptic Array (DSA) data product at a sky position you choose: continuum, HI and polarization images, fast radio bursts (FRBs), pulsar searches and pulsar timing. It works for a position in the Cadenced All-Sky Survey (CASS) or for a dedicated (targeted) observation. This guide explains the inputs, how to read each result, and how to answer common questions. The equations behind every number are in the [Methods](#methods). All capabilities assume the DSA project baseline at the Final Design Review.

## Getting started

1. Enter a position as RA and Dec, click one of the example positions, or click the sky map.
2. Choose **Survey products** to see what the survey will reach at that position, or **Targeted** to plan a dedicated observation and set its length.
3. Choose the **Data products** to calculate and press **Calculate**, at the top of the input panel. A summary appears on the right, followed by one panel per data product. The panels start collapsed: click a panel's header (or its arrow) to open it. Panels you open stay open when you calculate again.
4. Hover over (or tap) a **?** mark for a short explanation of any input or result. Each result panel's **Info** link leads to its section of this guide.
5. To change the pulsar or FRB you are interested in, edit the time-domain inputs under **Advanced settings**. In targeted mode these products use the on-source time; in survey mode, the track length given there.

When you change an input, the status label in the summary panel shows that the results are out of date until you press **Calculate** again.

## Inputs

### Observation: survey or targeted

**Survey products** describe the imaging data at the position after the survey: the continuum, HI and polarization images built up from all the 21-minute visits planned for that part of the sky. You can also ask for a single visit, or for any number of visits, under **Survey depth**.

**Targeted** describes one pointing centered on the position and tracked for the **on-source time** you enter. The DSA can track a source for at most ±2 hours of hour angle around transit, and only above 20° elevation; longer requests are split over several transits (100 hours is 25 transits of 4 hours). Near the southern limit of the sky the window is shorter: at declination −30° only about ±0.6 hours is available. In targeted mode you can also choose the **image weighting**; the default picks the weighting with the lowest total noise.

### Position

RA can be given in degrees (150.12) or in hours (10:00:28.6); Dec in degrees (+2.21) or as degrees, minutes and seconds (+02:12:21). The line under the boxes shows how the position was read, with its Galactic coordinates. The DSA observes the sky north of declination −30°.

### Survey plan and depth

In survey mode the sky map shows how many visits (epochs) each part of the sky receives in the selected survey plan, and you can click it to choose a position. The **Enlarge** button at the corner of the map opens a larger copy: scroll or use **+** and **−** to zoom (up to 8×), drag to pan, hover to read the epochs of a tile, and click to choose a position. Plan A is the default; other plans can be chosen under **Advanced settings** and are described in [Survey plan](#survey-plan). The depth at a position blends the plans of neighboring tiles, because the primary beam spans several survey pointings; this is why the number of effective epochs need not be an integer.

### Smoothing

Smoothing convolves the continuum, HI and polarization images to a coarser, circular Gaussian beam. Use it to judge the sensitivity to extended emission: a larger beam collects more surface brightness, so the brightness-temperature noise falls, although the noise per beam in Jy rises. With **Subtract sources detected at full resolution** checked (the default), every source brighter than 5σ in the full-resolution image is removed before smoothing. Without subtraction, faint sources blend together and the smoothed continuum image is limited by confusion; the results report both cases. Beyond about 15′ the smoothed beam is set by a few dozen short baselines and the results carry a warning.

### RFI profile

The RFI profile sets the fraction of each frequency lost to radio-frequency interference, for every product. The default, **Spring Valley model extrapolated**, keeps the frequency pattern of the site interference survey but scales it to the sensitivity of the DSA, which sees weaker and more distant transmitters: 15% of the band is lost, compared with 2.8% in the survey itself (also selectable). You can also choose no flagging, or upload your own profile as a two-column file of frequency (MHz) and occupancy (0–1 or percent); lines starting with # are ignored. The plot shows the selected profile with the HI band shaded.

### Time-domain inputs (Advanced settings)

The time-domain products, from the Chronoscope (the DSA's time-domain backend) and the Pulsar Timing subsystem, are calculated for a **track** centered on transit at the position. For a targeted observation the track is the on-source time you entered; in survey mode it is the **track length** set here (default 1260 s, one survey pointing).

One **pulsar**, set under **Chronoscope: pulsars**, drives the searches and the targeted timing. Give its period, intrinsic pulse width (full width at half maximum, before any broadening), dispersion measure (DM), flux density at a reference frequency, and spectral index. If you leave the DM empty, the calculator uses half the total Galactic DM along the line of sight, which is typical of a pulsar halfway through the Galaxy. The **detection threshold** is the signal-to-noise ratio (S/N) required for a detection.

- **Targeted band center:** the targeted pulsar beams cover 306.7 MHz. Two standard bands, centered on 953.35 MHz and 1800 MHz, are always reported; choose **Custom** to add any other center (the band is clipped to 0.70–2.00 GHz).
- **Untargeted beams:** the width of the search beams in each band. Leave the box empty for the standard widths (13.5″, 8.90″ and 6.98″). Wider beams tile more sky with the same number of beams but are less sensitive.
- **Scattering model:** NE2025, a model of the Galactic electron density, or the average relation between scattering time and DM. NE2025 also gives the pulsar's distance.

For **FRBs** (under **Chronoscope: FRBs**), give the DM, intrinsic width, detection threshold and the maximum DM searched.

The **PTA pulsar**, set under **Pulsar timing (PTA-like)**, is timed by the Pulsar Timing subsystem. By default it is a typical timing-array millisecond pulsar: period 4 ms, intrinsic width 0.2 ms, DM 20, 1 mJy at 1.4 GHz, spectral index −1.6.

### Advanced settings

These choose the survey plan, the image weighting of the survey products (by default each tile's planned choice), the HI line widths for mass limits, and change the instrument: the system temperature (empty for the measured bandpass, which applies to every product), the number of antennas, the dish diameter, an extra fraction of data loss, the confusion criterion (β<sub>min</sub> = 16 is standard; 25 is more conservative), whether Galactic synchrotron emission is added to the system temperature, and the elevation and hour-angle limits of targeted tracks. The aperture efficiency is fixed at its measured value, 0.67, for all products, and the imaging products carry the 0.988 efficiency of correlating 4-bit voltages.

## Reading the results

All noise values are 1σ, flux densities are per beam, and beam sizes are the full widths at half maximum in arcseconds. "Thermal" noise is the receiver and sky noise (with the 0.988 efficiency of correlating 4-bit voltages), which falls as the square root of the integration time; "confusion" is the noise from faint sources blended by the beam, which does not.

### Summary

The summary panel describes the observation: the position, the survey tile and its planned epochs (survey mode) or the transits used (targeted mode), the performance over the full band (system temperature and the SEFD, or system equivalent flux density, of one antenna, over the unflagged channels of 0.70–2.00 GHz, at this position at transit), and the usable fraction of the band. It also names the image weighting. In survey mode each tile uses the weighting that gives the lowest total noise in its final image; in targeted mode the default is the lowest total noise for your observation. **Compare all six weighting schemes**, in the Continuum panel, shows the alternatives. Warnings, for example about tracks split over transits or positions near the southern edge, appear here.

### Continuum

The DSA images the sky in ten continuum windows of 130 MHz each (Stokes I and V), which are combined into a full-band image. In the survey they are mosaicked into survey tiles; a targeted observation is a single pointing, tracked for the on-source time, with the noise given at the center of the primary beam. The headline is the full-band noise, thermal and confusion added in quadrature, with the resolution and effective frequency of the full-band image. The table lists each window; in the survey the low-frequency windows are deeper because the primary beam is larger there and each position is covered by more pointings. In survey mode the panel also gives the noise of one epoch and of one 21-minute pointing at the beam center without mosaicking. Both modes give the noise of the 6-second snapshot images made within each pointing for transient searches (four 325-MHz sub-bands and the full band).

If you asked for smoothing, the **Smoothed** box gives the thermal noise, the confusion (after source subtraction, or not), and the brightness-temperature sensitivity at the requested resolution.

### Spectral line (HI)

Three HI cubes are made in parallel: **Zoom B** for Galactic HI (0.2 km s⁻¹ channels), **Zoom A** for nearby galaxies to about 100 Mpc (1.7 km s⁻¹), and **Narrow Line** for HI to redshift about 1 (130-kHz channels). For each cube the panel gives the noise per channel and its brightness temperature, the 5σ HI column density over 20 km s⁻¹ for emission filling the beam, and the 5σ HI mass of an unresolved galaxy for each line width set under **Advanced settings** (default 50, 200 and 500 km s⁻¹) (Zoom A at 10, 50 and 100 Mpc; Narrow Line at the luminosity distance of each redshift). The HI cubes are continuum subtracted, so confusion does not apply. Survey cubes combine all epochs; targeted cubes use the on-source time.

With **Smoothing** set, the four headline tiles describe the smoothed cubes: the noise per channel at the requested resolution (with the native value alongside), the 5σ HI mass of a galaxy unresolved at the smoothed beam, and the 5σ column density in the smoothed beam. The Zoom B and Zoom A boxes add the smoothed noise, brightness temperature and column density as separate rows, and the Narrow Line table adds a column for the smoothed noise. The HI-mass table in the Zoom A box stays at the native resolution.

### Polarization

Full-Stokes cubes have 500 channels of 2.6 MHz across 0.70–2.00 GHz. The headline is the noise of a Stokes Q or U image averaged over the whole band; rotation-measure (RM) synthesis with the same channel weights has the same noise in its Faraday-depth spectrum. The panel also gives three RM-synthesis parameters. The **RMSF width** is the resolution in Faraday depth: sources whose RMs differ by less than this blend together. The **largest Faraday-depth scale** is the widest structure in Faraday depth (emission spread over a range of RMs) that can be recovered; it is not a limit on the RM of a source. The **largest detectable |RM|** is the highest RM, of either sign, that can be measured before rotation within a single 2.6-MHz channel at 700 MHz depolarizes the signal. The chart shows the noise per channel; spikes mark channels lost to RFI. Confusion is negligible in polarization because polarized sources are far fewer than total-intensity sources.

### Chronoscope: FRBs

The FRB search runs in three bands, B1 (880–980 MHz), B2 (1310–1510 MHz) and B3 (1650–1950 MHz), each searched with 6 million beams on a hexagonal grid at the center of the primary beam, with 1-ms sampling and 122.7-kHz channels. The beams are spaced by their width, so the sky they cover depends on declination: about 60% of the half-power area of the primary beam at declinations from +15° to +50°, more toward the pole, and more than the whole of it south of about −15°, where the beams are elongated. **Sky searched** gives the area in each band.

- **Fluence limit:** the fluence (Jy ms) of the faintest burst detectable at the threshold. The headline includes every loss: data quantization, the burst falling between search beams (beam straddle), the burst falling away from the center of the primary beam, the spacing of the DM trials, sidelobe confusion, and self-noise (the burst's own flux density adds to the noise of the beam, which costs 1–2% at the threshold). **At a beam peak** gives the limit for a burst centered on a search beam at the center of the primary beam. The peak flux-density limit is the fluence divided by the effective burst width.
- **Effective width:** the intrinsic width broadened by sampling, by dispersion within a channel, and by scattering in the Milky Way and in the host galaxy. The table breaks it down band by band.
- **DM budget:** the observed DM is split into the Milky Way (from NE2025), its halo, the intergalactic medium, which sets the redshift, and the host galaxy, using a typical host DM. Host scattering follows from the host DM.
- **Localization:** the 1σ position uncertainty along RA and Dec of a burst at the detection threshold, from a uniformly weighted image made from the recorded voltages. Higher bands have smaller beams, so B3 localizes best.
- **Rates:** the expected number of FRBs per year and in the track, scaled from the CHIME/FRB and Parkes surveys to the sky covered by the search beams, weighted by the primary-beam response. Treat these as estimates good to about a factor of two. The three bands observe overlapping sky, so many bursts are detected in more than one band: the band rates are not additive, and the headline quotes the band with the highest rate.
- **Fluence against DM:** the chart shows how the limit rises with DM as dispersion smearing and scattering widen the burst. The curve starts at the Milky Way and halo contribution along the line of sight, and the dashed line marks the DM you entered.

### Chronoscope: pulsars and pulsar timing

The pulsar panel reports three products for the pulsar you describe.

- **Untargeted search:** 200,000 beams in each of the three Chronoscope bands, formed from the cross-correlations and tapered to a wider beam so that they cover more sky. In B1 they cover the unique area of a survey pointing; the beams narrow as 1/ν, so they cover less in B2 and B3. Each beam is folded over the whole track. Periods from 10 ms to 10 s are searched; outside this range the search reports "not searched".
- **Targeted search:** beams formed from the voltages of the full array, pointed at known or candidate sources, covering 306.7 MHz with 0.1-ms sampling; periods from 1 ms to 10 s.
- **Targeted timing:** the arrival-time precision σ<sub>TOA</sub> from one track with the targeted beam.

For each product the panel gives the **S/N** of your pulsar and the **minimum detectable flux density** S<sub>min</sub> at the threshold, both at the band center and scaled to 1.4 GHz with your spectral index; timing products also give σ<sub>TOA</sub>. The losses column lists the quantization efficiency, the noise penalty of the untargeted beam taper, the effect of sidelobe confusion, which matters most for long periods, and self-noise, the loss from the pulsar's own on-pulse flux density adding to the noise of the beam, which matters only for bright pulsars. The details section breaks down the effective pulse width, describes the untargeted beams and the sky area they cover, and gives the scattering time in each band.

The **S<sub>min</sub> against period** chart shows the faintest detectable pulsar as a function of period, one curve per search, at the DM of your pulsar and with its duty cycle (intrinsic width divided by period) held fixed, so the pulse narrows as the period shortens. Curves are drawn only within each search's period range: the untargeted search starts at 10 ms, the targeted search at 1 ms. The dots mark your pulsar: its flux density at each band center, in the color of that band's curve. Your pulsar is detectable in a search when its dot lies above that search's curve.

### Pulsar timing (PTA-like)

The Pulsar Timing subsystem forms four coherently dedispersed beams, each covering the full 0.70–2.00 GHz band, which can be pointed in different directions. The beams are formed before the antenna voltages are requantized, so they carry no digitization loss; self-noise from the pulsar's on-pulse flux density is included. The panel gives the S/N, σ<sub>TOA</sub> and S<sub>min</sub> of the PTA pulsar for the track, with a breakdown over 100-MHz sub-bands.

## Common questions

**How long do I need to reach a given noise?** Thermal noise falls as 1/√t, but confusion does not. In targeted mode, increase the on-source time until the continuum total noise reaches your target. If the target is below the confusion noise, it cannot be reached at that resolution: try robust weighting, which gives a smaller beam and less confusion.

**Why does the survey reach a different depth at nearby positions?** The survey assigns epochs per tile. The depth blends smoothly across tile boundaries because the primary beam overlaps several tiles, and it drops near the southern limit (declination −30.45°), where fewer pointings overlap.

**Why are the pulsar and FRB limits worse in the Galactic plane?** The sky is brighter there, which raises the system temperature, and scattering by the interstellar medium broadens the pulses, especially at low frequency.

**Can I use my own RFI environment?** Upload a profile under **RFI profile**, or add an extra data loss under **Advanced settings**. Both apply to every product.

**What do the warnings mean?** They flag positions near the edge of the survey, tracks split over several transits, smoothing scales where the beam is poorly defined, and DMs outside the Galactic model.

## Copying and scripting

**Copy all results as JSON**, at the bottom of the results, copies every number shown (and more) for use elsewhere.

The same calculation is available as a Python package (`dsa_etc`) and command-line tool with identical results:

    dsa-etc --ra 150.12 --dec 2.21                         survey position
    dsa-etc --mode targeted --ra 150.12 --dec 2.21 --hours 10
    dsa-etc --products pulsar --psr-period-ms 3 --psr-width-ms 0.3 --psr-dm 150
    dsa-etc --ra 180 --dec 60 --json > result.json         every number, as JSON

Run `dsa-etc --help` for the full list of options; `--set KEY=VALUE` changes any model parameter.

## Glossary

| Term | Meaning |
|---|---|
| 1σ noise | the standard deviation of the noise; a 5σ detection is five times this |
| Beam, PSF | the resolution element of an image; sizes are full widths at half maximum |
| Brightness temperature | surface brightness expressed as a temperature (K or mK) |
| Confusion | noise from many faint sources blended within the beam |
| DM | dispersion measure: the column density of free electrons to the source, in pc cm⁻³ |
| Effective width (W<sub>eff</sub>) | the observed pulse width after sampling, dispersion smearing and scattering |
| Epoch | one visit of the survey to a position |
| Fluence | the time-integrated flux density of a burst, in Jy ms |
| Primary beam | the field of view of one antenna, 2.49° wide at 1.35 GHz |
| RFI | radio-frequency interference from transmitters |
| SEFD | system equivalent flux density: the noise of one antenna expressed in Jy |
| S<sub>min</sub> | the minimum detectable flux density at the detection threshold |
| σ<sub>TOA</sub> | the uncertainty of a pulse arrival time |
| T<sub>sys</sub> | system temperature: the total noise of the receiver and sky |
| Tile | a group of 30 survey pointings that share a planned number of epochs |
