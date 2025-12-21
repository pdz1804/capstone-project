To ensure your team can execute these fixes efficiently, I have organized the feedback into a structured **To-Do List** categorized by document sections and technical LaTeX requirements.

---

## 📋 Report Revision Checklist

### 1. Front Matter & Formatting (Priority: High)

* [X] **Cover Page:**

* Center the word "Report" (do not left-align).
* Increase font size for the title/main text.
* Add Council Information (Thông tin hội đồng).
* Update with correct council members and English titles.

* [X] **Special Pages:** Remove chapter numbering for **Abstract** and **Declaration of Authorship** (use `\chapter*`).
* [X] **Paragraphs:** Ensure every new paragraph has an indentation (thụt đầu dòng).
* [X] **Hyphenation:** Add hyphenation control to the preamble to prevent word-breaking at margins and manage spacing.
* [ ] **Subsubsections:** Ensure titles are **not** indented, end with a period (.), and do not have a line break after the title.

### 2. Structural Changes (Mostly Complete)

* [X] **Chapter Realignment:** Changed final chapter to use 08_plan.tex as conclusion.
* [X] **Chapter Renaming:** Renamed 08_plan.tex from "Project Timeline and Work Plan" to "Conclusion" with updated introduction.
* [ ] **Phase 1 Content:** In the conclusion/progress section, focus on *what was learned and achieved*. **Requires** reformatting 08_plan.tex content (currently contains Phase 1 & Phase 2 timelines).
* [X] **Section 3.5 (Structure of the Report):** Cross-checked and synced all section names. Updated to accurately reflect all 7 chapters with correct descriptions.
* [X] **Requirement Analysis:** Added **Technical Requirements** section in Chapter 7 (Initial Implementation).
* [X] **Unicode Symbol Fixes:** Replaced all Unicode characters (✓, ✗, —) in tables with text equivalents ("Yes", "No", "---") to prevent LaTeX compilation errors.
* [X] **Section Merging:** Merged "Detailed Component Architecture" and "Multimodal RAG System" sections in Chapter 5 into unified "Detailed Component Architecture of Multimodal RAG System".
* [X] **Architecture Reorganization:** Restructured Chapter 5 architecture into clear three-layer structure: (1) Input Processing Layer, (2) Dual-Stream Indexing Layer, (3) Generative Synthesis Layer, with Advanced Visual Retrieval as detailed subcomponent.
* [X] **Duplicate Content Removal:** Removed approximately 140 lines of duplicate/overlapping content from Chapter 5.
* [X] **Phase 1 Scope Statement:** Added comprehensive Phase 1 scope paragraph at beginning of Chapter 6, clarifying focus on architecture design and deferring production features to Phase 2.

### 3. Visuals (Figures & Tables)

* [X] **Captions:** * Figures: Caption **below** the image (already done).
* Tables: Caption **above** the table.
* LaTeX Syntax: Use `\caption[short title]{full description}`.


* [X] **Figure Citations:** Remove citations from inside the image itself. Put the source/citation in the caption.
* [X] **Table Consistency:** Reformat **Table 5.1** to match the style of all other tables in the report.
* [ ] **Diagram Updates:**

* Redraw/update the **Reranker** figure.
* Add 3 specific diagrams for Chapter 6: (1) A single pipeline (Input/Output), (2) High-level system architecture, (3) Full detailed architecture.

### 4. Mathematical & Technical Writing

* [X] **Equations:** Only number an equation if it is explicitly mentioned in the text.
* [X] **Colon (:) Usage:** Use colons only for **listings**. Do not use a colon if only one formula follows.
* [X] **Symbol Sync:** Audit the entire paper to ensure every mathematical symbol is consistent (e.g., if $S$ is used for a set, don't use $S$ later for the same thing).
* [ ] **Missing Sections:** Complete **Section 6.3** which is currently missing.

### 5. Citations & Terminology (Pending)

* [X] **Terminology Consistency:** * Define abbreviations only at the first occurrence: *Multimodal Retrieval-Augmented Generation (mRAG)*. Use "mRAG" thereafter.

* [X] **Terminology Consistency:** * Define abbreviations only at the first occurrence: *Multimodal Retrieval-Augmented Generation (mRAG)*. Use "mRAG" thereafter.
* Fix OCR: Use "Optical Character Recognition (OCR)" at first mention only.
* Check for consistent Bold/CamelCase usage across all terms.

* [X] **Reference Cleanup:** * Page 18: Remove redundant [40] citations; mention once per context.
* [X] Web links: Move URL references to **Footnotes**.
* [] Bibliography: Only **Research Papers** and **Textbooks** should remain in the formal References section.

### 6. Plan File Conversion (08_plan.tex -> Conclusion)

* [X] **Reference Cleanup:** * Page 18: Remove redundant [40] citations; mention once per context.
* Web links: Move URL references to **Footnotes**.
* Bibliography: Only **Research Papers** and **Textbooks** should remain in the formal References section.

**Actions completed:**

* [X] **Rename chapter title** from "Project Timeline and Work Plan" to "Conclusion"
* [X] **Update chapter introduction** to position as concluding chapter summarizing Phase 1 achievements and outlining Phase 2 timeline
* [X] **Restructure Phase 1 section** - Transformed from timeline-focused "Detailed Work Plan" to achievement-focused "Implementation Journey and Accomplishments", organizing content into four thematic stages (Foundation & Research, Pipeline Development, Baseline Integration, System Refinement)
* [X] **Reframe Phase 2 section** - Renamed to "Future Work -- Multimodal Integration and Scaling" with updated introduction and "Planned Work Schedule" subsection
* [X] **Update Gantt chart captions** - Phase 1 now labeled as "Completed work" and Phase 2 as "Planned Timeline" to clearly distinguish accomplishments from future plans

**Content preserved and enhanced:**

- All technical details from weekly plans reorganized into achievement-based narrative
- Learning Milestones section maintained
- Both Gantt charts retained with updated contextual framing
- Information density preserved while improving readability and conclusion-appropriate tone

---

## LaTeX Implementation Tips

**For the Abstract/Declaration without numbers:**

```latex
\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract} % Adds it to TOC despite no number
```

**For the Figure Captions:**

```latex
\begin{figure}[ht]
    \centering
    \includegraphics{reranker.png}
    \caption[Short Title for List of Figures]{Full description of the reranker including citation \cite{source}.}
\end{figure}
```

---

## Progress Summary

| Category | Status | PMostly Complete | 85% |
| Visuals (Figures & Tables) | Pending | 0% |
| Mathematical & Technical | Pending | 0% |
| Citations & Terminology | Pending | 0% |
| Plan File Conversion | Complete | 100% |
| Overall | In Progress | 5| Pending | 0% |
| Citations & Terminology | Pending | 0% |
| Plan File Conversion | In Progress | 10% |
| Overall | In Progress | 58% |
