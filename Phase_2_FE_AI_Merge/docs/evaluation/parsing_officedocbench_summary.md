# OfficeDocBench Parsing Evaluation Summary

## 1. Overview

This document summarizes methodology and evaluation framework for document parsing strategies on classical office documents (.docx, .xlsx, .pptx) within the project. The framework focuses on **Component-level Metrics**, comparing the exact structure extracted by our pipeline against standard benchmark annotations to ensure no critical formatting or object loss.

## 2. Evaluation Data (Ground Truth)

The evaluation utilizes the dataset provided by **OfficeDocBench**.

- **Source Files**: Located in `third_party/ailang-parse/data/test_files`.
- **Ground Truth**: JSON annotations in `third_party/ailang-parse/benchmarks/officedocbench/ground_truth`.
- **Dataset Scope**: Includes standard text documents, spreadsheets with merged cells/formulas, and presentations, along with "challenge" documents containing specific edge cases like bookmarks, comments, nested lists, etc.

`third_party/ailang-parse` is a local external benchmark checkout and is intentionally ignored by git. Restore it locally before running this evaluation; do not commit benchmark input files or generated results.

## 3. Evaluated Parsers

1. **`DocumentProcessorV2`**: Our main internal parsing system handling the reading and structure detection from office documents, mapping raw document data into our RAG-ready JSON schemas.

## 4. Evaluation Metrics

The parsed results are compared to ground-truth annotations across several dimensions:

- **Text Jaccard**: Token overlap between the extracted text and the ground truth.
- **Structural Recall**: The ratio of key structural elements (e.g., Headings) successfully extracted.
- **Structural Quality**: Correctness of lists and tables (e.g., table dimensions and spans).
- **Content Fidelity**: Preservation of paragraph counts, internal tags, and image indicators.
- **Feature Detection**: Detection of specific advanced features like bookmarks, tracked changes, or comments.
- **Metadata**: Preservation of document-level metadata (author, created date).

### 4.1 Composite Score Calculation

The composite score is a weighted average of all individual metrics:

```
Composite Score = 0.15 × FeatureDetection + 0.20 × StructuralRecall + 
                  0.15 × StructuralQuality + 0.15 × ContentFidelity + 
                  0.10 × TextJaccard + 0.15 × ElementCount + 0.10 × Metadata
```

**Weights Explanation:**
- Structural Recall (20%): Most important for RAG applications - ensuring document structure is preserved
- Feature Detection (15%): Critical for advanced features like track changes, comments
- Structural Quality (15%): Correctness of extracted structures (headings, tables, lists)
- Content Fidelity (15%): Preservation of content accuracy and ordering
- Element Count (15%): Precision in detecting the correct number of elements
- Text Jaccard (10%): Basic text preservation
- Metadata (10%): Document-level information

### 4.2 Text Jaccard (78.56%)

**Formula:**
```
Jaccard = |GT_words ∩ Actual_words| / |GT_words ∪ Actual_words|
```

**Calculation Method:**
1. Extract all alphanumeric words from ground truth elements (text, headings, tables, track_changes, comments, headers_footers, text_boxes, lists, footnotes, speaker_notes)
2. Extract all alphanumeric words from parser output elements
3. Calculate set intersection and union
4. Jaccard = intersection_size / union_size

**Example:**
```
GT_words = {"hello", "world", "test", "example"}
Actual_words = {"hello", "world", "different", "example"}
Intersection = {"hello", "world", "example"} → 3
Union = {"hello", "world", "test", "example", "different"} → 5
Jaccard = 3/5 = 60.0%
```

**Interpretation:** 78.56% indicates good text preservation with minor word-level losses.

### 4.3 Structural Recall (67.80%)

**Formula:**
```
Recall = (TableScore + TrackChangeScore + CommentScore + HeadingScore + 
          HeaderFooterScore + ImageScore) / NumberOfFeaturesPresent
```

**Component Calculations:**

**Table Recall:**
```
CountScore = min(actual_count, expected_count) / expected_count
MergeScore = 1.0 if has_merged_cells else 0.0
TableScore = 0.7 × CountScore + 0.3 × MergeScore (if merged cells present)
```

**Track Changes Recall:**
```
CountScore = min(actual_count, expected_count) / expected_count
TypeMatch = 1.0 if GT_types == Actual_types else 0.5 (if present)
TrackChangeScore = 0.6 × CountScore + 0.4 × TypeMatch
```

**Other Features (Comments, Headings, HeadersFooters, Images):**
```
Score = min(actual_count, expected_count) / expected_count
```

**Example:**
```
GT: 3 tables (1 merged), 2 comments, 5 headings
Actual: 2 tables (0 merged), 2 comments, 4 headings
TableScore = 0.7 × (2/3) + 0.3 × 0 = 0.467
CommentScore = 2/2 = 1.0
HeadingScore = 4/5 = 0.8
StructuralRecall = (0.467 + 1.0 + 0.8) / 3 = 75.6%
```

