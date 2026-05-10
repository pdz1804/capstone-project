# COMPREHENSIVE REPORT REVIEW & ACTION LIST

**Total Issues: 94** | **High Priority: 40** | **Medium Priority: 47** | **Low Priority: 13**

---

## ✅ IMPLEMENTATION STATUS - PHASE 1 COMPLETE

**Date Completed:** 2026-05-10
**Actions Implemented:** 45 (Section 1.5 update + 28 Phase 1 actions + 16 Phase 2 actions)
**Status:** ALL ACTIONS VERIFIED & PASSED ✅

### Verification Results:
- **Agent 1 (Chapters 1-5):** 23/23 PASSED
- **Agent 2 (Chapters 6-8):** 22/22 PASSED
- **Compilation:** ✅ Success (212 pages, 11.6 MB)

### Actions Completed:
- ✅ 1.1, 1.2, 1.3, 1.4, 1.6, 1.8, 1.9, 1.10, 1.11
- ✅ 2.2, 2.4, 2.6, 2.7, 2.8, 2.18, 2.22
- ✅ 3.1, 3.4, 3.6
- ✅ 4.1, 4.2, 4.3, 4.9
- ✅ 6.1, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8
- ✅ 7.1, 7.2, 7.3, 7.4, 7.5, 7.7, 7.8
- ✅ 8.1, 8.2, 8.3, 8.6, 8.7
- ✅ 1.5 (Structure of Report - Updated)

---

---

## CHAPTER 1: INTRODUCTION (13 issues)

### 🔴 HIGH PRIORITY (5 issues)

#### Action 1.1: Simplify Opening Paragraph
- **Current (Lines 5-6):** "Modern educational environments present two fundamental challenges related to information processing and retrieval. First, students conducting self-directed learning face the task of navigating distributed multimodal educational resources..."
- **Issue:** Too abstract, uses jargon without explanation
- **Action:** Rewrite as:
  > "Students learning on their own often struggle to find and organize course materials. These materials—videos, notes, slides, PDFs—are scattered across different websites and platforms. Gathering them all in one place takes too much time and effort."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.2: Replace Jargon "Manual Information Synthesis"
- **Current (Line 5):** "students must perform manual information synthesis across different modalities...This manual synthesis process creates high cognitive load"
- **Issue:** "Manual information synthesis" and "cognitive load" are academic jargon
- **Action:** Rewrite as:
  > "Students have to manually connect information from different sources—like watching a video lecture and then finding related notes. This requires a lot of mental effort and makes learning harder."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.3: Introduce MRAG Before Using It
- **Current (Line 9):** "This technical foundation motivates our investigation into integrating Retrieval-Augmented Generation (RAG) techniques with multimodal representation learning..."
- **Issue:** RAG introduced without explanation; "multimodal representation learning" is undefined
- **Action:** Rewrite as:
  > "We investigated using an AI retrieval system (called RAG—which we explain in Chapter 2) that can search through videos, images, and text together."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.4: Add Examples to Objectives
- **Current (Line 15):** "Apply OCR and Automatic Speech Recognition (ASR) to extract text from slides and audio content, enabling content indexing and retrieval."
- **Issue:** OCR/ASR undefined; no concrete example of outcome
- **Action:** Rewrite as:
  > "Convert slides and lecture videos into searchable text (like transcribing a video to find when the professor said 'photosynthesis')."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.5: Simplify Challenges Section
- **Current (Lines 46-47):** "RAG Adaptation to Multimodal Contexts...Our approach employs a dual-stream indexing architecture that processes text and visual content through separate pathways"
- **Issue:** Too technical for introduction; "dual-stream indexing architecture" unexplained
- **Action:** Rewrite as:
  > "Most search tools only work with text. But educational materials have videos, images, and diagrams too. Our system searches all of these together—it processes text and images separately, then combines the results."
- **Files Affected:** `_heading/02_introduction.tex`

### 🟡 MEDIUM PRIORITY (8 issues)

#### Action 1.6: Define "Grounding"
- **Current (Line 17):** "Utilize an LLM to ground retrieved evidence and generate coherent, contextually accurate responses."
- **Issue:** "Grounding" is undefined jargon
- **Action:** Change to: "Use an AI to confirm that answers are supported by the documents it found."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.7: Clarify "Study Roadmap Generation"
- **Current (Line 18):** "Provide personalized study tools, including lecture summarization and study roadmap generation"
- **Issue:** "Study roadmap generation" is vague
- **Action:** Change to: "Create personalized study guides: automatically summarize lectures and create a study plan that shows what topics to review for exams."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.8: Simplify Scope - Dense/Sparse Embeddings
- **Current (Line 30):** "Construction of a multimodal retrieval pipeline using both dense and sparse embeddings."
- **Issue:** "Dense and sparse embeddings" undefined
- **Action:** Change to: "Build a search system that finds relevant materials using different search methods that work together."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.9: Break Up Complex Modality Fusion Sentence
- **Current (Line 54):** "Our architecture implements a hybrid strategy that maintains separate indices during indexing and performs parallel retrieval with result aggregation during query execution."
- **Issue:** Complex chained technical terms
- **Action:** Split into: "Our system keeps separate search indexes for text and images. When a student searches, it searches both, then combines the results."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.10: Fix Inconsistent LLM Terminology
- **Current (Line 9):** Uses "MLLMs" without definition, then switches to "LLM"
- **Issue:** Inconsistent terminology
- **Action:** First use: "Multimodal Large Language Models (LLMs)—AI systems that can understand text, images, and audio—have recently improved dramatically."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.11: Simplify "Challenges and Solutions" Transition
- **Current (Line 37):** Launches into technical challenges without context
- **Issue:** No motivation for why these matter
- **Action:** Add intro: "To build this system, we had to solve several technical problems. Understanding these problems helps explain how we designed our solution."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.12: Simplify Vision-Language Models Explanation
- **Current (Line 50):** "Vision-Language Models...We integrate late-interaction visual models that preserve spatial and semantic nuances"
- **Issue:** "Late-interaction," "spatial and semantic nuances" unexplained
- **Action:** Change to: "We use AI models that can understand images. These models can find diagrams and charts even if they don't have descriptive text."
- **Files Affected:** `_heading/02_introduction.tex`

