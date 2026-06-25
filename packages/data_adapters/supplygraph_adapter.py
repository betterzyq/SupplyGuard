"""SupplyGraph heterogeneous supply chain graph adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from packages.data_adapters.base import BaseDatasetAdapter
from packages.data_adapters.schema import DatasetProfile, NormalizedDataset, RawDataset, ValidationReport, empty_tables
from packages.data_adapters.utils import (
    find_column,
    read_tabular,
    scan_dataset_files,
    stable_id,
)

SOURCE = "supplygraph"


class SupplyGraphAdapter(BaseDatasetAdapter):
    dataset_name = SOURCE

    def detect(self, file_paths: list[Path]) -> bool:
        return any("supplygraph" in str(p).lower() for p in file_paths)

    def _dataset_root(self) -> Path:
        return self.external_root / "supplygraph"

    def _find_file(self, *parts: str) -> Path | None:
        root = self._dataset_root()
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
        # fuzzy search
        name = parts[-1].lower()
        for path in scan_dataset_files(root):
            if path.name.lower() == name.lower():
                return path
        return None

    def profile(self) -> DatasetProfile:
        files = self.file_paths
        counts = {}
        cols = {}
        for path in files[:8]:
            df = read_tabular(path, nrows=50)
            counts[path.name] = len(read_tabular(path, nrows=self.limit or 5000))
            cols[path.name] = list(df.columns)
        return DatasetProfile(
            dataset_name=self.dataset_name,
            file_paths=[str(p) for p in files],
            row_counts=counts,
            columns=cols,
            notes=["Graph nodes/edges + plant/storage mapping"],
        )

    def load(self) -> RawDataset:
        root = self._dataset_root()
        homo = root / "Raw Dataset" / "Homogenoeus"
        frames: dict[str, pd.DataFrame] = {}

        mappings = {
            "nodes": homo / "Nodes" / "Nodes.csv",
            "node_index": homo / "Nodes" / "NodesIndex.csv",
            "node_types": homo / "Nodes" / "Node Types (Product Group and Subgroup).csv",
            "node_plant_storage": homo / "Nodes" / "Nodes Type (Plant & Storage).csv",
            "edges_plant": homo / "Edges" / "Edges (Plant).csv",
            "edges_storage": homo / "Edges" / "Edges (Storage Location).csv",
            "edges_product_group": homo / "Edges" / "Edges (Product Group).csv",
            "edges_product_subgroup": homo / "Edges" / "Edges (Product Sub-Group).csv",
        }

        for key, path in mappings.items():
            resolved = path if path.exists() else self._find_file(*path.parts[-3:])
            if resolved and resolved.exists():
                frames[key] = read_tabular(resolved, nrows=self.limit)

        self._raw = RawDataset(dataset_name=self.dataset_name, frames=frames)
        return self._raw

    def transform(self) -> NormalizedDataset:
        raw = self.load()
        frames = raw.frames
        tables = empty_tables()

        node_types = frames.get("node_types", pd.DataFrame())
        nodes_list = frames.get("nodes", pd.DataFrame())

        # Build node registry
        type_by_node: dict[str, dict] = {}
        if len(node_types):
            c_node = find_column(node_types, ["Node", "node"]) or node_types.columns[0]
            c_group = find_column(node_types, ["Group", "group"])
            c_subgroup = find_column(node_types, ["Sub-Group", "Sub Group", "sub-group"])
            for _, row in node_types.iterrows():
                code = str(row[c_node]).strip()
                type_by_node[code] = {
                    "group": str(row[c_group]) if c_group else None,
                    "subgroup": str(row[c_subgroup]) if c_subgroup else None,
                }

        if len(nodes_list):
            c = find_column(nodes_list, ["Node", "node"]) or nodes_list.columns[0]
            for val in nodes_list[c].dropna().astype(str):
                type_by_node.setdefault(val.strip(), {"group": None, "subgroup": None})

        materials, products = [], []
        node_to_material: dict[str, str] = {}
        node_to_product: dict[str, str] = {}

        for code, meta in type_by_node.items():
            grp = (meta.get("group") or "").upper()
            if grp == "P":
                pid = stable_id("SG-PRD", code)
                node_to_product[code] = pid
                products.append(
                    {
                        "product_id": pid,
                        "product_code": f"SG-{code}",
                        "product_name": code,
                        "category": meta.get("subgroup"),
                        "source_dataset": SOURCE,
                    }
                )
            else:
                mid = stable_id("SG-MAT", code)
                node_to_material[code] = mid
                materials.append(
                    {
                        "material_id": mid,
                        "material_code": f"SG-{code}",
                        "material_name": code,
                        "category": meta.get("subgroup") or meta.get("group"),
                        "is_critical": grp in {"M", "A"},
                        "source_dataset": SOURCE,
                    }
                )

        tables["materials"] = pd.DataFrame(materials)
        tables["products"] = pd.DataFrame(products)

        # Plant-based suppliers + facilities
        plant_storage = frames.get("node_plant_storage", pd.DataFrame())
        suppliers, facilities = [], []
        plant_supplier_id: dict[str, str] = {}
        if len(plant_storage):
            c_node = find_column(plant_storage, ["Node", "node"])
            c_plant = find_column(plant_storage, ["Plant", "plant"])
            c_storage = find_column(plant_storage, ["Storage Location", "storage location"])

            plants = plant_storage[c_plant].dropna().astype(str).unique() if c_plant else []
            for plant in plants:
                sid = stable_id("SG-PLT-SUP", plant)
                plant_supplier_id[plant] = sid
                suppliers.append(
                    {
                        "supplier_id": sid,
                        "supplier_code": f"PLANT-{plant}",
                        "supplier_name": f"Plant {plant}",
                        "country": None,
                        "city": None,
                        "latitude": None,
                        "longitude": None,
                        "tier": 1,
                        "risk_score": 0.0,
                        "status": "active",
                        "source_dataset": SOURCE,
                    }
                )

            if c_node and c_plant:
                for _, row in plant_storage.drop_duplicates(subset=[c_node, c_plant]).iterrows():
                    node = str(row[c_node]).strip()
                    plant = str(row[c_plant]).strip()
                    fid = stable_id("SG-FAC", plant, node)
                    facilities.append(
                        {
                            "facility_id": fid,
                            "supplier_id": plant_supplier_id.get(plant),
                            "facility_name": f"Plant {plant} / Node {node}",
                            "country": None,
                            "city": None,
                            "latitude": None,
                            "longitude": None,
                            "facility_type": "plant_storage",
                            "source_dataset": SOURCE,
                        }
                    )

        tables["suppliers"] = pd.DataFrame(suppliers)
        tables["facilities"] = pd.DataFrame(facilities)

        # Edges -> material_product + supplier_material
        sm_edges, mp_edges, alt_edges = [], [], []

        def ingest_edge_file(frame: pd.DataFrame, rel_type: str) -> None:
            if frame.empty:
                return
            c1 = find_column(frame, ["node1", "Node1"])
            c2 = find_column(frame, ["node2", "Node2"])
            if not c1 or not c2:
                cols = [c for c in frame.columns if c.lower() != "plant" and "storage" not in c.lower()]
                if len(cols) >= 2:
                    c1, c2 = cols[-2], cols[-1]
                else:
                    return
            for _, row in frame.iterrows():
                n1, n2 = str(row[c1]).strip(), str(row[c2]).strip()
                m1, m2 = node_to_material.get(n1), node_to_material.get(n2)
                p1, p2 = node_to_product.get(n1), node_to_product.get(n2)

                if m1 and p2:
                    mp_edges.append(
                        {
                            "material_id": m1,
                            "product_id": p2,
                            "relationship_type": "USED_IN",
                            "quantity": 1,
                            "is_critical": True,
                            "source_dataset": SOURCE,
                        }
                    )
                if m2 and p1:
                    mp_edges.append(
                        {
                            "material_id": m2,
                            "product_id": p1,
                            "relationship_type": "USED_IN",
                            "quantity": 1,
                            "is_critical": True,
                            "source_dataset": SOURCE,
                        }
                    )
                if m1 and m2:
                    mp_edges.append(
                        {
                            "material_id": m1,
                            "product_id": node_to_product.get(n2) or "",
                            "relationship_type": rel_type,
                            "quantity": 1,
                            "is_critical": False,
                            "source_dataset": SOURCE,
                        }
                    )
                    # supplier-material via plant supplier on upstream node
                    sid = plant_supplier_id.get(str(row.get(find_column(frame, ["Plant", "plant"]) or "", "")))
                    if sid and m1:
                        sm_edges.append(
                            {
                                "supplier_id": sid,
                                "material_id": m1,
                                "relationship_type": "SUPPLIES",
                                "lead_time_days": None,
                                "risk_weight": 1.0,
                                "source_dataset": SOURCE,
                            }
                        )

        for key, rel in [
            ("edges_plant", "PLANT_FLOW"),
            ("edges_storage", "STORAGE_FLOW"),
            ("edges_product_group", "GROUP_FLOW"),
            ("edges_product_subgroup", "SUBGROUP_FLOW"),
        ]:
            if key in frames:
                ingest_edge_file(frames[key], rel)

        # Clean mp_edges without product_id
        mp_clean = [e for e in mp_edges if e.get("product_id")]
        tables["material_product_edges"] = pd.DataFrame(mp_clean)
        tables["supplier_material_edges"] = pd.DataFrame(sm_edges).drop_duplicates() if sm_edges else pd.DataFrame(columns=tables["supplier_material_edges"].columns)

        # Alternative suppliers: nodes sharing same subgroup with different upstream plant
        if len(node_types):
            c_node = find_column(node_types, ["Node", "node"])
            c_subgroup = find_column(node_types, ["Sub-Group", "Sub Group"])
            if c_node and c_subgroup:
                by_sub = node_types.groupby(c_subgroup)[c_node].apply(list)
                for _, nodes in by_sub.items():
                    mats = [node_to_material.get(str(n)) for n in nodes if node_to_material.get(str(n))]
                    if len(mats) >= 2:
                        for i in range(len(mats)):
                            for j in range(i + 1, len(mats)):
                                alt_edges.append(
                                    {
                                        "supplier_id": mats[i],
                                        "alternative_supplier_id": mats[j],
                                        "material_id": mats[i],
                                        "similarity_score": 0.6,
                                        "certified": False,
                                        "source_dataset": SOURCE,
                                    }
                                )
        tables["supplier_alternative_edges"] = pd.DataFrame(alt_edges)

        self._normalized = NormalizedDataset(dataset_name=self.dataset_name, tables=tables)
        return self._normalized

    def validate(self) -> ValidationReport:
        report = super().validate()
        if self._normalized:
            if len(self._normalized.table("materials")) == 0:
                report.warnings.append("No materials from SupplyGraph")
            if len(self._normalized.table("material_product_edges")) == 0:
                report.warnings.append("No material-product edges from SupplyGraph")
        return report


def build_supplygraph_adapter(external_root: Path, limit: int | None = None) -> SupplyGraphAdapter | None:
    root = external_root / "supplygraph"
    files = scan_dataset_files(root)
    adapter = SupplyGraphAdapter(external_root, limit=limit)
    if adapter.detect(files):
        adapter.bind_files(files)
        return adapter
    return None
