"""RSA phone-number encryption used by the app SMS login flow."""

from __future__ import annotations

import base64
import os
import re


RSA_PUBLIC_DER = base64.b64decode(
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDZgjVwAiKTjZ55nG+mW6r3TSU4ECvNYqDMIS/bhCj"
    "2QaH5GI/KZb2TBp+CBvUj9SLFnmJQ0kzHzHoGZCQ88VevCffF7JePGF9cmKQqotlfTKbV4oxV5iLz"
    "7JSG6b/Vg7AXtrTolNtWsa8HiB0tI0YClYaQlOXm4UxLeSxQwSFETwIDAQAB"
)
_MODULUS_PREFIX = b"\x02\x81\x81"
_EXPONENT = b"\x02\x03\x01\x00\x01"
_PAD_BYTES = 128


def encrypt_phone(text: str) -> str:
    """Return the Base64 RSA PKCS#1 v1.5 value, including Android's newline."""
    message = text.encode("utf-8")
    if not message or len(message) > _PAD_BYTES - 11:
        raise ValueError("phone value cannot be encrypted")

    match = re.search(re.escape(_MODULUS_PREFIX) + b".{129}", RSA_PUBLIC_DER, re.S)
    if not match or _EXPONENT not in RSA_PUBLIC_DER:
        raise ValueError("embedded RSA public key is malformed")
    modulus = int.from_bytes(match.group(0)[3:], "big")

    padding = bytearray()
    while len(padding) < _PAD_BYTES - 3 - len(message):
        byte = os.urandom(1)[0]
        if byte:
            padding.append(byte)
    block = b"\x00\x02" + bytes(padding) + b"\x00" + message
    cipher = pow(int.from_bytes(block, "big"), 65537, modulus)
    encoded = base64.b64encode(cipher.to_bytes(_PAD_BYTES, "big")).decode("ascii")
    wrapped = "\n".join(encoded[index:index + 76] for index in range(0, len(encoded), 76))
    return wrapped + "\n"