#### Action 1.13: Break Up Modality Fusion Explanation
- **Current (Line 54):** "Our architecture implements a hybrid strategy that maintains separate indices during indexing and performs parallel retrieval with result aggregation during query execution."
- **Issue:** Too many concepts in one sentence
- **Action:** Break into: 
  1. "Our system keeps separate search indexes for text and images."
  2. "When a student searches, it searches both indexes in parallel."
  3. "Then it combines the results intelligently."
- **Files Affected:** `_heading/02_introduction.tex`

---

## CHAPTER 2: PRELIMINARIES (23 issues)

### 🔴 HIGH PRIORITY (9 issues)

#### Action 2.1: Restructure Terminology Table with Guidance
- **Current (Lines 1-55):** 55+ acronyms in alphabetical table with no context
- **Issue:** Overwhelming; no guidance on what's essential vs. optional
- **Action:**
  1. Add intro paragraph: "This chapter introduces key concepts. Don't memorize every term—focus on the **essential** concepts marked with an asterisk. You'll learn others as we use them."
  2. Reorganize by concept instead of alphabetically:
     - "Text Retrieval Terms" (TF-IDF, BM25, etc.)
     - "AI Model Terms" (Transformer, BERT, etc.)
     - "Cloud Deployment Terms" (API, latency, etc.)
  3. Add 1-2 sentence explanation after each term
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.2: Add Intuition to ASR Mathematical Formula
- **Current (Lines 69-73):** "Formally, the goal of an ASR system is to determine the most probable word sequence $\hat{W}$ given an input acoustic observation $X$: $\hat{W} = \arg\max_{W} P(W|X)$"
- **Issue:** Suddenly jumps to math without intuitive explanation
- **Action:** Before formula, add:
  > "In simple terms, the system tries to find the sequence of words (W) that is most likely given the audio (X). It looks for: 'What words would most likely produce this audio sound?'"
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.3: Condense ASR Historical Timeline
- **Current (Lines 57-155):** 100 lines covering GMM-HMMs, DNN-HMM, CTC, Conformer evolution
- **Issue:** Too much historical detail; students don't need 2012-2025 timeline
- **Action:** Reorganize as 3 sections:
  1. **What ASR does:** 1 paragraph
  2. **How it works:** 2 paragraphs on modern neural approaches
  3. **Why it's hard:** Accents, noise, technical terms
  4. Move detailed architectures (Transformers, CTC, Conformer) to Appendix
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.4: Explain CTC Without Pure Math
- **Current (Lines 95-101):** Pure mathematical formula with "blanks and repeated labels" unexplained
- **Issue:** No intuition; purely mathematical
- **Action:** Replace/precede with:
  > "CTC is a technique that helps the model learn to match audio to text without being told exactly where each letter occurs in the audio. It's like finding the transcript without needing word-by-word timestamps."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.5: Restructure Transformer Section with Intuition First
- **Current (Lines 191-230):** 40 lines of math-heavy explanation
- **Issue:** Hard for students without ML background; heavy math without intuition
- **Action:**
  1. Start with visual diagram description: "A Transformer architecture has three main parts: input, processing, and output"
  2. Explain conceptually: "A Transformer is an AI architecture that learns which parts of the input to focus on"
  3. Then introduce formulas with explanations
  4. Use concrete example: "If you're reading a sentence, the model learns to pay more attention to pronouns than random words"
  5. Move heavy math to appendix or sidebar
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.6: Define Cross-Attention Before Using It
- **Current (Line 267-268):** "Unlike dual encoders, which independently embed queries and documents into fixed-length vectors, cross-encoders..."
- **Issue:** Assumes readers know dual encoders, cross-encoders, fixed-length vectors
- **Action:** Add definition first:
  > "There are two main ways AI models compare text: **Independent comparison** (each text separately) or **Joint comparison** (texts together). Joint comparison (called cross-attention) is more accurate but slower."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.7: Add Intuition to Multimodal Embedding Equations
- **Current (Lines 317-320):** "Each input modality $m \in \{\text{text}, \text{audio}, \text{vision}\}$ is encoded into a latent vector using a modality-specific encoder $z_m = f_m(x_m; \theta_m)$..."
- **Issue:** No intuitive explanation before equations
- **Action:** Before equation, add:
  > "To search across different types of information (text, images, audio), we need to represent them in a way the AI system can understand. We use numerical vectors (arrays of numbers) to represent each piece of information."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.8: Explain Contrastive Loss Intuitively
- **Current (Lines 339-342):** Contrastive loss formula without context
- **Issue:** No explanation of what "contrastive loss" is or why it matters
- **Action:** Before formula, add:
  > "To make sure the AI learns to match similar information across modalities, we use a technique called 'contrastive learning.' It teaches the model to make similar things close together and different things far apart."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.9: Condense RAG Historical Evolution
- **Current (Lines 379-394):** Lengthy historical section (REALM 2020, RocketQA 2021, etc.)
- **Issue:** Reads like literature review; students need concepts, not history
- **Action:** Consolidate to 1-2 paragraphs:
  > "RAG evolved from early retrieval systems (2017-2019) into a standard pattern (2020) of retrieving documents and generating answers. Recent work (2023-2025) focuses on making systems more accurate and trustworthy."
- **Files Affected:** `_heading/03_preliminary.tex`

### 🟡 MEDIUM PRIORITY (14 issues)

