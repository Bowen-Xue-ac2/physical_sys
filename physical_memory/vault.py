"""Local memory, persistent wiki compilation and auditable lifecycle."""
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from .adapters import DOMAINS, digest, discover, extract, json_text, tokens

PHASES = {'intake': {'baseline','archive'}, 'baseline': {'plan','intake','archive'},
          'plan': {'execute','baseline','archive'}, 'execute': {'review','archive'},
          'review': {'revise','execute','archive'}, 'revise': {'plan','baseline','archive'},
          'archive': {'intake'}}


def now():
    return datetime.now(timezone.utc).isoformat()


def freshness(observed_at):
    if not observed_at:
        return 'undated'
    try:
        age = (date.today() - date.fromisoformat(observed_at[:10])).days
    except (ValueError, TypeError):
        return 'undated'
    return 'future-plan-or-date-check' if age < 0 else ('historical-needs-refresh' if age > 30 else 'recent-record-not-clinical-clearance')


class Vault:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = self.safe_path('vault')
        state = self.safe_path('vault/state')
        state.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(state / 'memory.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,path TEXT,hash TEXT,raw_path TEXT,
          extraction TEXT,imported_at TEXT,latest INTEGER DEFAULT 1,UNIQUE(path,hash));
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,path TEXT,locator TEXT,source_id TEXT,
          domain TEXT,kind TEXT,evidence_kind TEXT,observed_at TEXT,record_type TEXT,text TEXT,payload TEXT);
        CREATE TABLE IF NOT EXISTS membership(source_id TEXT,record_id TEXT,PRIMARY KEY(source_id,record_id));
        CREATE TABLE IF NOT EXISTS supersession(old_id TEXT,new_id TEXT,PRIMARY KEY(old_id,new_id));
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(key UNINDEXED,body);
        CREATE TABLE IF NOT EXISTS documents(key TEXT PRIMARY KEY,page TEXT,text TEXT,domain TEXT,
          observed_at TEXT,status TEXT,kind TEXT,refs TEXT);
        CREATE TABLE IF NOT EXISTS lifecycle_events(id TEXT PRIMARY KEY,at TEXT,previous TEXT,phase TEXT,reason TEXT);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
        ''')

    def safe_path(self, relative):
        p = (self.root / relative).resolve()
        try:
            p.relative_to(self.root)
        except ValueError as e:
            raise ValueError('path must remain in this project') from e
        return p

    def stats(self):
        return {k: self.db.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                for k,t in [('source_versions','sources'),('records','records'),('indexed_documents','documents')]}

    def log(self, operation, detail):
        p = self.safe_path('vault/wiki/log.md')
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(f'\n## [{now()}] {operation}\n\n{detail}\n')

    def ingest(self):
        # Validate every input before committing any source. Source files never written here.
        prepared = []
        memory_ids = {}
        for p in discover(self.root):
            rel = p.relative_to(self.root).as_posix()
            blob = p.read_bytes()
            h = digest(blob)
            if self.db.execute('SELECT 1 FROM sources WHERE path=? AND hash=? AND latest=1',(rel,h)).fetchone():
                prepared.append((rel,h,None,None,None))
                continue
            try:
                fragments, status = extract(rel,blob)
            except (ValueError, UnicodeError, KeyError, OSError) as e:
                raise ValueError(f'cannot import {rel}: {e}') from e
            if rel == 'data/memory/events.jsonl':
                for fragment in fragments:
                    rid = fragment['payload'].get('id')
                    if not rid:
                        raise ValueError('memory event requires an id')
                    known = self.db.execute('SELECT text FROM records WHERE id=?',(rid,)).fetchone()
                    previous = memory_ids.get(rid, known['text'] if known else fragment['text'])
                    if previous != fragment['text']:
                        raise ValueError('memory id collision: append a correction, do not replace the event')
                    memory_ids[rid] = fragment['text']
            prepared.append((rel,h,blob,fragments,status))
        added = 0
        with self.db:
            current_paths = [x[0] for x in prepared]
            for row in self.db.execute('SELECT id,path FROM sources WHERE latest=1').fetchall():
                if row['path'] not in current_paths:
                    self.db.execute('UPDATE sources SET latest=0 WHERE id=?',(row['id'],))
            for rel,h,blob,fragments,status in prepared:
                if blob is None:
                    continue
                sid = digest(rel + '\n' + h)
                raw_rel = f'vault/raw/{h}{Path(rel).suffix.lower()}'
                snapshot = self.safe_path(raw_rel)
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                if snapshot.exists():
                    if digest(snapshot.read_bytes()) != h:
                        raise ValueError('immutable snapshot was modified; repair explicitly before import')
                else:
                    with snapshot.open('xb') as f:
                        f.write(blob)
                self.db.execute('UPDATE sources SET latest=0 WHERE path=?',(rel,))
                self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,1)',(sid,rel,h,raw_rel,status,now()))
                self.db.execute('UPDATE sources SET latest=1 WHERE id=?',(sid,))
                for r in fragments:
                    rid = r['payload'].get('id') if rel == 'data/memory/events.jsonl' else None
                    rid = rid or digest(rel + '\n' + r['locator'] + '\n' + r['text'])
                    self.db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (rid,rel,r['locator'],sid,r['domain'],r['kind'],r['evidence_kind'],r['observed_at'],r['record_type'],r['text'],json_text(r['payload'])))
                    self.db.execute('INSERT OR IGNORE INTO membership VALUES(?,?)',(sid,rid))
                added += 1
            self._resolve_corrections()
        self._source_pages()
        if added:
            self.log('ingest', f'{added} source versions imported; originals unchanged.')
        return {'added_sources':added,'discovered_sources':len(prepared),
                'pending_extraction':[r['path'] for r in self.db.execute("SELECT path FROM sources WHERE latest=1 AND extraction='pending-text-extraction'")], **self.stats()}

    def _resolve_corrections(self):
        rows = self.db.execute('SELECT * FROM records ORDER BY observed_at,path,locator').fetchall()
        for row in rows:
            p = json.loads(row['payload'])
            if p.get('supersedes'):
                if not self.db.execute('SELECT 1 FROM records WHERE id=?',(p['supersedes'],)).fetchone():
                    raise ValueError(f"correction target not found: {p['supersedes']}")
                self.db.execute('INSERT OR IGNORE INTO supersession VALUES(?,?)',(p['supersedes'],row['id']))
            if p.get('supersedes_record_type'):
                for old in rows:
                    if old['domain']==row['domain'] and old['record_type']==p['supersedes_record_type'] and old['id']!=row['id']:
                        self.db.execute('INSERT OR IGNORE INTO supersession VALUES(?,?)',(old['id'],row['id']))

    def records(self, include_history=False):
        rows = self.db.execute('''SELECT r.*,s.hash,s.raw_path FROM records r
          JOIN sources s ON s.id=r.source_id ORDER BY r.observed_at,r.path,r.locator''').fetchall()
        superseded = {r[0] for r in self.db.execute('SELECT old_id FROM supersession')}
        active = {r[0] for r in self.db.execute('SELECT m.record_id FROM membership m JOIN sources s ON m.source_id=s.id WHERE s.latest=1')}
        retired_paths = {json.loads(r['payload']).get('supersedes_plan_file') for r in rows if r['id'] in active}
        result=[]
        for row in rows:
            r=dict(row)
            r['status']='superseded' if r['id'] in superseded or r['path'] in retired_paths else ('current-source' if r['id'] in active else 'historical-source-version')
            if include_history or r['status']=='current-source':
                result.append(r)
        return result

    def _ref(self,r):
        return {k:r[k] for k in ('path','locator','hash','raw_path','observed_at','evidence_kind')}

    def _write_page(self, rel, text):
        p = self.safe_path('vault/wiki/'+rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        header='<!-- generated-by: physical_memory; edit authored pages instead -->\n'
        text=header+text
        if p.exists():
            old=p.read_text('utf-8')
            if not old.startswith(header):
                raise ValueError(f'refusing to overwrite authored page: {rel}')
            if old==text:
                return
            history=self.safe_path(f'vault/history/{digest(rel)[:16]}/{digest(old)}.md')
            history.parent.mkdir(parents=True,exist_ok=True)
            if not history.exists():
                history.write_text(old,'utf-8')
        p.write_text(text,'utf-8')

    def _source_pages(self):
        for s in self.db.execute('SELECT * FROM sources').fetchall():
            fragments=self.db.execute('SELECT r.* FROM records r JOIN membership m ON m.record_id=r.id WHERE m.source_id=? ORDER BY locator',(s['id'],)).fetchall()
            text=f"# Source: {s['path']}\n\nVersion: `{s['hash']}`\n\nExtraction: {s['extraction']}\n\n[Immutable original](../../raw/{Path(s['raw_path']).name})\n\n"
            for r in fragments:
                text+=f"## {r['locator']} · {r['kind']} · {r['observed_at'] or 'undated'}\n\n```text\n{r['text']}\n```\n\n"
            self._write_page(f"sources/{s['id']}.md",text)

    def compile(self):
        live=self.records()
        domains=[x for x in DOMAINS if x!='memory']
        for domain in domains:
            rs=[r for r in live if r['domain']==domain and r['kind']!='reference']
            text=f'# {domain} — cited records\n\nLast known records are not present-day measurements. Plans, estimates and self-reports retain their source labels. null means unknown.\n\n'
            for r in rs:
                text+=f"## {r['record_type'] or r['kind']} · {r['observed_at'] or 'undated'}\n\nKind: {r['kind']}; evidence: {r['evidence_kind']}; freshness: {freshness(r['observed_at'])}.\n\n[Source](../sources/{r['source_id']}.md) · `{r['path']}#{r['locator']}`\n\n```json\n{r['text']}\n```\n\n"
            if not rs:
                text+='No dated records available; current status unknown.\n'
            self._write_page(f'domains/{domain}.md',text)
        summary='# Last-known status / 最近已知状态\n\nClinical clearance: false. Calendar dates do not prove that planned sessions were performed.\n\n'
        for d in domains:
            rs=[r for r in live if r['domain']==d and r['kind']!='reference']
            dates=[r['observed_at'] for r in rs if r['observed_at']]
            latest=max(dates) if dates else None
            summary+=f"- [{d}](../domains/{d}.md): {len(rs)} records; latest {latest or 'unknown'}; {freshness(latest)}.\n"
        summary+='\nRead [personal synthesis](../entities/personal-context.md) when present; its claims require citations and explicit dates.\n'
        # The optional synthesis link is added only once the authored page exists.
        if not self.safe_path('vault/wiki/entities/personal-context.md').exists():
            summary=summary.split('\nRead [personal synthesis]')[0]+'\n'
        self._write_page('overviews/current-status.md',summary)
        self._index()
        self.reindex()
        self.log('compile',f'{len(live)} current-source fragments compiled; authored pages preserved.')
        return self.stats()

    def _index(self):
        pages=sorted(self.safe_path('vault/wiki').rglob('*.md'))
        text='# physical_sys Knowledge Index\n\nRaw originals → cited sources → persistent domain/context synthesis → retrieve.\n\n'
        for p in pages:
            rel=p.relative_to(self.base/'wiki').as_posix()
            if rel in {'index.md','log.md'}:
                continue
            if rel.startswith('sources/'):
                sid=p.stem
                s=self.db.execute('SELECT latest,path FROM sources WHERE id=?',(sid,)).fetchone()
                if not s or not s['latest']:
                    continue
                title=s['path']
            else:
                title=next((l[2:] for l in p.read_text('utf-8').splitlines() if l.startswith('# ')),rel)
            text+=f'- [{title}]({rel})\n'
        self._write_page('index.md',text)

    def reindex(self):
        rows=self.records(include_history=True)
        with self.db:
            self.db.execute('DELETE FROM documents')
            self.db.execute('DELETE FROM search')
            for r in rows:
                self._doc(r['id'],f"wiki/sources/{r['source_id']}.md",r['text'],r['domain'],r['observed_at'],r['status'],r['kind'],[self._ref(r)])
            # Authored synthesis is indexed alongside records, never overwritten.
            for p in sorted(self.safe_path('vault/wiki').rglob('*.md')):
                self.safe_path(p.relative_to(self.root))
                text=p.read_text('utf-8')
                if text.startswith('<!-- generated-by:') or p.name=='log.md':
                    continue
                refs=[]
                for s in self.db.execute('SELECT * FROM sources WHERE latest=1').fetchall():
                    if s['hash'] in text or s['id'] in text:
                        refs.append({'path':s['path'],'locator':'see-authored-page','hash':s['hash'],'raw_path':s['raw_path'],'observed_at':None,'evidence_kind':'authored-synthesis-see-claims'})
                for i,chunk in enumerate(self._chunks(text)):
                    self._doc(f'wiki:{p.relative_to(self.root)}:{i}',p.relative_to(self.base).as_posix(),chunk,'synthesis',None,'current-source','synthesis',refs)
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('indexed_corpus',?)",(self._corpus_signature(),))

    def _corpus_signature(self):
        versions=[tuple(r) for r in self.db.execute('SELECT id,latest FROM sources ORDER BY id')]
        corrections=[tuple(r) for r in self.db.execute('SELECT old_id,new_id FROM supersession ORDER BY old_id,new_id')]
        return digest(json_text([versions,corrections]))

    def _chunks(self,text):
        lines=text.splitlines()
        return ['\n'.join(lines[i:i+30]) for i in range(0,len(lines),30)]

    def _doc(self,key,page,text,domain,observed_at,status,kind,refs):
        self.db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(key,page,text,domain,observed_at,status,kind,json_text(refs)))
        self.db.execute('INSERT INTO search VALUES(?,?)',(key,' '.join(tokens(text))))

    def retrieve(self,query,domain=None,include_history=False,limit=5,include_reference=False):
        indexed=self.db.execute("SELECT value FROM metadata WHERE key='indexed_corpus'").fetchone()
        if not indexed or indexed['value'] != self._corpus_signature():
            raise ValueError('retrieval index is out of date; run compile after ingest')
        query_tokens=tokens(query,aliases=True)
        if not query_tokens:
            return []
        match=' OR '.join('"'+x+'"' for x in query_tokens)
        sql='SELECT d.*,bm25(search) AS rank FROM search JOIN documents d ON search.key=d.key WHERE search MATCH ?'
        params=[match]
        if not include_history:
            sql+=" AND d.status='current-source'"
        if not include_reference:
            sql+=" AND d.kind!='reference'"
        if domain:
            sql+=' AND d.domain=?'
            params.append(domain)
        sql+=' ORDER BY rank LIMIT ?'
        count=max(1,min(int(limit),50))
        params.append(300)
        native=set(tokens(query))
        candidates=list(self.db.execute(sql,params))
        candidates.sort(key=lambda r: (len(native.intersection(tokens(r['text']))),
                        query.casefold() in r['text'].casefold(), -r['rank']),reverse=True)
        result=[]
        for row in candidates[:count]:
            r=dict(row)
            text=r['text']
            exact=query.casefold()
            pos=text.casefold().find(exact)
            if pos<0:
                positions=[text.casefold().find(t) for t in tokens(query,aliases=True) if t in text.casefold()]
                pos=min(positions) if positions else 0
            start=max(0,pos-100)
            result.append({'id':r['key'],'page':r['page'],'excerpt':text[start:start+700],
                'domain':r['domain'],'kind':r['kind'],'status':r['status'],
                'observed_at':r['observed_at'],'freshness':freshness(r['observed_at']),
                'source_refs':json.loads(r['refs'])})
        return result

    def remember(self,text,*,domain,kind,evidence_kind,observed_at,source_ref,supersedes=None):
        if domain not in DOMAINS or kind not in {'fact','observation','decision','hypothesis','goal','correction'}:
            raise ValueError('invalid memory domain or kind')
        date.fromisoformat(observed_at)
        if not text.strip() or not source_ref.strip() or evidence_kind not in {'user_reported','clinician_reported','measured','calculated','estimated','inferred','record_state'}:
            raise ValueError('memory requires text, provenance and a supported evidence kind')
        p=self.safe_path('data/memory/events.jsonl')
        existing=[json.loads(l) for l in p.read_text('utf-8-sig').splitlines() if l.strip()] if p.exists() else []
        if supersedes and not any(r['id']==supersedes for r in existing) and not self.db.execute('SELECT 1 FROM records WHERE id=?',(supersedes,)).fetchone():
            raise ValueError('correction target does not exist')
        if kind=='correction' and not supersedes:
            raise ValueError('correction needs a supersedes target')
        r={'id':str(uuid.uuid4()),'observed_at':observed_at,'recorded_at':now(),'domain':domain,
            'kind':kind,'evidence_kind':evidence_kind,'source_ref':source_ref,'text':text}
        if supersedes:
            r['supersedes']=supersedes
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('a',encoding='utf-8') as f:
            if p.stat().st_size and not p.read_bytes().endswith(b'\n'):
                f.write('\n')
            f.write(json_text(r)+'\n')
        self.log('remember',f"{r['id']} · {domain} · {kind}; source {source_ref}")
        return r['id']

    def review(self,start,end):
        if date.fromisoformat(start)>date.fromisoformat(end):
            raise ValueError('start must be before end')
        rs=[r for r in self.records() if r['observed_at'] and start<=r['observed_at'][:10]<=end and r['kind']!='reference']
        summaries={}
        for d in DOMAINS:
            xs=[r for r in rs if r['domain']==d]
            summaries[d]={'record_count':len(xs),'plan_count':sum(r['kind']=='plan' for r in xs),
                'observation_count':sum(r['kind']=='observation' for r in xs),
                'status':'records-present-not-clinical-clearance' if xs else 'unknown',
                'source_refs':[self._ref(r) for r in xs]}
        return {'window':{'start':start,'end':end},'domains':summaries,'clinical_clearance':False,
            'readiness':'unassessed','action_candidates':[],
            'limits':['Counts are source records, not workout sessions or adherence. No averaging across mixed metrics.',
                      'No current clinical or recovery inference from historical records.']}

    def lifecycle(self):
        last=self.db.execute('SELECT * FROM lifecycle_events ORDER BY rowid DESC LIMIT 1').fetchone()
        return {'phase':last['phase'] if last else 'intake','last_transition':dict(last) if last else None,
                'allowed_next':sorted(PHASES[last['phase'] if last else 'intake']),
                'clinical_clearance':False,'readiness':'unassessed',**self.stats()}

    def transition(self,target,reason):
        current=self.lifecycle()['phase']
        if target not in PHASES[current] or not reason.strip():
            raise ValueError('invalid lifecycle transition or empty reason')
        event={'id':str(uuid.uuid4()),'at':now(),'previous':current,'phase':target,'reason':reason}
        p=self.safe_path('vault/state/checkpoints/'+event['id']+'.json')
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(event,ensure_ascii=False,indent=2)+'\n','utf-8')
        with self.db:
            self.db.execute('INSERT INTO lifecycle_events VALUES(?,?,?,?,?)',tuple(event.values()))
        self.log('lifecycle',f'{current} → {target}: {reason}')
        return self.lifecycle()

    def lint(self):
        errors=[]
        for s in self.db.execute('SELECT * FROM sources').fetchall():
            p=self.safe_path(s['raw_path'])
            if not p.exists() or digest(p.read_bytes())!=s['hash']:
                errors.append(f"snapshot integrity: {s['path']}")
        for p in self.safe_path('vault/wiki').rglob('*.md'):
            self.safe_path(p.relative_to(self.root))
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text('utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                target=(p.parent/link.split('#')[0]).resolve()
                if not target.is_relative_to(self.root) or not target.exists():
                    errors.append(f'missing/outside link: {p.name} → {link}')
        pending=[r[0] for r in self.db.execute("SELECT path FROM sources WHERE latest=1 AND extraction='pending-text-extraction'")]
        return {'errors':errors,'pending_extraction':pending,'clinical_validation':False,**self.stats()}