**Interpretation:** 67.80% shows most structural elements are captured, but some complex structures like merged tables may be missed.

### 4.4 Structural Quality (63.86%)

**Formula:**
```
Quality = (Sum of all quality scores) / NumberOfQualityDimensions
```

**Quality Dimensions:**

**Heading Level Distribution:**
```
For each level:
  LevelScore = min(actual_count, expected_count) / max(actual_count, expected_count)
HeadingLevelScore = average(LevelScores)
```

**Track Change Author Attribution:**
```
AuthorScore = |GT_authors ∩ Actual_authors| / |GT_authors|
```

**Comment Quality (Author + Text):**
```
AuthorScore = |GT_authors ∩ Actual_authors| / |GT_authors|
TextOverlap = |GT_comment_words ∩ Actual_comment_words| / |GT_comment_words|
CommentScore = (AuthorScore + TextOverlap) / 2
```

**Table Row Accuracy:**
```
RowScore = min(actual_rows, expected_rows) / max(actual_rows, expected_rows)
```

**Table Merge Span Accuracy:**
```
MergeScore = min(actual_merges, expected_merges) / max(expected_merges, 1)
```

**List Numbering:**
```
OrderedAcc = 1 - |actual_ordered - expected_ordered| / max(...)
UnorderedAcc = 1 - |actual_unordered - expected_unordered| / max(...)
DepthScore = min(actual_max_depth, expected_max_depth) / expected_max_depth
```

**Example:**
```
GT: Heading levels {1: 2, 2: 1}, Table rows: 10
Actual: Heading levels {1: 2, 2: 2}, Table rows: 8
LevelScore[1] = 2/2 = 1.0
LevelScore[2] = 1/2 = 0.5
HeadingLevelScore = (1.0 + 0.5) / 2 = 0.75
RowScore = 8/10 = 0.8
StructuralQuality = (0.75 + 0.8) / 2 = 77.5%
```

**Interpretation:** 63.86% indicates moderate quality - structures are detected but some details (level distribution, row counts) may be inaccurate.

### 4.5 Content Fidelity (52.39%)

**Formula:**
```
Fidelity = (Sum of all fidelity scores) / NumberOfFidelityDimensions
```

**Fidelity Dimensions:**

**Key Phrase Recall:**
```
For each key phrase in GT:
  Match if phrase found in all_text (case-insensitive)
PhraseScore = Matched / TotalKeyPhrases
```

**Paragraph Count Accuracy:**
```
ParaScore = min(actual_paras, expected_paras) / max(actual_paras, expected_paras, 1)
```

**Element Ordering (LCS - Longest Common Subsequence):**
```
LCSRatio = LCS_length / max(GT_length, Actual_length)
```

**Hyperlink Extraction:**
```
URLRecall = |GT_URLs ∩ Actual_URLs| / |GT_URLs|
TextRecall = |GT_anchor_texts ∩ Actual_anchor_texts| / |GT_anchor_texts|
LinkScore = 0.6 × URLRecall + 0.4 × TextRecall
```

**Style Preservation:**
```
BoldAcc = min(actual_bold, expected_bold) / max(expected_bold, 1)
ItalicAcc = min(actual_italic, expected_italic) / max(expected_italic, 1)
StyleScore = (BoldAcc + ItalicAcc) / 2
```

**Example:**
```
GT: 10 key phrases, 5 paragraphs, 3 hyperlinks
Actual: 6 key phrases found, 4 paragraphs, 2 hyperlinks
PhraseScore = 6/10 = 0.6
ParaScore = 4/5 = 0.8
URLRecall = 2/3 = 0.667
LinkScore = 0.6 × 0.667 = 0.4
ContentFidelity = (0.6 + 0.8 + 0.4) / 3 = 60.0%
```

**Interpretation:** 52.39% shows moderate content preservation - key phrases and paragraphs are partially preserved, but ordering and hyperlinks may have issues.

### 4.6 Feature Detection (56.55%)

**Formula:**
```
Detection = detected_features / total_expected_features
```

**Binary Detection (Present/Absent):**
- Checked features: headings, tables, track_changes, comments, headers_footers, footnotes, speaker_notes, text_boxes, images, lists, sheets, hyperlinks, styles, equations, bookmarks, fields, section_breaks

**Calculation:**
```
For each feature present in GT:
  detected = len(output.get(feature, [])) > 0
  if detected: detected_count += 1
FeatureDetection = detected_count / total_features_in_GT
```

**Example:**
```
GT has: headings ✓, tables ✓, comments ✓, images ✓, bookmarks ✓ (5 features)
Parser output has: headings ✓, tables ✓, comments ✓, images ✗, bookmarks ✗ (3 detected)
FeatureDetection = 3/5 = 60.0%
```

