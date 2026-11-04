#!/usr/bin/env python3
"""Claude local cleanup helper. Python 3.9+, stdlib only. Never invokes uninstallers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA = 1
MODES = ('cache', 'history', 'reset', 'uninstall')
PRODUCTS = ('code', 'desktop', 'both')
DISPOSITIONS = ('delete', 'quarantine')
ASSETS = ('CLAUDE.md', 'skills', 'hooks', 'commands', 'agents')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def lexists(path):
    return os.path.lexists(str(path))


def linked(path):
    """Includes Windows junctions even on Python before Path.is_junction()."""
    if not lexists(path):
        return False
    s = path.lstat()
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def absolute(path):
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def contains(parent, child):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def plain_parents(path):
    for parent in path.parents:
        if linked(parent):
            raise ValueError('Linked/reparse parent; manual review required: ' + str(parent))


def identity(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns]


def process_snapshot(system):
    """Read process metadata only: never request arguments, environment or credentials."""
    try:
        if system == 'Darwin':
            r = subprocess.run(['ps', '-axo', 'pid=,ppid=,comm='],
                               capture_output=True, text=True, timeout=10, check=True)
            records = []
            for line in r.stdout.splitlines():
                parts = line.strip().split(maxsplit=2)
                if len(parts) != 3:
                    raise ValueError('Incomplete process metadata')
                records.append({'pid': int(parts[0]), 'ppid': int(parts[1]), 'executable': parts[2]})
        else:
            script = ('Get-CimInstance Win32_Process -ErrorAction Stop | '
                      'Select-Object ProcessId,ParentProcessId,Name,ExecutablePath | '
                      'ConvertTo-Json -Compress')
            r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                               capture_output=True, text=True, timeout=15, check=True)
            data = json.loads(r.stdout)
            data = [data] if isinstance(data, dict) else data
            records = [{'pid': int(p['ProcessId']), 'ppid': int(p['ParentProcessId']),
                        'executable': str(p.get('ExecutablePath') or p['Name'])} for p in data]
        if not records or os.getpid() not in {p['pid'] for p in records}:
            raise ValueError('Current process missing from process metadata')
        return records
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        raise ValueError('Cannot verify process state; no cleanup allowed') from None


def ensure_runtime_idle(ctx):
    records = process_snapshot(ctx.system)
    found = []
    native_versions = str(ctx.home / '.local/share/claude/versions').replace('\\', '/').lower().rstrip('/') + '/'
    for p in records:
        path = p['executable'].replace('\\', '/').lower()
        name = path.rsplit('/', 1)[-1]
        if (name in ('claude', 'claude-code', 'claude-3p', 'claude.exe', 'claude-code.exe', 'claude-3p.exe')
                or '/claude.app/' in path or '/claude-3p.app/' in path
                or path.startswith(native_versions)):
            found.append(p['pid'])
    if found:
        raise ValueError('Claude runtime active; use preview and close it normally before writing. PIDs: '
                         + ','.join(str(pid) for pid in sorted(set(found))))


def write_json(path, data):
    path = absolute(path)
    plain_parents(path)
    if lexists(path):
        raise ValueError('Refusing to overwrite existing output: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    if os.name != 'nt':
        path.chmod(0o600)


class Context:
    def __init__(self, home=None, system=None, env=None):
        self.home = absolute(home or Path.home())
        self.system = system or platform.system()
        self.env = dict(os.environ if env is None else env)
        if self.system not in ('Darwin', 'Windows'):
            raise ValueError('Supported hosts: macOS and native Windows; WSL/Linux require separate review')
        self.appdata = absolute(self.env.get('APPDATA', self.home / 'AppData/Roaming'))
        self.localappdata = absolute(self.env.get('LOCALAPPDATA', self.home / 'AppData/Local'))
        raw = self.env.get('CLAUDE_CONFIG_DIR')
        if raw and not Path(os.path.expanduser(raw)).is_absolute():
            raise ValueError('CLAUDE_CONFIG_DIR must be an absolute verified path')
        self.config = absolute(raw) if raw else self.home / '.claude'
        # An arbitrary custom root is not a license to erase a project/shared vault.
        # Automatic custom roots must be direct home children named .claude-*.
        if self.config != self.home / '.claude':
            if self.config.parent != self.home or not self.config.name.startswith('.claude-'):
                raise ValueError('Custom config outside direct ~/.claude-* requires manual scoped review')

    def code_user(self):
        if self.system == 'Darwin':
            return self.home / 'Library/Application Support/Code/User'
        return self.appdata / 'Code/User'

    def candidates(self, mode, product):
        if mode not in MODES or product not in PRODUCTS:
            raise ValueError('Invalid scope')
        if mode != 'uninstall' and product != 'code':
            raise ValueError('history/reset require --product code')
        targets, warnings = {}, []

        def add(path, kind, allow_link=False):
            path = absolute(path)
            if not lexists(path):
                return
            try:
                plain_parents(path)
                if linked(path) and not allow_link:
                    raise ValueError('Root is a link/reparse point: ' + str(path))
                targets[str(path)] = {'path': str(path), 'kind': kind, 'identity': identity(path)}
            except (ValueError, OSError) as e:
                warnings.append(str(e))

        code = product in ('code', 'both')
        if code:
            if mode == 'history':
                for name in ('history.jsonl', 'sessions', 'paste-cache', 'file-history', 'debug'):
                    add(self.config / name, 'history')
                # Only transcripts; never whole projects/ because it also contains memory.
                root = self.config / 'projects'
                if root.is_dir() and not linked(root):
                    for base, dirs, files in os.walk(root, followlinks=False):
                        dirs[:] = [d for d in dirs if not linked(Path(base) / d)]
                        for name in files:
                            parts = (Path(base) / name).relative_to(root).parts
                            transcript = (len(parts) == 2 or
                                          (len(parts) == 4 and parts[2] == 'subagents'
                                           and name.startswith('agent-')))
                            if transcript and name.endswith('.jsonl'):
                                add(Path(base) / name, 'transcript')
            elif mode != 'cache':
                add(self.config, 'code-data')
                # Default root JSON belongs to the default config only.
                if self.config == self.home / '.claude':
                    for name in ('.claude.json', '.claude.json.backup'):
                        add(self.home / name, 'code-config')
            if mode in ('cache', 'history'):
                for name in ('cache', 'telemetry', 'statsig', 'stats-cache.json'):
                    add(self.config / name, 'code-cache')
                if self.system == 'Darwin':
                    add(self.home / 'Library/Caches/claude-cli-nodejs', 'code-cache')
            if mode == 'uninstall':
                exe = 'claude.exe' if self.system == 'Windows' else 'claude'
                add(self.home / '.local/bin' / exe, 'native-executable', allow_link=True)
                for name in ('share', 'state'):
                    add(self.home / '.local' / name / 'claude', 'native-runtime')
                ext = self.home / '.vscode/extensions'
                cache = (self.home / 'Library/Application Support/Code/CachedExtensionVSIXs'
                         if self.system == 'Darwin' else self.appdata / 'Code/CachedExtensionVSIXs')
                for root in (ext, cache):
                    if root.is_dir() and not linked(root):
                        for p in root.iterdir():
                            if p.name.startswith('anthropic.claude-code-'):
                                add(p, 'vscode-extension')
                if self.system == 'Darwin':
                    add(self.home / 'Library/Caches/claude-cli-nodejs', 'code-cache')
        if mode == 'uninstall' and product in ('desktop', 'both'):
            if self.system == 'Darwin':
                lib = self.home / 'Library'
                for group, names in {
                    'Application Support': ('Claude', 'Claude-3p'),
                    'Caches': ('com.anthropic.claudefordesktop',),
                    'Logs': ('Claude', 'Claude-3p'),
                    'Preferences': ('com.anthropic.claudefordesktop.plist',),
                    'Saved Application State': ('com.anthropic.claudefordesktop.savedState',),
                    'HTTPStorages': ('com.anthropic.claudefordesktop',),
                    'WebKit': ('com.anthropic.claudefordesktop', 'com.claude-code-haha.desktop'),
                }.items():
                    for name in names:
                        add(lib / group / name, 'desktop-data')
            else:
                add(self.appdata / 'Claude', 'desktop-data')
                add(self.appdata / 'Claude-3p', 'desktop-data')
        if self.config != self.home / '.claude' and lexists(self.home / '.claude'):
            warnings.append('INFO: Default ~/.claude also exists; not selected under custom config scope')
        return list(targets.values()), warnings

    def plan(self, mode, product, disposition='delete'):
        if disposition not in DISPOSITIONS:
            raise ValueError('Invalid disposition')
        entries, warnings = self.candidates(mode, product)
        return {'schema': SCHEMA, 'created_at': stamp(), 'system': self.system,
                'home': str(self.home), 'config': str(self.config), 'mode': mode,
                'product': product, 'disposition': disposition, 'entries': entries, 'warnings': warnings,
                'not_automated': ['native package/desktop uninstall', 'logout and credential removal',
                                  'app/process shutdown', 'shell/env changes', 'custom forks/IDEs',
                                  'shared consumer migration', 'protected system records', 'WSL']}


def safe_output(out, entries):
    out = absolute(out)
    plain_parents(out)
    if lexists(out):
        raise ValueError('Output must be new: ' + str(out))
    for e in entries:
        p = Path(e['path'])
        if contains(p, out) or contains(out, p):
            raise ValueError('Output overlaps cleanup target')
    return out


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def backup(ctx, out):
    entries, _ = ctx.candidates('uninstall', 'both')
    out = safe_output(out, entries + [{'path': str(ctx.config)}])
    out.mkdir(parents=True, mode=0o700)
    copied, skipped = [], []

    def copy(src, dst):
        if linked(src):
            skipped.append({'path': str(src), 'reason': 'link/reparse; target not followed'})
        elif src.name in ('.trash', '.git', '.DS_Store', '.credentials.json') or src.name.startswith('.env'):
            skipped.append({'path': str(src), 'reason': 'excluded backup content'})
        elif src.is_dir():
            dst.mkdir(mode=0o700)
            for child in sorted(src.iterdir()):
                copy(child, dst / child.name)
        elif src.is_file():
            shutil.copyfile(src, dst)
            if os.name != 'nt':
                dst.chmod(0o600)
            before = digest(src)
            if before != digest(dst):
                raise ValueError('Backup verification failed')
            copied.append({'relative_path': str(dst.relative_to(out)), 'sha256': before})
        else:
            raise ValueError('Unsupported asset file type: ' + str(src))

    if lexists(ctx.config):
        plain_parents(ctx.config)
        if linked(ctx.config):
            raise ValueError('Config root is linked; back up manually before cleanup')
        for name in ASSETS:
            src = ctx.config / name
            if lexists(src):
                copy(src, out / name)
        settings = ctx.config / 'settings.json'
        if settings.is_file():
            if linked(settings):
                raise ValueError('Settings link requires manual review')
            data = json.loads(settings.read_text(encoding='utf-8'))
            # Do not copy arbitrary nested values just because their key looks safe.
            safe = {}
            if data.get('effortLevel') in ('low', 'medium', 'high', 'max', 'xhigh'):
                safe['effortLevel'] = data['effortLevel']
            if type(data.get('includeCoAuthoredBy')) is bool:
                safe['includeCoAuthoredBy'] = data['includeCoAuthoredBy']
            if isinstance(data.get('enabledPlugins'), dict):
                safe['enabledPlugins'] = {k: v for k, v in data['enabledPlugins'].items() if type(v) is bool}
            write_json(out / 'settings.safe.json', safe)
    write_json(out / 'backup-manifest.json', {
        'created_at': stamp(), 'files': copied, 'skipped': skipped,
        'limits': 'Reusable assets only; no full rollback. Raw env/MCP/hook settings, transcripts and credentials excluded. Custom asset content may be sensitive.'})
    return {'directory': str(out), 'files_verified': len(copied), 'skipped': len(skipped)}


def validate_plan(ctx, plan):
    if (plan.get('schema') != SCHEMA or plan.get('system') != ctx.system or
            plan.get('home') != str(ctx.home) or plan.get('config') != str(ctx.config)):
        raise ValueError('Plan host/config mismatch')
    if plan.get('disposition', 'delete') not in DISPOSITIONS:
        raise ValueError('Invalid disposition')
    mode, product = plan.get('mode'), plan.get('product')
    current, warnings = ctx.candidates(mode, product)
    blocking = [w for w in warnings if not w.startswith('INFO:')]
    if blocking:
        raise ValueError('Resolve candidate warnings before apply: ' + '; '.join(blocking))
    allowed = {e['path']: e for e in current}
    seen = set()
    for entry in plan['entries']:
        name = entry['path']
        if name in seen:
            raise ValueError('Duplicate plan path')
        seen.add(name)
        p = Path(name)
        plain_parents(p)
        if not lexists(p):
            continue  # Native uninstaller may already have removed it.
        if name not in allowed or entry != allowed[name]:
            raise ValueError('Target not allowed or identity changed; regenerate plan: ' + name)
    return current


def apply(ctx, plan, out, execute=False, apps_stopped=False):
    validate_plan(ctx, plan)
    if not execute:
        return {'dry_run': True, 'disposition': plan.get('disposition', 'delete'),
                'entries': plan['entries'], 'message': 'No files deleted'}
    if not apps_stopped:
        raise ValueError('Verify apps/extensions stopped, then use --apps-stopped')
    ensure_runtime_idle(ctx)
    entries = plan['entries']
    if any(contains(Path(e['path']), absolute(__file__)) for e in entries):
        raise ValueError('Cleanup helper is inside cleanup scope; run a copy outside the targets')
    out = safe_output(out, entries + [{'path': str(ctx.config)}])
    out.mkdir(parents=True, mode=0o700)
    report = {'started_at': stamp(), 'mode': plan['mode'], 'product': plan['product'],
              'disposition': plan.get('disposition', 'delete'), 'quarantined': [],
              'removed': [], 'already_absent': [], 'errors': [], 'backup': None,
              'native_steps': 'Not automated; agent must verify uninstall/logout/credentials/processes separately'}
    write_json(out / 'reviewed-plan.json', plan)
    try:
        if plan['mode'] in ('reset', 'uninstall') and plan['product'] in ('code', 'both'):
            report['backup'] = backup(ctx, out / 'reusable-assets')
        ensure_runtime_idle(ctx)
        validate_plan(ctx, plan)
        destinations = {}
        if report['disposition'] == 'quarantine':
            quarantine = out / 'quarantine'
            quarantine.mkdir(mode=0o700)
            for index, entry in enumerate(entries):
                p = Path(entry['path'])
                if lexists(p) and p.lstat().st_dev != quarantine.stat().st_dev:
                    raise ValueError('Quarantine requires the same filesystem; no cross-volume copy/delete fallback')
                destinations[str(p)] = str(quarantine / ('%04d-' % index + p.name))
            write_json(out / 'quarantine-map.json', {
                'notice': 'Raw data may include transcripts and credentials; not erased, no full rollback of native steps',
                'paths': destinations})
        for entry in entries:
            p = Path(entry['path'])
            if not lexists(p):
                report['already_absent'].append(str(p))
                continue
            plain_parents(p)
            if identity(p) != entry['identity']:
                raise ValueError('Target changed during cleanup: ' + str(p))
            if report['disposition'] == 'quarantine':
                destination = Path(destinations[str(p)])
                if lexists(destination):
                    raise ValueError('Quarantine destination exists')
                os.rename(str(p), str(destination))
                report['quarantined'].append({'source': str(p), 'destination': str(destination)})
                continue
            if linked(p):
                if entry['kind'] != 'native-executable':
                    raise ValueError('Unexpected linked cleanup target')
                p.unlink()
            elif p.is_dir():
                # Do not traverse Windows reparse points nested inside data directories.
                for base, dirs, files in os.walk(p, followlinks=False):
                    for name in dirs + files:
                        child = Path(base) / name
                        if linked(child):
                            if os.name == 'nt':
                                raise ValueError('Nested reparse point requires manual handling: ' + str(child))
                            # POSIX rmtree unlinks symlinks without following them.
                shutil.rmtree(p)
            elif p.is_file():
                p.unlink()
            else:
                raise ValueError('Unsupported target file type')
            report['removed'].append(str(p))
    except Exception as e:
        report['errors'].append(str(e))
    report['remaining'] = [e['path'] for e in entries if lexists(Path(e['path']))]
    report['finished_at'] = stamp()
    write_json(out / 'cleanup-report.json', report)
    return report


def editor_state(ctx, execute=False, apps_stopped=False):
    if execute and not apps_stopped:
        raise ValueError('Close VS Code before --execute --apps-stopped')
    if execute:
        ensure_runtime_idle(ctx)
    root = ctx.code_user()
    dbs = [root / 'globalStorage/state.vscdb', root / 'globalStorage/state.vscdb.backup']
    workspaces = root / 'workspaceStorage'
    if workspaces.is_dir():
        plain_parents(workspaces / '_check')
        for d in workspaces.iterdir():
            if d.is_dir() and not linked(d):
                dbs += [d / 'state.vscdb', d / 'state.vscdb.backup']
    result = {'dry_run': not execute, 'databases_checked': 0, 'matches': [], 'errors': []}
    for db in dbs:
        if not lexists(db):
            continue
        try:
            plain_parents(db)
            if linked(db):
                raise ValueError('Linked database')
            with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=3) as c:
                candidates = [row[0] for row in c.execute(
                    "SELECT key FROM ItemTable WHERE lower(key) LIKE '%anthropic.claude-code%'")]
                keys = []
                for key in candidates:
                    if key.lower() == 'anthropic.claude-code' or key.lower().startswith('secret://anthropic.claude-code/'):
                        keys.append(key)
                    elif key.startswith('secret://{'):
                        try:
                            meta = json.loads(key[len('secret://'):])
                            if str(meta.get('extensionId', '')).lower() == 'anthropic.claude-code':
                                keys.append(key)
                        except (ValueError, TypeError, AttributeError):
                            pass
                count = len(keys)
            result['databases_checked'] += 1
            if count:
                if execute:
                    with sqlite3.connect(str(db), timeout=3) as c:
                        if c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError('Database integrity check failed before write')
                        c.execute('PRAGMA secure_delete=ON')
                        c.executemany('DELETE FROM ItemTable WHERE key = ?', [(key,) for key in keys])
                        c.commit()
                        remaining = any(c.execute('SELECT 1 FROM ItemTable WHERE key = ?', (key,)).fetchone() for key in keys)
                        if remaining or c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError('Post-write verification failed')
                result['matches'].append({'database': str(db), 'records': count, 'removed': execute})
        except (ValueError, OSError, sqlite3.Error) as e:
            result['errors'].append({'database': str(db), 'error_type': type(e).__name__})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    plan_p = sub.add_parser('plan', help='Discover exact existing paths; never delete')
    plan_p.add_argument('--mode', choices=MODES, default='uninstall')
    plan_p.add_argument('--product', choices=PRODUCTS, default=None)
    plan_p.add_argument('--disposition', choices=DISPOSITIONS, default='delete',
                        help='delete permanently (default) or quarantine raw files on the same filesystem')
    plan_p.add_argument('--out', required=True)
    back_p = sub.add_parser('backup', help='Verified reusable assets, not credentials/history')
    back_p.add_argument('--out', required=True)
    apply_p = sub.add_parser('apply', help='Preview unless --execute explicitly supplied')
    apply_p.add_argument('--plan', required=True)
    apply_p.add_argument('--out', required=True)
    apply_p.add_argument('--execute', action='store_true')
    apply_p.add_argument('--apps-stopped', action='store_true')
    editor_p = sub.add_parser('editor-state', help='Narrow VS Code extension namespace only')
    editor_p.add_argument('--execute', action='store_true')
    editor_p.add_argument('--apps-stopped', action='store_true')
    editor_p.add_argument('--out', required=True)
    args = p.parse_args()
    try:
        ctx = Context()
        if args.command == 'plan':
            product = args.product or ('both' if args.mode == 'uninstall' else 'code')
            result = ctx.plan(args.mode, product, args.disposition)
            safe_output(args.out, result['entries'] + [{'path': str(ctx.config)}])
            write_json(Path(args.out), result)
        elif args.command == 'backup':
            ensure_runtime_idle(ctx)
            result = backup(ctx, Path(args.out))
        elif args.command == 'apply':
            plan_file = absolute(args.plan)
            plan = json.loads(plan_file.read_text(encoding='utf-8'))
            # Keep manifest outside all deletion roots.
            if any(contains(Path(e['path']), plan_file) for e in plan['entries']):
                raise ValueError('Manifest is inside cleanup scope')
            result = apply(ctx, plan, Path(args.out), args.execute, args.apps_stopped)
        else:
            # Check output before mutating SQLite so failed logging cannot hide changes.
            output = safe_output(args.out, [{'path': str(ctx.code_user())}])
            result = editor_state(ctx, args.execute, args.apps_stopped)
            write_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('errors') or result.get('remaining') else 0
    except (ValueError, OSError, KeyError, TypeError) as e:
        # Never print configuration content, command stdout, or arbitrary exception values.
        print(json.dumps({'error_type': type(e).__name__, 'message': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
