"""Pull the Synthea EHR dataset from Kaggle and build a small committed fixtures/ subset.

Usage: uv run python sample_data/health/download.py

Requires a Kaggle API token at ~/.kaggle/access_token (auto-detected by the
kaggle package). See docs/adr/0009-switch-dataset-to-synthea-ehr.md.
"""

import csv
from pathlib import Path

import kaggle

DATASET = "lucague/hospital-ehr-data-1171-patients-15-tables"
ENTITIES = ["patients", "providers", "organizations", "medications", "encounters", "conditions"]

HERE = Path(__file__).parent
FULL_DIR = HERE / "full"
FIXTURES_DIR = HERE / "fixtures"

N_FIXTURE_PATIENTS = 15


def download_full() -> None:
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    api = kaggle.api
    api.authenticate()
    for entity in ENTITIES:
        api.dataset_download_file(DATASET, f"{entity}.csv", path=str(FULL_DIR), force=True, quiet=False)
    print(f"Downloaded {len(ENTITIES)} entities to {FULL_DIR}")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    patients = read_csv(FULL_DIR / "patients.csv")
    selected_patient_ids = {p["Id"] for p in patients[:N_FIXTURE_PATIENTS]}

    def filter_by_patient(rows: list[dict]) -> list[dict]:
        return [r for r in rows if r["PATIENT"] in selected_patient_ids]

    encounters = filter_by_patient(read_csv(FULL_DIR / "encounters.csv"))
    medications = filter_by_patient(read_csv(FULL_DIR / "medications.csv"))
    conditions = filter_by_patient(read_csv(FULL_DIR / "conditions.csv"))

    provider_ids = {e["PROVIDER"] for e in encounters if e["PROVIDER"]}
    org_ids = {e["ORGANIZATION"] for e in encounters if e["ORGANIZATION"]}

    providers = [r for r in read_csv(FULL_DIR / "providers.csv") if r["Id"] in provider_ids]
    organizations = [r for r in read_csv(FULL_DIR / "organizations.csv") if r["Id"] in org_ids]

    fixture_patients = [p for p in patients if p["Id"] in selected_patient_ids]

    tables = {
        "patients": fixture_patients,
        "providers": providers,
        "organizations": organizations,
        "medications": medications,
        "encounters": encounters,
        "conditions": conditions,
    }
    for name, rows in tables.items():
        fieldnames = list(rows[0].keys()) if rows else []
        write_csv(FIXTURES_DIR / f"{name}.csv", rows, fieldnames)
        print(f"  {name}: {len(rows)} rows -> {FIXTURES_DIR / f'{name}.csv'}")

    print(f"Generated fixtures for {N_FIXTURE_PATIENTS} patients in {FIXTURES_DIR}")


def main() -> None:
    download_full()
    generate_fixtures()


if __name__ == "__main__":
    main()
