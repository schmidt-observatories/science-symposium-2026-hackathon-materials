"""Build beam-smoothed Galactic sky-temperature planes on an equatorial grid from GSM2008
(de Oliveira-Costa et al. 2008; component file from telegraphic/PyGSM, 408 MHz-locked basemap)."""
import numpy as np, h5py, healpy as hp
from scipy.interpolate import PchipInterpolator

f = h5py.File('gsm_components.h5', 'r')
pca_map = f['component_maps_408locked'][:].astype(np.float64)   # (npix, 3), Galactic, RING
comp = f['components'][:]
lnf = np.log(comp[:, 0]); scal = PchipInterpolator(lnf, np.log(comp[:, 1]))
spl = [PchipInterpolator(lnf, comp[:, 2 + k]) for k in range(3)]
nside = hp.npix2nside(pca_map.shape[0])
print('nside', nside, 'component freqs MHz', comp[:, 0])

def gsm(freq_mhz):
    x = np.log(freq_mhz)
    c = np.array([s(x) for s in spl])
    return np.exp(scal(x)) * pca_map.dot(c)          # K, no CMB

PLANES = [700., 1000., 1400., 2000.]                  # MHz
DEC = np.arange(-32., 90.001, 1.0)                    # 123 rows
RA = np.arange(0., 360., 1.0)                         # 360 cols
RAg, DECg = np.meshgrid(RA, DEC)
rot = hp.Rotator(coord=['C', 'G'])                    # equatorial -> galactic
th_c, ph_c = np.deg2rad(90 - DECg.ravel()), np.deg2rad(RAg.ravel())
th_g, ph_g = rot(th_c, ph_c)

out = {}
for fr in PLANES:
    m = gsm(fr)
    m = hp.ud_grade(m, 256)                           # plenty for >=1.7 deg beams
    fwhm_deg = 3.36 / (fr / 1000.)                    # DSA primary beam FWHM
    ms = hp.smoothing(m, fwhm=np.deg2rad(fwhm_deg))
    vals = hp.get_interp_val(ms, th_g, ph_g).reshape(DECg.shape)
    # reference: median over |b|>30 deg, dec >= -30
    b = 90 - np.rad2deg(th_g.reshape(DECg.shape))
    ref = np.median(vals[(np.abs(b) > 30) & (DECg >= -30)])
    out[fr] = (vals, ref)
    gc = hp.get_interp_val(ms, np.deg2rad(90 - (-0.05)), np.deg2rad(359.94))
    print(f'{fr:6.0f} MHz  beam {fwhm_deg:.2f} deg  min {vals.min():7.2f}  ref(|b|>30 median) {ref:6.2f}  '
          f'p99 {np.percentile(vals,99):7.1f}  max {vals.max():7.1f}  GC {gc:7.1f} K')

np.savez('tsky_planes.npz', planes=np.array(PLANES), dec=DEC, ra=RA,
         T=np.array([out[p][0] for p in PLANES]), Tref=np.array([out[p][1] for p in PLANES]))