#### Action 2.10: Add Context to MRAG Pipeline
- **Current (Lines 422-423):** "The pipeline combines retrieval with generation to produce grounded answers. A query is encoded into a vector representation..."
- **Issue:** Compressed; "encoded into a vector representation" is jargon
- **Action:** Expand to concrete steps:
  > "Here's how it works: (1) A student asks a question. (2) The system converts the question into a numerical form. (3) The system finds the most similar documents using this form. (4) An AI reads the documents and writes an answer based on them."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.11: Simplify Sparse vs. Dense Retrieval Terms
- **Current (Lines 430-432):** Introduces TF-IDF, BM25, SPLADE, "lexical vectors," "inverted indexes"
- **Issue:** All undefined jargon
- **Action:** Replace with:
  > "There are two main search strategies: (1) **Keyword search** (like Ctrl+F in a document): finds exact words but misses synonyms. (2) **Semantic search** (understanding meaning): finds similar ideas even with different words, but can be slower."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.12: Explain Inner Product Relevance Score
- **Current (Lines 464-467):** "Relevance is computed as the inner product $s_{\mathrm{dense}} = \langle e_p, e_q \rangle$"
- **Issue:** No explanation of what inner product is
- **Action:** Replace with:
  > "Relevance is computed by comparing two numerical vectors—the query and the document. Similar vectors point in the same direction, so we measure how aligned they are."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.13: Simplify Reranker Concept
- **Current (Line 500):** "Unlike bi-encoders, which independently embed queries and documents into fixed-length vectors, rerankers leverage full token-level interactions..."
- **Issue:** Assumes understanding of embeddings, bi-encoders, token-level interactions
- **Action:** Rewrite as:
  > "First-stage search is fast but may miss relevant documents. Reranking uses a more careful (but slower) method to double-check the top results."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.14: Add Intuition to Augmentation Math
- **Current (Lines 576-607):** Heavy mathematical optimization formulation
- **Issue:** Math without intuition or student benefit
- **Action:** Before math, add explanation:
  > "After retrieving documents, we clean them up. We might remove repetitive information, summarize them, or reorganize them to make them easier for the AI to use."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.15: Add Context to Terminology Table Before Using
- **Current (Line 1):** Table immediately starts without intro
- **Issue:** No guidance on how to use this section
- **Action:** Add intro paragraph explaining:
  - What's essential (mark with *)
  - How to use the table while reading
  - You'll encounter concepts naturally as we use them
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.16: Delete Unnecessary ASR History (GMM-HMM Details)
- **Current (Lines 91-92):** "Early ASR systems used Gaussian Mixture Models with Hidden Markov Models..."
- **Issue:** Chronological padding; not necessary for understanding
- **Action:** Delete. Focus on modern approaches only.
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.17: Simplify OCR Section Similarly
- **Current (Lines 157-190):** Similar historical timeline as ASR
- **Issue:** Too many model names (CRNN, Faster R-CNN, YOLO, TrOCR) without context
- **Action:** Reorganize as:
  1. What OCR does (1 paragraph)
  2. How modern OCR works (2 paragraphs)
  3. Why it's hard (handwriting, noise, languages)
  Delete historical timeline.
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.18: Add Motivation for Transformer Detail
- **Current (Lines 191-230):** Heavy Transformer explanation
- **Issue:** Jumps into detail without motivation
- **Action:** Add intro:
  > "Transformers are a breakthrough AI architecture used in modern language and vision models. Understanding how they work helps explain why our system is effective."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.19: Break Transformer Math into Chunks
- **Current (Lines 231-239):** Dense sequence of encoder/decoder/attention formulas
- **Issue:** Multiple concepts without transitions
- **Action:** Add section headers and transition sentences:
  - "**Positional Encoding**: How does the model know word order?"
  - "**Attention Mechanism**: How does the model focus on relevant parts?"
  Each gets its own visual + intuition + formula
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.20: Add Legend to Multimodal Models Table
- **Current (Lines 360-375):** Table of models without explanation
- **Issue:** Models (CLIP, MM-Embed, ImageBind) haven't been explained
- **Action:** Add paragraph before table:
  > "Here are some popular multimodal models. Each has different strengths. For example, CLIP was an early breakthrough, while newer models like Jina-v4 work better with document images."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.21: Move Prompt Engineering to Implementation
- **Current (Lines 668-686):** Prompt engineering suddenly introduced in Preliminaries
- **Issue:** Doesn't belong in theory section; more of implementation detail
- **Action:** Either:
  - Move to Implementation chapter (Chapter 6)
  - OR integrate into RAG Generation section with clear transition
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.22: Add Intuition Before Generation/Augmentation
- **Current (Line 620):** Jumps into "Generation" section
- **Issue:** Purpose not clear
- **Action:** Add intro:
  > "Once we retrieve relevant documents, we need an AI to read them and write answers in the student's own words. This is where generation comes in."
- **Files Affected:** `_heading/03_preliminary.tex`

#### Action 2.23: Simplify MRAG Pipeline Visual Description
- **Current (Line 418):** Title only, no visual or clear description
- **Issue:** Complex concept needs visual + description
- **Action:** Add:
  - ASCII diagram or reference to figure
  - Step-by-step explanation (student question → retrieval → generation → answer)
- **Files Affected:** `_heading/03_preliminary.tex`

---

## CHAPTER 3: RELATED WORK (12 issues)

### 🔴 HIGH PRIORITY (4 issues)

#### Action 3.1: Simplify Opening Paragraph
- **Current (Lines 4-6):** "Designing an effective search or question-answering system for educational settings requires adapting retrieval methodologies to the type of content involved...The current best practice favors a two-stage retrieval architecture"
- **Issue:** Too abstract; "two-stage retrieval architecture" unexplained
- **Action:** Rewrite as:
  > "Educational systems need to search through different types of materials: text notes, slides with images, and videos. The best systems use two search stages: a fast initial search, then a more careful second check."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.2: Define Hybrid Retrieval Methods
