"""Read-only adapters; source text is data, never executable instructions."""
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

DOMAINS = ('profile', 'training', 'nutrition', 'body', 'sleep', 'recovery', 'rehab', 'memory')
SUFFIXES = {'.json', '.jsonl', '.md', '.txt', '.docx', '.xlsx', '.pdf', '.png', '.jpg', '.jpeg'}


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def classify(record, path):
    if not isinstance(record, dict):
        return 'reference', 'unknown'
    if record.get('kind'):
        return record['kind'], record.get('evidence_kind', 'unknown')
    m = str(record.get('measurement_type', 'unknown'))
    t = str(record.get('record_type', ''))
    if any(s in m for s in ('program_decision', 'planning', 'not_completed', 'not_measured')) or 'macrocycle' in t or 'prescription' in t:
        return 'plan', m
    if 'correction' in t or record.get('supersedes_record_type'):
        return 'correction', m
    if path.endswith('goals.json'):
        return 'goal', m
    if path.endswith('profile.json'):
        return 'profile', 'mixed-see-field-labels'
    if 'deferred' in t:
        return 'decision', m
    return 'observation', m


def _fragment(path, locator, value, fallback_domain, reference=False):
    data = value if isinstance(value, dict) else {}
    kind, evidence = classify(data, path) if not reference else ('reference', 'document-not-personal-measurement')
    return {'locator': locator, 'text': json_text(value) if isinstance(value, (dict, list)) else str(value),
            'payload': data, 'domain': data.get('domain', fallback_domain), 'kind': kind,
            'evidence_kind': evidence, 'observed_at': data.get('observed_at') or data.get('date') or data.get('updated_at'),
            'record_type': data.get('record_type', ''),
            'supersedes': data.get('supersedes'), 'supersedes_record_type': data.get('supersedes_record_type')}


def extract(path, content):
    """Return locatable fragments plus an explicit extraction status."""
    p = Path(path)
    parts = p.parts
    domain = parts[1] if len(parts) > 1 and parts[0] == 'data' and parts[1] in DOMAINS else 'reference'
    suffix = p.suffix.lower()
    if suffix in {'.json', '.jsonl'}:
        text = content.decode('utf-8-sig')
        if suffix == '.json':
            value = json.loads(text)
            if not isinstance(value, (dict, list)):
                raise ValueError('JSON root must be an object or array')
            return [_fragment(path, '$', value, domain)], 'extracted'
        result = []
        for i, line in enumerate(text.splitlines(), 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f'{path}:{i}: JSONL record must be an object')
                result.append(_fragment(path, f'L{i}', value, domain))
        return result, 'extracted'
    if suffix in {'.md', '.txt'}:
        lines = content.decode('utf-8-sig').splitlines()
        result = []
        # Small source chunks retain original line locations, not synthetic facts.
        for start in range(0, len(lines), 24):
            block = '\n'.join(lines[start:start+24])
            if block.strip():
                result.append(_fragment(path, f'L{start+1}-L{min(start+24,len(lines))}', block, domain, True))
        return result, 'extracted'
    if suffix == '.docx':
        import io
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            tree = ET.fromstring(z.read('word/document.xml'))
            w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = [''.join(t.text or '' for t in p.iter(w+'t')) for p in tree.iter(w+'p')]
            return [_fragment(path, f'paragraph:{i}', text, domain, True)
                    for i,text in enumerate(paragraphs,1) if text.strip()], 'text-only-no-images'
    if suffix == '.xlsx':
        import io
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns)]
            wb = ET.fromstring(z.read('xl/workbook.xml'))
            rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
            result = []
            for sheet in wb.findall('m:sheets/m:sheet', ns):
                rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
                target = targets[rid]
                target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                tree = ET.fromstring(z.read(target))
                for row in tree.findall('m:sheetData/m:row', ns):
                    cells = []
                    for c in row.findall('m:c', ns):
                        v = c.find('m:v', ns)
                        value = v.text if v is not None else ''
                        if c.attrib.get('t') == 's' and value:
                            value = strings[int(value)]
                        elif c.attrib.get('t') == 'inlineStr':
                            value = ''.join(t.text or '' for t in c.findall('.//m:t',ns))
                        f = c.find('m:f', ns)
                        if f is not None:
                            value = f'formula={f.text}; cached={value}; not-recalculated'
                        if value:
                            cells.append(f"{c.attrib['r']}={value}")
                    if cells:
                        result.append(_fragment(path, f"{sheet.attrib['name']}!row:{row.attrib['r']}", ' | '.join(cells),domain,True))
            return result, 'cells-and-cached-formulas-not-recalculated'
    return [], 'pending-text-extraction'


def discover(root):
    found = []
    for directory in ('data', 'alignment', 'outputs/training-plan', 'reports', 'imports'):
        base = root / directory
        if not base.exists():
            continue
        for p in sorted(base.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in SUFFIXES:
                continue
            if any(x.startswith('.') or x in {'node_modules','nutrition_engine','credentials'} for x in p.relative_to(root).parts):
                continue
            if any(x in p.name.lower() for x in ('token', 'secret', 'credential')):
                continue
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError as e:
                raise ValueError(f'source path escapes workspace: {p.name}') from e
            found.append(p)
    return found


ALIASES = {
    '左踝': 'left_ankle ankle mechanical_locking', '脚踝': 'ankle dorsiflexion',
    '卡住': 'mechanical_locking locking', '左膝': 'left_knee knee', '颌面': 'jaw facial asymmetry orofacial',
    '体态': 'posture asymmetry', '不对称': 'asymmetry', '体重': 'weight_kg weight',
    '力量': 'strength baseline squat bench', '深蹲': 'squat', '卧推': 'bench_press',
    '睡眠': 'sleep hours awakenings', '营养': 'nutrition calories protein',
    '目标': 'goal primary_goal', '康复': 'rehab pain', '恢复': 'recovery readiness',
}


def tokens(text, aliases=False):
    text = text.casefold()
    if aliases:
        text += ' ' + ' '.join(v for k,v in ALIASES.items() if k in text)
    words = re.findall(r'[a-z0-9_]+', text)
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        words.extend(run[i:i+2] for i in range(len(run)-1))
        if len(run) == 1:
            words.append(run)
    return sorted(set(words))
