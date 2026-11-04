"""Isolated synthetic filesystem tests; never inspect real user configuration."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import stat
import subprocess

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).with_name('claude_cleanup.py'))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / '用户 with spaces'
        self.home.mkdir()
        self.ctx = cleanup.Context(self.home, 'Darwin', {})
        # All destructive test calls operate in fake homes and fake idle processes.
        self.runtime_guard = cleanup.ensure_runtime_idle
        guard = patch.object(cleanup, 'ensure_runtime_idle', return_value=None)
        guard.start()
        self.addCleanup(guard.stop)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, rel, text='sample'):
        p = self.home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def link(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except OSError as e:
            if os.name == 'nt' and getattr(e, 'winerror', None) == 1314:
                self.skipTest('Creating symlinks requires Windows Developer Mode or privilege')
            raise

    def execute(self, plan, name='result'):
        return cleanup.apply(self.ctx, plan, self.base / name, True, True)

    def test_preview_does_not_delete_or_create_output(self):
        p = self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code')
        result = cleanup.apply(self.ctx, plan, self.base / 'unused')
        self.assertTrue(result['dry_run'])
        self.assertTrue(p.exists())
        self.assertFalse((self.base / 'unused').exists())

    def test_history_preserves_memory_settings_credentials_and_skills(self):
        deleted = [self.file('.claude/history.jsonl'),
                   self.file('.claude/projects/demo/session.jsonl'),
                   self.file('.claude/projects/demo/session/subagents/agent-one.jsonl')]
        kept = [self.file('.claude/projects/demo/memory/events.jsonl'),
                self.file('.claude/projects/demo/memory/MEMORY.md'),
                self.file('.claude/settings.json', '{}'),
                self.file('.claude/.credentials.json', 'DO_NOT_PRINT'),
                self.file('.claude/skills/demo/SKILL.md')]
        result = self.execute(self.ctx.plan('history', 'code'))
        self.assertEqual(result['errors'], [])
        self.assertTrue(all(not p.exists() for p in deleted))
        self.assertTrue(all(p.exists() for p in kept))

    def test_reset_backups_verified_assets_excludes_secret_settings(self):
        self.file('.claude/skills/demo/SKILL.md', 'reusable')
        self.file('.claude/settings.json', json.dumps({
            'env': {'ANTHROPIC_AUTH_TOKEN': 'PRIVATE_SENTINEL'},
            'hooks': {'anything': 'PRIVATE_SENTINEL'}, 'effortLevel': 'high'}))
        self.file('.claude/.credentials.json', 'PRIVATE_SENTINEL')
        self.file('.local/share/claude/versions/test', 'executable')
        result = self.execute(self.ctx.plan('reset', 'code'))
        self.assertEqual(result['errors'], [])
        self.assertFalse((self.home / '.claude').exists())
        self.assertTrue((self.home / '.local/share/claude/versions/test').exists())
        self.assertEqual(result['backup']['files_verified'], 1)
        for p in (self.base / 'result').rglob('*'):
            if p.is_file():
                self.assertNotIn('PRIVATE_SENTINEL', p.read_text(encoding='utf-8'))

    def test_forged_plan_cannot_delete_project(self):
        p = self.file('project/source.py')
        plan = self.ctx.plan('uninstall', 'both')
        plan['entries'].append({'path': str(p), 'kind': 'code-data', 'identity': cleanup.identity(p)})
        with self.assertRaises(ValueError):
            self.execute(plan)
        self.assertTrue(p.exists())

    def test_identity_drift_rejected(self):
        p = self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code')
        p.write_text('changed content')
        with self.assertRaises(ValueError):
            self.execute(plan)
        self.assertTrue(p.exists())

    def test_symlinked_root_not_removed(self):
        external = self.base / 'shared'
        external.mkdir()
        (external / 'valuable.md').write_text('preserve')
        self.link(self.home / '.claude', external, True)
        plan = self.ctx.plan('reset', 'code')
        self.assertTrue(plan['warnings'])
        with self.assertRaises(ValueError):
            self.execute(plan)
        self.assertTrue((external / 'valuable.md').exists())

    def test_linked_parent_refused(self):
        outside = self.base / 'elsewhere'
        outside.mkdir()
        self.link(self.home / '.local', outside, True)
        self.file('.local/share/claude/valuable')
        plan = self.ctx.plan('uninstall', 'code')
        self.assertTrue(plan['warnings'])
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_native_symlink_unlinked_without_following(self):
        target = self.file('shared/keep-executable')
        p = self.home / '.local/bin/claude'
        p.parent.mkdir(parents=True)
        self.link(p, target)
        result = self.execute(self.ctx.plan('uninstall', 'code'))
        self.assertFalse(cleanup.lexists(p))
        self.assertTrue(target.exists())
        self.assertEqual(result['errors'], [])

    def test_nested_asset_symlink_not_backed_up_or_followed(self):
        target = self.file('shared/SKILL.md', 'preserve')
        link = self.home / '.claude/skills/shared'
        link.parent.mkdir(parents=True)
        self.link(link, target.parent, True)
        result = self.execute(self.ctx.plan('reset', 'code'))
        self.assertEqual(result['errors'], [])
        self.assertTrue(target.exists())
        self.assertEqual(result['backup']['skipped'], 1)

    def test_backup_overlap_refused_even_without_existing_config(self):
        with self.assertRaises(ValueError):
            cleanup.backup(self.ctx, self.home / '.claude/backup')
        self.assertFalse((self.home / '.claude').exists())

    def test_execute_requires_apps_stopped(self):
        self.file('.claude/history.jsonl')
        with self.assertRaises(ValueError):
            cleanup.apply(self.ctx, self.ctx.plan('history', 'code'), self.base / 'out', True)

    def test_windows_uses_appdata_and_exact_extension(self):
        roaming = self.home / 'Roaming folder'
        local = self.home / 'Local folder'
        ctx = cleanup.Context(self.home, 'Windows', {'APPDATA': str(roaming), 'LOCALAPPDATA': str(local)})
        selected = self.file('Roaming folder/Claude/Cookies')
        kept = self.file('Roaming folder/OtherApp/config')
        self.file('.local/bin/claude.exe')
        self.file('.vscode/extensions/anthropic.claude-code-1.0/file')
        unrelated = self.file('.vscode/extensions/company.claude-tool-1.0/file')
        plan = ctx.plan('uninstall', 'both')
        result = cleanup.apply(ctx, plan, self.base / 'windows-result', True, True)
        self.assertEqual(result['errors'], [])
        self.assertFalse(selected.exists())
        self.assertTrue(kept.exists())
        self.assertTrue(unrelated.exists())

    def test_dangerous_custom_roots_rejected(self):
        for root in [self.home, self.home / 'project', self.home / '.codex', self.base / 'shared']:
            with self.subTest(root=root), self.assertRaises(ValueError):
                cleanup.Context(self.home, 'Darwin', {'CLAUDE_CONFIG_DIR': str(root)})

    def test_custom_config_isolated_from_default(self):
        default = self.file('.claude/keep')
        custom = self.file('.claude-work/remove')
        ctx = cleanup.Context(self.home, 'Darwin', {'CLAUDE_CONFIG_DIR': str(self.home / '.claude-work')})
        plan = ctx.plan('reset', 'code')
        result = cleanup.apply(ctx, plan, self.base / 'custom-result', True, True)
        self.assertEqual(result['errors'], [])
        self.assertTrue(default.exists())
        self.assertFalse(custom.exists())

    def test_wrong_host_plan_rejected(self):
        plan = self.ctx.plan('uninstall', 'both')
        plan['system'] = 'Windows'
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_duplicate_plan_entries_rejected(self):
        self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code')
        plan['entries'].append(copy.deepcopy(plan['entries'][0]))
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_editor_state_only_exact_extension_and_secrets(self):
        db = self.ctx.code_user() / 'globalStorage/state.vscdb'
        db.parent.mkdir(parents=True)
        secret = 'secret://' + json.dumps({'extensionId': 'anthropic.claude-code', 'key': 'session'})
        kept = ['other.extension', 'anthropic.claude-code-extra',
                'secret://' + json.dumps({'extensionId': 'other.extension', 'key': 'anthropic.claude-code'})]
        removed = ['Anthropic.claude-code', secret]
        with sqlite3.connect(str(db)) as c:
            c.execute('CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)')
            c.executemany('INSERT INTO ItemTable VALUES (?,?)', [(k, 'DO_NOT_PRINT_VALUE') for k in kept + removed])
        preview = cleanup.editor_state(self.ctx)
        self.assertEqual(preview['matches'][0]['records'], 2)
        actual = cleanup.editor_state(self.ctx, True, True)
        self.assertEqual(actual['errors'], [])
        with sqlite3.connect(str(db)) as c:
            remaining = [r[0] for r in c.execute('SELECT key FROM ItemTable')]
        self.assertEqual(set(remaining), set(kept))
        self.assertNotIn('DO_NOT_PRINT_VALUE', json.dumps(actual))

    def test_malformed_settings_fail_before_delete_with_report(self):
        p = self.file('.claude/settings.json', '{invalid JSON')
        result = self.execute(self.ctx.plan('reset', 'code'))
        self.assertTrue(result['errors'])
        self.assertTrue(p.exists())
        self.assertTrue((self.base / 'result/cleanup-report.json').is_file())

    def test_repeated_cleanup_is_idempotent(self):
        self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code')
        self.assertEqual(self.execute(plan, 'first')['errors'], [])
        again = self.execute(plan, 'second')
        self.assertEqual(again['errors'], [])
        self.assertTrue(again['already_absent'])

    def test_desktop_only_preserves_code_and_vscode(self):
        keep = self.file('.claude/history.jsonl')
        ext = self.file('.vscode/extensions/anthropic.claude-code-1/file')
        remove = self.file('Library/Application Support/Claude/Cookies')
        result = self.execute(self.ctx.plan('uninstall', 'desktop'))
        self.assertEqual(result['errors'], [])
        self.assertTrue(keep.exists())
        self.assertTrue(ext.exists())
        self.assertFalse(remove.exists())

    def test_partial_delete_failure_is_reported(self):
        p = self.file('.claude/projects/demo/session.jsonl')
        self.file('.claude/settings.json', '{}')
        plan = self.ctx.plan('reset', 'code')
        def fail_after_one_file(path):
            p.unlink()
            raise PermissionError('synthetic file lock')
        with patch.object(cleanup.shutil, 'rmtree', side_effect=fail_after_one_file):
            result = self.execute(plan)
        self.assertTrue(result['errors'])
        self.assertTrue(result['remaining'])
        saved = json.loads((self.base / 'result/cleanup-report.json').read_text())
        self.assertEqual(saved['remaining'], result['remaining'])
        self.assertTrue((self.base / 'result/reusable-assets/backup-manifest.json').exists())

    def test_windows_reparse_attribute_detected(self):
        p = self.file('junction-like')
        attributes = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch.object(Path, 'lstat', return_value=attributes):
            self.assertTrue(cleanup.linked(p))

    def test_native_uninstall_already_removed_path_is_accepted(self):
        p = self.file('.local/bin/claude')
        plan = self.ctx.plan('uninstall', 'code')
        p.unlink()
        result = self.execute(plan)
        self.assertEqual(result['errors'], [])
        self.assertIn(str(p), result['already_absent'])

    def test_cache_preserves_history_memory_login_and_exact_settings(self):
        removed = [self.file('.claude/cache/item'), self.file('.claude/telemetry/item'),
                   self.file('.claude/statsig/item'), self.file('.claude/stats-cache.json'),
                   self.file('Library/Caches/claude-cli-nodejs/item')]
        content = json.dumps({'env': {'DISABLE_TELEMETRY': '1', 'ANTHROPIC_AUTH_TOKEN': 'PRIVATE'},
                              'hooks': {'event': 'keep'}, 'permissions': {'allow': ['keep']}})
        keep = [self.file('.claude/settings.json', content), self.file('.claude/history.jsonl'),
                self.file('.claude/projects/demo/session.jsonl'), self.file('.claude/debug/log'),
                self.file('.claude/.credentials.json'), self.file('.claude/skills/demo/SKILL.md')]
        result = self.execute(self.ctx.plan('cache', 'code'))
        self.assertEqual(result['errors'], [])
        self.assertIsNone(result['backup'])
        self.assertTrue(all(not p.exists() for p in removed))
        self.assertTrue(all(p.exists() for p in keep))
        self.assertEqual((self.home/'.claude/settings.json').read_text(), content)

    def test_windows_cache_scope_preserves_other_app_and_history(self):
        ctx = cleanup.Context(self.home, 'Windows', {})
        cache = self.file('.claude/cache/item')
        history = self.file('.claude/history.jsonl')
        other = self.file('AppData/Roaming/OtherApp/Cache/item')
        result = cleanup.apply(ctx, ctx.plan('cache', 'code'), self.base/'win-cache', True, True)
        self.assertEqual(result['errors'], [])
        self.assertFalse(cache.exists())
        self.assertTrue(history.exists() and other.exists())

    def test_quarantine_preserves_raw_content_and_records_original_path(self):
        source = self.file('.claude/history.jsonl', 'synthetic transcript')
        plan = self.ctx.plan('history', 'code', 'quarantine')
        result = self.execute(plan)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['disposition'], 'quarantine')
        self.assertEqual(result['removed'], [])
        self.assertFalse(source.exists())
        destination = Path(result['quarantined'][0]['destination'])
        self.assertEqual(destination.read_text(), 'synthetic transcript')
        mapping = json.loads((self.base/'result/quarantine-map.json').read_text())
        self.assertEqual(mapping['paths'][str(source)], str(destination))

    def test_quarantine_preview_does_not_move(self):
        source = self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code', 'quarantine')
        result = cleanup.apply(self.ctx, plan, self.base/'preview')
        self.assertTrue(result['dry_run'])
        self.assertEqual(result['disposition'], 'quarantine')
        self.assertTrue(source.exists())
        self.assertFalse((self.base/'preview').exists())

    def test_quarantine_never_uses_cross_volume_copy_delete_fallback(self):
        source = self.file('.claude/history.jsonl')
        plan = self.ctx.plan('history', 'code', 'quarantine')
        with patch.object(cleanup.os, 'rename', side_effect=OSError('synthetic cross-device failure')):
            result = self.execute(plan)
        self.assertTrue(result['errors'])
        self.assertTrue(source.exists())
        self.assertEqual(result['quarantined'], [])
        self.assertTrue((self.base/'result/quarantine-map.json').is_file())

    def test_quarantine_native_symlink_does_not_follow_target(self):
        target = self.file('shared/keep')
        link = self.home/'.local/bin/claude'
        link.parent.mkdir(parents=True)
        self.link(link, target)
        result = self.execute(self.ctx.plan('uninstall', 'code', 'quarantine'))
        self.assertEqual(result['errors'], [])
        self.assertTrue(target.exists())
        self.assertFalse(cleanup.lexists(link))
        self.assertTrue(Path(result['quarantined'][0]['destination']).is_symlink())

    def test_quarantine_partial_failure_preserves_both_moved_and_remaining_data(self):
        first = self.file('.claude/history.jsonl', 'first transcript')
        second = self.file('.claude/debug/log', 'second log')
        original_rename = cleanup.os.rename
        calls = []
        def fail_second(src, dst):
            calls.append(src)
            if len(calls) == 2:
                raise OSError('synthetic second move failure')
            return original_rename(src, dst)
        with patch.object(cleanup.os, 'rename', side_effect=fail_second):
            result = self.execute(self.ctx.plan('history', 'code', 'quarantine'))
        self.assertEqual(len(result['quarantined']), 1)
        self.assertFalse(first.exists())
        self.assertEqual(Path(result['quarantined'][0]['destination']).read_text(), 'first transcript')
        self.assertEqual(second.read_text(), 'second log')
        self.assertIn(str(second.parent), result['remaining'])
        self.assertTrue(result['errors'])

    def test_unknown_disposition_refused(self):
        plan = self.ctx.plan('history', 'code')
        plan['disposition'] = 'external-command'
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_running_claude_refused_before_output_creation(self):
        source = self.file('.claude/history.jsonl')
        processes = [{'pid': 123, 'ppid': 1, 'executable': '/tools/claude'}]
        with patch.object(cleanup, 'ensure_runtime_idle', wraps=self.runtime_guard), \
                patch.object(cleanup, 'process_snapshot', return_value=processes):
            with self.assertRaises(ValueError):
                self.execute(self.ctx.plan('history', 'code'))
        self.assertTrue(source.exists())
        self.assertFalse((self.base/'result').exists())

    def test_process_check_failure_refuses_cleanup(self):
        self.file('.claude/history.jsonl')
        with patch.object(cleanup, 'ensure_runtime_idle', wraps=self.runtime_guard), \
                patch.object(cleanup, 'process_snapshot', side_effect=ValueError('unavailable')):
            with self.assertRaises(ValueError):
                self.execute(self.ctx.plan('history', 'code'))
        self.assertFalse((self.base/'result').exists())

    def test_windows_runtime_detection(self):
        ctx = cleanup.Context(self.home, 'Windows', {})
        records = [{'pid': 123, 'ppid': 1, 'executable': r'C:\Tools\Claude.exe'}]
        with patch.object(cleanup, 'process_snapshot', return_value=records), self.assertRaises(ValueError):
            self.runtime_guard(ctx)

    def test_native_versioned_binary_is_detected(self):
        records = [{'pid': 123, 'ppid': 1,
                    'executable': str(self.home/'.local/share/claude/versions/2.1.304')}]
        with patch.object(cleanup, 'process_snapshot', return_value=records), self.assertRaises(ValueError):
            self.runtime_guard(self.ctx)

    def test_restart_after_backup_stops_before_removal(self):
        source = self.file('.claude/CLAUDE.md')
        with patch.object(cleanup, 'ensure_runtime_idle', side_effect=[None, ValueError('restarted')]):
            result = self.execute(self.ctx.plan('reset', 'code'))
        self.assertTrue(result['errors'])
        self.assertTrue(source.exists())
        self.assertEqual(result['removed'], [])
        self.assertTrue((self.base/'result/reusable-assets/CLAUDE.md').exists())

    def test_posix_process_snapshot_never_requests_arguments(self):
        result = SimpleNamespace(stdout=f'{os.getpid()} 1 /tools/python3\n123 1 /apps/Claude.app/Contents/MacOS/Claude\n')
        with patch.object(cleanup.subprocess, 'run', return_value=result) as run:
            records = cleanup.process_snapshot('Darwin')
        self.assertEqual(len(records), 2)
        self.assertEqual(run.call_args.args[0], ['ps', '-axo', 'pid=,ppid=,comm='])

    def test_windows_process_snapshot_uses_metadata_without_command_line(self):
        data = [{'ProcessId': os.getpid(), 'ParentProcessId': 1, 'Name': 'python.exe', 'ExecutablePath': None}]
        with patch.object(cleanup.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(data))) as run:
            records = cleanup.process_snapshot('Windows')
        self.assertEqual(records[0]['executable'], 'python.exe')
        cmd = run.call_args.args[0]
        self.assertNotIn('CommandLine', cmd[-1])
        self.assertIn('ExecutablePath', cmd[-1])

    def test_process_snapshot_error_hides_command_output(self):
        error = subprocess.CalledProcessError(1, 'ps', output='PRIVATE_SENTINEL', stderr='PRIVATE_SENTINEL')
        with patch.object(cleanup.subprocess, 'run', side_effect=error):
            with self.assertRaises(ValueError) as caught:
                cleanup.process_snapshot('Darwin')
        self.assertNotIn('PRIVATE_SENTINEL', str(caught.exception))

    def test_helper_inside_cleanup_root_is_refused(self):
        self.file('.claude/settings.json', '{}')
        with patch.object(cleanup, '__file__', str(self.home/'.claude/skills/cleanup.py')):
            with self.assertRaises(ValueError):
                self.execute(self.ctx.plan('reset', 'code'))
        self.assertFalse((self.base/'result').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