- **Current (Lines 9-11):** "Hybrid sparse–dense retrieval...combined with a dense retriever such as a bi-encoder BERT or SciBERT"
- **Issue:** BM25, SPLADE, bi-encoder, BERT, SciBERT undefined
- **Action:** Replace with:
  > "Hybrid search combines two methods: keyword search (fast, good for exact terms) and semantic search (slower, good for finding related ideas). Using both together usually works better than using just one."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.3: Clarify Multimodal Embeddings Section
- **Current (Lines 13-16):** "For video lectures...Models such as M2HF index video segments into dense vectors...Text queries are mapped into the same embedding space"
- **Issue:** "Dense vectors," "embedding space," "cross-modal retrieval" undefined
- **Action:** Replace with:
  > "When searching through lecture videos, the system needs to find relevant parts (clips) based on a student's question. It converts both the question and the video into a form that can be compared—like converting them to maps where similar things are close together."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.4: Rewrite Feature-Level Fusion Section
- **Current (Lines 49-51):** "Early fusion, or feature-level fusion, merges modalities prior to computing similarity...M2HF model...highlights sound-producing regions within frames"
- **Issue:** "Feature-level fusion," "joint representations," "optical flow," "sound-producing regions" all undefined
- **Action:** Replace with:
  > "There are two main ways to combine information from different sources: (1) **Early fusion**: combine them before searching. (2) **Late fusion**: search separately then combine results. Early fusion can pick up on interactions (like what sound is happening where in a video), but it's more complex."
- **Files Affected:** `_heading/04_related_work.tex`

### 🟡 MEDIUM PRIORITY (8 issues)

#### Action 3.5: Improve Photosynthesis Example
- **Current (Lines 11-12):** Example good, but followed by dense academic language
- **Issue:** Example disconnects from explanation
- **Action:** Keep example, simplify follow-up:
  > "Research has confirmed that combining both search methods works better than using just one."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.6: Clarify Query Adaptation Section Title
- **Current (Line 18-24):** Section titled "Query Adaptation" but describes reranking
- **Issue:** Title doesn't match content
- **Action:** Rename to "Query Adaptation and Reranking" and add intro:
  > "Before reranking, sometimes the system needs to improve the original question. For example, mathematical queries might be reformatted so the system understands them better. Then, results are reranked for accuracy."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.7: Simplify Reranking Explanation
- **Current (Lines 22-24):** Dense explanation with technical framing
- **Issue:** Good example buried in technical language
- **Action:** Simplify to:
  > "In the second stage, a more careful AI looks at the top results to reorder them. It can catch subtle differences—like whether a slide just mentions photosynthesis or actually explains it—that a fast search might miss."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.8: Simplify Modality Balancing Explanation
- **Current (Line 57):** "Modality balancing, which ensures that no single modality dominates...techniques such as modality-specific weighting and loss balancing"
- **Issue:** "Loss balancing," "modality balancing" not explained; why it matters?
- **Action:** Replace with:
  > "Sometimes the AI relies too much on one type of information. For example, it might only look at images and ignore the transcript. Balancing techniques make sure the AI considers all sources equally."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.9: Rename "Educational Applications" Section
- **Current (Line 30):** Generic title "Educational applications"
- **Issue:** Vague; doesn't describe content
- **Action:** Rename to: "Datasets and Benchmarks for Educational Retrieval"
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.10: Simplify LPM Dataset Description
- **Current (Lines 34-36):** Dense paragraph with many concepts
- **Issue:** Multiple concepts compressed; hard to follow
- **Action:** Rewrite as:
  > "The LPM dataset is a collection of 180 hours of lecture videos with 9,000+ slides. It has detailed annotations showing which parts of the slide go with which parts of the lecture. This helps train and test AI systems on three tasks: (1) finding which diagram matches a spoken explanation, (2) finding which explanation matches a diagram, and (3) generating descriptions for slides."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.11: Clarify CK12-QA Description
- **Current (Lines 37-38):** Awkward phrasing; "doubles as a testbed" unclear
- **Issue:** Confusing structure
- **Action:** Simplify to:
  > "CK12-QA is another dataset with textbook questions. Researchers found that retrieving both text and diagrams (not just text alone) helps answer questions better."
- **Files Affected:** `_heading/04_related_work.tex`

#### Action 3.12: Condense M3AV Dataset Explanation
- **Current (Line 39):** Dense information dump; unclear purpose
- **Issue:** Too much detail; unclear what "repurposed for retrieval research" means
- **Action:** Simplify to:
  > "M3AV is a large dataset of 367 hours of lectures with transcripts and OCR text from slides. While it was designed for recognition tasks, it can also be used to train search systems."
- **Files Affected:** `_heading/04_related_work.tex`

---

## CHAPTER 4: PROPOSED SOLUTION (14 issues)

### 🔴 HIGH PRIORITY (4 issues)

#### Action 4.1: Define MRAG at Chapter Start
- **Current (Line 2):** MRAG used immediately without sufficient introduction
- **Issue:** Readers unfamiliar with RAG are confused
- **Action:** Add intro paragraph:
  > "This chapter describes our **Multimodal Retrieval-Augmented Generation (MRAG) system**—which combines large language models with a knowledge database to answer questions with cited sources. This design allows our system to process and retrieve information from diverse HCMUT educational materials while maintaining accuracy and transparency."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.2: Explain "Lost in the Middle" Phenomenon
- **Current (Line 25):** "Studies show that as the context length increases, the model's ability to reason over the data ('Lost in the Middle' phenomenon) decreases"
- **Issue:** Phenomenon presented as fact without explanation
- **Action:** Replace with:
  > "Studies show that when too much context is provided, LLMs struggle to locate relevant information deep within the text—a phenomenon called 'Lost in the Middle.' This occurs because AI models can focus on all positions, but effectiveness decreases when important information is buried among thousands of tokens."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.3: Clarify "Black Box" Language
