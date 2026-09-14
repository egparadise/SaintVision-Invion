"""Bounded GitHub object adapter. Fixed host, no redirects, hooks or shell.

Publication uses createCommitOnBranch's atomic expectedHeadOid precondition.
There is deliberately no transport retry: an ambiguous mutation is reconciled
read-only by the caller. Only regular non-executable files are supported.
"""

import base64
import hashlib
import re
import ssl
import time
from pathlib import Path
from threading import Timer
from urllib.parse import quote

from .approvals import digest
from .errors import DomainError
from .identity import strict_object
from .node_transport import OneConnection, private_key
from .workspace_files import FORMAT, canonical, portable_path
from .workspace_resume import bounded_snapshot


def oid(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{40}", value):
        raise DomainError("VAL-0003", "Exact SHA-1 Git object ID required", 422)
    return value


def git_files(raw, workspace_id):
    manifest = bounded_snapshot(raw, workspace_id)
    if len(manifest["files"]) > 128:
        raise DomainError("STORE-0020", "Remote Git supports at most 128 files", 422)
    for f in manifest["files"]:
        if f["executable"] or any(p.casefold() == ".git" for p in portable_path(f["path"])):
            raise DomainError(
                "SEC-0020", "Remote Git requires regular non-executable files without .git", 422
            )
    # Git does not preserve empty directories. Refuse silent loss on export.
    parents = {f["path"].rsplit("/", 1)[0] for f in manifest["files"] if "/" in f["path"]}
    all_parents = set()
    for parent in parents:
        parts = parent.split("/")
        all_parents.update("/".join(parts[:n]) for n in range(1, len(parts) + 1))
    if set(manifest["directories"]) != all_parents:
        raise DomainError("VAL-0003", "Remote Git cannot preserve empty directories", 422)
    return {f["path"]: f for f in manifest["files"]}


def export_snapshot(raw, workspace_id):
    """Git metadata is local execution state, never part of a remote file commit."""
    manifest = bounded_snapshot(raw, workspace_id)
    manifest["files"] = [
        f for f in manifest["files"] if f["path"].split("/")[0].casefold() != ".git"
    ]
    manifest["directories"] = [
        p for p in manifest["directories"] if p.split("/")[0].casefold() != ".git"
    ]
    result = canonical(manifest)
    git_files(result, workspace_id)
    return result


class GitHubRepository:
    def __init__(self, *, alias, projectId, repository, branch, tokenFile):
        if (
            not re.fullmatch("[a-z][a-z0-9-]{0,63}", alias)
            or not re.fullmatch("[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository)
            or not isinstance(branch, str)
            or not 1 <= len(branch) <= 200
            or not re.fullmatch("[A-Za-z0-9_/-]+", branch)
            or any(p in {"", ".", ".."} for p in branch.split("/"))
        ):
            raise ValueError("Explicit repository alias and portable branch required")
        from .contracts import validate_contract

        validate_contract("ProjectId", projectId)
        self.alias, self.project, self.repository, self.branch = (
            alias,
            projectId,
            repository,
            branch,
        )
        self.token_file = private_key(tokenFile)
        self.fingerprint = digest(
            {"alias": alias, "project": projectId, "repository": repository, "branch": branch}
        )

    def _request(self, path, *, data=None, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DomainError("STORE-0020", "Remote Git observation deadline reached", 503)
        timeout = min(5.0, remaining)
        token = Path(private_key(self.token_file)).read_text("utf-8").strip()
        if not re.fullmatch("[A-Za-z0-9_]{20,512}", token):
            raise DomainError("AUTH-0071", "Configured Git credential is unavailable", 503)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_default_certs()  # Does not enable SSLKEYLOGFILE.
        conn = OneConnection("api.github.com", timeout=timeout, context=context)

        # Bound a slow response as well as individual socket reads. No proxies.
        def abort():
            import socket

            try:
                if conn.sock:
                    conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()

        timer = Timer(timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            conn.connect()
            if time.monotonic() >= deadline:
                raise ValueError("connection exceeded operation deadline")
            body = canonical(data) if data is not None else None
            if body is not None and len(body) > 100000:
                raise ValueError("body budget")
            conn.request(
                "POST" if data is not None else "GET",
                path,
                body=body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "User-Agent": "SaintVision-remote-git",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Accept-Encoding": "identity",
                },
            )
            result = conn.getresponse()
            raw = result.read(262145)
            if (
                result.status not in {200, 201}
                or len(raw) > 262144
                or result.getheader("Content-Encoding") not in {None, "identity"}
            ):
                raise ValueError("remote response")
            value = strict_object(raw)
            if value.get("errors"):
                raise ValueError("remote GraphQL rejection")
            return value
        except Exception:
            # Never include provider errors, repository contents or credentials.
            raise DomainError(
                "STORE-0024", "Remote Git result requires observation; no automatic retry", 503
            ) from None
        finally:
            timer.cancel()
            conn.close()

    @property
    def prefix(self):
        return "/repos/" + self.repository + "/git/"

    def head(self):
        result = self._request(
            self.prefix + "ref/heads/" + quote(self.branch, safe="/"), deadline=time.monotonic() + 5
        )
        if (
            result.get("ref") != "refs/heads/" + self.branch
            or result.get("object", {}).get("type") != "commit"
        ):
            raise DomainError("VERIFY-0024", "Remote branch scope differs")
        return oid(result["object"]["sha"])

    def snapshot(self, commit, workspace_id):
        deadline = time.monotonic() + 20
        commit = oid(commit)
        info = self._request(self.prefix + "commits/" + commit, deadline=deadline)
        if info.get("sha") != commit:
            raise DomainError("VERIFY-0024", "Remote commit differs")
        tree_id = oid(info["tree"]["sha"])
        tree = self._request(self.prefix + "trees/" + tree_id + "?recursive=1", deadline=deadline)
        entries = tree.get("tree")
        if (
            tree.get("sha") != tree_id
            or tree.get("truncated") is not False
            or not isinstance(entries, list)
            or len(entries) > 256
        ):
            raise DomainError("STORE-0020", "Complete bounded Git tree required", 422)
        files, directories, content_bytes = [], [], 0
        for entry in entries:
            path = entry["path"]
            if any(p.casefold() == ".git" for p in portable_path(path)):
                raise DomainError("SEC-0020", ".git paths cannot be imported", 422)
            if entry["type"] == "tree" and entry["mode"] == "040000":
                directories.append(path)
                continue
            if entry["type"] != "blob" or entry["mode"] != "100644" or len(files) >= 128:
                raise DomainError(
                    "SEC-0020", "Git symlinks, executables and submodules are unsupported", 422
                )
            if (
                type(entry.get("size")) is not int
                or not 0 <= entry["size"] <= 32768 - content_bytes
            ):
                raise DomainError("STORE-0020", "Remote file content exceeds 32 KiB", 422)
            blob_id = oid(entry["sha"])
            blob = self._request(self.prefix + "blobs/" + blob_id, deadline=deadline)
            if blob.get("sha") != blob_id or blob.get("encoding") != "base64":
                raise DomainError("VERIFY-0024", "Remote blob scope differs")
            data = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
            actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if actual != blob_id or len(data) != entry["size"] or blob.get("size") != len(data):
                raise DomainError("VERIFY-0024", "Remote blob checksum differs")
            content_bytes += len(data)
            files.append(
                {
                    "path": path,
                    "executable": False,
                    "sizeBytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "dataBase64": base64.b64encode(data).decode(),
                }
            )
        raw = canonical(
            {
                "format": FORMAT,
                "workspaceId": workspace_id,
                "directories": sorted(directories),
                "files": sorted(files, key=lambda f: f["path"]),
            }
        )
        git_files(raw, workspace_id)
        return raw, info

    @staticmethod
    def changes(before, after, workspace_id):
        old, new = git_files(before, workspace_id), git_files(after, workspace_id)
        return {
            "additions": [
                {"path": p, "contents": f["dataBase64"]}
                for p, f in new.items()
                if p not in old or old[p]["sha256"] != f["sha256"]
            ],
            "deletions": [{"path": p} for p in old if p not in new],
        }

    def publish(self, operation_id, expected_head, changes):
        result = self._request(
            "/graphql",
            data={
                "query": "mutation($input:CreateCommitOnBranchInput!){createCommitOnBranch(input:$input){clientMutationId commit{oid}}}",
                "variables": {
                    "input": {
                        "branch": {
                            "repositoryNameWithOwner": self.repository,
                            "branchName": self.branch,
                        },
                        "expectedHeadOid": oid(expected_head),
                        "fileChanges": changes,
                        "message": {
                            "headline": "SaintVision approved Workspace update",
                            "body": "SaintVision-Operation: " + operation_id,
                        },
                        "clientMutationId": operation_id,
                    }
                },
            },
            deadline=time.monotonic() + 5,
        )
        value = result["data"]["createCommitOnBranch"]
        if value.get("clientMutationId") != operation_id:
            raise DomainError("VERIFY-0024", "Remote Git response identity differs")
        return oid(value["commit"]["oid"])

    def reconcile(self, operation_id, expected_head, expected_raw, workspace_id, candidate=None):
        # Only prove the current head, or the exact returned commit; never guess
        # through unbounded history or issue a second mutation on an unknown result.
        candidate = candidate or self.head()
        raw, info = self.snapshot(candidate, workspace_id)
        parents = info.get("parents", [])
        if (
            len(parents) != 1
            or parents[0].get("sha") != expected_head
            or info.get("message")
            != "SaintVision approved Workspace update\n\nSaintVision-Operation: " + operation_id
            or git_files(raw, workspace_id) != git_files(expected_raw, workspace_id)
        ):
            raise DomainError(
                "VERIFY-0024",
                "Remote publication remains uncertain; manual reconciliation required",
                409,
            )
        return candidate
