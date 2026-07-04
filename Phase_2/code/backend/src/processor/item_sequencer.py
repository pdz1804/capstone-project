"""Sequence extracted regions into Docling-like section items."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple
import re

TABLE_START = "[START_TABLE_CONTENT]"
TABLE_END = "[END_TABLE_CONTENT]"
IMG_START = "[START_IMAGE_PATH]"
IMG_END = "[END_IMAGE_PATH]"


@dataclass
class SectionNode:
    """Mutable section tree node used while sequencing content."""

    heading_text: str
    heading_level: int
    page_start: int = 1
    children: List["SectionNode"] = field(default_factory=list)
    content: str = ""


@dataclass
class ItemSequencerConfig:
    """Settings for region-to-item sequencing."""

    include_unmatched_heading_as_bold: bool = True


class ItemSequencer:
    """Map extracted regions into section tree content."""

    def __init__(self, config: Optional[ItemSequencerConfig] = None) -> None:
        self.config = config or ItemSequencerConfig()

    def sequence(
        self,
        extracted_regions: List[Any],
        section_tree: List[SectionNode],
    ) -> List[Dict[str, Any]]:
        heading_queue = self._build_heading_queue(section_tree)

        preamble = SectionNode(heading_text="", heading_level=0, page_start=1)
        current: SectionNode = preamble

        for item in extracted_regions:
            if item.region.region_type == "text":
                current = self._consume_text_item(
                    text=item.text or "",
                    current=current,
                    heading_queue=heading_queue,
                    page_no=int(item.provenance.get("page_no") or item.region.page_no or 1),
                )
                continue

            if item.region.region_type == "table":
                md = (item.markdown_table or self._table_fallback(item.text)).strip()
                if md:
                    self._append(current, f"{TABLE_START}\n{md}\n{TABLE_END}")
                continue

            if item.region.region_type == "formula":
                latex_raw = (item.latex or item.text or "").strip().strip("$").strip()
                latex = self._normalize_formula_block(latex_raw.splitlines())
                if latex and self._is_meaningful_formula(latex):
                    self._append(current, f"$$\n{latex}\n$$")
                continue

            if item.region.region_type == "image":
                if item.image_rel_path and item.image_md5:
                    self._append(
                        current,
                        f"{IMG_START} {item.image_rel_path}|{item.image_md5} {IMG_END}",
                    )
                description = (getattr(item, "description", None) or "").strip()
                if description:
                    self._append(current, f"Image description: {description}")
                    continue
                caption = (getattr(item, "caption", None) or "").strip()
                if caption:
                    self._append(current, f"Image caption: {caption}")

        roots = [preamble, *section_tree] if preamble.content.strip() else section_tree
        out = [self._to_dict(n) for n in roots]
        self._normalize_levels(out)
        return self._prune_empty(out)

    def _consume_text_item(
        self,
        text: str,
        current: SectionNode,
        heading_queue: Dict[str, Deque[SectionNode]],
        page_no: int,
    ) -> SectionNode:
        raw_lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        lines = self._sanitize_text_lines(raw_lines)
        if not lines:
            return current

        buffer: List[str] = []

        def flush() -> None:
            if buffer:
                self._append(current, "\n".join(buffer))
                buffer.clear()

        i = 0
        while i < len(lines):
            line = lines[i]

            if line.endswith("-") and i + 1 < len(lines):
                merged = f"{line[:-1]}{lines[i + 1]}"
                matched = self._match_heading(merged, heading_queue, page_no=page_no)
                if matched is not None:
                    flush()
                    current = matched
                    i += 2
                    continue

            matched = self._match_heading(line, heading_queue, page_no=page_no)
            if matched is not None:
                flush()
                current = matched
                i += 1
                continue

            if self._is_heading_candidate(line):
                if self.config.include_unmatched_heading_as_bold:
                    flush()
                    self._append(current, f"**{line}**")
                    i += 1
                    continue

            buffer.append(line)
            i += 1

        flush()
        return current

    @staticmethod
    def build_section_tree(flat: List[Tuple[int, str, int]]) -> List[SectionNode]:
        """Convert flat (level, title, page_start) entries into a nested tree."""
        if not flat:
            return []

        root: List[SectionNode] = []
        stack: List[Tuple[int, SectionNode]] = []

        for level, title, page_start in flat:
            node = SectionNode(
                heading_text=title,
                heading_level=max(1, int(level)),
                page_start=max(1, int(page_start)),
            )
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].children.append(node)
            else:
                root.append(node)
            stack.append((level, node))

        return root

    @staticmethod
    def _append(node: SectionNode, text: str) -> None:
        node.content = f"{node.content}\n{text}".strip() if node.content else text

    def _build_heading_queue(self, nodes: List[SectionNode]) -> Dict[str, Deque[SectionNode]]:
        queue: Dict[str, Deque[SectionNode]] = defaultdict(deque)

        def walk(items: List[SectionNode]) -> None:
            for node in items:
                key = self._normalize(node.heading_text)
                if key:
                    queue[key].append(node)
                walk(node.children)

        walk(nodes)
        return queue

    def _match_heading(
        self,
        text: str,
        queue: Dict[str, Deque[SectionNode]],
        page_no: Optional[int] = None,
    ) -> Optional[SectionNode]:
        key = self._normalize(text)
        if not key:
            return None

        if key in queue and queue[key]:
            candidate = queue[key][0]
            if page_no is None or candidate.page_start <= page_no:
                return queue[key].popleft()

        for q_key, q_nodes in queue.items():
            if not q_nodes:
                continue
            if not self._is_heading_key_match(observed=key, expected=q_key):
                continue
            candidate = q_nodes[0]
            if page_no is None or candidate.page_start <= page_no:
                return q_nodes.popleft()
        return None

    @staticmethod
    def _is_heading_key_match(observed: str, expected: str) -> bool:
        if observed == expected:
            return True

        if len(expected) > 5 and observed.startswith(expected):
            rest = observed[len(expected):].strip(" .:-")
            if not rest:
                return True

        # Handle wrapped headings where OCR/text extraction truncates trailing words.
        if len(observed) < 18 or len(expected) < len(observed):
            return False

        observed_words = observed.split()
        expected_words = expected.split()
        if len(observed_words) < 4 or len(observed_words) > len(expected_words):
            return False

        for idx, word in enumerate(observed_words):
            target = expected_words[idx]
            if idx == len(observed_words) - 1:
                if not target.startswith(word):
                    return False
            elif word != target:
                return False
        return True

    def _is_heading_candidate(self, text: str) -> bool:
        compact = " ".join((text or "").split())
        if len(compact) > 180:
            return False
        if compact.count("\n") > 0:
            return False
        if compact in {"$", "$$", TABLE_START, TABLE_END, IMG_START, IMG_END}:
            return False
        if compact.startswith("$") or compact.endswith("$"):
            return False
        if compact.startswith("[START_") or compact.startswith("[END_"):
            return False
        if self._looks_like_formula_line(compact):
            return False
        if re.fullmatch(r"\(?\d+\)?\.?", compact):
            return False
        if compact.endswith(":"):
            return True
        if re.match(r"^\d+(?:\.\d+)*\s+", compact):
            return True
        words = compact.split()
        return 1 <= len(words) <= 16 and not compact.endswith(".")

    @staticmethod
    def _looks_like_formula_line(text: str) -> bool:
        t = " ".join((text or "").split())
        if not t:
            return False
        if len(t) > 220:
            return False
        if re.fullmatch(r"\(?\d+\)?\.?", t):
            return True
        if re.search(r"\\(frac|sqrt|sum|int|prod|alpha|beta|gamma|delta|theta|lambda|mu|sigma|pi|phi)\\b", t):
            return True
        if re.search(r"[=^_]|∑|∫|√|∞|≈|≠|≤|≥|±|×|÷", t):
            return True
        if re.search(r"\b[A-Za-zα-ωΑ-Ω]\s*=", t):
            return True
        symbols = sum(1 for c in t if c in "=^_()[]{}")
        return symbols >= 3 and len(t.split()) <= 18

    @staticmethod
    def _normalize_formula_block(lines: List[str]) -> str:
        cleaned: List[str] = []
        for line in lines:
            ln = (line or "").strip().strip("*").strip()
            if not ln:
                continue
            if len(ln) >= 3 and (ln.count("�") / len(ln)) > 0.35:
                continue
            ln = ln.replace("�", "").replace("□", "")
            ln = re.sub(r"\s+", " ", ln).strip()
            if not ln:
                continue
            cleaned.append(ln)
        return " ".join(cleaned).strip()

    @staticmethod
    def _is_meaningful_formula(text: str) -> bool:
        t = " ".join((text or "").split())
        if len(t) < 3:
            return False

        replacement_ratio = t.count("�") / max(1, len(t))
        if replacement_ratio > 0.12:
            return False

        if re.fullmatch(r"[\d\s\.,;:()\[\]{}+\-/*=^_]+", t):
            return False

        return bool(
            re.search(
                r"[A-Za-zα-ωΑ-Ω0-9]|∑|∫|√|∞|≈|≠|≤|≥|±|×|÷|\\[A-Za-z]+",
                t,
            )
        )

    def _sanitize_text_lines(self, lines: List[str]) -> List[str]:
        sanitized: List[str] = []
        recent_norms: set[str] = set()

        for raw in lines:
            line = " ".join((raw or "").split()).strip()
            line = self._sanitize_corrupted_tokens(line)
            if not line:
                continue

            if self._is_obviously_garbled_line(line):
                continue

            norm = self._line_norm(line)
            if sanitized and norm == self._line_norm(sanitized[-1]):
                continue
            if norm and norm in recent_norms:
                continue

            sanitized.append(line)
            if norm:
                recent_norms.add(norm)

            if len(recent_norms) > 20:
                recent_norms = {self._line_norm(x) for x in sanitized[-8:]}

        return sanitized

    @staticmethod
    def _line_norm(text: str) -> str:
        t = (text or "").lower()
        t = re.sub(r"\s+", " ", t).strip()
        t = re.sub(r"[^a-z0-9α-ω]+", "", t)
        return t

    @staticmethod
    def _is_obviously_garbled_line(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True

        if len(t) >= 4 and (t.count("�") / len(t)) > 0.12:
            return True

        if re.fullmatch(r"\(?\d+\)?", t):
            return True

        if re.fullmatch(r"[\W_]+", t):
            return True

        if len(t) <= 3 and re.fullmatch(r"[A-Za-z]", t):
            return True

        if re.fullmatch(r"[√∑∫∞≈≠≤≥±×÷]+", t):
            return True

        return False

    @staticmethod
    def _sanitize_corrupted_tokens(text: str) -> str:
        tokens = [tok for tok in (text or "").split() if tok.strip()]
        if not tokens:
            return ""

        cleaned_tokens: List[str] = []
        for tok in tokens:
            if tok.count("�") >= 2:
                continue

            if "�" in tok:
                if re.search(r"[A-Za-zα-ωΑ-Ω]", tok):
                    continue
                tok = tok.replace("�", "")

            tok = tok.strip()
            if tok:
                cleaned_tokens.append(tok)

        line = " ".join(cleaned_tokens)
        line = re.sub(r"\s+", " ", line).strip()
        return line

    def _flatten(self, nodes: List[SectionNode]) -> List[SectionNode]:
        out: List[SectionNode] = []

        def walk(items: List[SectionNode]) -> None:
            for node in items:
                out.append(node)
                walk(node.children)

        walk(nodes)
        return out

    @staticmethod
    def _to_dict(node: SectionNode) -> Dict[str, Any]:
        return {
            "heading_text": node.heading_text,
            "heading_level": node.heading_level,
            "content": node.content,
            "children": [ItemSequencer._to_dict(c) for c in node.children],
        }

    def _normalize(self, text: str) -> str:
        t = re.sub(r"^\s*[\d]+(?:\.[\d]+)*\.?\s*", "", text or "")
        t = re.sub(r"^\s*[A-Z](?:\.[\d]+)*\.?\s+", "", t)
        t = re.sub(r"\s+", " ", t).strip().lower()
        t = t.replace("-", "").replace("–", "").replace("—", "")
        return t

    @staticmethod
    def _prune_empty(tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for node in tree:
            node["children"] = ItemSequencer._prune_empty(node.get("children", []))
            has_content = bool((node.get("content") or "").strip())
            has_children = bool(node.get("children"))
            has_heading = bool((node.get("heading_text") or "").strip())
            if has_content or has_children or has_heading:
                out.append(node)
        return out

    @staticmethod
    def _normalize_levels(tree: List[Dict[str, Any]], parent_level: int = 0) -> None:
        if not tree:
            return
        min_child = min(int(n.get("heading_level", 1)) for n in tree)
        shift = (parent_level + 1) - min_child
        for node in tree:
            if shift:
                node["heading_level"] = max(1, int(node.get("heading_level", 1)) + shift)
            ItemSequencer._normalize_levels(node.get("children", []), int(node.get("heading_level", 1)))

    @staticmethod
    def _table_fallback(text: str) -> str:
        compact = " ".join((text or "").split()) or "Table"
        return f"| Table |\n| --- |\n| {compact} |"
