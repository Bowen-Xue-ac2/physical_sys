# All records below are fictional test fixtures, not personal observations.
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from physical_memory import Vault


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.v = Vault(self.root)
        self.addCleanup(self.v.db.close)

    def put(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def record(self, **kwargs):
        return json.dumps(kwargs, ensure_ascii=False) + '\n'

    def seed(self):
        self.put('data/profile/profile.json', '\ufeff' + json.dumps({
            'updated_at': '2000-08-16', 'fixture': True, 'status': 'synthetic_profile'}))
        self.put('data/rehab/rehab_log.jsonl', self.record(date='2000-08-15',
            record_type='symptoms', source='user_self_report', measurement_type='self_report',
            text='睡眠测试 sleep fixture_only_marker'))

    def test_snapshot_and_original_bytes_are_immutable_and_ingest_idempotent(self):
        self.seed()
        p = self.root / 'data/profile/profile.json'
        before = p.read_bytes()
        first = self.v.ingest()
        again = self.v.ingest()
        self.assertEqual(first['added_sources'], 2)
        self.assertEqual(again['added_sources'], 0)
        self.assertEqual(before, p.read_bytes())
        self.assertEqual(self.v.lint()['errors'], [])
        snapshots = list((self.root / 'vault/raw').glob('*'))
        self.assertEqual(len(snapshots), 2)
        self.assertIn(before, [s.read_bytes() for s in snapshots])

    def test_chinese_retrieval_cites_source_date_and_staleness(self):
        self.seed()
        self.v.ingest()
        self.v.compile()
        hits = self.v.retrieve('睡眠测试', domain='rehab')
        self.assertTrue(hits)
        self.assertTrue(any(x['source_refs'] for x in hits))
        self.assertTrue(any('data/rehab/rehab_log.jsonl' == r['path']
                            for x in hits for r in x['source_refs']))
        self.assertTrue(any(x['freshness'] == 'historical-needs-refresh' for x in hits))

    def test_revision_keeps_old_snapshot_but_current_query_excludes_old_claim(self):
        p = self.put('data/body/body_metrics.jsonl', self.record(date='2000-08-01', text='unique_old_marker'))
        self.v.ingest()
        p.write_text(self.record(date='2000-08-02', text='unique_new_marker'), 'utf-8')
        self.v.ingest()
        self.v.compile()
        self.assertEqual(self.v.retrieve('unique_old_marker'), [])
        self.assertTrue(self.v.retrieve('unique_old_marker', include_history=True))
        self.assertEqual(len(list((self.root / 'vault/raw').glob('*'))), 2)

    def test_explicit_supersession_and_plans_not_observations(self):
        a = dict(date='2000-08-15', record_type='old_baseline', text='unique_wrong_marker', measurement_type='estimated_1rm')
        b = dict(date='2000-08-16', record_type='correction', supersedes_record_type='old_baseline', text='unique_right_marker', measurement_type='self_report')
        c = dict(date='2000-08-16', record_type='macrocycle_decision', measurement_type='program_decision', text='planned jump')
        self.put('data/training/training_log.jsonl', ''.join(self.record(**r) for r in (a,b,c)))
        self.v.ingest()
        self.v.compile()
        self.assertFalse(self.v.retrieve('unique_wrong_marker'))
        review = self.v.review('2000-08-01', '2000-08-31')
        self.assertEqual(review['domains']['training']['plan_count'], 1)
        self.assertEqual(review['domains']['training']['record_count'], 2)
        self.assertFalse(review['clinical_clearance'])

    def test_bad_json_aborts_before_any_source_commit(self):
        self.put('data/body/good.json', '{"value": 1}')
        self.put('data/rehab/bad.jsonl', '{broken')
        with self.assertRaises(ValueError):
            self.v.ingest()
        self.assertEqual(self.v.stats()['source_versions'], 0)

    def test_authored_wiki_survives_compile_and_has_retrieval_citation(self):
        self.seed()
        self.v.ingest()
        text = '# 独立判断\n\n测试不确定性，独立内容 unique_authored_marker。\n\n[来源](../../raw/'
        snapshot = next((self.root / 'vault/raw').glob('*')).name
        p = self.put('vault/wiki/entities/authored.md', text + snapshot + ')\n')
        self.v.compile()
        self.assertEqual(p.read_text('utf-8'), text + snapshot + ')\n')
        self.assertTrue(self.v.retrieve('unique_authored_marker'))

    def test_remember_and_correction_are_append_only(self):
        old = self.v.remember('unique_mistake_marker', domain='rehab', kind='hypothesis',
            evidence_kind='inferred', observed_at='2000-10-11', source_ref='conversation://test')
        p = self.root / 'data/memory/events.jsonl'
        before = p.read_bytes()
        self.v.remember('unique_fixed_marker', domain='rehab', kind='correction',
            evidence_kind='user_reported', observed_at='2000-10-11', source_ref='conversation://test', supersedes=old)
        self.assertTrue(p.read_bytes().startswith(before))
        self.v.ingest()
        self.v.compile()
        self.assertFalse(self.v.retrieve('unique_mistake_marker'))
        self.assertTrue(self.v.retrieve('unique_fixed_marker'))

    def test_missing_is_unknown_and_review_window_is_enforced(self):
        self.seed()
        self.v.ingest()
        r = self.v.review('2000-10-01', '2000-10-11')
        self.assertEqual(r['domains']['rehab']['record_count'], 0)
        self.assertEqual(r['domains']['rehab']['status'], 'unknown')
        with self.assertRaises(ValueError):
            self.v.review('2000-10-11', '2000-10-01')

    def test_lifecycle_transition_checkpoint_survives_new_instance(self):
        with self.assertRaises(ValueError):
            self.v.transition('execute', 'skip all stages')
        self.v.transition('baseline', 'intake recorded, measurements not current')
        reopened = Vault(self.root)
        self.addCleanup(reopened.db.close)
        self.assertEqual(reopened.lifecycle()['phase'], 'baseline')
        self.assertEqual(len(list((self.root / 'vault/state/checkpoints').glob('*.json'))), 1)
        self.assertFalse(self.v.lifecycle()['clinical_clearance'])

    def test_path_escape_and_secret_sources_are_not_imported(self):
        self.put('.env', 'SECRET=never_index_marker')
        self.put('imports/.env.json', '{"text":"never_index_marker"}')
        self.put('data/body/good.json', '{"text":"ordinary_marker"}')
        self.v.ingest()
        self.assertEqual(self.v.stats()['source_versions'], 1)
        with self.assertRaises(ValueError):
            self.v.safe_path('../outside.txt')

    def test_raw_tamper_is_reported(self):
        self.seed()
        self.v.ingest()
        p = next((self.root / 'vault/raw').glob('*'))
        p.write_bytes(b'tampered')
        self.assertTrue(self.v.lint()['errors'])

    def test_superseded_plan_file_is_excluded_from_current_reference_search(self):
        self.put('outputs/training-plan/old.md', '# old\nunique_old_plan_marker\n')
        self.put('data/training/training_log.jsonl', self.record(date='2000-08-16',
            record_type='schedule_correction', supersedes_plan_file='outputs/training-plan/old.md'))
        self.v.ingest()
        self.v.compile()
        self.assertFalse(self.v.retrieve('unique_old_plan_marker', include_reference=True))
        self.assertTrue(self.v.retrieve('unique_old_plan_marker', include_reference=True, include_history=True))

    def test_memory_id_collision_cannot_silently_replace_provenance(self):
        first=dict(id='same-id',domain='rehab',kind='observation',text='first')
        second=dict(id='same-id',domain='rehab',kind='observation',text='second')
        self.put('data/memory/events.jsonl',self.record(**first)+self.record(**second))
        with self.assertRaises(ValueError):
            self.v.ingest()
        self.assertEqual(self.v.stats()['source_versions'],0)

    def test_chinese_query_matches_its_subject_before_broad_english_aliases(self):
        self.put('data/memory/events.jsonl', self.record(id='concern',domain='rehab',kind='observation',
            text='合成文档包含体态与颌面检索关键词',observed_at='2000-10-11') + self.record(id='unrelated',domain='memory',kind='decision',
            text='install posture orofacial jaw skills',observed_at='2000-10-11'))
        self.v.ingest(); self.v.compile()
        self.assertEqual(self.v.retrieve('体态颌面', limit=1)[0]['id'], 'concern')

    def test_changed_ingested_corpus_requires_recompilation(self):
        self.seed();self.v.ingest();self.v.compile()
        self.put('data/rehab/rehab_log.jsonl',self.record(date='2000-08-16',text='updated_sleep_fixture'))
        self.v.ingest()
        with self.assertRaises(ValueError):
            self.v.retrieve('sleep')

    def test_office_text_and_cached_formula_remain_reference_material(self):
        doc=self.root/'alignment/files/report.docx'
        doc.parent.mkdir(parents=True)
        with zipfile.ZipFile(doc,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>报告：功能评估</w:t></w:r></w:p></w:body></w:document>')
        x=self.root/'alignment/files/template.xlsx'
        with zipfile.ZipFile(x,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Template" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>90*2</f><v>180</v></c></row></sheetData></worksheet>')
        self.v.ingest();self.v.compile()
        self.assertFalse(self.v.retrieve('180'))
        h=self.v.retrieve('180',include_reference=True)
        self.assertTrue(h)
        self.assertIn('not-recalculated',h[0]['excerpt'])
        self.assertEqual(h[0]['source_refs'][0]['locator'],'Template!row:1')
        self.assertTrue(self.v.retrieve('功能评估',include_reference=True))

    def test_unextractable_image_is_preserved_and_reported(self):
        p=self.root/'imports/photo.png'
        p.parent.mkdir();p.write_bytes(b'opaque-image-fixture')
        r=self.v.ingest()
        self.assertEqual(r['pending_extraction'],['imports/photo.png'])
        self.assertEqual(self.v.stats()['records'],0)
        self.assertEqual(self.v.lint()['errors'],[])


if __name__ == '__main__':
    unittest.main()
