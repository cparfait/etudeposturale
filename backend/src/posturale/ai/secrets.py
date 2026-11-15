"""Chiffrement des clés d'API avec DPAPI (Windows) : seule ta session Windows peut les relire."""
from __future__ import annotations

import base64
import sys

PREFIX_DPAPI, PREFIX_PLAIN = "dpapi:", "b64:"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data: bytes) -> _Blob:
        buf = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _call(fn, data: bytes) -> bytes:
        out = _Blob()
        if not fn(ctypes.byref(_blob(data)), None, None, None, None, 0, ctypes.byref(out)):
            raise OSError("DPAPI : opération refusée")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    def _protect(data: bytes) -> bytes:
        return _call(ctypes.windll.crypt32.CryptProtectData, data)

    def _unprotect(data: bytes) -> bytes:
        return _call(ctypes.windll.crypt32.CryptUnprotectData, data)


def encrypt(secret: str) -> str:
    if sys.platform == "win32":
        return PREFIX_DPAPI + base64.b64encode(_protect(secret.encode())).decode()
    return PREFIX_PLAIN + base64.b64encode(secret.encode()).decode()  # hors Windows : simple masquage


def decrypt(token: str) -> str:
    if token.startswith(PREFIX_DPAPI):
        return _unprotect(base64.b64decode(token[len(PREFIX_DPAPI):])).decode()
    if token.startswith(PREFIX_PLAIN):
        return base64.b64decode(token[len(PREFIX_PLAIN):]).decode()
    raise ValueError("Clé enregistrée illisible")
