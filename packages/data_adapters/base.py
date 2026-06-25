"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from packages.data_adapters.schema import (
    DatasetProfile,
    NormalizedDataset,
    RawDataset,
    ValidationReport,
)


class BaseDatasetAdapter(ABC):
    dataset_name: str = "unknown"

    def __init__(self, external_root: Path, limit: int | None = None) -> None:
        self.external_root = external_root
        self.limit = limit
        self.file_paths: list[Path] = []
        self._raw: RawDataset | None = None
        self._normalized: NormalizedDataset | None = None

    @abstractmethod
    def detect(self, file_paths: list[Path]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def profile(self) -> DatasetProfile:
        raise NotImplementedError

    @abstractmethod
    def load(self) -> RawDataset:
        raise NotImplementedError

    @abstractmethod
    def transform(self) -> NormalizedDataset:
        raise NotImplementedError

    def validate(self) -> ValidationReport:
        if self._normalized is None:
            self._normalized = self.transform()
        errors: list[str] = []
        warnings: list[str] = []
        stats = {name: len(df) for name, df in self._normalized.tables.items() if len(df) > 0}
        if not stats:
            warnings.append("No normalized rows produced")
        return ValidationReport(
            dataset_name=self.dataset_name,
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats,
        )

    def export(self, output_dir: str | Path) -> None:
        if self._normalized is None:
            self._normalized = self.transform()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for name, df in self._normalized.tables.items():
            if df is not None and len(df) > 0:
                df.to_csv(out / f"{name}.csv", index=False)

    def bind_files(self, file_paths: list[Path]) -> None:
        self.file_paths = file_paths
