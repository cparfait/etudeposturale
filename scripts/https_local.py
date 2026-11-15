"""HTTPS sur le réseau local, sans outil externe : autorité de certification propre à ce PC + certificat du serveur.

Le navigateur d'un téléphone n'ouvre la caméra d'une page qu'en HTTPS. Ce script :
  1. crée (une fois) une autorité locale dans data/https/ (ca.crt, ca.key — la clé ne quitte pas ce PC) ;
  2. émet un certificat pour localhost, 127.0.0.1, le nom du PC et ses adresses Wi-Fi / Ethernet,
     écrit dans frontend/certs/ (utilisé automatiquement par l'interface) ;
  3. avec --installer-autorite : demande à Windows de faire confiance à l'autorité (magasin de l'utilisateur ;
     Windows affiche une fenêtre de confirmation).

Usage :
    backend\\.venv\\Scripts\\python scripts\\https_local.py                       (crée ou met à jour si l'IP a changé)
    backend\\.venv\\Scripts\\python scripts\\https_local.py --installer-autorite

Sur un serveur derrière un proxy (Nginx Proxy Manager…), inutile : le proxy fournit un vrai certificat.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import socket
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parent.parent
CA_DIR = ROOT / "data" / "https"
CERT_DIR = ROOT / "frontend" / "certs"


def local_names() -> tuple[list[str], list[str]]:
    names = ["localhost", socket.gethostname()]
    ips = ["127.0.0.1"]
    try:  # interface de sortie (aucun paquet envoyé)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.0.1", 9))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    return list(dict.fromkeys(names)), list(dict.fromkeys(ips))


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def ensure_ca() -> tuple[x509.Certificate, object]:
    CA_DIR.mkdir(parents=True, exist_ok=True)
    crt, key = CA_DIR / "ca.crt", CA_DIR / "ca.key"
    if crt.exists() and key.exists():
        return x509.load_pem_x509_certificate(crt.read_bytes()), serialization.load_pem_private_key(key.read_bytes(), None)
    k = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Étude posturale — autorité locale ({socket.gethostname()})"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Étude posturale (local)")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False)
            .sign(k, hashes.SHA256()))
    _write_key(key, k)
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert, k


def current_sans(path: Path) -> set[str]:
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        if cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) < dt.timedelta(days=30):
            return set()  # bientôt expiré : on renouvelle
        return {str(v) for v in san.get_values_for_type(x509.DNSName)} | {str(v) for v in san.get_values_for_type(x509.IPAddress)}
    except (OSError, ValueError, x509.ExtensionNotFound):
        return set()


def issue_server_cert(force: bool = False) -> bool:
    """Émet le certificat du serveur si absent, expirant, ou si une adresse du PC n'y figure pas. True si réémis."""
    names, ips = local_names()
    wanted = set(names) | set(ips)
    out_crt, out_key = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"
    if not force and out_key.exists() and wanted <= current_sans(out_crt):
        return False
    ca_cert, ca_key = ensure_ca()
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    k = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    san = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname())]))
            .issuer_name(ca_cert.subject).public_key(k.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=397))  # durée max acceptée par les navigateurs
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _write_key(out_key, k)
    out_crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM))
    return True


def install_ca_windows() -> int:
    """Ajoute l'autorité au magasin « Autorités racines » de l'utilisateur (Windows demande confirmation)."""
    if sys.platform != "win32":
        print("Installation automatique prévue pour Windows : ajoute data/https/ca.crt aux autorités de confiance de ton système.")
        return 0
    ensure_ca()
    r = subprocess.run(["certutil", "-user", "-addstore", "Root", str(CA_DIR / "ca.crt")], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--installer-autorite", action="store_true", help="faire confiance à l'autorité locale sur ce PC (Windows)")
    ap.add_argument("--forcer", action="store_true", help="réémettre le certificat même s'il est encore valable")
    a = ap.parse_args()
    changed = issue_server_cert(a.forcer)
    names, ips = local_names()
    print(("Certificat HTTPS émis" if changed else "Certificat HTTPS à jour") + f" pour : {', '.join(names + ips)}")
    if a.installer_autorite:
        return install_ca_windows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