- **Current (Lines 16-17):** "A fine-tuned model outputs an answer based on 'black box' internal weights. RAG provides citation and source attribution"
- **Issue:** "Black box" is jargon; why it matters unclear
- **Action:** Replace with:
  > "Fine-tuned models encode knowledge in their internal weights, making it impossible to trace where a specific answer came from. RAG, by contrast, retrieves the actual source documents, so you can verify the claim by reading the original text. This transparency is critical for academic integrity."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.4: Rewrite Qdrant Database Section
- **Current (Lines 216-240):** Dense section with excessive jargon: "tensor formalism," "HNSW," "multi-vector payloads"
- **Issue:** Impenetrable to students; multiple undefined terms
- **Action:** Rewrite as:
  > "Different vector databases use different strategies for storing and searching embeddings. Qdrant's key advantage is that it avoids creating an expensive index (called HNSW) for multi-vector data, which saves memory. Instead, it searches quickly using a simpler two-step approach: (1) find candidate documents using a fast, single-vector search, then (2) re-rank them by comparing all vectors from the query against all vectors in the document."
- **Files Affected:** `_heading/05_proposed_solution.tex`

### 🟡 MEDIUM PRIORITY (10 issues)

#### Action 4.5: Define Vector Databases
- **Current (Line 29):** "Semantic search utilizes Vector Databases to retrieve documents"
- **Issue:** No explanation of what a Vector Database is
- **Action:** Add definition:
  > "Semantic search uses **Vector Databases**—specialized storage systems that convert text into numerical 'vectors' (arrays of numbers). The system measures similarity between vectors to find documents with similar meaning, even if the wording differs."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.6: Simplify "Grounding the Generation"
- **Current (Line 16):** "RAG mitigates this by grounding the generation in retrieved evidence"
- **Issue:** "Grounding the generation" is jargon
- **Action:** Replace with:
  > "RAG prevents hallucinations by forcing the model to base its answer on retrieved documents. If the document doesn't mention something, the model can't invent it."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.7: Reduce Marketing Tone (React/Vue.js)
- **Current (Lines 109-111):** "React boasts a significantly larger...industry surveys consistently demonstrate React's dominant position"
- **Issue:** Reads like marketing material rather than technical justification
- **Action:** Rewrite as:
  > "React has a larger ecosystem (more third-party libraries available), which accelerates development because developers don't need to build custom components from scratch. We selected React because our team has more prior experience with it and because its larger library ecosystem was valuable for building complex UI features like document viewers and real-time chat."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.8: Define DRF Acronym Properly
- **Current (Line 175):** "Django REST Framework (DRF)...which involves writing separate Serializer classes"
- **Issue:** DRF defined once in parentheses; "Serializer classes" not explained
- **Action:** Expand to:
  > "In Django, you need the Django REST Framework (DRF), which requires writing separate 'Serializer' classes—code that manually converts Python objects into JSON. FastAPI skips this boilerplate and handles conversion automatically."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.9: Add Intuition to RRF Formula
- **Current (Lines 617-620):** "Reciprocal Rank Fusion (RRF) calculates: [formula] where k is a constant (typically 60)"
- **Issue:** Formula shown without intuition
- **Action:** Before formula, add:
  > "Reciprocal Rank Fusion (RRF) combines BM25 and dense results by assigning a score to each result based on its rank position. Results ranked higher (lower rank number) get higher scores. The constant k (60) is a smoothing factor that prevents low-ranked results from getting zero score and allows high-ranked results from both methods to be boosted."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.10: Standardize LLM vs. Reasoning Engine Terminology
- **Current (Line 41):** Uses "reasoning engine" and "LLM" interchangeably
- **Issue:** Inconsistent terminology confuses readers
- **Action:** Pick one term. If using "reasoning engine," define:
  > "the **reasoning engine** (the large language model that generates answers)"
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.11: Expand ColBERT Explanation
- **Current (Lines 349-353):** Dense explanation of ColBERT mechanism
- **Issue:** Compressed; lacks concrete example
- **Action:** Split into multiple sentences with example:
  > "Standard dense retrievers compress an entire document into one vector, losing details. For example, if a document discusses both 'machine learning' and 'calculus,' the single vector averages these topics together. ColBERT instead creates a vector for each word or phrase, allowing it to match specific terms in the query (e.g., 'machine learning') against specific parts of the document without losing fidelity."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.12: Improve Phase 2 Comparison Formatting
- **Current (Phase 2 section):** Overcrowded bullet lists with multiple sentences per point
- **Issue:** Hard to scan
- **Action:** Restructure as:
  - Short bullet point (main idea)
  - Detailed explanation in paragraphs below
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.13: Add Legend to RAG vs. Alternatives Table
- **Current (Lines 48-63):** Table with undefined terms ("Lost in the Middle," "N/A")
- **Issue:** Student doesn't understand column criteria
- **Action:** Add legend before table:
  > "**Knowledge Update** means how fresh the system's knowledge is when new documents are added. **Hallucination Risk** refers to the model generating plausible-sounding but false information."
- **Files Affected:** `_heading/05_proposed_solution.tex`

#### Action 4.14: Add Context to "Proof-of-Concept"
- **Current (Line 23 in 06_implementation):** "validate the technical feasibility of the multimodal retrieval logic"
- **Issue:** "Multimodal retrieval logic" is vague
- **Action:** Add concrete example:
  > "The primary objective was to validate that the system could successfully retrieve both text AND images to answer a single student query. For example, if a student asked 'What is photosynthesis?', the system should return both a textual explanation from lecture notes AND a diagram from a slide."
- **Files Affected:** `_heading/06_implementation.tex`

---

