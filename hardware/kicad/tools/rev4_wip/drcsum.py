import json,collections,sys
d=json.load(open(sys.argv[1]))
c=collections.Counter((v['severity'],v['type']) for v in d.get('violations',[]))
for k,v in sorted(c.items()): print(k,v)
un=d.get('unconnected_items',[]); print('unconnected',len(un),'parity',len(d.get('schematic_parity',[])))
nets=collections.Counter()
import re
for u in un:
    m=re.search(r'\[(.*?)\]', u['items'][0]['description']); nets[m.group(1) if m else '?']+=1
print(dict(nets.most_common(60)))
for p in d.get('schematic_parity',[])[:12]: print('parity:', p['description'], [i['description'] for i in p.get('items',[])][:2])
