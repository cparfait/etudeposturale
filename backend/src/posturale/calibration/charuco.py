"""Calibration ChArUco : distorsion de l'objectif (intrinsèques) et plan du vélo (échelle, perpendicularité).

Mires : calibration/charuco_A3.json et charuco_A2.json (générées par tools/generate_charuco.py).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path

import cv2
import numpy as np

from posturale.config import repo_root


@dataclass
class Board:
    name: str
    cols: int
    rows: int
    square_mm: float
    marker_mm: float
    dictionary: str

    def cv(self):
        d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, self.dictionary))
        return cv2.aruco.CharucoBoard((self.cols, self.rows), self.square_mm, self.marker_mm, d)


def load_board(name: str = "A3") -> Board:
    p = repo_root() / "calibration" / f"charuco_{name}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return Board(d["name"], d["cols"], d["rows"], d["square_mm"], d["marker_mm"], d["dictionary"])


def detect(frame: np.ndarray, board: Board):
    """Coins ChArUco détectés : (coins image (n,2), ids (n,)) ou (None, None)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    detector = cv2.aruco.CharucoDetector(board.cv())
    corners, ids, _, _ = detector.detectBoard(gray)
    if ids is None or len(ids) < 6:
        return None, None
    return corners.reshape(-1, 2), ids.reshape(-1)


def board_points(board: Board, ids: np.ndarray) -> np.ndarray:
    """Coordonnées (mm) des coins ChArUco dans le plan de la mire."""
    return board.cv().getChessboardCorners()[ids][:, :2]


@dataclass
class Intrinsics:
    camera: str
    width: int
    height: int
    K: list
    dist: list
    rms_px: float
    n_views: int

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def K_np(self) -> np.ndarray:
        return np.array(self.K, dtype=float)

    @property
    def dist_np(self) -> np.ndarray:
        return np.array(self.dist, dtype=float)


def calibrate_intrinsics(frames, board: Board, camera: str = "camera", max_views: int = 40) -> Intrinsics:
    """Distorsion à partir d'images de la mire vue sous différents angles (vidéo où l'on bouge la mire)."""
    obj, img, size = [], [], None
    for frame in frames:
        size = frame.shape[1], frame.shape[0]
        c, ids = detect(frame, board)
        if c is None or len(ids) < 10:
            continue
        pts3 = board.cv().getChessboardCorners()[ids].astype(np.float32)
        obj.append(pts3)
        img.append(c.astype(np.float32))
        if len(obj) >= max_views:
            break
    if len(obj) < 6:
        raise ValueError(f"Mire vue sur trop peu d'images ({len(obj)} ; 6 minimum, 20 conseillées).")
    rms, K, dist, _, _ = cv2.calibrateCamera(obj, img, size, None, None)
    return Intrinsics(camera, size[0], size[1], K.tolist(), dist.ravel().tolist(), float(rms), len(obj))


@dataclass
class PlaneCalib:
    """Passage image → plan de la mire (mm), posée dans le plan médian du vélo."""
    H: list                     # homographie 3×3 (points non distordus → mm)
    mm_per_px: float
    tilt_deg: float | None      # écart à la perpendicularité caméra/mire (None sans intrinsèques)
    n_frames: int
    board: str
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def plane_from_frames(frames, board: Board, intr: Intrinsics | None = None) -> PlaneCalib | None:
    src, dst, tilts, n = [], [], [], 0
    for frame in frames:
        c, ids = detect(frame, board)
        if c is None:
            continue
        n += 1
        pts = undistort(c, intr)
        src.append(pts)
        dst.append(board_points(board, ids))
        if intr is not None:
            obj = board.cv().getChessboardCorners()[ids].astype(np.float32)
            ok, rvec, _ = cv2.solvePnP(obj, c.astype(np.float32), intr.K_np, intr.dist_np)
            if ok:
                R, _ = cv2.Rodrigues(rvec)
                normal_cam = R @ np.array([0.0, 0.0, 1.0])
                tilts.append(math.degrees(math.acos(min(1.0, abs(normal_cam[2])))))
    if n == 0:
        return None
    src_all, dst_all = np.vstack(src), np.vstack(dst)
    H, _ = cv2.findHomography(src_all, dst_all, cv2.RANSAC, 3.0)
    # échelle locale moyenne autour des coins
    proj = apply_h(H, src_all)
    d_img = np.linalg.norm(np.diff(src_all, axis=0), axis=1)
    d_mm = np.linalg.norm(np.diff(proj, axis=0), axis=1)
    ok = d_img > 1
    mm_per_px = float(np.median(d_mm[ok] / d_img[ok])) if ok.any() else float("nan")
    return PlaneCalib(H.tolist(), mm_per_px, float(np.median(tilts)) if tilts else None, n, board.name)


def undistort(points_px: np.ndarray, intr: Intrinsics | None) -> np.ndarray:
    pts = np.asarray(points_px, dtype=np.float64).reshape(-1, 2)
    if intr is None:
        return pts
    out = cv2.undistortPoints(pts.reshape(-1, 1, 2), intr.K_np, intr.dist_np, P=intr.K_np)
    return out.reshape(-1, 2)


def apply_h(H, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, float).reshape(-1, 2)
    hom = np.hstack([pts, np.ones((len(pts), 1))]) @ np.asarray(H, float).T
    return hom[:, :2] / hom[:, 2:3]
