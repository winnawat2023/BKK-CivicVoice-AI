"""HTTP Message Signature verification for the Genesys AudioHook handshake.

Genesys Cloud signs the WebSocket upgrade request with ``HMAC-SHA256`` using the
client secret configured on the Audio Connector integration (RFC 9421,
"Signing HTTP Messages").  The signed components are::

    "@request-target" "@authority" "audiohook-organization-id"
    "audiohook-session-id" "audiohook-correlation-id" "x-api-key"

The signature base has one line per covered component plus a final
``"@signature-params"`` line::

    "@request-target": /api/v1/audiohook/ws
    "@authority": audiohook.example.com
    "audiohook-organization-id": d7934305-...
    ...
    "@signature-params": ("@request-target" "@authority" ...);keyid="...";nonce="...";alg="hmac-sha256";created=1641013200;expires=3282026430

This module implements only the subset needed by AudioHook.  The same helpers
can *create* a signature, which keeps the unit tests and the local test client
in sync with the verifier.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass, field
from typing import Mapping, Optional

REQUIRED_COMPONENTS: tuple[str, ...] = (
    "@request-target",
    "@authority",
    "audiohook-organization-id",
    "audiohook-session-id",
    "audiohook-correlation-id",
    "x-api-key",
)

MAX_CLOCK_SKEW = 3

_OBS_FOLD = re.compile(r"[ \t]*\r?\n[ \t]+")


def canonicalize_header(value: str) -> str:
    """Trim and unfold a header field value (RFC 9110 section 5.2)."""

    return _OBS_FOLD.sub(" ", value).strip()


def _secret_keys(secret: str) -> list[bytes]:
    """Return candidate HMAC keys for a configured client secret.

    Genesys AudioHook client secrets are configured as base64 in the admin UI,
    but some integrations/tests provide a raw shared secret. To be compatible we
    try the UTF-8 bytes first, then common base64 decodings.
    """

    keys: list[bytes] = []
    seen: set[bytes] = set()

    def add(value: bytes) -> None:
        if value not in seen:
            seen.add(value)
            keys.append(value)

    raw = secret.encode("utf-8")
    add(raw)

    compact = "".join(secret.split())
    for candidate in (compact, compact.replace("-", "+").replace("_", "/")):
        pad = "=" * ((4 - len(candidate) % 4) % 4)
        padded = candidate + pad
        try:
            decoded = base64.b64decode(padded, validate=True)
        except Exception:
            continue
        # Ignore trivial/empty decodes; they are never valid shared secrets.
        if decoded:
            add(decoded)

    return keys


@dataclass
class HttpRequestInfo:
    """The parts of an HTTP request that a signature can reference."""

    method: str
    target: str  # @request-target: path plus "?query"
    authority: str  # @authority: the Host header value
    headers: Mapping[str, str]  # lower-case names -> canonicalized values
    scheme: str = "https"


@dataclass
class VerifyResult:
    ok: bool
    code: str
    reason: str = ""

    def __bool__(self) -> bool:  # convenience: `if verify(...)`
        return self.ok


# ---------------------------------------------------------------------------
# Structured-field parsing (focused subset)
# ---------------------------------------------------------------------------
def _split_members(value: str) -> list[str]:
    """Split a dictionary header into its top-level members on commas."""

    members: list[str] = []
    depth = 0
    in_quote = False
    start = 0
    i = 0
    while i < len(value):
        ch = value[i]
        if in_quote:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_quote = False
        else:
            if ch == '"':
                in_quote = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(depth - 1, 0)
            elif ch == "," and depth == 0:
                members.append(value[start:i])
                start = i + 1
        i += 1
    members.append(value[start:])
    return [m.strip() for m in members if m.strip()]


def _matching_paren(value: str, start: int) -> int:
    """Return the index of the ``)`` matching the ``(`` at ``start``."""

    if value[start] != "(":
        raise ValueError("expected '('")
    depth = 0
    in_quote = False
    i = start
    while i < len(value):
        ch = value[i]
        if in_quote:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_quote = False
        else:
            if ch == '"':
                in_quote = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unbalanced parentheses in signature parameters")


def _parse_components(inner: str) -> list[str]:
    """Extract component names from a parenthesized inner list."""

    components: list[str] = []
    i = 1  # skip '('
    end = len(inner) - 1  # the closing ')'
    while i < end:
        ch = inner[i]
        if ch.isspace() or ch == ";":
            i += 1
            continue
        if ch == '"':
            j = i + 1
            buf: list[str] = []
            while j < end:
                if inner[j] == "\\" and j + 1 < end:
                    buf.append(inner[j + 1])
                    j += 2
                    continue
                if inner[j] == '"':
                    break
                buf.append(inner[j])
                j += 1
            components.append("".join(buf))
            i = j + 1
            # Skip any component parameters (e.g. ``;req``) up to whitespace.
            while i < end and not inner[i].isspace():
                i += 1
        else:
            i += 1
    return components


def _parse_params(value: str) -> dict[str, str]:
    """Parse ``;key=value`` parameters while preserving their order."""

    params: dict[str, str] = {}
    i = 0
    while i < len(value):
        if value[i] != ";":
            i += 1
            continue
        i += 1
        key_start = i
        while i < len(value) and value[i] not in "=;":
            i += 1
        key = value[key_start:i].strip()
        if not key:
            continue
        if i < len(value) and value[i] == "=":
            i += 1
            if i < len(value) and value[i] == '"':
                i += 1
                buf: list[str] = []
                while i < len(value):
                    if value[i] == "\\" and i + 1 < len(value):
                        buf.append(value[i + 1])
                        i += 2
                        continue
                    if value[i] == '"':
                        i += 1
                        break
                    buf.append(value[i])
                    i += 1
                params[key] = "".join(buf)
            else:
                val_start = i
                while i < len(value) and value[i] != ";":
                    i += 1
                params[key] = value[val_start:i].strip()
        else:
            params[key] = ""
    return params


def parse_signature_input(header: str) -> dict[str, dict]:
    """Parse the ``Signature-Input`` header into ``{label: info}``."""

    result: dict[str, dict] = {}
    for member in _split_members(header):
        if "=" not in member:
            continue
        label, rest = member.split("=", 1)
        label = label.strip()
        rest = rest.strip()
        if not rest.startswith("("):
            continue
        close = _matching_paren(rest, 0)
        inner = rest[: close + 1]
        params_str = rest[close + 1 :]
        result[label] = {
            "components": _parse_components(inner),
            "params": _parse_params(params_str),
        }
    return result


def parse_signature(header: str) -> dict[str, bytes]:
    """Parse the ``Signature`` header (``label=:base64:``) into bytes."""

    result: dict[str, bytes] = {}
    for member in _split_members(header):
        if "=" not in member:
            continue
        label, rest = member.split("=", 1)
        label = label.strip()
        rest = rest.strip()
        if len(rest) >= 2 and rest[0] == ":" and rest[-1] == ":":
            try:
                result[label] = base64.b64decode(rest[1:-1], validate=True)
            except Exception:
                continue
    return result


# ---------------------------------------------------------------------------
# Signature base construction
# ---------------------------------------------------------------------------
def _resolve_component(name: str, request: HttpRequestInfo) -> Optional[str]:
    if name == "@request-target":
        return request.target
    if name == "@authority":
        return request.authority
    if name == "@method":
        return request.method.upper()
    if name == "@scheme":
        return request.scheme
    if name == "@path":
        return request.target.split("?", 1)[0]
    if name == "@query":
        if "?" not in request.target:
            return "?"
        return "?" + request.target.split("?", 1)[1]
    if name == "@target-uri":
        return f"{request.scheme}://{request.authority}{request.target}"
    if name.startswith("@"):
        return None
    raw = request.headers.get(name.lower())
    if raw is None:
        return None
    return canonicalize_header(raw)


def _escape_sf_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def serialize_signature_params(
    components: list[str], params: Mapping[str, str]
) -> str:
    """Serialize ``(...);key=value`` exactly as it appears in Signature-Input."""

    inner = "(" + " ".join(f'"{_escape_sf_string(c)}"' for c in components) + ")"
    for key, value in params.items():
        if key in ("created", "expires"):
            inner += f";{key}={value}"
        else:
            inner += f';{key}="{_escape_sf_string(value)}"'
    return inner


def build_signature_base(
    request: HttpRequestInfo,
    components: list[str],
    signature_params: str,
) -> str:
    """Assemble the string that is signed / verified."""

    lines: list[str] = []
    for name in components:
        value = _resolve_component(name, request)
        if value is None:
            raise ValueError(f"covered component {name!r} is not available")
        lines.append(f'"{name}": {value}')
    lines.append(f'"@signature-params": {signature_params}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_request(
    secret: str,
    request: HttpRequestInfo,
    *,
    api_key: Optional[str] = None,
    required_components: Optional[tuple[str, ...]] = None,
    max_age: Optional[int] = None,
    now: Optional[float] = None,
) -> VerifyResult:
    """Verify the signature of a handshake request.

    ``api_key`` (if given) must equal the signature ``keyid`` and the
    ``X-API-KEY`` covered header.
    """

    signature_input = request.headers.get("signature-input")
    signature_header = request.headers.get("signature")
    if not signature_input and not signature_header:
        return VerifyResult(False, "UNSIGNED", "no signature headers present")
    if not signature_input or not signature_header:
        return VerifyResult(False, "INVALID", "incomplete signature headers")

    try:
        inputs = parse_signature_input(signature_input)
        signatures = parse_signature(signature_header)
    except Exception as exc:  # malformed structured field
        return VerifyResult(False, "INVALID", f"failed to parse signature: {exc}")

    if not inputs:
        return VerifyResult(False, "INVALID", "no signature-input members")

    label = next(iter(inputs))
    info = inputs[label]
    signature = signatures.get(label)
    if signature is None:
        return VerifyResult(False, "INVALID", "signature label mismatch")

    params: Mapping[str, str] = info["params"]
    alg = params.get("alg", "hmac-sha256")
    if alg != "hmac-sha256":
        return VerifyResult(False, "UNSUPPORTED", f"unsupported alg {alg!r}")

    keyid = params.get("keyid")
    if api_key is not None and keyid != api_key:
        return VerifyResult(
            False, "PRECONDITION", "X-API-KEY and signature keyid do not match"
        )

    nonce = params.get("nonce")
    if not nonce or len(nonce) < 22:
        return VerifyResult(False, "PRECONDITION", "missing or short nonce")

    clock = time.time() if now is None else now
    created_raw = params.get("created")
    expires_raw = params.get("expires")
    try:
        created = int(created_raw) if created_raw is not None else None
        expires = int(expires_raw) if expires_raw is not None else None
    except ValueError:
        return VerifyResult(False, "INVALID", "non-integer created/expires")

    if created is not None:
        if created > clock + MAX_CLOCK_SKEW:
            return VerifyResult(False, "PRECONDITION", "signature created in future")
        if max_age is not None and created + max_age < clock + MAX_CLOCK_SKEW:
            return VerifyResult(False, "EXPIRED", "signature is too old")
    elif max_age is not None:
        return VerifyResult(False, "PRECONDITION", "missing created parameter")

    if expires is not None and expires < clock + MAX_CLOCK_SKEW:
        return VerifyResult(False, "EXPIRED", "signature expired")

    if required_components:
        covered = set(info["components"])
        missing = [c for c in required_components if c not in covered]
        if missing:
            return VerifyResult(
                False,
                "PRECONDITION",
                "signature does not cover required components: "
                + ", ".join(missing),
            )

    try:
        signature_params = serialize_signature_params(info["components"], params)
        base = build_signature_base(request, info["components"], signature_params)
    except ValueError as exc:
        return VerifyResult(False, "PRECONDITION", str(exc))

    base_bytes = base.encode("utf-8")
    for key in _secret_keys(secret):
        computed = hmac.new(key, base_bytes, hashlib.sha256).digest()
        if hmac.compare_digest(computed, signature):
            return VerifyResult(True, "VERIFIED")

    return VerifyResult(False, "FAILED", "signature does not match")


# ---------------------------------------------------------------------------
# Signature creation (used by tests and the local test client)
# ---------------------------------------------------------------------------
def create_signature_headers(
    secret: str,
    request: HttpRequestInfo,
    *,
    keyid: str,
    nonce: Optional[str] = None,
    created: Optional[int] = None,
    expires: Optional[int] = None,
    label: str = "sig1",
    components: Optional[tuple[str, ...]] = None,
) -> dict[str, str]:
    """Create ``Signature-Input`` / ``Signature`` / ``X-API-KEY`` headers."""

    component_list = list(components or REQUIRED_COMPONENTS)
    if nonce is None:
        # 16 random bytes -> 22 base64url characters without padding.
        nonce = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
    created_ts = int(created if created is not None else time.time())
    expires_ts = int(expires if expires is not None else created_ts + 300)

    params = {
        "keyid": keyid,
        "nonce": nonce,
        "alg": "hmac-sha256",
        "created": str(created_ts),
        "expires": str(expires_ts),
    }
    signature_params = serialize_signature_params(component_list, params)
    base = build_signature_base(request, component_list, signature_params)
    # Use the first candidate key. Raw UTF-8 preserves existing behavior; for
    # base64-configured secrets Genesys decodes the secret, and callers should
    # pass the same configured value here.
    digest = hmac.new(_secret_keys(secret)[0], base.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii")
    return {
        "Signature-Input": f"{label}={signature_params}",
        "Signature": f"{label}=:{signature}:",
        "X-API-KEY": keyid,
    }
