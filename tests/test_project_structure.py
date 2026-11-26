"""Checks that need no database: every ref/source/var resolves, schema.yml names real models, the exercises and
grader agree, and nothing in the repo looks like a private identifier."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODELS = {p.stem: p for p in (ROOT / 'models').rglob('*.sql')}
SQL_FILES = list((ROOT / 'models').rglob('*.sql')) + list((ROOT / 'tests_sql').glob('*.sql'))


def text(p):
    return p.read_text(encoding='utf-8')


PRIVATE = re.compile(r'/Users/|\brick|\bray-|term_[0-9a-f]|run_[0-9a-f]|S-[0-9a-f]{8}|C0[A-Z0-9]{8}|'
                     r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|[a-z0-9._%+-]+@[a-z0-9-]+\.[a-z]{2,}|claude|codex|anthropic\.com', re.I)
# The one public link allowed: only in README.md, and only as this exact Markdown link destination. Anything
# around it, a longer URL, or the same URL in another file is scanned as written and still fails.
PUBLIC_LINK = '](https://github.com/rick-ray-wldd/orca-coordination-handbook)'


def private_hits(name, body):
    if name == 'README.md':
        body = body.replace(PUBLIC_LINK, '](<public link>)')
    return PRIVATE.findall(body)


class StructureTests(unittest.TestCase):
    def test_every_ref_points_at_a_model(self):
        for f in SQL_FILES:
            for name in re.findall(r"ref\('([^']+)'\)", text(f)):
                self.assertIn(name, MODELS, f'{f.name} refs unknown model {name}')

    def test_every_source_is_declared(self):
        sources = text(ROOT / 'models/sources.yml')
        declared = set()
        for block in re.split(r'\n  - name: ', sources)[1:]:
            group = block.split('\n', 1)[0].strip()
            for t in re.findall(r'\n      - name: (\w+)', block):
                declared.add((group, t))
        used = {(g, t) for f in SQL_FILES for g, t in re.findall(r"source\('(\w+)', '(\w+)'\)", text(f))}
        self.assertTrue(used)
        self.assertLessEqual(used, declared)

    def test_every_var_is_defined(self):
        project = text(ROOT / 'dbt_project.yml')
        for f in SQL_FILES:
            for name in re.findall(r"var\('([^']+)'\)", text(f)):
                self.assertRegex(project, rf'\n  {name}:', f'{f.name} uses undefined var {name}')

    def test_schema_yml_models_exist(self):
        names = re.findall(r'\n  - name: (\w+)', text(ROOT / 'models/schema.yml'))
        self.assertTrue(names)
        for n in names:
            self.assertIn(n, MODELS)

    def test_reference_tests_cover_every_metric_mart(self):
        marts = {n for n in MODELS if n.startswith('mart_')}
        covered = {m for f in (ROOT / 'tests_sql').glob('assert_*reference*.sql')
                   for m in re.findall(r"ref\('(mart_\w+)'\)", text(f))}
        self.assertEqual(marts, covered)

    def test_exercises_and_grader_agree(self):
        grader = text(ROOT / 'exercises/grade.py')
        for f in ('01_decision_wait.sql', '02_work_sessions.sql', '03_rework_share.sql'):
            self.assertTrue((ROOT / 'exercises' / f).is_file())
            self.assertIn(f, grader)
            self.assertIn('TODO', text(ROOT / 'exercises' / f), 'starter files must not contain a solution')

    def test_fact_is_incremental_on_arrival_time(self):
        fct = text(MODELS['fct_event'])
        self.assertIn("materialized='incremental'", fct)
        block = fct.split('{% if is_incremental() %}', 1)[1].split('{% endif %}', 1)[0]
        self.assertIn('loaded_at_utc >', block)
        self.assertNotIn('event_time', block)

    def test_no_private_identifiers_in_the_repo(self):
        # Exactly what would be published: tracked files plus untracked ones that .gitignore does not exclude.
        listed = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.split('\0')
        listed = [name for name in listed if name]
        self.assertTrue(listed)
        for name in listed:
            f = ROOT / name
            if f == Path(__file__).resolve():
                continue  # this file spells the patterns out
            if f.is_file() and f.suffix in {'.py', '.sql', '.md', '.yml', '.json', '.txt', '.sh', ''}:
                hits = private_hits(name, text(f))
                self.assertFalse(hits, f'{name}: {hits[:3]}')

    def test_public_link_exception_is_narrow(self):
        url = 'https://github.com/rick-ray-wldd/orca-coordination-handbook'
        self.assertFalse(private_hits('README.md', f'- [handbook]({url}): the workflow.'))
        for name, body in [
            ('README.md', f'[handbook](x{url})'),              # prefix
            ('README.md', f'[handbook]({url}-old)'),           # longer repo name
            ('README.md', f'[handbook]({url}/blob/main/x)'),   # path
            ('README.md', f'[handbook]({url}?q=1)'),           # query
            ('README.md', f'[handbook]({url}#top)'),           # fragment
            ('README.md', f'[handbook]({url})rick'),           # text glued after
            ('README.md', f'ray-x[handbook]({url})'),          # text glued before
            ('README.md', f'see {url}'),                       # bare URL, not a link destination
            ('README.md', '[other](https://github.com/rick-ray-wldd/other)'),
            ('docs/DESIGN.md', f'[handbook]({url})'),          # another file
        ]:
            self.assertTrue(private_hits(name, body), f'{name}: {body}')

if __name__ == '__main__':
    unittest.main()
