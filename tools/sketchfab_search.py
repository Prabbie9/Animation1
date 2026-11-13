"""Search Sketchfab for downloadable CC0 / CC-BY models (auth injected by the proxy).
python3 tools/sketchfab_search.py "query" [count]"""
import json, sys, urllib.request, urllib.parse
q = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
out = []
for lic in ('cc0', 'by'):
    url = 'https://api.sketchfab.com/v3/search?' + urllib.parse.urlencode(dict(
        type='models', q=q, downloadable='true', license=lic, count=n, sort_by='-likeCount'))
    with urllib.request.urlopen(url, timeout=60) as r:
        d = json.load(r)
    for m in d.get('results', []):
        arch = m.get('archives') or {}
        gl = arch.get('glb') or arch.get('gltf') or {}
        out.append((m.get('likeCount', 0), lic, m['uid'], m['name'][:48], m.get('faceCount'),
                    (gl.get('size') or 0) // 1_000_000, (m.get('user') or {}).get('username'),
                    m.get('license', {}).get('label') if isinstance(m.get('license'), dict) else m.get('license')))
for o in sorted(out, reverse=True):
    print(f'{o[0]:5d} {o[1]:3s} {o[2]} {o[3]:48s} faces={o[4]} glbMB={o[5]} by={o[6]}')
