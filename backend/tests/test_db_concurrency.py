from concurrent.futures import ThreadPoolExecutor

from posturale.storage import db


def test_first_start_concurrent_requests(tmp_path, monkeypatch):
    """Au premier démarrage, plusieurs requêtes simultanées ne doivent pas créer les tables deux fois."""
    monkeypatch.setenv("POSTURALE_DATA", str(tmp_path))
    monkeypatch.setattr(db, "_engine", None)
    with ThreadPoolExecutor(8) as pool:
        engines = list(pool.map(lambda _: db.get_engine(), range(16)))
    assert len({id(e) for e in engines}) == 1
    assert (tmp_path / "posturale.sqlite").exists()
