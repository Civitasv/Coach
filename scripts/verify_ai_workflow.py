"""Standard-library-only checks for Coach's durable AI-native SDLC artifacts."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'AGENTS.md',
    'docs/architecture/overview.md',
    'docs/process/development.md',
    'docs/decisions/0001-local-first-boundaries.md',
    '.github/pull_request_template.md',
    '.github/ISSUE_TEMPLATE/feature_request.yml',
    '.github/ISSUE_TEMPLATE/bug_report.yml',
    '.github/workflows/test.yml',
)
SPEC_PATTERN = re.compile(r'^\d{3}-[a-z0-9-]+\.md$')
AC_PATTERN = re.compile(r'^- \*\*AC-(\d{3})(?::\*\*|\*\*:)', re.MULTILINE)


def validate(root: Path) -> list[str]:
    """Return actionable errors; never depend on the network or model output."""
    problems = []
    for name in REQUIRED:
        p = root / name
        if not p.is_file():
            problems.append(f'missing required file: {name}')
        elif not p.read_text(encoding='utf-8').strip():
            problems.append(f'empty required file: {name}')

    specs = root / 'docs/specs'
    plans = root / 'docs/plans'
    if not specs.is_dir() or not list(specs.glob('*.md')):
        problems.append('missing versioned specs in docs/specs/')
        return problems

    for path in sorted(specs.glob('*.md')):
        if not SPEC_PATTERN.match(path.name):
            problems.append(f'invalid spec filename: {path.name}')
            continue
        source = path.read_text(encoding='utf-8')
        ids = AC_PATTERN.findall(source)
        if not ids:
            problems.append(f'{path.name}: needs acceptance criteria with **AC-001**: syntax')
        if len(ids) != len(set(ids)):
            problems.append(f'{path.name}: duplicate acceptance criterion IDs')
        for heading in ('## Acceptance criteria', '## Verification', '## Non-goals'):
            if heading not in source:
                problems.append(f'{path.name}: missing {heading}')
        if not re.search(r'\*\*Status:\*\*', source):
            problems.append(f'{path.name}: missing explicit Status')
        if 'Draft' not in source and 'not implemented' not in source.lower():
            related = list(plans.glob(path.name[:4] + '*.md')) if plans.exists() else []
            if not related:
                problems.append(f'{path.name}: implemented spec needs matching Plan in docs/plans/')

    pr = root / '.github/pull_request_template.md'
    if pr.exists():
        text = pr.read_text(encoding='utf-8')
        for term in ('Spec', 'Acceptance criteria', 'Verification', 'Review', 'Merge gate'):
            if term.lower() not in text.lower():
                problems.append(f'PR template missing section/field: {term}')

    agents = root / 'AGENTS.md'
    if agents.exists():
        text = agents.read_text(encoding='utf-8')
        for term in ('docs/specs/', 'docs/process/development.md', 'consent', 'CI', 'Review'):
            if term.lower() not in text.lower():
                problems.append(f'AGENTS.md missing required context: {term}')
    return problems


def main() -> int:
    problems = validate(ROOT)
    if problems:
        print('AI workflow validation failed:')
        for problem in problems:
            print(f'  - {problem}')
        return 1
    print('AI workflow validation passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())