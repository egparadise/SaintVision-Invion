"""Meaningful file-safety checks for the Obsidian exporter."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sync_obsidian
from sync_obsidian import ConflictsDetected, default_state_path, export, sha


class SyncTests(unittest.TestCase):
    def test_export_is_idempotent_and_preserves_unmanaged_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            (src/'a.md').write_text('new', encoding='utf-8')
            (dst/'personal.md').write_text('private', encoding='utf-8')
            self.assertEqual(export(src,dst,state,{},True), 1)
            self.assertEqual(export(src,dst,state,{},True), 0)
            self.assertEqual((dst/'personal.md').read_text('utf-8'), 'private')

    def test_conflict_aborts_before_any_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            (src/'a.md').write_text('new', encoding='utf-8')
            (src/'b.md').write_text('git', encoding='utf-8')
            (dst/'b.md').write_text('user edit', encoding='utf-8')
            with self.assertRaises(ConflictsDetected):
                export(src,dst,state,{},True)
            self.assertFalse((dst/'a.md').exists())
            self.assertFalse(state.exists())
            self.assertEqual((dst/'b.md').read_text('utf-8'), 'user edit')

    def test_cli_adopts_identical_files_before_aborting_other_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            source = root / 'docs' / 'vault'
            destination = Path(temp) / 'external-vault'
            source.mkdir(parents=True)
            destination.mkdir()
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'docs' / 'source-manifest.json').write_text(
                json.dumps({'vault': str(destination), 'files': []}), encoding='utf-8')
            (source / 'same.md').write_text('identical bytes', encoding='utf-8')
            (destination / 'same.md').write_text('identical bytes', encoding='utf-8')
            (source / 'conflict.md').write_text('repository version', encoding='utf-8')
            (destination / 'conflict.md').write_text('user version', encoding='utf-8')
            self.assertFalse(default_state_path(root).exists())

            with patch.object(sync_obsidian, 'ROOT', root):
                exit_code = sync_obsidian.main([
                    '--check', '--adopt-identical', '--vault', str(destination)])

            self.assertEqual(exit_code, 3)
            state_path = default_state_path(root)
            state = json.loads(state_path.read_text('utf-8'))
            self.assertEqual(state['files'], {'same.md': sha(source / 'same.md')})
            self.assertEqual((destination / 'conflict.md').read_text('utf-8'), 'user version')
            conflict_report = json.loads((root / '.work' / 'obsidian-sync-conflicts.json').read_text('utf-8'))
            self.assertEqual(conflict_report['adoptedIdentical'], ['same.md'])

    def test_default_state_uses_git_metadata_and_survives_work_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            root.mkdir()
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            state_path = default_state_path(root)
            git_dir = Path(subprocess.run(
                ['git', 'rev-parse', '--git-dir'], cwd=root, check=True,
                capture_output=True, text=True).stdout.strip())
            if not git_dir.is_absolute():
                git_dir = root / git_dir
            self.assertTrue(state_path.resolve().is_relative_to(git_dir.resolve()))
            self.assertNotIn('.work', state_path.parts)

            work = root / '.work'
            work.mkdir()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text('{"files": {"baseline.md": "sha"}}', encoding='utf-8')
            shutil.rmtree(work)
            self.assertTrue(state_path.is_file())

    def test_original_hash_allows_initial_navigation_update(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            (src/'a.md').write_text('banner + original', encoding='utf-8')
            (dst/'a.md').write_text('original', encoding='utf-8')
            before = sha(dst/'a.md')
            self.assertEqual(export(src,dst,state,{'a.md':before},True), 1)


if __name__ == '__main__':
    unittest.main()
