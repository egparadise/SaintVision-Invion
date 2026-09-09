"""Bounded mTLS calls to an operator-pinned Node; no proxy, redirect or retry."""

import base64
from copy import deepcopy
import http.client
import json
from pathlib import Path
import os
import socket
import ssl
import stat
from threading import Timer
from time import monotonic
from .contracts import validate_contract
from .errors import DomainError
from .node_channels import NodeChannels, certificate_identity, endpoint_parts
from .node_execution import NodeReceiptStore
from .tooling import NodePrincipal


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def invalid(_):
        raise ValueError()

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise DomainError("NODE-0035", "Invalid Node response", 502) from None


def private_key(path):
    p = Path(path)
    info = p.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or (os.name != "nt" and info.st_mode & 0o077)
        or info.st_size > 65536
    ):
        raise ValueError()
    return str(p)


class OneConnection(http.client.HTTPSConnection):
    _connected_once = False

    def connect(self):
        if self._connected_once:
            raise OSError("automatic reconnect prohibited")
        self._connected_once = True
        super().connect()


class NodeTLSClient:
    def __init__(self, *, ca_file, certificate_file, key_file, timeout=40):
        if type(timeout) not in (int, float) or not 0.1 <= timeout <= 40:
            raise DomainError("NODE-0031", "Invalid Node transport timeout", 422)
        try:
            # Build explicit trust without SSLKEYLOGFILE/system trust side effects.
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.load_verify_locations(cafile=str(ca_file))
            self.context.minimum_version = ssl.TLSVersion.TLSv1_3
            self.context.verify_flags |= ssl.VERIFY_X509_STRICT
            self.context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
            self.context.load_cert_chain(str(certificate_file), private_key(key_file))
        except (OSError, ValueError, ssl.SSLError):
            raise DomainError(
                "NODE-0031", "Explicit Node TLS credentials unavailable", 503
            ) from None
        self.timeout = timeout

    def exchange(self, channel, permit, *, observation_only=False):
        body = json.dumps(permit, separators=(",", ":"), allow_nan=False).encode()
        if len(body) > 2 * 1024 * 1024:
            raise DomainError("NODE-0031", "Permit exceeds limit", 422)
        host, port = endpoint_parts(channel.endpoint)
        conn = OneConnection(host, port, context=self.context, timeout=self.timeout)
        deadline = monotonic() + self.timeout
        wire_socket = [None]
        response = None

        def abort():
            sock = wire_socket[0] or conn.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.close()

        timer = Timer(self.timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            conn.connect()  # CA, hostname, EKU and TLS version before sending bytes.
            wire_socket[0] = conn.sock
            if conn.sock is None or monotonic() >= deadline:
                raise DomainError("NODE-0030", "Node delivery deadline exceeded", 503)
            fingerprint, _ = certificate_identity(
                conn.sock.getpeercert(binary_form=True),
                NodePrincipal(channel.tenant_id, channel.node_id),
                channel.recovery_epoch,
            )
            if fingerprint != channel.certificate_sha256 or monotonic() >= deadline:
                raise DomainError("NODE-0032", "Pinned Node certificate rejected", 403)
            conn.sock.settimeout(max(0.001, deadline - monotonic()))
            path = "/v1/executions/receipts" if observation_only else "/v1/executions"
            conn.request(
                "POST",
                path,
                body,
                {"Content-Type": "application/json", "Connection": "close"},
            )
            response = conn.getresponse()
            if (
                response.status != 200
                or response.getheader("Content-Type", "").split(";")[0]
                != "application/json"
            ):
                raise DomainError(
                    "NODE-0030",
                    "Node delivery unconfirmed; observe the same command",
                    503,
                )
            raw = response.read(1048577)
            if len(raw) > 1048576 or monotonic() >= deadline:
                raise DomainError("NODE-0035", "Node response exceeds bounds", 502)
            result = strict_json(raw)
            validate_contract("NodeExecutionResult", result)
            return result
        except (OSError, ValueError, ssl.SSLError, http.client.HTTPException):
            raise DomainError(
                "NODE-0030", "Node delivery unconfirmed; observe the same command", 503
            ) from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            conn.close()


class NodeDelivery:
    def __init__(self, database, client):
        self.db = database
        self.client = client
        self.channels = NodeChannels(database)
        self.receipts = NodeReceiptStore(database)

    def deliver(self, node, permit, *, observation_only=False):
        permit = deepcopy(permit)
        validate_contract("SignedNodePermit", permit)
        try:
            payload = strict_json(base64.b64decode(permit["payload"], validate=True))
        except ValueError:
            raise DomainError("NODE-0031", "Invalid signed permit", 422) from None
        validate_contract("NodeExecutionPermit", payload)
        claim = payload["claim"]
        if (
            claim["tenantId"] != node.tenant_id
            or claim["nodeId"] != node.node_id
            or claim["recoveryEpoch"] != self.db.recovery_epoch
        ):
            raise DomainError("NODE-0032", "Permit Node identity differs", 403)
        channel = self.channels.snapshot(node, observation_only=observation_only)
        result = self.client.exchange(
            channel, permit, observation_only=observation_only
        )
        receipt = result["receipt"]
        if (
            any(
                receipt[k] != claim[k]
                for k in [
                    "claimId",
                    "commandId",
                    "tenantId",
                    "nodeId",
                    "projectId",
                    "runId",
                    "recoveryEpoch",
                    "planDigest",
                ]
            )
            or receipt["allocations"] != payload["allocations"]
        ):
            raise DomainError(
                "NODE-0035", "Node response is not bound to the requested permit", 502
            )
        self.receipts.record(node, receipt, channel=channel)
        return result
