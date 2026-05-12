from __future__ import annotations

from pathlib import Path

import pytest

from src.processor import document_processor_v2 as dp_v2
from src.processor.item_sequencer import IMG_END, IMG_START, ItemSequencer, SectionNode
from src.processor.pdf_reader import (
    CustomPdfConfig,
    CustomPdfReader,
    ExtractedLayoutRegion,
    ExtractedRegion,
    PdfPageBatch,
)
from src.processor.document_processor_v2 import DocumentProcessorV2, ProcessingConfigV2


def _make_pdf(path: Path, pages: int) -> None:
    fitz = pytest.importorskip("fitz")

    doc = fitz.open()
    try:
        for idx in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {idx + 1}")
        doc.save(str(path))
    finally:
        doc.close()


def _region(page_no: int, region_id: str = "r1") -> ExtractedRegion:
    return ExtractedRegion(
        region=ExtractedLayoutRegion(
            region_id=region_id,
            page_no=page_no,
            region_type="text",
        ),
        text=f"page {page_no}",
        provenance={"page_no": page_no, "bbox": [0.0, 100.0, 10.0, 90.0]},
    )


def test_split_pdf_into_page_batches_keeps_page_ranges(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    batch_dir = tmp_path / "batches"
    _make_pdf(pdf_path, pages=9)

    batches = CustomPdfReader._split_pdf_into_page_batches(
        str(pdf_path),
        batch_dir,
        batch_size=4,
    )

    assert [(b.start_page, b.end_page) for b in batches] == [(1, 4), (5, 8), (9, 9)]
    assert all(Path(b.pdf_path).exists() for b in batches)
    assert [CustomPdfReader._get_page_count(b.pdf_path) for b in batches] == [4, 4, 1]


def test_offset_region_page_maps_batch_page_to_global_page() -> None:
    reader = CustomPdfReader(CustomPdfConfig())
    batch = PdfPageBatch(batch_id=1, start_page=9, end_page=16, pdf_path="batch.pdf")
    region = _region(page_no=1, region_id="p1_text")

    reader._offset_region_page(region, batch, page_offset=batch.start_page - 1)

    assert region.region.page_no == 9
    assert region.region.region_id == "b0001_p9_p1_text"
    assert region.provenance["page_no"] == 9
    assert region.provenance["docling_batch_id"] == 1
    assert region.provenance["docling_batch_start_page"] == 9
    assert region.provenance["docling_batch_end_page"] == 16


def test_hybrid_batched_extracts_batches_and_sorts_global_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(pdf_path, pages=5)
    seen_batch_page_counts: list[int] = []

    reader = CustomPdfReader(
        CustomPdfConfig(
            content_source="hybrid_batched",
            docling_batch_size=2,
            max_docling_concurrency=1,
            docling_batched_min_pages=1,
        )
    )

    def _fake_docling(batch_pdf_path: str, output_dir: str | None, **kwargs):
        seen_batch_page_counts.append(CustomPdfReader._get_page_count(batch_pdf_path))
        return [_region(page_no=1, region_id="docling_local_p1")]

    monkeypatch.setattr(reader, "_extract_docling_regions", _fake_docling)

    regions = reader._extract_content_hybrid_batched(str(pdf_path), str(tmp_path / "out"))

    assert seen_batch_page_counts == [2, 2, 1]
    assert [r.region.page_no for r in regions] == [1, 3, 5]
    assert [r.provenance["page_no"] for r in regions] == [1, 3, 5]
    assert [r.provenance["docling_batch_id"] for r in regions] == [0, 1, 2]


def test_hybrid_batched_falls_back_to_unbatched_then_pymupdf(monkeypatch) -> None:
    reader = CustomPdfReader(CustomPdfConfig(content_source="hybrid_batched"))

    monkeypatch.setattr(
        reader,
        "_extract_content_hybrid_batched",
        lambda pdf_path, output_dir: (_ for _ in ()).throw(RuntimeError("batch failed")),
    )
    monkeypatch.setattr(
        reader,
        "_extract_docling_regions",
        lambda pdf_path, output_dir: (_ for _ in ()).throw(RuntimeError("docling failed")),
    )
    monkeypatch.setattr(reader, "_extract_text_blocks", lambda pdf_path: [_region(1, "fallback")])

    regions = reader._extract_content("sample.pdf", None)

    assert len(regions) == 1
    assert regions[0].region.region_id == "fallback"


def test_hybrid_batched_merges_filtered_enrichment_without_base_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_pdf(pdf_path, pages=3)
    reader = CustomPdfReader(
        CustomPdfConfig(
            content_source="hybrid_batched",
            docling_batch_size=2,
            max_docling_concurrency=1,
            docling_batched_min_pages=1,
            enable_vlm=True,
            do_formula_enrichment=True,
        )
    )

    def _fake_docling(batch_pdf_path: str, output_dir: str | None, **kwargs):
        if kwargs.get("enable_vlm") or kwargs.get("do_formula_enrichment"):
            return [
                ExtractedRegion(
                    region=ExtractedLayoutRegion("formula", 1, "formula"),
                    text="E = mc^2",
                    latex="E = mc^2",
                    provenance={"page_no": 1, "bbox": [0, 90, 10, 80]},
                ),
                ExtractedRegion(
                    region=ExtractedLayoutRegion("image", 1, "image"),
                    image_rel_path="images/img.png",
                    image_md5="abc123",
                    description="A model architecture diagram.",
                    provenance={"page_no": 1, "bbox": [0, 80, 10, 70]},
                ),
                _region(1, "duplicate_text_from_enrichment"),
            ]
        return [_region(1, "base_text")]

    monkeypatch.setattr(reader, "_extract_docling_regions", _fake_docling)
    monkeypatch.setattr(reader, "_select_enrichment_pages", lambda *args, **kwargs: [1])

    regions = reader._extract_content_hybrid_batched(str(pdf_path), str(tmp_path / "out"))

    assert [r.region.region_type for r in regions].count("text") == 2
    assert any(r.region.region_type == "formula" and r.latex == "E = mc^2" for r in regions)
    assert any(
        r.region.region_type == "image" and r.description == "A model architecture diagram."
        for r in regions
    )


def test_item_sequencer_preserves_image_marker_and_appends_description() -> None:
    seq = ItemSequencer()
    image = ExtractedRegion(
        region=ExtractedLayoutRegion("img1", 1, "image"),
        image_rel_path="images/foo.png",
        image_md5="deadbeef",
        description="A compact architecture diagram.",
        provenance={"page_no": 1},
    )

    tree = seq.sequence([image], [SectionNode("Intro", 1, page_start=1)])
    content = tree[0]["content"]

    assert f"{IMG_START} images/foo.png|deadbeef {IMG_END}" in content
    assert "Image description: A compact architecture diagram." in content


def test_item_sequencer_formula_region_outputs_latex_block() -> None:
    seq = ItemSequencer()
    formula = ExtractedRegion(
        region=ExtractedLayoutRegion("f1", 1, "formula"),
        latex="E = mc^2",
        provenance={"page_no": 1},
    )

    tree = seq.sequence([formula], [SectionNode("Intro", 1, page_start=1)])

    assert "$$\nE = mc^2\n$$" in tree[0]["content"]


def test_document_processor_v2_passes_hybrid_batched_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    pdf_path = input_dir / "lesson.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    captured: dict[str, object] = {}

    class _DummyReader:
        def __init__(self, config: CustomPdfConfig) -> None:
            captured["config"] = config

        def read(self, file_path: str, output_dir: str | None = None):
            captured["file_path"] = file_path
            captured["output_dir"] = output_dir
            return [{"heading_text": "Lesson", "heading_level": 1, "content": "", "children": []}]

    monkeypatch.setattr(dp_v2, "PPTX_READER_AVAILABLE", False)
    monkeypatch.setattr("src.processor.pdf_reader.CustomPdfReader", _DummyReader)

    runtime = {
        "inference": {"use_aws_sagemaker_docling": True},
        "processing": {"document": {"docling_backend": "sagemaker"}},
    }
    processor = DocumentProcessorV2(
        input_dir=input_dir,
        output_dir=output_dir,
        config=ProcessingConfigV2(
            prefer_custom_readers=True,
            pdf_content_source="hybrid_batched",
            pdf_docling_batch_size=5,
            pdf_max_docling_concurrency=2,
            pdf_docling_batched_min_pages=10,
            pdf_do_formula_enrichment=True,
            pdf_vlm_page_filter="all_pages",
            pdf_vlm_batch_size=3,
            docling_config=type(
                "Cfg",
                (),
                {
                    "enable_ocr": True,
                    "export_images": False,
                    "enable_vlm": True,
                    "vlm_model": "HuggingFaceTB/SmolVLM-256M-Instruct",
                },
            )(),
            runtime_yaml=runtime,
        ),
    )

    processor._run_pdf_reader(pdf_path, output_dir / "lesson")

    cfg = captured["config"]
    assert isinstance(cfg, CustomPdfConfig)
    assert cfg.content_source == "hybrid_batched"
    assert cfg.runtime_yaml == runtime
    assert cfg.docling_batch_size == 5
    assert cfg.max_docling_concurrency == 2
    assert cfg.docling_batched_min_pages == 10
    assert cfg.enable_vlm is True
    assert cfg.do_formula_enrichment is True
    assert cfg.vlm_page_filter == "all_pages"
    assert cfg.vlm_batch_size == 3


def test_processing_service_accepts_hybrid_batched_config() -> None:
    from app.services.processing_service import _build_pipeline_config

    runtime = {
        "processing": {
            "document": {
                "v2": {
                    "pdf_content_source": "hybrid_batched",
                    "pdf_docling_batch_size": "6",
                    "pdf_max_docling_concurrency": "3",
                    "pdf_docling_batched_min_pages": "11",
                    "pdf_do_formula_enrichment": "true",
                    "pdf_vlm_page_filter": "all_pages",
                    "pdf_vlm_batch_size": "2",
                }
            }
        },
        "inference": {"use_aws_sagemaker_docling": True},
    }

    cfg = _build_pipeline_config(runtime, force=False)

    assert cfg.document_config_v2 is not None
    assert cfg.document_config_v2.pdf_content_source == "hybrid_batched"
    assert cfg.document_config_v2.pdf_docling_batch_size == 6
    assert cfg.document_config_v2.pdf_max_docling_concurrency == 3
    assert cfg.document_config_v2.pdf_docling_batched_min_pages == 11
    assert cfg.document_config_v2.pdf_do_formula_enrichment is True
    assert cfg.document_config_v2.pdf_vlm_page_filter == "all_pages"
    assert cfg.document_config_v2.pdf_vlm_batch_size == 2
