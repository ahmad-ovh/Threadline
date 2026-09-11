"""New, explicit example games. No claim to contain THRESHOLD source."""
from pathlib import Path
import json
import os
import shutil
import subprocess
from .model import ContractError
from .scanner import Scanner, write_feature
from .store import Store

TEMPLATES=Path(__file__).parent/'demo_templates'
DEMO_NAMES={'lantern-harbor':'Lantern Harbor','orbit-courier':'Orbit Courier'}

def setup_demos(store: Store) -> list[dict]:
    projects=[]
    for ident,name in DEMO_NAMES.items():
        directory=store.directory/'workspaces'/ident
        if not directory.exists():
            shutil.copytree(TEMPLATES/ident,directory)
            (directory/'.threadline-demo-marker').write_text('threadline-example-v1',encoding='utf-8')
            seed=json.loads((directory/'features.seed.json').read_text(encoding='utf-8'))
            for feature in seed['features']:
                write_feature(directory,feature['id'],feature['name'],feature['files'],feature['description'],'example-author')
            # Local Git provenance for the examples. Never configure or commit user repositories.
            try:
                args=['git','-C',str(directory)]
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                subprocess.run(args+['init','-q'],check=True,capture_output=True,timeout=10,creationflags=creationflags)
                subprocess.run(args+['add','.'],check=True,capture_output=True,timeout=10,creationflags=creationflags)
                subprocess.run(args+['-c','user.name=Threadline Demo','-c','user.email=demo@example.invalid',
                                    '-c','commit.gpgsign=false','commit','-qm','Example game baseline'],check=True,capture_output=True,timeout=10,creationflags=creationflags)
            except (OSError,subprocess.SubprocessError): pass
        project=store.register(ident,name,str(directory),demo=True)
        result=Scanner(store,ident).scan('Playable example baseline',actor='example setup')
        if not store.checkpoints(ident):
            store.checkpoint(ident,'Playable baseline','New example game; not the THRESHOLD source.')
        projects.append(project)
    return projects

def apply_demo_change(store: Store, project_id: str) -> dict:
    project=store.project(project_id)
    expected=(store.directory/'workspaces'/project_id).resolve()
    root=Path(project['root']).resolve() if project.get('root') else None
    if not project['demo'] or project_id not in DEMO_NAMES or root!=expected or not (root/'.threadline-demo-marker').is_file():
        raise ContractError('Scripted changes are allowed only in disposable bundled-example workspaces')
    if project_id=='lantern-harbor':
        file=root/'src/narrative/dialogue.js'
        added=root/'src/narrative/journal.js'
        changed=added.exists()
        if changed:
            file.write_text((TEMPLATES/project_id/'src/narrative/dialogue.js').read_text(encoding='utf-8'),encoding='utf-8')
            added.unlink()
            message='Removed the example memory journal integration'
        else:
            added.write_text("// Example change: an inspectable summary, separated from state mutation.\nexport function formatJournal(memory) {\n  return memory.events.length ? 'JOURNAL · ' + memory.events.map((event, i) => `${i+1}. ${event}`).join(' | ') : 'JOURNAL · No shared history yet.';\n}\n",encoding='utf-8')
            text=file.read_text(encoding='utf-8')
            text="import { formatJournal } from './journal.js';\n"+text
            text=text.replace('return memorySummary(memory);','return formatJournal(memory);')
            file.write_text(text,encoding='utf-8')
            message='Added a memory journal and connected dialogue to it'
    else:
        file=root/'src/engine/core.js';added=root/'src/engine/beacon.js';changed=added.exists()
        if changed:
            file.write_text((TEMPLATES/project_id/'src/engine/core.js').read_text(encoding='utf-8'),encoding='utf-8');added.unlink()
            message='Removed the example navigation beacon'
        else:
            added.write_text("import { CARGO, STATION } from '../world/map.js';\nexport function beaconHint(state) {\n  const target = state.carrying ? STATION : CARGO;\n  return `BEACON · Target sector ${target[0]+1}, ${target[1]+1}. ${state.energy} energy remaining.`;\n}\n",encoding='utf-8')
            text="import { beaconHint } from './beacon.js';\n"+file.read_text(encoding='utf-8')
            text=text.replace("return state.carrying ? 'Cargo secured. Navigate to the green station.' : 'Find the gold cargo marker.';","return beaconHint(state);")
            file.write_text(text,encoding='utf-8')
            message='Added a navigation beacon shared with the world map'
    return {'summary':message,'enabled':not changed,'actor':'scripted example change (not a live AI call)'}


