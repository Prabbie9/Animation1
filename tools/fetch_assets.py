"""Download every asset listed in assets/manifest.json (re-runnable; skips files already present).

Sketchfab downloads need an API token: set SKETCHFAB_TOKEN (your token from
https://sketchfab.com/settings/password) if you are not behind an authenticating proxy.
Poly Haven downloads need no auth. Assets are committed to the repo already, so you only
need this script to re-create or update them.
"""
import json, os, sys, urllib.request, zipfile, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, 'assets', 'manifest.json')


def get(url, auth=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'asset-fetch/1.0'})
    tok = os.environ.get('SKETCHFAB_TOKEN')
    if auth and tok:
        req.add_header('Authorization', f'Token {tok}')
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def fetch_sketchfab(a):
    dst = os.path.join(ROOT, a['path'])
    if os.path.exists(dst):
        return 'present'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    info = json.loads(get(f"https://api.sketchfab.com/v3/models/{a['uid']}/download", auth=True))
    data = get(info['glb']['url'])
    with open(dst, 'wb') as f:
        f.write(data)
    return f'{len(data) // 1_000_000} MB'


def fetch_polyhaven(a):
    """a: {'id', 'kind': 'hdri'|'texture', 'res': '2k', 'maps': [...], 'path': dir or file}"""
    files = json.loads(get(f"https://api.polyhaven.com/files/{a['id']}"))
    a.setdefault('path', f"assets/polyhaven/{a['id']}")
    if a['kind'] == 'hdri':
        dst = os.path.join(ROOT, a['path'])
        if os.path.exists(dst):
            return 'present'
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        url = files['hdri'][a['res']]['exr' if dst.endswith('.exr') else 'hdr']['url']
        open(dst, 'wb').write(get(url))
        return 'ok'
    d = os.path.join(ROOT, a['path'])
    os.makedirs(d, exist_ok=True)
    got = []
    for m in a['maps']:
        if m not in files or a['res'] not in files[m]:
            continue
        opts = files[m][a['res']]
        fmt = 'jpg' if 'jpg' in opts else 'png'
        ent = opts[fmt]
        dst = os.path.join(d, f"{a['id']}_{m.lower()}_{a['res']}.{fmt}")
        if not os.path.exists(dst):
            open(dst, 'wb').write(get(ent['url']))
        got.append(m)
    return ','.join(got)


def main():
    man = json.load(open(MAN))
    only = set(sys.argv[1:])
    for a in man['assets']:
        if only and a['key'] not in only:
            continue
        try:
            r = fetch_sketchfab(a) if a['source'] == 'sketchfab' else fetch_polyhaven(a)
        except Exception as e:  # keep going; report at the end
            r = f'FAILED: {e}'
        print(f"{a['key']:24s} {r}")


if __name__ == '__main__':
    main()
