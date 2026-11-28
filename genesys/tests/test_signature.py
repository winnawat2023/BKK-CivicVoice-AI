import time

from app.audiohook.signature import (
    REQUIRED_COMPONENTS,
    HttpRequestInfo,
    create_signature_headers,
    parse_signature,
    parse_signature_input,
    verify_request,
)


def make_request(
    *,
    target: str = "/api/v1/audiohook/ws",
    authority: str = "audiohook.example.com",
    api_key: str = "test-api-key",
    organization: str = "11111111-1111-1111-1111-111111111111",
    session: str = "22222222-2222-2222-2222-222222222222",
    correlation: str = "33333333-3333-3333-3333-333333333333",
) -> HttpRequestInfo:
    headers = {
        "host": authority,
        "x-api-key": api_key,
        "audiohook-organization-id": organization,
        "audiohook-session-id": session,
        "audiohook-correlation-id": correlation,
    }
    return HttpRequestInfo(
        method="GET",
        target=target,
        authority=authority,
        headers=headers,
        scheme="https",
    )


def sign_and_attach(request, secret, *, now=None):
    now = int(now if now is not None else time.time())
    signed = create_signature_headers(
        secret, request, keyid=request.headers["x-api-key"],
        created=now, expires=now + 300,
    )
    request.headers = {
        **request.headers,
        **{k.lower(): v for k, v in signed.items()},
    }
    return request


def test_signature_roundtrip_verifies():
    secret = "super-secret"
    request = sign_and_attach(make_request(), secret)

    result = verify_request(
        secret,
        request,
        api_key="test-api-key",
        required_components=REQUIRED_COMPONENTS,
        max_age=30,
    )
    assert result.ok, result


def test_tampered_component_fails():
    secret = "super-secret"
    request = sign_and_attach(make_request(), secret)
    request.headers["audiohook-session-id"] = "tampered"

    result = verify_request(
        secret,
        request,
        api_key="test-api-key",
        required_components=REQUIRED_COMPONENTS,
        max_age=30,
    )
    assert not result.ok
    assert result.code == "FAILED"


def test_wrong_secret_fails():
    request = sign_and_attach(make_request(), "super-secret")
    result = verify_request(
        "other-secret",
        request,
        api_key="test-api-key",
        required_components=REQUIRED_COMPONENTS,
        max_age=30,
    )
    assert not result.ok
    assert result.code == "FAILED"


def test_expired_signature_is_rejected():
    secret = "super-secret"
    request = sign_and_attach(make_request(), secret, now=int(time.time()) - 3600)
    result = verify_request(
        secret,
        request,
        api_key="test-api-key",
        required_components=REQUIRED_COMPONENTS,
        max_age=30,
    )
    assert not result.ok
    assert result.code == "EXPIRED"


def test_missing_signature_is_unsigned():
    result = verify_request("super-secret", make_request(), api_key="test-api-key")
    assert not result.ok
    assert result.code == "UNSIGNED"


def test_keyid_mismatch_is_rejected():
    secret = "super-secret"
    request = sign_and_attach(make_request(api_key="key-a"), secret)
    result = verify_request(
        secret, request, api_key="key-b", required_components=REQUIRED_COMPONENTS
    )
    assert not result.ok
    assert result.code == "PRECONDITION"


def test_folded_header_is_parsed():
    header = (
        'sig1=("@request-target" "@authority" "audiohook-organization-id" '
        '"audiohook-session-id"\n "audiohook-correlation-id" "x-api-key");'
        'keyid="abc";nonce="0123456789012345678901";alg="hmac-sha256";'
        "created=1641013200;expires=3282026430"
    )
    parsed = parse_signature_input(header)
    assert "sig1" in parsed
    assert parsed["sig1"]["components"][0] == "@request-target"
    assert parsed["sig1"]["params"]["alg"] == "hmac-sha256"
    assert parsed["sig1"]["params"]["created"] == "1641013200"


def test_signature_header_parsing():
    parsed = parse_signature("sig1=:AAECAw==:")
    assert parsed["sig1"] == b"\x00\x01\x02\x03"
