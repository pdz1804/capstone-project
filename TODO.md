To ensure your team can execute these fixes efficiently, I have organized the feedback into a structured **To-Do List** categorized by document sections and technical LaTeX requirements.

---

## 📋 Report Revision Checklist

### 1. Front Matter & Formatting (Priority: High)

* [ ] **Cover Page:**
* Center the word "Report" (do not left-align).
* Increase font size for the title/main text.
* Add Council Information (Thông tin hội đồng).


* [ ] **Special Pages:** Remove chapter numbering for **Abstract** and **Declaration of Authorship** (use `\chapter*`).
* [ ] **Paragraphs:** Ensure every new paragraph has an indentation (thụt đầu dòng).
* [ ] **Hyphenation:** Add `\usepackage[none]{hyphenate}` and `\sloppy` to the preamble to prevent word-breaking at margins and manage spacing.
* [ ] **Subsubsections:** Ensure titles are **not** indented, end with a period (.), and do not have a line break after the title.

### 2. Structural Changes

* [ ] **Chapter Realignment:** Change Chapter 9 to **Chapter 7: Conclusion**.
* [ ] **Phase 1 Content:** In the conclusion/progress section, focus on *what was learned and achieved*. **Remove** the weekly "to-do" log.
* [ ] **Section 3.5 (Structure of the Report):** Cross-check and sync all section names. Ensure they match the actual Table of Contents (e.g., sync *Evaluation Methods* vs *Evaluation Plan*).
* [ ] **Requirement Analysis:** Add a **Technical Requirements** section immediately *before* the Main Architecture section.

### 3. Visuals (Figures & Tables)

* [ ] **Captions:** * Figures: Caption **below** the image.
* Tables: Caption **above** the table.
* LaTeX Syntax: Use `\caption[short title]{full description}`.


* [ ] **Figure Citations:** Remove citations from inside the image itself. Put the source/citation in the caption.
* [ ] **Table Consistency:** Reformat **Table 5.1** to match the style of all other tables in the report.
* [ ] **Diagram Updates:**
* Redraw/update the **Reranker** figure.
* Add 3 specific diagrams for Chapter 6: (1) A single pipeline (Input/Output), (2) High-level system architecture, (3) Full detailed architecture.



### 4. Mathematical & Technical Writing

* [ ] **Equations:** Only number an equation if it is explicitly mentioned in the text.
* [ ] **Colon (:) Usage:** Use colons only for **listings**. Do not use a colon if only one formula follows.
* [ ] **Symbol Sync:** Audit the entire paper to ensure every mathematical symbol is consistent (e.g., if  is used for a set, don't use  later for the same thing).
* [ ] **Missing Sections:** Complete **Section 6.3** which is currently missing.

### 5. Citations & Terminology

* [ ] **Terminology Consistency:** * Define abbreviations only at the first occurrence: *Multimodal Retrieval-Augmented Generation (mRAG)*. Use "mRAG" thereafter.
* Fix OCR: Use "Optical Character Recognition (OCR)" at first mention only.
* Check for consistent Bold/CamelCase usage across all terms.


* [ ] **Reference Cleanup:** * Page 18: Remove redundant [40] citations; mention once per context.
* Web links: Move URL references to **Footnotes**.
* Bibliography: Only **Research Papers** and **Textbooks** should remain in the formal References section.



### 6. Personnel Details

* [ ] **Advisor Info:** Update the mentor's title to: **Motohashi Laboratory Research Assistant**.

---

## 🛠 LaTeX Implementation Tips

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

**Would you like me to draft the "Technical Requirements" section or help rephrase the "Structure of the Report" section to match your new chapter list?**