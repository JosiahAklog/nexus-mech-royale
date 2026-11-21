"""Offline map cache generator. Not required at runtime. Uses official kit map."""
import json,sys, pathlib
import numpy as np
from matplotlib.path import Path
from scipy.ndimage import distance_transform_edt
root=pathlib.Path(sys.argv[1]); dst=pathlib.Path(sys.argv[2]); w=json.loads((root/'world.json').read_text()); t=w['terrain']; nx,ny=t['nx'],t['ny']; ground=np.fromfile(root/'terrain.i16',dtype='<i2').reshape(ny,nx).astype(np.float32)*.01
# Two-meter grid samples, with exact polygon membership at sample centers.
step=2; g=ground[::step,::step].copy(); h=g.copy(); by,bx=g.shape
for prism in w['prisms']:
    ring=np.array(prism['ring']).reshape(-1,2); ix0=max(0,int(np.floor((ring[:,0].min()-t['minX'])/step))); ix1=min(bx,int(np.ceil((ring[:,0].max()-t['minX'])/step))+1); iy0=max(0,int(np.floor((ring[:,1].min()-t['minY'])/step))); iy1=min(by,int(np.ceil((ring[:,1].max()-t['minY'])/step))+1)
    if ix1<=ix0 or iy1<=iy0: continue
    xx,yy=np.meshgrid(t['minX']+np.arange(ix0,ix1)*step,t['minY']+np.arange(iy0,iy1)*step); pts=np.column_stack((xx.ravel(),yy.ravel())); mask=Path(ring).contains_points(pts,radius=.3)
    for hole in prism['holes']: mask &= ~Path(np.array(hole).reshape(-1,2)).contains_points(pts)
    mask=mask.reshape(xx.shape); view=h[iy0:iy1,ix0:ix1]; view[mask]=np.maximum(view[mask],prism['top'])
obstacles=(h-g>1.4); clear=distance_transform_edt(~obstacles)*step
with open(dst,'wb') as f:
    for a in (g,h,clear): np.clip(np.rint(a*100),-32768,32767).astype('<i2').tofile(f)
(dst.parent/'mapinfo.json').write_text(json.dumps({'x':t['minX'],'y':t['minY'],'step':step,'nx':bx,'ny':by,'bounds':w['bounds']}))