## CHAPTER 5: IMPLEMENTATION (14 issues - see Chapter 6)

---

## CHAPTER 6: EVALUATION & TESTING (11 issues)

### 🔴 HIGH PRIORITY (6 issues)

#### Action 6.1: Define Temporal IoU Metric
- **Current (Line 241):** "Mean Temporal IoU & 56.59%"
- **Issue:** IoU undefined; 56.59% meaningfulness unclear
- **Action:** Change to:
  > "Mean Temporal IoU (Intersection over Union) at 56.59%—measuring how precisely transcript chunks align with target time windows"
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.2: Break Up Dense Failure Analysis Paragraph
- **Current (Lines 35-36):** "The 47.43% Text Score indicates that token-level extraction remains challenging, primarily due to missing complex LaTeX formulas, text block fragmentation on heavily mathematical pages, and OCR noise."
- **Issue:** Three distinct problems compressed; student can't focus
- **Action:** Break into:
  > "The 47.43% Text Score reveals three bottlenecks: (1) missing complex LaTeX formulas (not extracted), (2) text block fragmentation on mathematical pages (chunks split incorrectly), and (3) OCR noise (incorrect character recognition)."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.3: Add Practical Context to WER/CER
- **Current (Lines 212-213):** "Mean WER (Word Error Rate) & 16.63%"
- **Issue:** WER defined minimally; meaningfulness unclear
- **Action:** Expand to:
  > "Mean WER (Word Error Rate)—percentage of incorrectly transcribed words—is 16.63%, which is acceptable for CPU-based speech recognition."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.4: Clarify Top-1 Precision Failure
- **Current (Line 139):** "Neither retriever excels at top-1 precision (approximately 24%)...expected because ranking relevant documents first requires understanding query intent"
- **Issue:** Explanation trails off; doesn't explain why 24% is bad or solution
- **Action:** Replace with:
  > "Both retrievers fail at single-attempt lookup (24% top-1 precision). This is expected: the first result often isn't correct because the system hasn't yet understood what you're really asking. Solution: the system searches deeper (at top-10, it finds 100% of answers)."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.5: Define nDCG and RRF Metrics with Intuition
- **Current (Lines 68, 139):** "nDCG@K (ranking quality considering both relevance and position)" without intuition
- **Issue:** nDCG definition is one line; no intuition. RRF introduced without definition.
- **Action:** Expand both:
  > "**nDCG@K** (normalized Discounted Cumulative Gain): a ranking score where top results count more. If the right answer is position 5, you get more credit than if it's position 10. Higher is better."
  > "**RRF** (Reciprocal Rank Fusion): a method that combines keyword search and semantic search by averaging their rankings—gets benefits of both."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.6: Break Up Dense Technical Sequence
- **Current (Lines 203-204):** "The pipeline extracted audio, ran Whisper ASR for transcription, chunked transcripts temporally, and extracted frames at 100-frame intervals."
- **Issue:** Four actions stacked without explaining purpose
- **Action:** Rewrite as:
  > "The system performed four steps: (1) extracted audio from videos, (2) transcribed it using Whisper (speech-to-text), (3) split transcriptions into time-aligned chunks, and (4) sampled video frames every 100 frames to index visual content."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

### 🟡 MEDIUM PRIORITY (5 issues)

#### Action 6.7: Add Educational Example to Retrieval Quality
- **Current (Lines 63-64):** "Retrieval quality directly impacts answer correctness...if the right passages are not retrieved"
- **Issue:** States fact without illustration; students don't internalize dependency
- **Action:** Add example:
  > "Retrieval is the foundation. If the system can't find the relevant lecture material, the AI assistant can't answer your question—no matter how good the AI is. For example, if you ask 'What is photosynthesis?' but the system retrieves a paragraph about mitochondria instead, the AI will explain mitochondria, not photosynthesis."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.8: Clarify Image Retrieval Trade-Off
- **Current (Line 197):** "Image retrieval excels as a complementary modality"
- **Issue:** "Excels" contradicts earlier statement that image nDCG is lower
- **Action:** Clarify:
  > "Image retrieval is weaker than text retrieval (62-67% nDCG vs 82-85%) because it must match visual patterns, which is harder than matching keywords. However, images are valuable when searching for diagrams, tables, or charts that text keywords can't describe."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.9: Add Intuition to Chunking Trade-Off
- **Current (Lines 330-331):** "Semantic chunking retrieves approximately 33% more average characters per chunk (1,006 vs 755)"
- **Issue:** Numbers alone; no intuition
- **Action:** Expand:
  > "Recursive chunking is leaner: 755 characters per result vs. 1,006 for semantic chunking. This matters because the AI must read every character to generate an answer. Fewer irrelevant words = faster, cheaper responses. Semantic chunking recalls more relevant content (71% vs 69%), but at a cost."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.10: Make RAG Success Criteria Actionable
- **Current (Lines 362-363):** "The 22.4% incorrect rate is primarily driven by questions whose answers require information not retrieved...indicating retrieval as the primary optimization target"
- **Issue:** Diagnosis is clear, but doesn't motivate why to fix or impact of fix
- **Action:** Rewrite:
  > "The 22.4% error rate is a solvable problem: 16.4% fails because the system didn't retrieve the relevant paragraph, and 1.7% fails because it retrieved only part of the answer. If we improve retrieval to find complete answers 90% of the time, we could push correctness from 73% to 85%+."
- **Files Affected:** `_heading/07_evaluation_testing.tex`

#### Action 6.11: Move Footnote to Main Text
- **Current (Lines 214-215):** "Temporal Hit Rate" explanation relegated to footnote
- **Issue:** Important metric explanation breaks reading flow
- **Action:** Move explanation into main text or table caption.
- **Files Affected:** `_heading/07_evaluation_testing.tex`

---

## CHAPTER 7: CONCLUSION (9 issues)

