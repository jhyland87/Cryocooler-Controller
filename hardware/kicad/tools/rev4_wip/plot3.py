"""All copper layers in one picture: plot3.py in.json out.png [px_per_mm] [layers e.g. FBI]"""
import sys, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
d=json.load(open(sys.argv[1])); ppm=float(sys.argv[3]) if len(sys.argv)>3 else 120; show=sys.argv[4] if len(sys.argv)>4 else 'FBI'
x0,y0,x1,y1=d['win']; w=x1-x0; h=y1-y0; dpi=100
fig=plt.figure(figsize=(w*ppm/dpi,h*ppm/dpi),dpi=dpi); ax=fig.add_axes([0,0,1,1]); ax.set_xlim(x0,x1); ax.set_ylim(y1,y0)
lw=lambda mm: mm*ppm*72/dpi
col={'F.Cu':'#d62728','B.Cu':'#1f5fd4','In2.Cu':'#2ca02c','In1.Cu':'#9467bd'}; key={'F.Cu':'F','B.Cu':'B','In2.Cu':'I','In1.Cu':'G'}
def short(n): return n.replace('/General Purpose IO/','').replace('Net-(','').replace(')','').replace('/Cold Head Temp/','')[:9]
for l,t,r,btm,layer,net,name in d['pads']:
    if layer!='T' and layer not in show: continue
    c={'F':'#ffb3b3','B':'#b3ccff','T':'#d9c2f0'}[layer]
    ax.add_patch(Rectangle((l,t),r-l,btm-t,facecolor=c,edgecolor='k',lw=0.6,alpha=0.8,zorder=3 if layer=='F' else 1))
    ax.text((l+r)/2,(t+btm)/2,name+'\n'+short(net),fontsize=max(4,ppm/22),ha='center',va='center',zorder=8)
for xs,ys,xe,ye,wd,layer,net in d['tracks']:
    if key.get(layer,'?') not in show: continue
    ax.plot([xs,xe],[ys,ye],color=col[layer],lw=lw(wd),alpha=0.55,zorder=2,solid_capstyle='round')
    if ((xe-xs)**2+(ye-ys)**2)**.5>1.0: ax.text((xs+xe)/2,(ys+ye)/2,short(net),fontsize=max(4,ppm/26),color=col[layer],ha='center',va='center',zorder=9)
for x,y,dia,net in d['vias']:
    ax.add_patch(Circle((x,y),dia/2,facecolor='#fff7a8',edgecolor='k',lw=0.6,zorder=5))
    ax.text(x,y,short(net)[:6],fontsize=max(3.5,ppm/30),ha='center',va='center',zorder=9)
ax.set_xticks([x0+i*0.5 for i in range(int(w*2)+1)]); ax.set_yticks([y0+i*0.5 for i in range(int(h*2)+1)]); ax.grid(True,lw=0.3,color='#999')
ax.tick_params(labelsize=7,direction='in',pad=-22)
fig.savefig(sys.argv[2],dpi=dpi)
