import json
from pathlib import Path

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.governance.policies import GOVERNANCE_SUMMARY
from starscream.tools.model_card import (
    analyze_export,
    build_citation_text,
    generate_model_card,
    main,
)

client = TestClient(app)


def _write_sample_export(export_dir: Path) -> None:
    export_dir.mkdir(parents=True)
    rows = [
        {
            "id": "1",
            "license": "CC0",
            "contributor_id": "contrib-a",
            "contributor_name": "Alice",
        },
        {
            "id": "2",
            "license": "CC-BY",
            "contributor_id": "contrib-b",
            "contributor_name": "Bob",
        },
        {
            "id": "3",
            "license": "CC0",
            "contributor_id": "contrib-a",
            "contributor_name": "Alice",
        },
    ]
    (export_dir / "dataset.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    (export_dir / "export_meta.json").write_text(
        json.dumps(
            {
                "total": 3,
                "train": 2,
                "val": 1,
                "split_by": "country",
                "formats": ["jsonl"],
                "audio_downloaded": 3,
            }
        ),
        encoding="utf-8",
    )


def test_governance_api_summary():
    response = client.get("/v1/governance")
    assert response.status_code == 200
    body = response.json()

    assert body["license_policy"]["allowed_licenses"] == ["CC0", "CC-BY"]
    assert body["foundation"]["name"] == "Starscream Foundation"
    assert body["mirror_reciprocity"]["threshold_tb"] == 10
    assert body["ai_training_clause"]["required"] is True
    assert body == GOVERNANCE_SUMMARY


def test_analyze_export_stats(tmp_path: Path):
    export_dir = tmp_path / "dataset"
    _write_sample_export(export_dir)

    analysis = analyze_export(export_dir)

    assert analysis["export_meta"]["total"] == 3
    assert analysis["row_count"] == 3
    assert analysis["unique_contributors"] == 2
    assert analysis["license_breakdown"] == {"CC-BY": 1, "CC0": 2}


def test_generate_model_card_cli(tmp_path: Path):
    export_dir = tmp_path / "dataset"
    _write_sample_export(export_dir)
    output = tmp_path / "MODEL_CARD.md"

    assert (
        main(
            [
                "generate",
                "--export-dir",
                str(export_dir),
                "--model-name",
                "my-model",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    content = output.read_text(encoding="utf-8")
    assert "# my-model" in content
    assert "Unique contributors | 2" in content
    assert "CC0 | 2" in content
    assert "CC-BY | 1" in content
    assert "data.starscream.org" in content
    assert "AI training clause" in content or "governance" in content.lower()


def test_generate_model_card_function(tmp_path: Path):
    export_dir = tmp_path / "dataset"
    _write_sample_export(export_dir)
    output = tmp_path / "out" / "MODEL_CARD.md"

    path = generate_model_card(export_dir, "test-model", output)
    assert path == output.resolve()
    assert "test-model" in path.read_text(encoding="utf-8")


def test_build_citation_text():
    citation = build_citation_text("demo-model")
    assert "Starscream Open Acoustic Corpus" in citation["plain_text"]
    assert "demo-model" in citation["plain_text"]
    assert "@misc{" in citation["bibtex"]
    assert "demo_model" in citation["bibtex"]
