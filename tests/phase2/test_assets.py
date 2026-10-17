import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offline_asset_manifest_matches_shipped_files_and_versions():
    directory = ROOT / "apps/web/public/maps"
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["coordinate_system"] == "WGS84"
    assert not manifest["remote_runtime_requests"]
    for filename, info in manifest["files"].items():
        content = (directory / filename).read_bytes()
        assert len(content) == info["bytes"]
        assert hashlib.sha256(content).hexdigest() == info["sha256"]
    dependencies = json.loads((ROOT / "apps/web/package.json").read_text())[
        "dependencies"
    ]
    for name, version in manifest["dependencies"].items():
        assert dependencies[name] == version
    assert (directory / "map-ui.woff2").read_bytes()[:4] == b"wOF2"
    assert (
        json.loads((directory / "land.geojson").read_text())["type"]
        == "FeatureCollection"
    )
