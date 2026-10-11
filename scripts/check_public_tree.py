"""Reject unapproved tracked paths and common publication hazards.

Checks Git's index, not ignored private working data. Manual content review
is still required; a pattern scan cannot establish complete anonymity.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    '.gitignore', 'README.md', 'AGENTS.md',
    'physical_memory/__init__.py', 'physical_memory/__main__.py',
    'physical_memory/adapters.py', 'physical_memory/vault.py',
    'tests/test_memory.py', 'docs/lifecycle.md', 'docs/skills.md',
    'templates/vault/AGENTS.md', 'scripts/check_public_tree.py',
    '.agents/skills/personal-performance-orchestrator/SKILL.md',
    '.agents/skills/physical-memory/SKILL.md',
    '.agents/skills/posture-physio-support/SKILL.md',
    '.agents/skills/orofacial-tmj-support/SKILL.md',
    '.agent/domain/schemas/observation.schema.json',
    '.agent/domain/schemas/goal.schema.json',
    '.agent/domain/schemas/constraint.schema.json',
    '.agent/domain/schemas/correction.schema.json',
}
PATTERNS = [
    ('absolute Windows path', re.compile(r'(?i)[a-z]:[\\/](?:users|gate|personal-agent-runtime)')),
    ('private key block', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY')),
    ('GitHub credential', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})')),
    ('session authorization', re.compile(r'已于\s*\d{4}-\d{2}-\d{2}\s*获授权')),
]


def main():
    proc = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                          capture_output=True, check=True)
    paths = [p.decode('utf-8') for p in proc.stdout.split(b'\0') if p]
    errors = [f'unapproved tracked path: {p}' for p in paths if p not in ALLOWED]
    if set(paths) != ALLOWED:
        errors.extend(f'missing expected file: {p}' for p in sorted(ALLOWED-set(paths)))
    for path in paths:
        # Audit the exact index content that the next commit will use.
        staged = subprocess.run(['git', 'show', ':'+path], cwd=ROOT,
                                capture_output=True, check=True).stdout
        text = staged.decode('utf-8')
        if path != 'scripts/check_public_tree.py':
            for label, pattern in PATTERNS:
                if pattern.search(text):
                    errors.append(f'{label}: {path}')
        for line in text.splitlines():
            if line.startswith('local-export-source:'):
                errors.append(f'local export metadata: {path}')
    print(json.dumps({'tracked_files': len(paths), 'errors': errors,
                      'manual_content_review_required': True}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