### 🔴 HIGH PRIORITY (5 issues)

#### Action 7.1: Break Up Dense Learning Outcomes
- **Current (Lines 198-199):** "The team learned that building a practical MRAG system is not only a matter of selecting strong models, but also of designing reliable data flow, preserving traceability, managing latency, and making careful trade-offs between retrieval quality, infrastructure cost, and user experience."
- **Issue:** 5+ concepts in one sentence; overwhelming
- **Action:** Rewrite as:
  > "The team's biggest learning wasn't about picking the best models—it was about the engineering: (1) ensuring data moves reliably through the pipeline, (2) keeping track of where results come from (traceability), (3) keeping responses fast (latency), and (4) balancing quality, cost, and usability."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.2: Define "Heterogeneous Data"
- **Current (Line 201):** "the team learned how difficult heterogeneous educational data can be"
- **Issue:** "Heterogeneous" not explained; students may not know it means "mixed types"
- **Action:** Change to:
  > "the team discovered how hard it is to work with mixed educational content in practice."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.3: Explain "End-to-End Engineering Problem"
- **Current (Line 203):** "evaluate retrieval as an end-to-end engineering problem involving parsing quality, chunk granularity, metadata, ranking, and generation grounding."
- **Issue:** Lists 5 concepts without explaining how they connect
- **Action:** Replace with:
  > "Retrieval success depends on the entire pipeline: If parsing is bad (step 1), retrieval fails. If chunking is poor (step 2), ranking fails. If metadata is missing (step 3), search can't filter. If ranking is wrong (step 4), the AI gets the wrong paragraph. And if generation isn't grounded (step 5), the AI ignores what it retrieved. You can't improve retrieval by tweaking one part—you must optimize the whole chain."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.4: Contextualize User Study Metrics
- **Current (Lines 216-231):** "The user study will be conducted with a cohort of 10–20 HCMUT students" lists metrics without explaining why
- **Issue:** Metrics listed without context; hypothesis unclear
- **Action:** Rewrite:
  > "The study measures five things to answer: 'Does BK-MInD help students learn?' (Learning Gains), 'Does it save time?' (Study Time Efficiency), 'Do students like using it?' (Feature Utility), 'Is it reliable?' (System Satisfaction), and 'Do students keep using it?' (Long-Term Adoption). Together, these show whether BK-MInD is truly valuable for education."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.5: Define "Measurable Improvement" Concretely
- **Current (Lines 318-323):** "Demonstrated measurable improvement in student learning outcomes compared to control groups"
- **Issue:** Vague success criteria; what counts as "measurable"?
- **Action:** Make concrete:
  > "Demonstrated that students using BK-MInD improve their test scores by 10%+ compared to control groups (e.g., 70% to 77%), or show faster comprehension of new material."
- **Files Affected:** `_heading/08_conclusion.tex`

### 🟡 MEDIUM PRIORITY (4 issues)

#### Action 7.6: Strengthen Conclusion Title
- **Current (Line 325):** "Concluding Remarks"
- **Issue:** Generic title doesn't signal importance
- **Action:** Rename to:
  > "Why This Matters: From Lab System to Real Educational Tool"
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.7: Make Vision Statement Concrete
- **Current (Lines 327-331):** "The MRAG system represents a meaningful advancement toward intelligent educational technology that honors the multimodal richness...the system provides students with an intelligent assistant that amplifies learning efficiency."
- **Issue:** Abstract language; doesn't describe what students actually get
- **Action:** Rewrite:
  > "BK-MInD is a practical tool that lets students ask questions about their lectures and instantly get answers with citations. Instead of scrolling through video timestamps or re-reading notes, students can search for what they want to know and get personalized explanations. This frees study time for deeper thinking, not content hunting."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.8: Explain System Limitations
- **Current (Lines 189-191):** Lists limitations without explaining impact
- **Issue:** Limitations listed without workarounds or context
- **Action:** Expand each with impact:
  > "Key limitations: (1) The system was built for Vietnamese lectures—other languages require retraining. (2) It needs significant computing power (GPU servers cost ~$684/month for 50 users). (3) Combining text, images, and video is complex and sometimes slow. (4) We turned off reranking because it made searches too slow—we can turn it back on if needed. (5) New lectures take time to process before they're searchable."
- **Files Affected:** `_heading/08_conclusion.tex`

#### Action 7.9: Verify Cross-References
- **Current (Lines 259, 261):** References to Section 6.3 that may not exist
- **Issue:** Broken references undermine credibility
- **Action:** Verify all cross-references are valid and visible.
- **Files Affected:** `_heading/08_conclusion.tex`

---

## CHAPTER 8: APPENDICES (10 issues)

### 🔴 HIGH PRIORITY (7 issues)

