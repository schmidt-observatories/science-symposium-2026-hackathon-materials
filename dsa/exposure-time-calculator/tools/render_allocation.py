import json, math, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Polygon
al=json.load(open('../python/dsa_etc/data/allocation.json'))
ev=json.load(open('tile_eval.json')); ev=ev.get('tiles', ev)   # cache holds {signature, tiles}
BLUE={250:'#86b6ef',300:'#6da7ec',350:'#5598e7',400:'#3987e5',450:'#2a78d6',500:'#256abf',550:'#1c5cab',600:'#184f95',650:'#104281',700:'#0d366b'}
ecols=[BLUE[k] for k in (250,300,350,400,450,500,550,600,650)]  # epochs 2..10
cm_e=ListedColormap([plt.get_cmap('Blues')(x) for x in np.linspace(0.22,1.0,9)]); norm_e=BoundaryNorm(np.arange(1.5,11.5,1),cm_e.N)
cm_n=plt.get_cmap('Blues')
def poly(t):
    ra=np.linspace(t['ra0'],t['ra1'],12); dec0,dec1=t['dec0'],min(t['dec1'],89.9)
    lon=lambda r: np.radians(-(((r+180)%360)-180)) if False else np.radians(-((r+180)%360-180))
    xs=list(lon(ra))+list(lon(ra[::-1])); ys=[math.radians(dec0)]*12+[math.radians(dec1)]*12
    return np.c_[xs,ys]
variants=['A','B','C','fig1']
titles={'A':'v2-A DSA-00264 corrected fill (default)','B':'v2-B DSA-00264 uniform Euclid/HSC depth','C':'v2-C maximum detections','fig1':'DSA-00264 Fig. 1 as published (63,110 used)'}
fig=plt.figure(figsize=(16,17),facecolor='#fcfcfb')
for col,v in enumerate(variants):
    for row in range(2):
        ax=fig.add_subplot(4,2,col*2+row+1,projection='mollweide'); ax.set_facecolor('#fcfcfb')
        for k,t in al['tiles'].items():
            n=t['epochs'][v]
            if row==0: c=cm_e(norm_e(n))
            else:
                val=ev[k]['rms_uJy'][n-1]; c=cm_n(np.clip((val-0.3)/(1.0-0.3),0,1)*0.85+0.1)
            p=poly(t)
            # split polygons crossing the RA=180 seam
            if t['ra0']<180<t['ra1']:
                for a,b in ((t['ra0'],180-1e-6),(180+1e-6,t['ra1'])):
                    tt=dict(t,ra0=a,ra1=b); ax.add_patch(Polygon(poly(tt),closed=True,fc=c,ec='#fcfcfb',lw=0.4))
            else:
                ax.add_patch(Polygon(p,closed=True,fc=c,ec='#fcfcfb',lw=0.4))
        ax.set_xticklabels(['10h','8h','6h','4h','2h','0h','22h','20h','18h','16h','14h'],fontsize=7,color='#52514e')
        ax.set_yticklabels([]); ax.grid(True,color='#e1e0d9',lw=0.5)
        ax.set_title(titles[v]+(' — epochs' if row==0 else ' — final noise'),fontsize=12,color='#0b0b0b',pad=8)
        s=al['variants'][v]['summary']
        if row==1:
            b=s['by_class']
            ax.set_xlabel('Euclid/HSC median %.2f  |  GP %.2f  |  wide %.2f uJy   •  %.2f bn sources >5σ'%(b['euclid_hsc']['median_total_uJy'],b['galactic']['median_total_uJy'],b['wide']['median_total_uJy'],s['detections_millions']/1000),fontsize=9,color='#52514e')
cax=fig.add_axes([0.13,0.075,0.34,0.008]); cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm_e,cmap=cm_e),cax=cax,orientation='horizontal',ticks=range(2,11)); cb.set_label('Epochs (21-min pointings per position)',fontsize=9,color='#52514e'); cb.ax.tick_params(labelsize=8)
cax2=fig.add_axes([0.56,0.075,0.34,0.008]); sm=plt.cm.ScalarMappable(norm=plt.Normalize(0.3,1.0),cmap=matplotlib.colors.LinearSegmentedColormap.from_list('b',[cm_n(0.1),cm_n(0.95)])); cb2=fig.colorbar(sm,cax=cax2,orientation='horizontal'); cb2.set_label('Final full-band coadd noise, thermal + confusion (µJy/beam)',fontsize=9,color='#52514e'); cb2.ax.tick_params(labelsize=8)
fig.savefig('allocation_variants.png',dpi=110,bbox_inches='tight',facecolor='#fcfcfb')
print('saved')
