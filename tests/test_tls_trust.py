"""Outbound TLS trust (issue #67).

dirtforever.net chains to ISRG Root X1. Windows boxes that only hold the
expired DST-cross-signed copy of X1 fail with "certificate has expired", so
the client carries the ISRG roots itself and layers them over the OS store.
"""
from __future__ import annotations

import ssl
from unittest.mock import MagicMock, patch

from dr2server import tls
from dr2server.api_client import DirtForeverClient


def _common_names(ctx: ssl.SSLContext) -> set[str]:
    names = set()
    for cert in ctx.get_ca_certs():
        for rdn in cert.get("subject", ()):
            for key, value in rdn:
                if key == "commonName":
                    names.add(value)
    return names


def test_embedded_roots_parse_and_match_known_fingerprints() -> None:
    import hashlib
    expected = {
        tls.ISRG_ROOT_X1: "96bcec06264976f37460779acf28c5a7cfe8a3c0aae11a8ffcee05c0bddf08c6",
        tls.ISRG_ROOT_X2: "69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470",
    }
    for pem, digest in expected.items():
        der = ssl.PEM_cert_to_DER_cert(pem)
        assert hashlib.sha256(der).hexdigest() == digest


def test_context_trusts_isrg_roots_on_top_of_system_store() -> None:
    ctx = tls.build_context()
    names = _common_names(ctx)
    assert {"ISRG Root X1", "ISRG Root X2"} <= names
    # System roots are still there (not replaced by the embedded pair).
    assert len(ctx.get_ca_certs()) >= len(ssl.create_default_context().get_ca_certs())
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_stale_store_fails_without_embedded_roots_and_passes_with_them() -> None:
    """Simulate the broken Windows store: only the expired cross-signed X1.

    A context seeded with just that cert must not trust ISRG Root X1 as a
    time-valid anchor; adding the embedded roots fixes it.
    """
    # ISRG Root X1 cross-signed by DST Root CA X3, expired 2024-09-30.
    # https://letsencrypt.org/certs/isrg-root-x1-cross-signed.pem
    x1_cross = """\
-----BEGIN CERTIFICATE-----
MIIFYDCCBEigAwIBAgIQQAF3ITfU6UK47naqPGQKtzANBgkqhkiG9w0BAQsFADA/
MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMT
DkRTVCBSb290IENBIFgzMB4XDTIxMDEyMDE5MTQwM1oXDTI0MDkzMDE4MTQwM1ow
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwggIiMA0GCSqGSIb3DQEB
AQUAA4ICDwAwggIKAoICAQCt6CRz9BQ385ueK1coHIe+3LffOJCMbjzmV6B493XC
ov71am72AE8o295ohmxEk7axY/0UEmu/H9LqMZshftEzPLpI9d1537O4/xLxIZpL
wYqGcWlKZmZsj348cL+tKSIG8+TA5oCu4kuPt5l+lAOf00eXfJlII1PoOK5PCm+D
LtFJV4yAdLbaL9A4jXsDcCEbdfIwPPqPrt3aY6vrFk/CjhFLfs8L6P+1dy70sntK
4EwSJQxwjQMpoOFTJOwT2e4ZvxCzSow/iaNhUd6shweU9GNx7C7ib1uYgeGJXDR5
bHbvO5BieebbpJovJsXQEOEO3tkQjhb7t/eo98flAgeYjzYIlefiN5YNNnWe+w5y
sR2bvAP5SQXYgd0FtCrWQemsAXaVCg/Y39W9Eh81LygXbNKYwagJZHduRze6zqxZ
Xmidf3LWicUGQSk+WT7dJvUkyRGnWqNMQB9GoZm1pzpRboY7nn1ypxIFeBntPlF4
FQsDj43QLwWyPntKHEtzBRL8xurgUBN8Q5N0s8p0544fAQjQMNRbcTa0B7rBMDBc
SLeCO5imfWCKoqMpgsy6vYMEG6KDA0Gh1gXxG8K28Kh8hjtGqEgqiNx2mna/H2ql
PRmP6zjzZN7IKw0KKP/32+IVQtQi0Cdd4Xn+GOdwiK1O5tmLOsbdJ1Fu/7xk9TND
TwIDAQABo4IBRjCCAUIwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAQYw
SwYIKwYBBQUHAQEEPzA9MDsGCCsGAQUFBzAChi9odHRwOi8vYXBwcy5pZGVudHJ1
c3QuY29tL3Jvb3RzL2RzdHJvb3RjYXgzLnA3YzAfBgNVHSMEGDAWgBTEp7Gkeyxx
+tvhS5B1/8QVYIWJEDBUBgNVHSAETTBLMAgGBmeBDAECATA/BgsrBgEEAYLfEwEB
ATAwMC4GCCsGAQUFBwIBFiJodHRwOi8vY3BzLnJvb3QteDEubGV0c2VuY3J5cHQu
b3JnMDwGA1UdHwQ1MDMwMaAvoC2GK2h0dHA6Ly9jcmwuaWRlbnRydXN0LmNvbS9E
U1RST09UQ0FYM0NSTC5jcmwwHQYDVR0OBBYEFHm0WeZ7tuXkAXOACIjIGlj26Ztu
MA0GCSqGSIb3DQEBCwUAA4IBAQAKcwBslm7/DlLQrt2M51oGrS+o44+/yQoDFVDC
5WxCu2+b9LRPwkSICHXM6webFGJueN7sJ7o5XPWioW5WlHAQU7G75K/QosMrAdSW
9MUgNTP52GE24HGNtLi1qoJFlcDyqSMo59ahy2cI2qBDLKobkx/J3vWraV0T9VuG
WCLKTVXkcGdtwlfFRjlBz4pYg1htmf5X6DYO8A4jqv2Il9DjXA6USbW1FzXSLr9O
he8Y4IWS6wY7bCkjCWDcRQJMEhg76fsO3txE+FiYruq9RUWhiF1myv4Q6W+CyBFC
Dfvp7OOGAN6dEOM4+qR9sdjoSYKEBpsr6GtPAQw4dy753ec5
-----END CERTIFICATE-----
"""
    # DST Root CA X3 (expired 2021-09-30).
    # https://letsencrypt.org/certs/trustid-x3-root.pem
    dst_x3 = """\
-----BEGIN CERTIFICATE-----
MIIDSjCCAjKgAwIBAgIQRK+wgNajJ7qJMDmGLvhAazANBgkqhkiG9w0BAQUFADA/
MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMT
DkRTVCBSb290IENBIFgzMB4XDTAwMDkzMDIxMTIxOVoXDTIxMDkzMDE0MDExNVow
PzEkMCIGA1UEChMbRGlnaXRhbCBTaWduYXR1cmUgVHJ1c3QgQ28uMRcwFQYDVQQD
Ew5EU1QgUm9vdCBDQSBYMzCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AN+v6ZdQCINXtMxiZfaQguzH0yxrMMpb7NnDfcdAwRgUi+DoM3ZJKuM/IUmTrE4O
rz5Iy2Xu/NMhD2XSKtkyj4zl93ewEnu1lcCJo6m67XMuegwGMoOifooUMM0RoOEq
OLl5CjH9UL2AZd+3UWODyOKIYepLYYHsUmu5ouJLGiifSKOeDNoJjj4XLh7dIN9b
xiqKqy69cK3FCxolkHRyxXtqqzTWMIn/5WgTe1QLyNau7Fqckh49ZLOMxt+/yUFw
7BZy1SbsOFU5Q9D8/RhcQPGX69Wam40dutolucbY38EVAjqr2m7xPi71XAicPNaD
aeQQmxkqtilX4+U9m5/wAl0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNV
HQ8BAf8EBAMCAQYwHQYDVR0OBBYEFMSnsaR7LHH62+FLkHX/xBVghYkQMA0GCSqG
SIb3DQEBBQUAA4IBAQCjGiybFwBcqR7uKGY3Or+Dxz9LwwmglSBd49lZRNI+DT69
ikugdB/OEIKcdBodfpga3csTS7MgROSR6cz8faXbauX+5v3gTt23ADq1cEmv8uXr
AvHRAosZy5Q6XkjEGB5YGV8eAlrwDPGxrancWYaLbumR9YbK+rlmM6pZW87ipxZz
R8srzJmwN0jP41ZL9c8PDHIyh8bwRLtTcm1D9SZImlJnt1ir/md2cXjbDaJWFBM5
JDGFoqgCWjBH4d1QB7wCCZAA62RjYJsWvIjJEubSfZGL+T0yjWW06XyxV3bqxbYo
Ob8VZRzI9neWagqNdwvYkQsEjgfbKbYK7p2CNTUQ
-----END CERTIFICATE-----
"""
    stale = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    stale.load_verify_locations(cadata=x1_cross + dst_x3)
    # The only ISRG Root X1 in the stale store is the expired cross-sign.
    assert "ISRG Root X1" in _common_names(stale)
    x1_entries = [c for c in stale.get_ca_certs()
                  if ("commonName", "ISRG Root X1") in [tuple(r[0]) for r in c["subject"]]]
    assert len(x1_entries) == 1
    assert ssl.cert_time_to_seconds(x1_entries[0]["notAfter"]) < ssl.cert_time_to_seconds("Jan  1 00:00:00 2025 GMT")

    # Layering the embedded roots adds a self-signed, in-date X1 and X2.
    stale.load_verify_locations(cadata=tls.EMBEDDED_ROOTS)
    x1_entries = [c for c in stale.get_ca_certs()
                  if ("commonName", "ISRG Root X1") in [tuple(r[0]) for r in c["subject"]]]
    assert len(x1_entries) == 2
    assert any(ssl.cert_time_to_seconds(c["notAfter"]) > ssl.cert_time_to_seconds("Jan  1 00:00:00 2030 GMT")
               for c in x1_entries)
    assert "ISRG Root X2" in _common_names(stale)


def test_client_context_is_shared() -> None:
    assert tls.client_context() is tls.client_context()


def test_api_client_passes_context_to_urlopen() -> None:
    resp = MagicMock()
    resp.__enter__.return_value.read.return_value = b'{"ok": true, "username": "driver"}'
    with patch("urllib.request.urlopen", return_value=resp) as urlopen:
        client = DirtForeverClient(base_url="https://example.invalid", api_token="t")
        assert client.test_token() == "driver"
        client._post("/api/game/anything", {"a": 1})
    assert urlopen.call_count == 2
    for call in urlopen.call_args_list:
        assert call.kwargs["context"] is tls.client_context()
