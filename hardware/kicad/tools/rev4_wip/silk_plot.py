"""silk_plot.py in.json out.png [px_per_mm]"""
import sys, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
d=json.load(open(sys.argv[1])); ppm=float(sys.argv[3]) if len(sys.argv)>3 else 60
x0,y0,x1,y1=d['win']; w=x1-x0; h=y1-y0; dpi=100
fig=plt.figure(figsize=(w*ppm/dpi,h*ppm/dpi),dpi=dpi); ax=fig.add_axes([0,0,1,1])
if d['side']=='B': ax.set_xlim(x0,x1)
else: ax.set_xlim(x0,x1)
ax.set_ylim(y1,y0)
for r,name in d['pads']:
    ax.add_patch(Rectangle((r[0],r[1]),r[2]-r[0],r[3]-r[1],facecolor='#f4c27a',edgecolor='#a66',lw=0.5,zorder=1))
    ax.text((r[0]+r[2])/2,(r[1]+r[3])/2,name,fontsize=5,ha='center',va='center',color='#733',zorder=2)
for xs,ys,xe,ye,ref in d['lines']:
    ax.plot([xs,xe],[ys,ye],color='#333' if ref!='board' else '#0a0',lw=1.0,zorder=3)
for r,text,kind in d['texts']:
    ax.add_patch(Rectangle((r[0],r[1]),r[2]-r[0],r[3]-r[1],facecolor='#9ecbff' if 'M' not in kind else '#d6b3ff',edgecolor='b',lw=0.8,alpha=0.6,zorder=4))
    ax.text((r[0]+r[2])/2,(r[1]+r[3])/2,text,fontsize=6,ha='center',va='center',zorder=5)
ax.set_xticks(range(int(x0),int(x1)+1)); ax.set_yticks(range(int(y0),int(y1)+1)); ax.grid(True,lw=0.3,color='#bbb'); ax.tick_params(labelsize=7,direction='in',pad=-18)
fig.savefig(sys.argv[2],dpi=dpi)
