#!/usr/bin/env python3
"""Small synthetic measurement, not a large-repository throughput guarantee."""
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from threadline.store import Store
from threadline.scanner import Scanner


def main():
    count=300
    with tempfile.TemporaryDirectory(prefix='threadline-bench-') as tmp:
        base=Path(tmp);root=base/'source';root.mkdir()
        for i in range(count):
            (root/f'module_{i}.py').write_text((f'from module_{i-1} import value as prior\n' if i else '')+f'def value():\n    return {i}\n',encoding='utf-8')
        store=Store(base/'private');store.register('synthetic','Synthetic 300-file fixture',str(root));scanner=Scanner(store,'synthetic')
        runs=[]
        for label in ('initial','unchanged','one-file-edit'):
            if label=='one-file-edit':(root/'module_150.py').write_text('from module_149 import value as prior\ndef value():\n    return 151\n',encoding='utf-8')
            start=time.perf_counter();result=scanner.scan(label);elapsed=(time.perf_counter()-start)*1000
            # Scanner returns per-run stats, while unchanged snapshots intentionally retain prior identity.
            runs.append({'name':label,'wallMs':round(elapsed,2),'changed':result['changed'],'revision':result['revision'],'stats':result.get('scanStats')})
        output={'fixtureFiles':count,'environment':{'python':platform.python_version(),'platform':platform.platform()},'runs':runs,'notes':['Synthetic local files, a single scan sequence; not statistically controlled.','No LLM or token usage benchmark.','The steady observer reuses file analysis, but still enumerates files and builds/validates the current graph.']}
        print(json.dumps(output,indent=2))

if __name__=='__main__':main()
