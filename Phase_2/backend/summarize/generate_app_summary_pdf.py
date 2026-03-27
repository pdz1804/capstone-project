from pathlib import Path
from textwrap import wrap

import fitz
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/frankie/Library/CloudStorage/onedrive/BK227/CO4029-Specialized-Project/capstone-project")
OUTPUT_PDF = ROOT / "output" / "pdf" / "phase2_app_summary.pdf"
TMP_PNG = ROOT / "tmp" / "pdfs" / "phase2_app_summary_render.png"


def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

title_font = load_font(FONT_BOLD, 54)
section_font = load_font(FONT_BOLD, 28)
body_font = load_font(FONT_REG, 21)
small_font = load_font(FONT_REG, 16)
small_bold_font = load_font(FONT_BOLD, 16)


PAGE_W, PAGE_H = 1654, 1850
MARGIN = 86
GUTTER = 48
LEFT_W = 430
RIGHT_X = MARGIN + LEFT_W + GUTTER
RIGHT_W = PAGE_W - MARGIN - RIGHT_X

bg = Image.new("RGB", (PAGE_W, PAGE_H), "#f6f7fb")
draw = ImageDraw.Draw(bg)

# Header
draw.rounded_rectangle((MARGIN, 60, PAGE_W - MARGIN, 248), radius=36, fill="#0f172a")
draw.text((MARGIN + 42, 95), "Phase 2 Multimodal RAG App", font=title_font, fill="white")
draw.text(
    (MARGIN + 42, 168),
    "One-page repo-based summary of the web app in Phase_2",
    font=body_font,
    fill="#cbd5e1",
)


def section_box(x, y, w, title, body_lines, line_gap=8, bullet_indent=22):
    pad = 24
    cursor_y = y + pad
    draw.rounded_rectangle((x, y, x + w, y + 10), radius=0, fill="#f6f7fb")
    draw.rounded_rectangle((x, y, x + w, y + 10), radius=0, fill="#f6f7fb")
    box_h = measure_section_height(w, title, body_lines, line_gap=line_gap)
    draw.rounded_rectangle((x, y, x + w, y + box_h), radius=26, fill="white", outline="#dbe2ea", width=2)
    draw.text((x + pad, cursor_y), title, font=section_font, fill="#0f172a")
    cursor_y += 50
    for line in body_lines:
        if isinstance(line, tuple) and line[0] == "bullet":
            text = line[1]
            wrapped = wrap_text(text, w - pad * 2 - bullet_indent)
            draw.text((x + pad, cursor_y), "-", font=small_bold_font, fill="#0ea5e9")
            draw.text((x + pad + bullet_indent, cursor_y), wrapped[0], font=body_font, fill="#334155")
            cursor_y += 30
            for cont in wrapped[1:]:
                draw.text((x + pad + bullet_indent, cursor_y), cont, font=body_font, fill="#334155")
                cursor_y += 30
            cursor_y += line_gap
        else:
            wrapped = wrap_text(line, w - pad * 2)
            for sub in wrapped:
                draw.text((x + pad, cursor_y), sub, font=body_font, fill="#334155")
                cursor_y += 30
            cursor_y += line_gap
    return y + box_h


def wrap_text(text, width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), test, font=body_font)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def measure_section_height(w, title, body_lines, line_gap=8, bullet_indent=22):
    pad = 24
    total = pad + 50
    for line in body_lines:
        text = line[1] if isinstance(line, tuple) and line[0] == "bullet" else line
        inner_w = w - pad * 2 - (bullet_indent if isinstance(line, tuple) and line[0] == "bullet" else 0)
        total += len(wrap_text(text, inner_w)) * 30 + line_gap
    return total + pad


left_y = 288
left_y = section_box(
    MARGIN,
    left_y,
    LEFT_W,
    "What It Is",
    [
        "A React + FastAPI web app for uploading documents, running a multimodal RAG pipeline, building retrieval indexes, and asking natural-language questions over the indexed content.",
        "Repo docs frame it around educational and lecture materials, but the code accepts many document, media, and image formats.",
    ],
)
left_y += 26
left_y = section_box(
    MARGIN,
    left_y,
    LEFT_W,
    "Who It's For",
    [
        "Primary persona: Not found in repo.",
        "Closest repo evidence points to teams working with educational content, lecture files, and courseware.",
    ],
)
left_y += 26
left_y = section_box(
    MARGIN,
    left_y,
    LEFT_W,
    "How To Run",
    [
        ("bullet", "Backend: `cd Phase_2/backend`, create a venv, and `pip install -r requirements.txt`."),
        ("bullet", "Set `OPENAI_API_KEY` manually if you want answer generation; `.env.example` was not found in repo."),
        ("bullet", "Start the API with `cd api && python main.py` and use `http://localhost:8000/docs` to verify it."),
        ("bullet", "Frontend: `cd Phase_2/frontend && npm install && npm run dev`, then open `http://localhost:5173`."),
    ],
    line_gap=6,
)

right_y = 300
right_y = section_box(
    RIGHT_X,
    right_y,
    RIGHT_W,
    "What It Does",
    [
        ("bullet", "Uploads one or more files into the backend input workspace."),
        ("bullet", "Processes raw inputs through normalization, media processing, document processing, and consolidation stages."),
        ("bullet", "Builds text indexes with BM25, dense retrieval, and hybrid retrieval."),
        ("bullet", "Optionally builds image retrieval indexes with ColQwen."),
        ("bullet", "Runs natural-language search and returns ranked text chunks and image pages."),
        ("bullet", "Generates cited answers from retrieved results when generation is enabled."),
        ("bullet", "Shows pipeline status, config, indexed counts, and file previews in the UI."),
    ],
    line_gap=6,
)
right_y += 26
right_y = section_box(
    RIGHT_X,
    right_y,
    RIGHT_W,
    "How It Works",
    [
        ("bullet", "Frontend: React/Vite UI (`Phase_2/frontend/src/App.jsx`) calls `/api/files`, `/api/process`, `/api/index`, `/api/status`, `/api/config`, and `/api/search`."),
        ("bullet", "API layer: FastAPI app (`Phase_2/backend/api/main.py`) mounts route modules for files, pipeline, search, and images, with shared paths for `input/`, `output/`, and `config/default.yaml`."),
        ("bullet", "Processing core: `UnifiedRAGPipeline` (`Phase_2/backend/src/unified_rag_pipeline.py`) orchestrates four stages: normalization, media processing, document processing, and consolidation into RAG-ready outputs."),
        ("bullet", "Retrieval: the same pipeline sets up text retrievers (`bm25`, `dense`, `hybrid`), optional image retrievers (`colqwen`), and a generator for answer creation."),
        ("bullet", "Search flow: `/api/search` loads existing indexes, runs text search, optionally runs image search, then sends retrieved items to the generator to return an answer plus citations."),
    ],
    line_gap=6,
)

footer_y = max(left_y, right_y) + 24
footer = "Evidence used: root README, Phase_2/backend README + API/src files, Phase_2/frontend README + src/App.jsx."
draw.text((MARGIN, footer_y), footer, font=small_font, fill="#64748b")

OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
TMP_PNG.parent.mkdir(parents=True, exist_ok=True)
bg.save(TMP_PNG, "PNG")

pdf = fitz.open()
page = pdf.new_page(width=PAGE_W * 72 / 150, height=PAGE_H * 72 / 150)
page.insert_image(page.rect, filename=str(TMP_PNG))
pdf.save(str(OUTPUT_PDF))
pdf.close()
print(OUTPUT_PDF)
