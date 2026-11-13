"""Regenerate CREDITS.md from assets/manifest.json. python3 tools/make_credits.py"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
man = json.load(open(os.path.join(ROOT, 'assets', 'manifest.json')))
LIC = {'CC-BY-4.0': '[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)',
       'CC0-1.0': '[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)'}
lines = ['# Credits', '',
         'Third-party assets used in this project. CC BY 4.0 assets require attribution: keep this',
         'file with any distribution of the project and credit the authors below in the film credits',
         'or the video description. Changes made: rescaled to metres, re-oriented, wheels separated,',
         'textures resized to max 2048 px, materials adjusted for wet/night rendering.', '']
for src, title in (('sketchfab', 'Models (Sketchfab)'), ('polyhaven', 'Textures and HDRI (Poly Haven)')):
    lines += [f'## {title}', '', '| Asset | Author | Licence | Used as |', '|---|---|---|---|']
    for a in man['assets']:
        if a['source'] != src or a.get('unused'):
            continue
        lines.append(f"| [{a['title']}]({a['url']}) | {a['author']} | {LIC[a['license']]} | {a.get('use', '')} |")
    lines.append('')
unused = [a for a in man['assets'] if a.get('unused')]
if unused:
    lines += ['## Downloaded and evaluated but not used', '']
    lines += [f"- [{a['title']}]({a['url']}) by {a['author']}: {a['unused']}" for a in unused]
    lines.append('')
open(os.path.join(ROOT, 'CREDITS.md'), 'w').write('\n'.join(lines))
print('\n'.join(lines))