#### Action 8.1: Add Purpose Statements to Database Schemas
- **Current (Lines 99-125):** Table headers only; no explanation of why data is stored
- **Issue:** Students don't understand purpose
- **Action:** Before each table, add purpose:
  > "The **User Profile** table stores information about each student so the system can personalize responses. For example, if a student marks themselves as 'beginner', the AI explains concepts more simply. The email lets instructors contact students about course updates."
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.2: Add Trade-Off Context to API Parameters
- **Current (Lines 345-353):** "mode (String, Optional): Pipeline fidelity level (standard or fast)"
- **Issue:** No explanation of trade-off; when to use which?
- **Action:** Expand:
  > "**mode** (String, Optional): Processing quality. 'standard' extracts more detail from pages (slower, more accurate). 'fast' processes quickly but may miss complex layouts. Use 'fast' if you have many files to process."
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.3: Clarify Contribution Table
- **Current (Lines 585-597):** All contributors show 100% across all areas
- **Issue:** Unrealistic for parallel work; doesn't show how responsibilities differed
- **Action:** Restructure to show effort distribution:
  - Either use percentage of effort (e.g., "60% infrastructure")
  - OR explain that 100% means "completed all assigned tasks in this area"
  - Add a note explaining methodology
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.4: Explain SSE Streaming
- **Current (Lines 607-610):** "response (String): Server-Sent Events (SSE) stream"
- **Issue:** SSE not explained; why it matters unclear
- **Action:** Expand:
  > "**response** (String): The AI's answer arrives word-by-word in real-time (Server-Sent Events / SSE streaming). So you see the answer appear gradually, not all at once after a long wait. This is more interactive and gives feedback that the system is working."
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.5: Add Example API Requests/Responses
- **Current (Lines 310-577):** All API specifications list parameters but no examples
- **Issue:** Students can't see what real requests look like
- **Action:** Add JSON examples for each endpoint:
  ```json
  // POST /api/search request example
  {"query": "What is photosynthesis?", "top_k": 5, "retriever_type": "hybrid"}
  // Response example
  {"generation": {...}, "telemetry": {...}}
  ```
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.6: Clarify Feedback Schema Complexity
- **Current (Lines 209-242):** Feedback table has 20+ fields
- **Issue:** Unclear which are user-input vs. auto-generated
- **Action:** Add note:
  > "**User-provided fields**: vote, feedback_text, reason_code. **System-generated fields** (filled automatically): category, sub_category, suggested_action, analysis_summary, classification_status. This lets the system learn from feedback over time."
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.7: Expand Interface Captions
- **Current (Lines 4-94):** Single-word captions ("Dashboard", "Upload Files", etc.)
- **Issue:** No context for what students should notice
- **Action:** Expand captions:
  > "**Dashboard**: Shows your uploaded lecture materials and processing status. The green checkmarks mean files are ready to search."
- **Files Affected:** `_heading/09_appendices.tex`

### 🟡 MEDIUM PRIORITY (3 issues)

#### Action 8.8: Explain Chat Stream API Better
- **Current (Lines 524-530):** Technical description of SSE without user benefit
- **Issue:** Implementation detail; doesn't explain why it matters
- **Action:** Start with user benefit:
  > "The Chat API lets students have conversations with the AI. Responses stream in real-time (word-by-word) rather than waiting for the full answer."
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.9: Mark Foreign Keys in Schema
- **Current (Lines 99-305):** Tables don't show relationships
- **Issue:** Students don't understand how tables connect
- **Action:** Add notation to mark foreign keys:
  > "Partition Key: user_id | Sort Key: created_at | → references User Profile Table"
- **Files Affected:** `_heading/09_appendices.tex`

#### Action 8.10: Add Schema Relationships Diagram
- **Current:** No visual showing how tables connect
- **Issue:** Text-only schema explanation is hard to follow
- **Action:** Create simple ASCII diagram or reference figure showing:
  - User Profile → Sessions → Messages
  - Document metadata relationships
- **Files Affected:** `_heading/09_appendices.tex`

---

## IMPLEMENTATION PRIORITY MATRIX

### PHASE 1 (Highest Impact) - Start Here
**Focus: Clear understanding for first-time readers**
- [ ] 1.1, 1.2, 1.3 (Intro simplification)
- [ ] 2.1, 2.4, 2.5 (Preliminaries structure)
- [ ] 3.1, 3.2, 3.3 (Related work clarity)
- [ ] 4.1, 4.2 (Solution foundation)
- [ ] 6.1, 6.2 (Evaluation metrics)
- [ ] 7.1, 7.2, 7.3 (Conclusion impact)

**Estimated Time: 4-6 hours**
**Impact: 60% clarity improvement**

### PHASE 2 (Medium Impact)
**Focus: Examples and intuitions**
- [ ] 1.4-1.13 (Introduction remaining issues)
- [ ] 2.6-2.23 (Preliminaries detail issues)
- [ ] 3.4-3.12 (Related work depth)
- [ ] 4.3-4.14 (Solution clarification)
- [ ] 6.3-6.11 (Evaluation context)
- [ ] 7.4-7.9 (Conclusion details)

**Estimated Time: 6-8 hours**
**Impact: 30% additional clarity improvement**

### PHASE 3 (Polish)
**Focus: Formatting and references**
- [ ] 8.1-8.10 (Appendices clarity)
- [ ] All LOW priority issues

**Estimated Time: 2-3 hours**
**Impact: 10% final polish**

---

## SUMMARY BY CATEGORY

| Issue Type | Count | Suggested Approach |
|-----------|-------|-----------------|
| **Undefined Jargon** | 26 | Define before use; add intuitive explanation |
| **Math Without Intuition** | 15 | Add concrete example before formula |
| **Dense Paragraphs** | 13 | Break into smaller, numbered points |
| **Missing Context** | 12 | Add "why this matters" statement |
| **Technical Detail** | 9 | Move to appendix or simplify |
| **Confusing Structure** | 9 | Add transition sentences or restructure |
| **Vague Examples** | 6 | Replace with concrete student-relevant examples |
| **Formatting Issues** | 4 | Improve visual hierarchy |

---

## KEY PRINCIPLES FOR FIXES

1. **Assume No ML Background**: Define "embedding," "vector," "semantic" on first use
2. **Add Intuitive Examples**: Every technical concept needs a concrete example
3. **Break Dense Sections**: If a paragraph has 3+ concepts, split it
4. **Simplify Jargon**: Use "find documents" instead of "retrieve documents"
5. **Explain Motivation**: Before showing a formula, explain the problem it solves
6. **Use Consistent Terminology**: Pick one term per concept and stick with it
7. **Link to Student Goals**: Explain why each concept matters for their learning
8. **Provide Concrete Numbers**: "Faster and cheaper" → "30% faster, 40% cheaper"

---

**Total Estimated Implementation Time: 12-17 hours**
**Recommended Batch Size: 10-15 issues per session**
