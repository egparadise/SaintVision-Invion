import json

import pytest

from tools.check_docs import password_bearing_postgres_dsn_count, validate


def test_password_bearing_postgres_dsn_is_detected():
    assert password_bearing_postgres_dsn_count(
        'INV_TEST_DSN=postgresql://operator:sample-secret@db.internal:5432/app'
    ) == 1


def test_explicitly_redacted_dsn_and_passwordless_uri_are_allowed():
    text = '\n'.join(
        [
            'postgresql://operator:***@db.internal:5432/app',
            'postgresql://inv_app:CHANGE_ME@localhost:55432/invdev',
            'postgresql://operator@db.internal:5432/app',
        ]
    )
    assert password_bearing_postgres_dsn_count(text) == 0


@pytest.mark.parametrize(
    'relative_path',
    [
        'docs/vault/Evidence/proposal.txt',
        '.env.example',
        'tools/deploy_intranet.ps1',
    ],
)
def test_validation_rejects_passworded_dsn_in_docs_and_runtime_configs(tmp_path, relative_path):
    vault = tmp_path / 'docs' / 'vault'
    vault.mkdir(parents=True)
    (vault / 'index.md').write_text(
        '---\ndoc_id: "DOC-1"\ntitle: "Index"\nversion: "1"\n'
        'status: "review"\nauthor: "Codex"\n'
        'updated: "2026-09-21T00:00:00+09:00"\nsource_of_truth: "Git"\n---\n',
        encoding='utf-8',
    )
    (vault / 'contract.md').write_text('contract target\n', encoding='utf-8')
    bad_config = tmp_path / relative_path
    bad_config.parent.mkdir(parents=True, exist_ok=True)
    bad_config.write_text(
        'dsn=postgresql://operator:sample-secret@db.internal:5432/app\n',
        encoding='utf-8',
    )
    (tmp_path / 'docs' / 'source-manifest.json').write_text(
        json.dumps({'files': []}), encoding='utf-8'
    )
    (tmp_path / 'skills' / 'test-skill').mkdir(parents=True)
    (tmp_path / 'skills' / 'test-skill' / 'SKILL.md').write_text('skill\n', encoding='utf-8')

    acceptance_ids = [f'A{i}' for i in range(12)]
    task_ids = []
    for sprint in range(1, 13):
        for area in ['Frontend', 'Backend', 'DB', 'Storage']:
            task_ids.append({
                'task_id': f'T-{sprint}-{area}', 'sprint': f'S{sprint:02}', 'area': area,
                'owner': 'Codex', 'reviewer': 'Claude', 'status': 'planned',
                'outcome_ids': [f'O{i}' for i in range(12)],
                'acceptance_ids': acceptance_ids, 'contract_refs': ['contract.md'],
                'skill_refs': ['test-skill'], 'scope': 'fixture',
                'evidence_required': 'test', 'next_handoff': 'none', 'depends_on': [],
            })
    registry = {
        'tasks': task_ids,
        'outcomes': [{'id': f'O{i}', 'acceptance_id': f'A{i}'} for i in range(12)],
    }
    (tmp_path / 'docs' / 'task-registry.json').write_text(
        json.dumps(registry), encoding='utf-8'
    )

    with pytest.raises(ValueError, match='Password-bearing PostgreSQL DSN must be redacted'):
        validate(tmp_path)