def live_build_steps(store: Store, project_id: str) -> list[dict]:
    """A reversible, explicitly scripted refactor in disposable example roots only.

    These are real file edits. The server does NOT publish graph frames or request
    scans for them: the ordinary filesystem observer discovers each accepted batch.
    """
    project = store.project(project_id)
    root = Path(project['root']).resolve() if project.get('root') else None
    expected = (store.directory / 'workspaces' / project_id).resolve()
    if (not project['demo'] or project_id not in DEMO_NAMES or root != expected
            or not (root / '.threadline-demo-marker').is_file()):
        raise ContractError('Live example edits are allowed only in disposable bundled-example workspaces')
    if project_id == 'lantern-harbor':
        entry = 'src/narrative/dialogue.js'
        helper = 'src/journal/format.js'
        module = 'src/journal'
        baseline = (TEMPLATES / project_id / entry).read_text(encoding='utf-8')
        first = ("// Extracted journal formatter; no state mutation.\n"
                 "export function formatJournal(memory) {\n"
                 "  return memory.events.length ? 'JOURNAL · ' + memory.events.join(' | ') : 'No shared history yet.';\n"
                 "}\n")
        connected = "import { formatJournal } from '../journal/format.js';\n" + baseline.replace('return memorySummary(memory);', 'return formatJournal(memory);')
        refined = first.replace("memory.events.join(' | ')", "numberedEvents(memory).join(' | ')") + ("\nexport function numberedEvents(memory) {\n  return memory.events.map((event, index) => `${index + 1}. ${event}`);\n}\n")
        name = 'journal'
    else:
        entry = 'src/engine/core.js'
        helper = 'src/navigation/beacon.js'
        module = 'src/navigation'
        baseline = (TEMPLATES / project_id / entry).read_text(encoding='utf-8')
        first = ("import { CARGO, STATION } from '../world/map.js';\n"
                 "export function beaconHint(state) {\n"
                 "  const target = state.carrying ? STATION : CARGO;\n"
                 "  return `BEACON · Target sector ${target[0]+1}, ${target[1]+1}.`;\n"
                 "}\n")
        connected = "import { beaconHint } from '../navigation/beacon.js';\n" + baseline.replace("return state.carrying ? 'Cargo secured. Navigate to the green station.' : 'Find the gold cargo marker.';", 'return beaconHint(state);')
        refined = first.replace('${target[1]+1}.', '${target[1]+1}. ${distanceToTarget(state, target)} sectors away.') + ("\nexport function distanceToTarget(state, target) {\n  return Math.abs((state.x || 0) - target[0]) + Math.abs((state.y || 0) - target[1]);\n}\n")
        name = 'navigation'
    if (root / helper).exists():
        return [{'summary': 'Disconnecting the extracted ' + name + ' component', 'path': entry, 'text': baseline},
                {'summary': 'Removing the unused ' + name + ' component', 'path': helper, 'text': None, 'prune': module}]
    return [{'summary': 'Creating the ' + name + ' component', 'path': helper, 'text': first},
            {'summary': 'Connecting the game to ' + name, 'path': entry, 'text': connected},
            {'summary': 'Refining the ' + name + ' implementation', 'path': helper, 'text': refined}]
