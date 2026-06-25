"""Optional external dataset adapters (no-op when data absent)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from packages.data_adapters.base import BaseDatasetAdapter
from packages.data_adapters.schema import DatasetProfile, NormalizedDataset, RawDataset, empty_tables
from packages.data_adapters.utils import scan_dataset_files


class OptionalDatasetAdapter(BaseDatasetAdapter):
    """Base for second-batch datasets; returns empty tables if directory missing."""

    folder_name: str = "unknown"

    def detect(self, file_paths: list[Path]) -> bool:
        return bool(file_paths)

    def profile(self) -> DatasetProfile:
        return DatasetProfile(
            dataset_name=self.dataset_name,
            file_paths=[str(p) for p in self.file_paths],
            notes=["Optional dataset — skipped if directory absent"],
        )

    def load(self) -> RawDataset:
        frames = {}
        for path in self.file_paths:
            frames[path.name] = pd.read_csv(path, nrows=self.limit or 5000) if path.suffix == ".csv" else pd.DataFrame()
        self._raw = RawDataset(dataset_name=self.dataset_name, frames=frames)
        return self._raw

    def transform(self) -> NormalizedDataset:
        self._normalized = NormalizedDataset(dataset_name=self.dataset_name, tables=empty_tables())
        return self._normalized


class OpenSupplyHubAdapter(OptionalDatasetAdapter):
    dataset_name = "open_supply_hub"
    folder_name = "open_supply_hub"


class GdeltAdapter(OptionalDatasetAdapter):
    dataset_name = "gdelt"
    folder_name = "gdelt"


class OfacAdapter(OptionalDatasetAdapter):
    dataset_name = "ofac"
    folder_name = "ofac"


class WorldBankLpiAdapter(OptionalDatasetAdapter):
    dataset_name = "world_bank_lpi"
    folder_name = "world_bank_lpi"


class UnComtradeAdapter(OptionalDatasetAdapter):
    dataset_name = "un_comtrade"
    folder_name = "un_comtrade"


class AcledAdapter(OptionalDatasetAdapter):
    dataset_name = "acled"
    folder_name = "acled"


OPTIONAL_ADAPTERS: list[type[OptionalDatasetAdapter]] = [
    OpenSupplyHubAdapter,
    GdeltAdapter,
    OfacAdapter,
    WorldBankLpiAdapter,
    UnComtradeAdapter,
    AcledAdapter,
]


def build_optional_adapters(external_root: Path, limit: int | None = None) -> list[OptionalDatasetAdapter]:
    adapters: list[OptionalDatasetAdapter] = []
    for cls in OPTIONAL_ADAPTERS:
        folder = external_root / cls.folder_name
        files = scan_dataset_files(folder)
        if not files:
            continue
        adapter = cls(external_root, limit=limit)
        adapter.bind_files(files)
        adapters.append(adapter)
    return adapters
