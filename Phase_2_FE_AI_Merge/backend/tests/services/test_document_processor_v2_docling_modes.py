from __future__ import annotations

import base64
import json
import os
from pathlib import Path

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba")

from app.services.processing_service import _build_pipeline_config
from src.processor import document_processor_v2 as dp_v2
from src.processor.document_processor_v2 import DocumentProcessorV2, ProcessingConfigV2


class _DummyDoc:
    page_count = 1

    def export_to_markdown(self) -> str:
        return "# Local Docling\n\nhello"


class _DummyResult:
    document = _DummyDoc()


class _DummyConverter:
    def convert(self, path: str) -> _DummyResult:
        assert path.endswith(".md")
        return _DummyResult()


def test_processing_service_passes_runtime_yaml_into_v2_config() -> None:
    runtime = {
        "processing": {
            "document": {
                "enable_ocr": True,
                "v2": {
                    "prefer_custom_readers": True,
                },
            }
        },
        "inference": {
            "use_aws_sagemaker_docling": True,
            "sagemaker_docling_endpoint_name": "phase2-docling-rt",
        },
    }

    cfg = _build_pipeline_config(runtime, force=False)

    assert cfg.document_config_v2 is not None
    assert cfg.document_config_v2.runtime_yaml == runtime


def test_document_processor_v2_uses_local_docling_when_sagemaker_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    source = input_dir / "lesson.md"
    source.write_text("# Lesson\n\nhello", encoding="utf-8")

    monkeypatch.setattr(dp_v2, "should_use_sagemaker_docling", lambda runtime: False)
    monkeypatch.setattr(DocumentProcessorV2, "_get_primary_converter", lambda self: _DummyConverter())

    processor = DocumentProcessorV2(
        input_dir=input_dir,
        output_dir=output_dir,
        config=ProcessingConfigV2(prefer_custom_readers=False),
    )

    info = processor.process_single_file(source)

    assert info["success"] is True
    assert info["processor_used"] == "docling"
    assert info["docling_mode"] == "local"

    exported = processor.export_processed_document(info)
    md_path = Path(exported["markdown"])
    meta_path = Path(exported["metadata"])

    assert md_path.exists()
    assert meta_path.exists()
    assert md_path.read_text(encoding="utf-8").startswith("# Local Docling")


def test_document_processor_v2_uses_sagemaker_docling_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    source = input_dir / "notes.txt"
    source.write_text("Plain text input", encoding="utf-8")

    runtime = {
        "inference": {
            "use_aws_sagemaker_docling": True,
            "sagemaker_docling_endpoint_name": "phase2-docling-rt",
        }
    }
    invoked: dict[str, str] = {}

    def _fake_invoke(file_path: Path, runtime_yaml: dict) -> dict:
        invoked["name"] = file_path.name
        invoked["suffix"] = file_path.suffix
        invoked["endpoint"] = runtime_yaml["inference"]["sagemaker_docling_endpoint_name"]
        return {
            "markdown": "# Remote Docling\n\nprocessed",
            "additional_files": {
                "docling_additional/assets/info.txt": base64.b64encode(b"extra").decode("ascii"),
            },
        }

    monkeypatch.setattr(dp_v2, "should_use_sagemaker_docling", lambda runtime_yaml: True)
    monkeypatch.setattr(dp_v2, "invoke_sagemaker_docling", _fake_invoke)

    processor = DocumentProcessorV2(
        input_dir=input_dir,
        output_dir=output_dir,
        config=ProcessingConfigV2(
            prefer_custom_readers=False,
            runtime_yaml=runtime,
        ),
    )

    info = processor.process_single_file(source)

    assert info["success"] is True
    assert info["processor_used"] == "docling"
    assert info["docling_mode"] == "sagemaker"
    assert invoked["suffix"] == ".md"
    assert invoked["name"].endswith("_temp.md")
    assert invoked["endpoint"] == "phase2-docling-rt"

    exported = processor.export_processed_document(info)
    md_path = Path(exported["markdown"])
    meta_path = Path(exported["metadata"])
    addl_path = output_dir / "notes" / "docling_additional" / "assets" / "info.txt"

    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8").startswith("# Remote Docling")
    assert meta_path.exists()
    assert addl_path.exists()
    assert addl_path.read_text(encoding="utf-8") == "extra"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["docling_mode"] == "sagemaker"
