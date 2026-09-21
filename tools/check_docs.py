"""Validate the source archive, document links and planned task traceability."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
PASSWORD_BEARING_POSTGRES_DSN = re.compile(
    r'(?i)(?:postgres(?:ql)?(?:\+[a-z0-9_]+)?|postgres)://[^:/@\s]+:'
    r'(?!(?:\*{3,}|<redacted>|\[redacted\]|redacted|change[_-]?me)(?=@))[^@/\s?#]+@'
)
DOC_TEXT_SUFFIXES = {'.md', '.txt', '.json', '.jsonl', '.xml', '.yaml', '.yml', '.csv', '.log'}
SECRET_BEARING_CONFIG_PATHS = ('.env.example', 'tools/deploy_intranet.ps1')


def password_bearing_postgres_dsn_count(text):
    """Count credential-bearing PostgreSQL URIs, excluding explicit mask markers."""
    return len(PASSWORD_BEARING_POSTGRES_DSN.findall(text))


def validate(root=ROOT):
    errors = []
    vault = root / 'docs/vault'
    manifest = json.loads((root / 'docs/source-manifest.json').read_text('utf-8'))
    for item in manifest['files']:
        source = root / 'docs/sources' / item['path']
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            errors.append(f'Original source changed: {item["path"]}')
    files = list(vault.rglob('*'))
    targets = {p.name for p in files if p.is_file()} | {p.stem for p in files if p.is_file()}
    scan_targets = [
        (path, path.relative_to(vault))
        for path in files
        if path.is_file() and path.suffix.lower() in DOC_TEXT_SUFFIXES
    ]
    scan_targets.extend(
        (root / relative, Path(relative))
        for relative in SECRET_BEARING_CONFIG_PATHS
        if (root / relative).is_file()
    )
    for path, display_path in scan_targets:
        try:
            content = path.read_text('utf-8-sig')
        except UnicodeDecodeError:
            errors.append(f'Unreadable UTF-8 document/config: {display_path}')
            continue
        dsn_count = password_bearing_postgres_dsn_count(content)
        if dsn_count:
            errors.append(
                f'Password-bearing PostgreSQL DSN must be redacted '
                f'({dsn_count} occurrence(s)): {display_path}'
            )
    ids = {}
    count = 0
    for path in files:
        if path.suffix != '.md':
            continue
        content = path.read_text('utf-8-sig')
        for match in re.finditer(r'\[\[([^\]|#]+)(?:[^\]]*)\]\]', content):
            target = match.group(1).split('/')[-1]
            if target not in targets:
                errors.append(f'Broken wiki link {path.relative_to(vault)} → {target}')
        match = re.search(r'^doc_id: (.+)$', content, re.M)
        if match:
            doc_id = json.loads(match.group(1))
            if doc_id in ids:
                errors.append(f'Duplicate document ID: {doc_id}')
            ids[doc_id] = path
            count += 1
            for field in ['title', 'version', 'status', 'author', 'updated', 'source_of_truth']:
                if not re.search(rf'^{field}: ', content, re.M):
                    errors.append(f'Missing metadata {field}: {path.name}')
    registry = json.loads((root / 'docs/task-registry.json').read_text('utf-8'))
    tasks = registry['tasks']
    task_ids = {t['task_id'] for t in tasks}
    outcomes = {o['id']: o for o in registry['outcomes']}
    if len(task_ids) != len(tasks):
        errors.append('Duplicate task IDs')
    # Deliberate governance baseline, not a derived count: accidental task or
    # outcome deletion/addition must trigger an explicit registry review.
    if len(tasks) != 48 or len(outcomes) != 12:
        errors.append('Baseline must contain 48 tasks and 12 outcomes')
    for task in tasks:
        for field in ['sprint', 'area', 'owner', 'reviewer', 'status', 'outcome_ids', 'acceptance_ids', 'contract_refs', 'skill_refs', 'scope', 'evidence_required', 'next_handoff']:
            if not task.get(field):
                errors.append(f'Missing {field}: {task["task_id"]}')
        if task['owner'] == task['reviewer']:
            errors.append(f'Self-review: {task["task_id"]}')
        if task['owner'] not in ['Codex', 'Claude', 'Gemini']:
            errors.append(f'Unknown owner: {task["task_id"]}')
        if task['area'] == 'Frontend' and task['owner'] != 'Gemini':
            errors.append(f'Frontend ownership mismatch: {task["task_id"]}')
        if task['status'] not in ['planned', 'ready', 'in_progress', 'review', 'done', 'blocked']:
            errors.append(f'Unknown status: {task["task_id"]}')
        for ref in task['contract_refs']:
            if ref not in targets:
                errors.append(f'Missing contract reference: {ref}')
        for skill in task['skill_refs']:
            if not (root / 'skills' / skill / 'SKILL.md').is_file():
                errors.append(f'Missing skill: {skill}')
        for oid in task['outcome_ids']:
            if oid not in outcomes or outcomes[oid]['acceptance_id'] not in task['acceptance_ids']:
                errors.append(f'Broken acceptance trace: {task["task_id"]}')
        if not set(task['depends_on']).issubset(task_ids):
            errors.append(f'Unknown dependency: {task["task_id"]}')
    graph = {t['task_id']: t['depends_on'] for t in tasks}
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            errors.append(f'Dependency cycle: {node}')
            return
        if node in visited or node not in graph:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    for oid in outcomes:
        if not any(oid in task['outcome_ids'] for task in tasks):
            errors.append(f'Unimplemented outcome mapping: {oid}')
    for n in range(1, 13):
        areas = {t['area'] for t in tasks if t['sprint'] == f'S{n:02}'}
        if areas != {'Frontend', 'Backend', 'DB', 'Storage'}:
            errors.append(f'Missing area in S{n:02}')
    if errors:
        raise ValueError('\n'.join(errors))
    print(f'PASS: {len(manifest["files"])} original hashes, {count} versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.')


if __name__ == '__main__':
    validate()
