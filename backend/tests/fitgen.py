"""Petit générateur de fichiers .FIT pour les tests (format FIT : en-tête, définitions, données, CRC).

Écrit une activité : file_id, un enregistrement par seconde (puissance, cadence, cardio, équilibre G/D,
efficacité du couple, fluidité) et un message session (sport, distance, temps en mouvement).
"""
from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
_CRC = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
        0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]
SPORT = {"running": 1, "cycling": 2}
SUB = {"generic": 0, "indoor_cycling": 6, "road": 7}


def crc16(data: bytes, crc: int = 0) -> int:
    for b in data:
        tmp = _CRC[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC[b & 0xF]
        tmp = _CRC[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ _CRC[(b >> 4) & 0xF]
    return crc


def _ts(t: datetime) -> int:
    return int((t - FIT_EPOCH).total_seconds())


def _definition(local: int, glob: int, fields: list[tuple[int, int, int]]) -> bytes:
    out = struct.pack("<BBBHB", 0x40 | local, 0, 0, glob, len(fields))
    for num, size, base in fields:
        out += struct.pack("<BBB", num, size, base)
    return out


FILE_ID = [(0, 1, 0x00), (1, 2, 0x84), (4, 4, 0x86)]
RECORD = [(253, 4, 0x86), (3, 1, 0x02), (4, 1, 0x02), (7, 2, 0x84), (30, 1, 0x02),
          (43, 1, 0x02), (44, 1, 0x02), (45, 1, 0x02), (46, 1, 0x02)]   # efficacité du couple G/D, fluidité G/D
SESSION = [(253, 4, 0x86), (2, 4, 0x86), (5, 1, 0x00), (6, 1, 0x00), (8, 4, 0x86), (9, 4, 0x86)]


def activity(start: datetime, minutes: float, *, sport: str = "cycling", sub: str = "road", power: int = 200,
             cadence: int = 88, hr: int = 140, left_pct: float = 50.0, left_pct_end: float | None = None,
             torque: tuple[float, float] = (75.0, 77.0), smooth: tuple[float, float] = (21.0, 22.0),
             speed_kmh: float = 30.0, step_s: int = 5) -> bytes:
    """Une sortie synthétique ; l'équilibre gauche peut dériver linéairement de left_pct à left_pct_end."""
    body = _definition(0, 0, FILE_ID) + struct.pack("<BBHI", 0, 4, 1, _ts(start))
    body += _definition(1, 20, RECORD)
    n = int(minutes * 60 / step_s) + 1
    for i in range(n):
        k = i / max(1, n - 1)
        left = left_pct + ((left_pct_end if left_pct_end is not None else left_pct) - left_pct) * k
        bal = 0x80 | int(round(100 - left))           # bit 7 : valeur du côté droit
        t = start + timedelta(seconds=i * step_s)
        body += struct.pack("<BIBBHBBBBB", 1, _ts(t), hr, cadence, power, bal,
                            int(torque[0] * 2), int(torque[1] * 2), int(smooth[0] * 2), int(smooth[1] * 2))
    end = start + timedelta(seconds=(n - 1) * step_s)
    body += _definition(2, 18, SESSION)
    body += struct.pack("<BIIBBII", 2, _ts(end), _ts(start), SPORT[sport], SUB[sub], int(minutes * 60 * 1000),
                        int(speed_kmh / 3.6 * minutes * 60 * 100))
    header = struct.pack("<BBHI4s", 14, 0x10, 2132, len(body), b".FIT")
    header += struct.pack("<H", crc16(header))
    data = header + body
    return data + struct.pack("<H", crc16(data))
