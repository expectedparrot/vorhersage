#!/usr/bin/env python3
"""Freeze the published AIRO panel from the authors' pinned GitHub tarball."""

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

COMMIT = "646da9a2cd61f7043f46b2ccd4ac53e525925018"
RUN = "2026-09-10T2141Z"
LOG = "results/conditional_runs_combined.jsonl"
FILES = ["LICENSE", "LICENSE-DATA", "data/autoarc_ladder.json", "data/autoarc_crosscutting.json",
         "data/combined_conditions.json", "data/epoch_capabilities_index_2026-09-08.csv",
         "data/auto-arc/definitions-2026-09-10.md", "results/graph1_data.json", "results/graph2_data.json",
         "results/conditional_data.json", "results/capability_data.json", "paper/numbers.tex"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(archive_path, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new source directory; frozen inputs are never overwritten.")
    with tarfile.open(archive_path) as archive:
        require_root = f"forecastingresearch-airo-{COMMIT[:7]}"
        if archive.getmembers()[0].name.split("/")[0] != require_root:
            raise ValueError("Archive root does not match the pinned upstream commit.")
        members = {"/".join(m.name.split("/")[1:]): m for m in archive if m.isfile()}
        blobs = {name: archive.extractfile(members[name]).read() for name in [*FILES, LOG]}
    selected, indices = [], []
    for line_number, line in enumerate(blobs[LOG].splitlines(keepends=True), 1):
        if json.loads(line).get("run_id") == RUN:
            selected.append(line)
            indices.append({"line": line_number, "sha256": sha(line)})
    if len(selected) != 1960:
        raise ValueError("Expected the 1,960 question/condition rows in the four-session published run.")
    selected_bytes = b"".join(selected)
    output.mkdir(parents=True)
    for name in FILES:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blobs[name])
    # mtime=0 prevents the compression timestamp from changing the frozen input.
    compressed = gzip.compress(selected_bytes, mtime=0)
    (output / "selected-run.jsonl.gz").write_bytes(compressed)
    manifest = {"repository": "https://github.com/forecastingresearch/airo", "commit": COMMIT,
                "archive_url": f"https://api.github.com/repos/forecastingresearch/airo/tarball/{COMMIT}",
                "archive_sha256": sha(Path(archive_path).read_bytes()), "run_id": RUN,
                "source_log": LOG, "source_log_sha256": sha(blobs[LOG]),
                "selection": "All rows with run_id exactly equal to the published run; no probability-based exclusions.",
                "selected_lines": indices, "selected_uncompressed_sha256": sha(selected_bytes),
                "files": {**{name: sha(blobs[name]) for name in FILES}, "selected-run.jsonl.gz": sha(compressed)},
                "attribution": "AIRO, Forecasting Research Institute, https://airo.forecastingresearch.org",
                "license": "Data/documentation/figures CC BY 4.0; see LICENSE-DATA for third-party carve-outs."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"output": str(output), "selected_rows": len(selected), "compressed_bytes": len(compressed)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.out), indent=2))
