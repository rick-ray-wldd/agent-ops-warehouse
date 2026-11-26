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
# The one public link allowed, checked by a deliberately narrow format rule rather than a Markdown parser. README.md
# may mask it only when all of these hold; otherwise nothing is masked and the scan fails:
# - the URL occurs exactly once in the file;
# - that line starts with PUBLIC_LINK_ITEM at column 0, right after a blank line that follows "## Related" at
#   column 0, which itself follows a blank line;
# - before it, every code fence is at column 0 and closed by a column-0 fence of the same character, at least as
#   long, followed only by ASCII spaces or tabs; any indented fence-like line (it may belong to a list or another
#   container), any line starting with "<" (an HTML block) and any tab-indented line refuse the exception.
# Only the link destination is masked; the rest of that line is still scanned.
PUBLIC_URL = 'https://github.com/rick-ray-wldd/orca-coordination-handbook'
PUBLIC_LINK_ITEM = f'- [orca-coordination-handbook]({PUBLIC_URL}): '
FENCE = re.compile(r'`{3,}|~{3,}')
CLOSING_FENCE = re.compile(r'(`{3,}|~{3,})[ \t]*')


def public_link_line(lines):
    """Index of the approved README line, or None when anything about it is ambiguous."""
    if sum(line.count(PUBLIC_URL) for line in lines) != 1:
        return None
    i = next(n for n, line in enumerate(lines) if PUBLIC_URL in line)
    if (not lines[i].startswith(PUBLIC_LINK_ITEM) or i < 2 or lines[i - 1] != '' or lines[i - 2] != '## Related'
            or (i >= 3 and lines[i - 3] != '')):
        return None
    fence = None
    for line in lines[:i]:
        bare = line.lstrip()  # any whitespace, including non-ASCII
        if line.startswith('\t') or bare.startswith('<'):
            return None
        m = FENCE.match(bare)
        if not m:
            continue
        if bare != line:
            return None  # an indented fence may sit in a list or another container; do not guess
        run = m.group(0)
        if fence is None:
            if run[0] == '`' and '`' in line[len(run):]:
                return None  # not a valid opening fence; do not guess
            fence = (run[0], len(run))
        elif CLOSING_FENCE.fullmatch(line) and run[0] == fence[0] and len(run) >= fence[1]:
            fence = None
    return None if fence else i

def private_hits(name, body):
    if name == 'README.md':
        lines = body.split('\n')
        i = public_link_line(lines)
        if i is not None:
            lines[i] = lines[i].replace(PUBLIC_URL, '<public link>', 1)
            body = '\n'.join(lines)
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
        url = PUBLIC_URL
        item = f'- [orca-coordination-handbook]({url}): the workflow.'
        good = f'# T\n\n```\ncode\n```\n\n## Related\n\n{item}\n\n## License\n'
        self.assertFalse(private_hits('README.md', good))
        self.assertFalse(private_hits('README.md', text(ROOT / 'README.md')))  # the real README passes
        rel = '## Related\n\n'
        for name, body in [
            ('README.md', f'{rel}- [orca-coordination-handbook](x{url}): a'),          # prefix
            ('README.md', f'{rel}- [orca-coordination-handbook]({url}-old): a'),       # longer repo name
            ('README.md', f'{rel}- [orca-coordination-handbook]({url}/blob/x): a'),    # path
            ('README.md', f'{rel}- [orca-coordination-handbook]({url}?q=1): a'),       # query
            ('README.md', f'{rel}- [orca-coordination-handbook]({url}#top): a'),       # fragment
            ('README.md', f'{rel}{item} rick'),                                        # rest of the line
            ('README.md', f'{rel}ray-x {item}'),                                       # not at line start
            ('README.md', f'{rel}see {url}'),                                          # plain text
            ('README.md', f'{rel}see `]({url})`'),                                     # inline code
            ('README.md', f'{rel}[a](https://example.invalid/(]({url}))x)'),          # inside a longer destination
            ('README.md', f'{rel}{item}\n{item}'),                                     # twice
            ('README.md', f'{rel}{item}\n\nsee {url}'),                                # a second copy elsewhere
            ('README.md', f'## Usage\n\n{item}'),                                     # wrong section
            ('README.md', f' ## Usage\n\n{item}'),                                    # indented heading, wrong section
            ('README.md', f'```\n{rel}{item}\n```\n'),                                 # heading and item in a code block
            ('README.md', f'{rel}```\n{item}\n```\n'),                                 # item in a code block
            ('README.md', f'~~~~\n```\n~~~\n{rel}{item}\n'),                           # still inside the ~~~~ fence
            ('README.md', f'<!--\n{rel}{item}\n-->\n'),                                # inside an HTML comment
            ('README.md', f'<details>\n\n{rel}{item}\n'),                              # after an HTML block start
            ('README.md', f'\t```\n{rel}{item}\n'),                                    # tab-indented lines are refused
            ('README.md', f'- list\n\n  ```\n```\n\n{rel}{item}\n'),                    # fence in a list item, then top level
            ('README.md', f'- list\n\n  ~~~\n~~~\n\n{rel}{item}\n'),                    # same with tildes
            ('README.md', f'```\n``` \n\n{rel}{item}\n'),                            # non-ASCII space after the close
            ('README.md', f'```\n   ```\n\n{rel}{item}\n'),                              # indented close is refused
            ('README.md', f'```py`x\n\n{rel}{item}\n'),                                   # backtick in the info string
            ('README.md', f'Intro\n## Related\n\n{item}'),                             # heading glued to a paragraph
            ('README.md', '## Related\n\n- [other](https://github.com/rick-ray-wldd/other): a'),
            ('docs/DESIGN.md', f'{rel}{item}'),                                        # another file
        ]:
            self.assertTrue(private_hits(name, body), f'{name}: {body!r}')

if __name__ == '__main__':
    unittest.main()
