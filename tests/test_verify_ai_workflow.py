"""Mutation-style checks so a missing Spec/AC really blocks validation."""
import tempfile
import unittest
from pathlib import Path

from scripts.verify_ai_workflow import REQUIRED, validate


class WorkflowArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in REQUIRED:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('valid placeholder', encoding='utf-8')
        (self.root / 'AGENTS.md').write_text('docs/specs/ docs/process/development.md consent CI Review', encoding='utf-8')
        (self.root / '.github/pull_request_template.md').write_text('Spec Acceptance criteria Verification Review Merge gate', encoding='utf-8')
        spec = self.root / 'docs/specs/001-sample.md'
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text('# Test\n**Status:** Implemented\n## Acceptance criteria\n- **AC-001**: test\n## Verification\nTest run\n## Non-goals\nnone\n', encoding='utf-8')
        plan = self.root / 'docs/plans/001-sample.md'
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text('# Plan', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_tree(self):
        self.assertEqual(validate(self.root), [])

    def test_missing_agents(self):
        (self.root / 'AGENTS.md').unlink()
        self.assertTrue(any('AGENTS.md' in error for error in validate(self.root)))

    def test_missing_acceptance_criteria(self):
        p = self.root / 'docs/specs/001-sample.md'
        p.write_text(p.read_text(encoding='utf-8').replace('- **AC-001**: test', 'not a criterion'), encoding='utf-8')
        self.assertTrue(any('acceptance criteria' in error for error in validate(self.root)))

    def test_duplicate_criterion(self):
        p = self.root / 'docs/specs/001-sample.md'
        p.write_text(p.read_text(encoding='utf-8') + '- **AC-001**: duplicate\n', encoding='utf-8')
        self.assertTrue(any('duplicate' in error for error in validate(self.root)))

    def test_missing_matching_plan(self):
        (self.root / 'docs/plans/001-sample.md').unlink()
        self.assertTrue(any('matching Plan' in error for error in validate(self.root)))

    def test_draft_does_not_require_plan(self):
        p = self.root / 'docs/specs/001-sample.md'
        p.write_text(p.read_text(encoding='utf-8').replace('Implemented', 'Draft'), encoding='utf-8')
        (self.root / 'docs/plans/001-sample.md').unlink()
        self.assertEqual(validate(self.root), [])


if __name__ == '__main__':
    unittest.main()