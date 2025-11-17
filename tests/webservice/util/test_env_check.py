import pytest

from server_manager.webservice.util.env_check import check_mount_path


def test_check_mount_path_bad_access(monkeypatch):
    monkeypatch.setenv("SM_MOUNT_PATH", "/tmp/server_manager_test_mount")
    monkeypatch.setattr("os.access", lambda _path, _mode: False)
    with pytest.raises(SystemExit, match="1") as exc_info:
        check_mount_path()
    assert exc_info.value.code == 1


def test_check_mount_path_good_access(monkeypatch):
    monkeypatch.setenv("SM_MOUNT_PATH", "/tmp/server_manager_test_mount")
    monkeypatch.setattr("os.access", lambda _path, _mode: True)
    # Should not raise any exception
    check_mount_path()


def test_check_mount_path_creates_directory(monkeypatch, tmp_path):
    test_mount_path = tmp_path / "server_manager_test_mount"
    monkeypatch.setenv("SM_MOUNT_PATH", str(test_mount_path))
    monkeypatch.setattr("os.access", lambda _path, _mode: True)

    # Ensure the directory does not exist before the check
    assert not test_mount_path.exists()

    # This should create the directory
    check_mount_path()

    # Verify that the directory was created
    assert test_mount_path.exists()
    assert test_mount_path.is_dir()
