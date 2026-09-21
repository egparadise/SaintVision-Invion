"""Meaningful file-safety checks for the Obsidian exporter."""
from pathlib import Path
import json
import hashlib
from contextlib import redirect_stdout
from io import StringIO
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sync_obsidian
from sync_obsidian import ConflictsDetected, default_state_path, export, sha, sync_sha


class SyncTests(unittest.TestCase):
    def _cli_repo(self, temp, source_files, destination_files, original_files=()):
        root = Path(temp) / 'repo'
        source = root / 'docs' / 'vault'
        destination = Path(temp) / 'external-vault'
        source.mkdir(parents=True)
        destination.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        for rel, content in source_files.items():
            target = source / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for rel, content in destination_files.items():
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        original_hashes = [
            {'path': rel, 'sha256': sha(destination / rel)} for rel in original_files]
        (root / 'docs' / 'source-manifest.json').write_text(
            json.dumps({'vault': str(destination), 'files': original_hashes}), encoding='utf-8')
        return root, source, destination

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

    def test_check_normalizes_crlf_without_rewriting_destination_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            source_bytes = b'first line\nsecond line\n'
            destination_bytes = b'first line\r\nsecond line\r\n'
            (src/'note.md').write_bytes(source_bytes)
            (dst/'note.md').write_bytes(destination_bytes)

            self.assertNotEqual(sha(src/'note.md'), sha(dst/'note.md'))
            self.assertEqual(sync_sha(src/'note.md'), sync_sha(dst/'note.md'))
            self.assertEqual(export(src, dst, state, {'note.md': sha(src/'note.md')}), 0)
            self.assertFalse(state.exists())
            self.assertEqual((dst/'note.md').read_bytes(), destination_bytes)

            self.assertEqual(export(src, dst, state, {'note.md': sha(src/'note.md')}, apply=True), 0)
            saved = json.loads(state.read_text('utf-8'))
            self.assertEqual(saved['files']['note.md'], sync_sha(src/'note.md'))
            self.assertEqual((dst/'note.md').read_bytes(), destination_bytes)

    def test_eol_normalization_does_not_hide_real_two_sided_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            baseline = b'original\n'
            (src/'note.md').write_bytes(b'source edit\n')
            destination_bytes = b'original\r\nvault edit\r\n'
            (dst/'note.md').write_bytes(destination_bytes)
            state.write_text(json.dumps({
                'vault': str(dst.resolve()),
                'files': {'note.md': hashlib.sha256(baseline).hexdigest()},
            }), encoding='utf-8')

            with self.assertRaises(ConflictsDetected) as raised:
                export(src, dst, state, {})

            self.assertEqual(raised.exception.conflicts, [('note.md', 'both-diverged')])
            self.assertEqual((dst/'note.md').read_bytes(), destination_bytes)

    def test_large_collision_set_keeps_only_non_eol_differences(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, dst, state = base/'src', base/'dst', base/'state.json'
            src.mkdir(); dst.mkdir()
            original_hashes = {}
            for index in range(683):
                rel = f'note-{index:03}.md'
                if index < 667:
                    source_bytes = b'same content\nsecond line\n'
                    destination_bytes = b'same content\r\nsecond line\r\n'
                elif index < 681:
                    source_bytes = b'repository version\n'
                    destination_bytes = b'user version\r\n'
                else:
                    baseline = b'original baseline\n'
                    source_bytes = b'repository edit\n'
                    destination_bytes = b'vault edit\r\n'
                    original_hashes[rel] = hashlib.sha256(baseline).hexdigest()
                (src/rel).write_bytes(source_bytes)
                (dst/rel).write_bytes(destination_bytes)

            with self.assertRaises(ConflictsDetected) as raised:
                export(src, dst, state, original_hashes)

            conflicts = raised.exception.conflicts
            reasons = {reason: sum(1 for _, item_reason in conflicts if item_reason == reason)
                       for reason in {item_reason for _, item_reason in conflicts}}
            self.assertEqual(len(conflicts), 16)
            self.assertEqual(reasons, {'no-baseline': 14, 'both-diverged': 2})

    def test_explicit_resolution_writes_only_listed_conflicts_and_keeps_exit_three(self):
        with tempfile.TemporaryDirectory() as temp:
            root, source, destination = self._cli_repo(temp, {
                'approved.md': b'repository approved bytes\n',
                'remaining.md': b'repository remaining bytes\n',
                'pending.md': b'new pending export\n',
            }, {
                'approved.md': b'vault edit approved\r\n',
                'remaining.md': b'vault edit remaining\r\n',
            })
            paths_file = Path(temp) / 'approved-paths.txt'
            paths_file.write_text('approved.md\n', encoding='utf-8')
            remaining_before = (destination / 'remaining.md').read_bytes()

            with patch.object(sync_obsidian, 'ROOT', root):
                exit_code = sync_obsidian.main([
                    '--apply', '--vault', str(destination),
                    '--resolve-conflicts-from', str(paths_file)])

            self.assertEqual(exit_code, 3)
            self.assertEqual((destination / 'approved.md').read_bytes(),
                             (source / 'approved.md').read_bytes())
            self.assertEqual((destination / 'remaining.md').read_bytes(), remaining_before)
            self.assertFalse((destination / 'pending.md').exists())
            report = json.loads((root / '.work' / 'obsidian-sync-conflicts.json').read_text('utf-8'))
            self.assertEqual(report['resolvedFromRepository'], ['approved.md'])
            self.assertEqual([item['path'] for item in report['conflicts']], ['remaining.md'])
            self.assertEqual(json.loads(default_state_path(root).read_text('utf-8'))['files'], {
                'approved.md': sync_sha(source / 'approved.md')})

    def test_resolution_list_rejects_a_path_that_is_not_a_current_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root, source, destination = self._cli_repo(temp, {
                'stale.md': b'repository updated bytes\n',
                'real-conflict.md': b'repository conflict version\n',
            }, {
                'stale.md': b'baseline bytes\n',
                'real-conflict.md': b'unmanaged vault bytes\r\n',
            }, original_files=('stale.md',))
            paths_file = Path(temp) / 'stale-path.txt'
            paths_file.write_text('stale.md\n', encoding='utf-8')
            stale_before = (destination / 'stale.md').read_bytes()
            conflict_before = (destination / 'real-conflict.md').read_bytes()

            with patch.object(sync_obsidian, 'ROOT', root):
                exit_code = sync_obsidian.main([
                    '--apply', '--vault', str(destination),
                    '--resolve-conflicts-from', str(paths_file)])

            self.assertEqual(exit_code, 1)
            self.assertEqual((destination / 'stale.md').read_bytes(), stale_before)
            self.assertEqual((destination / 'real-conflict.md').read_bytes(), conflict_before)
            self.assertFalse(default_state_path(root).exists())

    def test_resolving_all_listed_conflicts_updates_state_and_rerun_is_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            root, source, destination = self._cli_repo(temp, {
                'one.md': b'repository one\n',
                'two.md': b'repository two\n',
            }, {
                'one.md': b'vault one\r\n',
                'two.md': b'vault two\r\n',
            })
            paths_file = Path(temp) / 'all-paths.txt'
            paths_file.write_text('one.md\ntwo.md\n', encoding='utf-8')
            output = StringIO()
            with patch.object(sync_obsidian, 'ROOT', root):
                with redirect_stdout(output):
                    exit_code = sync_obsidian.main([
                        '--apply', '--vault', str(destination),
                        '--resolve-conflicts-from', str(paths_file)])
                check_code = sync_obsidian.main(['--check', '--vault', str(destination)])
                stale_list_code = sync_obsidian.main([
                    '--apply', '--vault', str(destination),
                    '--resolve-conflicts-from', str(paths_file)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(check_code, 0)
            self.assertEqual(stale_list_code, 1)
            self.assertIn('RESOLVED APPROVED CONFLICT: one.md', output.getvalue())
            self.assertIn('RESOLVED APPROVED CONFLICT: two.md', output.getvalue())
            for rel in ('one.md', 'two.md'):
                self.assertEqual((destination / rel).read_bytes(), (source / rel).read_bytes())
            state = json.loads(default_state_path(root).read_text('utf-8'))
            self.assertEqual(state['files'], {
                'one.md': sync_sha(source / 'one.md'),
                'two.md': sync_sha(source / 'two.md'),
            })

    def test_conflict_path_file_rejects_unsafe_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path_file = Path(temp) / 'paths.txt'
            for contents in ('../outside.md\n', '/absolute.md\n', 'C:/outside.md\n',
                             'a\\b.md\n', 'same.md\nsame.md\n'):
                with self.subTest(contents=contents):
                    path_file.write_text(contents, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        sync_obsidian.read_conflict_paths(path_file)

    def test_conflict_resolution_option_is_apply_only(self):
        with tempfile.TemporaryDirectory() as temp:
            paths_file = Path(temp) / 'paths.txt'
            paths_file.write_text('note.md\n', encoding='utf-8')
            with self.assertRaises(SystemExit) as raised:
                sync_obsidian.main([
                    '--check', '--resolve-conflicts-from', str(paths_file)])
            self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