**Interpretation:** 56.55% indicates about half of advanced features are detected - basic features (headings, tables, comments) work well, but advanced features (bookmarks, track changes) may be missed.

### 4.7 Element Count

**Formula:**
```
ElementCount = sum(count_accuracy) / number_of_element_types
```

**Count Accuracy per Element Type:**
```
Accuracy = 1 - |actual - expected| / max(actual, expected, 1)
```

**Element Types Checked:**
- headings, tables, track_changes, comments, images, lists, text_boxes, footnotes, speaker_notes

**Example:**
```
GT: 3 headings, 2 tables, 5 comments
Actual: 2 headings, 2 tables, 7 comments
HeadingAcc = 1 - |2-3| / 3 = 0.667
TableAcc = 1 - |2-2| / 2 = 1.0
CommentAcc = 1 - |7-5| / 7 = 0.714
ElementCount = (0.667 + 1.0 + 0.714) / 3 = 79.4%
```

### 4.8 Metadata (2.38%)

**Formula:**
```
MetadataScore = matched_fields / total_fields
```

**Fields Checked (Exact Match):**
- title, author, created, modified
- sheet_names (set match for xlsx)

**Example:**
```
GT: {"title": "Test Doc", "author": "John", "created": "2024-01-01"}
Actual: {"title": "Test Doc", "author": "Unknown", "created": "2024-01-02"}
Title: "Test Doc" == "Test Doc" ✓
Author: "John" == "Unknown" ✗
Created: "2024-01-01" == "2024-01-02" ✗
MetadataScore = 1/3 = 33.3%
```

**Interpretation:** 2.38% is extremely low, indicating that parser does not prioritize extracting document metadata. This is expected as pipeline schema focuses on text and structure for RAG applications.

### 4.9 Coverage Calculation

**Formula:**
```
Coverage = number_of_OK_results / total_jobs
```

**Example:**
```
Total jobs: 43 files (29 docx, 6 xlsx, 8 pptx)
OK results: 42 files (1 failed)
Coverage = 42/43 = 97.67%
```

**By Format:**
```
docx coverage = 28/29 = 96.55%
pptx coverage = 8/8 = 100.00%
xlsx coverage = 6/6 = 100.00%
```

**Interpretation:** 96.55% coverage for docx indicates 1 out of 29 docx files failed to parse. 100% for pptx and xlsx indicates all files of these types were successfully parsed.

## 5. Results & Observations

**Recent Evaluation Results** (Total Jobs: 43 [29 docx, 6 xlsx, 8 pptx], Output: `backend/output/evaluation/officedocbench_document_processor_v2`):

| Parser Strategy | OK | ERROR | MISSING_PARSED | Text Jaccard | Struct Recall | Struct Quality | Content Fidelity | Feature Detection | Metadata |
|-----------------|----|-------|----------------|--------------|---------------|----------------|------------------|------------------|----------|
| **DocumentProcessorV2** | 42 | 1 (\*) | 0 | 78.56% | 67.80% | 63.86% | 52.39% | 56.55% | 2.38% |

**By Format**:

| Format | OK | Total | Coverage | Composite Score |
|--------|-----|-------|----------|----------------|
| **docx** | 28 | 29 | 96.55% | 60.98% |
| **pptx** | 8 | 8 | 100.00% | 54.10% |
| **xlsx** | 6 | 6 | 100.00% | 43.10% |

> **(\*) Note:** One file (`tables-with-incomplete-rows.docx`) failed due to a parsing error: "Invalid input tag of type <class '_cython_3_1_4.cython_function_or_method'>"

**Analysis**:

- **Strong Text Extraction**: `DocumentProcessorV2` performs well on text extraction with 78.56% Jaccard score, indicating good preservation of raw text content.
- **Good Structural Recall**: 67.80% structural recall shows the pipeline captures most structural elements like headings.
- **Moderate Structural Quality**: 63.86% structural quality indicates reasonable handling of lists and tables, though there's room for improvement in complex table structures.
- **Content Fidelity**: 52.39% content fidelity shows partial preservation of paragraph counts, element ordering, and special features.
- **Feature Detection**: 56.55% feature detection indicates partial success in detecting advanced features like bookmarks, comments, and track changes.
- **Metadata Preservation**: 2.38% metadata score is very low, as the generic pipeline schema prioritizes plain text and structure over office-specific metadata.
- **Format Performance**:
  - **docx**: Best overall performance (60.98% composite) with 96.55% coverage
  - **pptx**: Good performance (54.10% composite) with 100% coverage
  - **xlsx**: Lower performance (43.10% composite) with 100% coverage, indicating challenges with spreadsheet structures

## 6. Commands Reference

- **Run OfficeDocBench Evaluation**:
  ```bash
  python backend/evals/parsing/office/run_officedocbench_eval.py \
    --adapter DocumentProcessorV2 \
    --output-dir backend/output/evaluation/officedocbench_document_processor_v2 \
    --skip-processing false
  ```
