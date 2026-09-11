"""Portable, read-only map: the identical viewer bytes plus a data bundle."""
import json
from .server import WEB

SCRIPTS = ('cytoscape.min.js', 'graph.js', 'map-view.js', 'app.js')

def render_export(bundle: dict) -> str:
    html=(WEB/'index.html').read_text(encoding='utf-8')
    css=(WEB/'style.css').read_text(encoding='utf-8')
    payload=json.dumps(bundle,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+css+'</style>')
    for i,name in enumerate(SCRIPTS):
        script=(WEB/name).read_text(encoding='utf-8').replace('</script','<\\/script')
        data='<script id="threadline-data" type="application/json">'+payload+'</script>' if i==0 else ''
        html=html.replace('<script src="'+name+'" defer></script>',data+'<script>'+script+'</script>')
    return html
