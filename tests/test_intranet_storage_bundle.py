import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "deploy" / "intranet" / "storage"


def test_product_policy_has_only_product_and_u6_object_permissions():
    policy = json.loads((BUNDLE / "product-policy.json").read_text(encoding="utf-8"))
    assert policy == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                "Resource": [
                    "arn:aws:s3:::saintvision-objects/saintvision/product/*",
                    "arn:aws:s3:::saintvision-objects/saintvision-u6/*",
                ],
            }
        ],
    }


def test_pitr_policy_separates_object_and_prefix_scoped_list_permissions():
    policy = json.loads((BUNDLE / "pitr-policy.json").read_text(encoding="utf-8"))
    statements = policy["Statement"]
    assert statements[0]["Action"] == [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
    ]
    assert statements[0]["Resource"] == "arn:aws:s3:::saintvision-pitr/pilot/*"
    assert statements[1] == {
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": "arn:aws:s3:::saintvision-pitr",
        "Condition": {"StringLike": {"s3:prefix": ["pilot/*"]}},
    }


def test_minio_script_pins_image_and_keeps_container_boundary():
    script = (BUNDLE / "provision-minio.sh").read_text(encoding="utf-8")
    assert "coollabsio/minio@sha256:72b4794d" in script
    for required in (
        "--user \"$(id -u):$(id -g)\"",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "refusing to replace an unowned container",
        "preserved rollback container",
        'docker rename "$ROLLBACK_NAME" "$NAME"',
        "partial TLS input is forbidden",
        'set -- "$@" --certs-dir /certs',
        '[ "$TLS_ENABLED" = true ] && admin_host="$BIND_ADDRESS"',
        "timeout 3 docker exec -i",
        "until mc_ready",
        'printf \'%s\\n\' "$ADMIN_ALIAS" "$SVC_KEY" "$SVC_SECRET"',
        "IFS= read -r MC_HOST_local",
        "exec stdin, never host process arguments",
    ):
        assert required in script
    assert "MINIO_CERTS_DIR" not in script
    assert '-e "MC_HOST_local=$ADMIN_ALIAS"' not in script
    for forbidden in ("docker system", "docker volume prune", "docker image prune", "sudo "):
        assert forbidden not in script
    assert '$CONFIG_DIR:/run/saintvision-intranet' not in script


def test_pitr_rehearsal_uses_uploaded_bytes_and_checks_replication_before_source_mutation():
    script = (BUNDLE / "rehearse-pilot-pitr.sh").read_text(encoding="utf-8")
    for required in (
        "pg_receivewal --synchronous",
        "pg_basebackup",
        "pitr_archive_retention.py",
        "uploadDownloadDigestMatched",
        "recovery_target_time",
        "afterMarkerAbsent",
        "refusing to remove an unowned container",
    ):
        assert required in script
    receiver_check = script.index("WAL receiver did not start")
    source_mutation = script.index('source_psql postgres -c "CREATE DATABASE $DB"')
    assert receiver_check < source_mutation
    for forbidden in ("docker system", "docker volume prune", "docker image prune", "rm -rf", "sudo "):
        assert forbidden not in script
    assert '$CONFIG_DIR:/run/saintvision-intranet' not in script
    assert 'trusted MinIO CA chain is absent' in script
    assert '-e "MC_HOST_pitr=' not in script
    assert '--env-file "$SOURCE_ENV"' not in script
    assert '$PITR_ENV:/run/secrets/pitr.env:ro' in script
    assert script.count('$SOURCE_ENV:/run/secrets/source.env:ro') == 3
    assert 'the host process arguments or Docker Config.Env' in script
    assert 'TLS operational acceptance is pending' not in script
