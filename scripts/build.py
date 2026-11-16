#!/usr/bin/env python3
"""Build a self-contained page; publish only public/ through GitHub Pages."""
from pathlib import Path
import json
import shutil
from refresh_sources import baseline_hash,canonical,read_baseline

ROOT=Path(__file__).resolve().parents[1]
def build():
    data=read_baseline();out=ROOT/'public';out.mkdir(exist_ok=True)
    markup=(ROOT/'src/body.html').read_text();css=(ROOT/'src/styles.css').read_text();js=(ROOT/'src/app.js').read_text()
    assert '</script' not in js.lower()
    config=dict(reviewedHash=baseline_hash(data),snapshotUrl='data/source-status.json',maxAgeHours=30)
    page='<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Canola white mold label guide with dated evidence, research and automatic source checks."><title>Canola White Mold Fungicide Guide</title><style>'+css+'</style></head><body>'+markup
    page+='<script type="application/json" id="audit-data">'+canonical(data).decode().replace('<','\\u003c')+'</script>'
    page+='<script type="application/json" id="saved-state">{"version":4,"auto":true}</script>'
    page+='<script type="application/json" id="cloud-config">'+json.dumps(config)+'</script>'
    page+='<script>'+js+'</script></body></html>'
    (out/'index.html').write_text(page);(out/'.nojekyll').write_text('')
    (out/'data').mkdir(exist_ok=True)
    status=ROOT/'data/source-status.json'
    if status.exists():
        snapshot=json.loads(status.read_text())
        if snapshot.get('reviewedHash')==config['reviewedHash']:
            shutil.copyfile(status,out/'data/source-status.json')
        else:
            (out/'data/source-status.json').unlink(missing_ok=True)
            print('Previous shared check excluded: reviewed dataset changed.')
    print(f'Built public/index.html: {len(data["products"])} profiles; {len(data["registry"])} federal records')
if __name__=='__main__':build()
