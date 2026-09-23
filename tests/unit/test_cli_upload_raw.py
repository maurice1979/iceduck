from unittest.mock import MagicMock

from click.testing import CliRunner

from iceduck.cli import main


def _setup(monkeypatch, tmp_path):
    for dataset in ("fixtures", "full"):
        (tmp_path / dataset).mkdir()
    (tmp_path / "fixtures" / "patients.csv").write_text("Id\n1\n")
    (tmp_path / "full" / "patients.csv").write_text("Id\n1\n2\n")
    monkeypatch.setattr(main, "DATASET_DIRS", {"fixtures": tmp_path / "fixtures", "full": tmp_path / "full"})
    monkeypatch.setattr(main.settings, "bucket_name", "iceduck-lakehouse")
    client = MagicMock()
    monkeypatch.setattr(main, "get_s3_client", lambda: client)
    return client


def test_upload_raw_defaults_to_fixtures(monkeypatch, tmp_path):
    client = _setup(monkeypatch, tmp_path)

    result = CliRunner().invoke(main.cli, ["s3-upload-raw"])

    assert result.exit_code == 0
    client.upload_file.assert_called_once_with(
        str(tmp_path / "fixtures" / "patients.csv"), "iceduck-lakehouse", "raw/patients/patients.csv"
    )


def test_upload_raw_full_dataset_uses_same_key(monkeypatch, tmp_path):
    client = _setup(monkeypatch, tmp_path)

    result = CliRunner().invoke(main.cli, ["s3-upload-raw", "--dataset", "full"])

    assert result.exit_code == 0
    client.upload_file.assert_called_once_with(
        str(tmp_path / "full" / "patients.csv"), "iceduck-lakehouse", "raw/patients/patients.csv"
    )


def test_upload_raw_missing_dataset_points_at_download_script(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    (tmp_path / "full" / "patients.csv").unlink()

    result = CliRunner().invoke(main.cli, ["s3-upload-raw", "--dataset", "full"])

    assert result.exit_code != 0
    assert "No full CSVs found" in result.output
    assert "download.py" in result.output
