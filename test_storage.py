import pytest

from backend import storage


def test_upload_path_uses_configured_upload_root(monkeypatch, tmp_path):
    upload_root = tmp_path / "persistent" / "uploads"
    monkeypatch.setattr(storage, "UPLOADS_DIR", upload_root)

    saved_path = storage.upload_path("prescriptions", "scan.png")

    assert saved_path == str(upload_root / "prescriptions" / "scan.png")
    assert (upload_root / "prescriptions").is_dir()
    assert (upload_root / "tablets").is_dir()
    assert (upload_root / "reports").is_dir()


def test_upload_path_rejects_unknown_category():
    with pytest.raises(ValueError, match="Unsupported upload category"):
        storage.upload_path("private", "scan.png")


def test_upload_path_discards_client_directory_components(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path / "uploads")

    saved_path = storage.upload_path("tablets", r"..\outside.png")

    assert saved_path == str(tmp_path / "uploads" / "tablets" / "outside.png")
