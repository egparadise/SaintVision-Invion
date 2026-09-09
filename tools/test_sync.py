"""Meaningful file-safety checks for the Obsidian exporter."""
from pathlib import Path
import tempfile
import unittest
from sync_obsidian import export, sha


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
            with self.assertRaises(ValueError):
                export(src,dst,state,{},True)
            self.assertFalse((dst/'a.md').exists())
            self.assertFalse(state.exists())
            self.assertEqual((dst/'b.md').read_text('utf-8'), 'user edit')

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
