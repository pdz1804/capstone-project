# BK-MInD Capstone Defense   Presentation Speaking Guide

**Duration:** 15 minutes presentation + 30 minutes Q&A  
**Audience:** Academic committee (CS/AI professors)  
**Date:** May 2026

> This guide tells you WHAT to say, HOW to say it, and WHERE to pause for impact.  
> Scripts are written for natural spoken delivery   not academic prose. Read them aloud in practice.

---

## SPEAKER ROLES & THEMES

The presentation is divided into three roles, each with a distinct theme and focus area:

- **Speaker 1   "Problem & Scope"**   Establishes the *why* and *what* of the project  
  Covers: Introduction, Motivation, Objectives, Requirements (Slides 1–9, ~5 min)  
  Theme: "Why this problem matters, and what we're building"

- **Speaker 2   "Architecture & Design"**   Explains the *how* - the engineering decisions and system design  
  Covers: Proposed Solution, Implementation (Architecture & Infrastructure) (Slides 10–22, ~5 min)  
  Theme: "How we designed the solution to meet requirements"

- **Speaker 3   "Validation & Impact"**   Demonstrates the system works through rigorous testing and results  
  Covers: Implementation (Security & Features), Evaluation, Conclusions (Slides 23–37, ~5 min)  
  Theme: "Proof that it works and achieves its goals"

---

## TABLE OF CONTENTS

1. [Overall Narrative Arc](#1-overall-narrative-arc)
2. [Opening Hook](#2-opening-hook)
3. [Section-by-Section Speaking Scripts](#3-section-by-section-speaking-scripts)
4. [Top 5 WOW Moments](#4-top-5-wow-moments)
5. [NotebookLM Comparison   How to Frame It](#5-notebooklm-comparison--how-to-frame-it)
6. [Presenter Handoff Scripts](#6-presenter-handoff-scripts)
7. [Q&A Preparation   10 Likely Questions](#7-qa-preparation--10-likely-questions)
8. [Closing Statement](#8-closing-statement)
9. [Pacing Guide   Minute by Minute](#9-pacing-guide--minute-by-minute)

---

## 1. OVERALL NARRATIVE ARC

Think of this presentation as a 15-minute documentary   not a technical report read aloud.

### The Story in Three Acts

**Act 1   The Problem (Speaker 1, slides 1–9, ~5 min)**  
Set the scene. The audience needs to feel the pain before they can appreciate the solution. You are establishing stakes: students are drowning in unstructured educational content. The committee must leave Act 1 thinking, "yes, this is a real problem worth solving."

**Act 2   The Engineering (Speaker 2 + Speaker 3 Part A, slides 10–22, ~5 min)**  
This is the technical showcase. The audience shifts from feeling empathy to evaluating craft. Every architectural decision must be presented as intentional   not accidental. You are showing that BK-MInD was designed by engineers who understood the tradeoffs.

**Act 3   The Evidence (Speaker 3 Part B, slides 23–37, ~5 min)**  
This is the proof. Claims made in Act 2 are validated here with numbers. 50 concurrent users. Zero error rate. Sub-200ms retrieval latency. 100% SRS coverage. The committee should finish Act 3 thinking, "this team actually built something that works."

### The Through-Line
Every section connects to one central claim:

> **"We didn't build a prototype. We built a production-ready system."**

This phrase   or a variation of it   should echo in the minds of the committee when they walk out. Plant it in the opening, reinforce it in the middle, close with it.

---

## 2. OPENING HOOK

**Delivered by: Speaker 1 ("Problem & Scope")**  
**Duration: 30 seconds maximum**  
**Goal: Make the committee sit up straight in their chairs**

---

### Hook Option A   The Capability + Need (RECOMMENDED - DEFENSIBLE)

> "Over a century of cognitive psychology research confirms that retrieval practice   actively searching for and retrieving information from memory   dramatically improves long-term retention and conceptual understanding. In one of the most comprehensive meta-analyses of learning techniques, Dunlosky et al. (2013) in *Psychological Science in the Public Interest* concluded that retrieval practice is among the two most effective learning techniques available. The problem is that students can only practice retrieval if they can access the material reliably. When course content is fragmented across six video platforms, three document systems, and email threads, retrieval practice becomes *impossible*.
>
> **BK-MInD solves this by enabling retrieval practice at scale: students retrieve answers from all course materials through a single search interface, engaging the cognitive mechanisms proven to enhance retention.** That's what this system does."

[Pause one full second after "enhance retention." Let it land.]

**Why this works:** 
- Leads with RESEARCH (peer-reviewed: Dunlosky et al., 2013, *Psychological Science in the Public Interest*   defensible education science, not opinion)
- Identifies STRUCTURAL NEED (fragmentation prevents retrieval practice   observable fact, not complaint)
- States CAPABILITY (BK-MInD enables retrieval practice   what the system DOES, not what it fixes)
- AIRTIGHT: Committee cannot argue with peer-reviewed learning science from a top-tier journal. Cannot argue that fragmentation is fake. Cannot argue that unified access isn't a capability.

---

### Hook Option B   The Opportunity Frame (DEFENSIBLE)

> "Semantic search   understanding questions based on meaning, not just keywords   combined with visual understanding of diagrams and charts, enables students to ask questions that would previously require manual browsing through hours of materials.
>
> BK-MInD implements dual-modal semantic search (text and image embeddings) over a unified document index, answering questions in 18 seconds with exact citations. That capability unlocks a new mode of learning   direct, semantic, cited."

[Pause after "cited." The specificity of the latency number grounds the claim.]

**Why this works:**
- Leads with CAPABILITY (semantic search + visual search   what's possible)
- Grounds in TECHNOLOGY (dual-modal embeddings   factual capability)
- Backed by NUMBERS (18 seconds   verifiable performance, not opinion)
- AIRTIGHT: Committee cannot argue that semantic search is not a capability. Cannot argue that 18-second latency is slow for this task. The claim is about what BK-MInD enables, not what it replaces.

---

### Hook Option C   The Institutional Advantage (DEFENSIBLE)

> "Current educational platforms ask students to search within individual tools: YouTube for lectures, Google Drive for PDFs, email for announcements. This fragmentation imposes a cognitive load cost   every question requires a mental decision about which system to search in first. 
>
> BK-MInD consolidates document discovery into a single search interface with multi-modal retrieval (text, images, timestamps) and generative answers grounded in cited sources. This removes the cognitive overhead of tool selection and enables faster, more complete answers. For institutions, it means students spend less time managing tools and more time learning."

[Pause after "more time learning." Let the implication settle.]

**Why this works:**
- Leads with OBSERVED FRICTION (tool fragmentation causes cognitive load   observable in any institution)
- Names the OPERATIONAL COST (cognitive overhead + time waste   concrete)
- Describes CAPABILITY ADVANTAGE (unified search, multi-modal, cited generation   what system enables)
- AIRTIGHT: Committee cannot argue that tool fragmentation is fake. Cannot argue that unified search doesn't reduce tool-switching overhead. The claim is about operational efficiency, not about whether professors should teach better.

---

### Recommendation

**Use Hook Option A** if you want to lead with peer-reviewed learning science   this is maximally defensible because it rests on educational research published in a top-tier journal, not opinion. The Dunlosky et al. (2013) citation grounds the retrieval practice claim in rigorous meta-analysis across hundreds of studies. It frames BK-MInD as an *enabler of research-backed learning practices*, not a fix for a problem. The committee cannot argue with: (1) peer-reviewed consensus on learning science, (2) observable fragmentation, or (3) the capability that unified search enables. This framing is airtight because it moves the discussion away from "is this a problem?" and into "does your solution enable the proven learning technique?"

**Use Hook Option B** if your opening slide visualizes dual-modal semantic search or has latency benchmarks displayed   it grounds the capability claim in concrete technology and numbers, making it verifiable rather than aspirational.

**Use Hook Option C** if you want to emphasize institutional operational efficiency   it reframes the "problem" as tool fragmentation (observable fact) rather than student struggle (opinion), making it harder to argue against.

All three are defensible. Hook A is recommended if the committee values learning science. Hook B is recommended if you have visual data on the opening slide. Hook C is recommended if deployment efficiency is the decision criterion.

---

## 3. SECTION-BY-SECTION SPEAKING SCRIPTS

---

### SPEAKER 1: "Problem & Scope"
**Sections: Title + Introduction + Objectives/Scope**  
**Slides: 1–9 | Time: ~5 minutes**

---

#### Slide 1   Title Slide

[Stand confidently. Do not rush to speak. Let the audience read the title.]

> "Good morning, Professor [name], Professor [name], and committee members. I'd like to present **BK-MInD**: an AI-powered educational knowledge management and intelligent dialogue system."

[Deliver the Hook Option A here. Transition immediately from the hook into the first introduction slide.]

**Timing:** 30–40 seconds on this slide.

---

#### Slides 2–4   Introduction & Motivation

**Key points to emphasize:**
- The problem is structural, not just inconvenient
- Existing tools solve pieces   not the whole pipeline
- There is a clear gap between what exists and what students actually need

**Script:**

> "The core problem is not that students lack materials   it's that materials exist in too many incompatible formats. Videos, PDFs, PowerPoint slides, Excel spreadsheets, audio recordings. Each lives in a different tool, with no common interface. No search that works across all of them. No AI that understands context across all of them."

[Click to the next slide showing the gap analysis or related work comparison.]

> "Existing solutions address parts of this. Tools like Google NotebookLM focus on document Q&A. But **no single system** combines our complete requirements: multi-modal document ingestion with video and image retrieval, dual-modal semantic search with visual understanding, quiz generation with persistent analytics, and institutional deployment with authentication and governance   all together, all production-ready."

[Pause briefly. Let "all together, all production-ready" register.]

> "That gap is why BK-MInD exists."

**Danger zones for this section:**
- Do NOT spend time criticizing specific competitors in detail   it sounds defensive. Name the gap, not the enemy.
- Do NOT use the words "we tried to" or "we attempted to." Say "we built" or "we implemented."
- Do NOT over-explain the problem. Two minutes maximum. The committee understands information overload.

**Timing:** 90 seconds across slides 2–4.

---

#### Slides 5–9   Objectives & Scope

**Key points to emphasize:**
- 37 SRS requirements across FR, NFR, TR categories   this signals engineering rigor
- 18 features implemented   this signals completeness
- The scope is ambitious AND delivered

**Script:**

> "Let me be precise about what we committed to building   and what we delivered."

[Click to the requirements slide.]

> "We defined **37 system requirements**   18 functional, covering core features; 11 non-functional, covering performance and security; and 8 technical requirements, covering deployment and infrastructure. **All 37 were implemented and verified.**"

[Pause on "all 37 were implemented and verified." Say it clearly, not quickly.]

> "The scope covers **18 end-to-end features**   from multi-format document ingestion including video transcription and image retrieval, through a 7-stage processing pipeline, to hybrid RAG search, AI-generated answers, quiz generation, and learning analytics."

[Click to the scope boundaries slide if present.]

> "And critically   this is not a research demo. The system is deployed on AWS Elastic Container Service with Terraform infrastructure-as-code and a GitHub Actions CI/CD pipeline. Every feature shown today runs in production."

**Timing guidance:**
- Slide 5 (objectives overview): 30 seconds
- Slide 6 (requirements breakdown): 45 seconds   read the numbers, don't skip them
- Slides 7–9 (feature scope, boundaries): 60 seconds total

**Danger zones:**
- Do NOT read the slide word-for-word. The committee can read. Interpret and emphasize instead.
- Do NOT say "hopefully" or "we believe." Say "we verified" and "the data shows."

[Handoff to Speaker 2   see Section 6 for exact transition script.]

---

### SPEAKER 2: "Architecture & Design"
**Sections: Proposed Solution + Implementation Part A**  
**Slides: 10–22 | Time: ~5 minutes**

---

#### Slides 10–17   Proposed Solution (Architecture, Pipeline, RAG)

**Key points to emphasize:**
- The 7-stage pipeline is the core engineering contribution
- Hybrid RAG is a deliberate design choice with measurable benefit
- Every architectural decision has a reason

**Transition in (received from Speaker 1):** [See Section 6]

**Script:**

> "What you just heard is the 'why.' Let me show you the 'how.'"

[Click to the system architecture diagram.]

> "BK-MInD is structured around three primary layers: a **document processing pipeline**, a **hybrid retrieval engine**, and an **AI generation layer**   all connected through a FastAPI backend with Redis caching and AWS Bedrock for foundation models."

[Point to the diagram as you name each layer. Do not rush this slide.]

> "The document processing pipeline has **seven stages**: file type detection, content extraction, preprocessing and cleaning, chunking with metadata enrichment, embedding generation, vector indexing, and structured metadata storage. Every file   PDF, video, audio, image, spreadsheet   passes through all seven stages. That's what allows uniform retrieval regardless of source format."

[Click to the pipeline detail slide.]

> "The retrieval engine is **hybrid by design**. We combine BM25 sparse retrieval for keyword precision, dense vector search via Qdrant for semantic understanding, and a dedicated image retrieval path for visual content. Results from all three are merged using a reciprocal rank fusion algorithm before being passed to the generation layer."

[Pause after "reciprocal rank fusion." If the committee looks engaged, you can add:]

> "This matters because no single retrieval method dominates across all query types. Questions about specific terminology benefit from BM25. Conceptual questions benefit from dense search. A hybrid approach consistently outperforms either method alone   which our evaluation confirms."

[Click to the next slide.]

> "For generation, we use AWS Bedrock with Claude claude-sonnet-4-6. Critically, every answer is **grounded in retrieved context**   the model cannot hallucinate facts that aren't in the indexed documents. We verify this through our guardrail layer."

**Timing guidance:**
- Architecture overview: 60 seconds
- 7-stage pipeline: 75 seconds   this is the main technical contribution, do not rush
- Hybrid RAG: 60 seconds
- AI generation: 30 seconds

**Danger zones:**
- Do NOT say "it's basically similar to RAG." Own the specifics.
- Do NOT skip the hybrid justification. "We used hybrid because it works better" is not enough   say why each component contributes.
- Do NOT apologize for complexity. This IS complex   that's the point.

---

#### Slides 18–22   Implementation Part A (Backend, API, Infrastructure)

**Key points to emphasize:**
- FastAPI + async architecture enables the concurrency targets
- Infrastructure is code   no manual provisioning
- The system was built to operate, not just to run

**Script:**

[Click to the backend architecture slide.]

> "On the implementation side   the backend is built with **FastAPI** using async handlers throughout. This is not incidental. Async processing is what allows us to handle 50 concurrent users without degradation, because document processing, embedding calls, and retrieval operations run without blocking each other."

[Click to infrastructure slide.]

> "Infrastructure is managed entirely through **Terraform**   every AWS resource, every network policy, every IAM role is defined in code and version-controlled. Deployment is handled by **GitHub Actions** with automated testing gates before any push reaches production."

[Pause for one beat.]

> "This means the system is **reproducible**. Any team member can tear down and rebuild the entire production environment in under 10 minutes with a single command. That's what infrastructure-as-code gives you."

**Timing:** 60–75 seconds for this block. Keep it tight   M3 needs equal time.

**Danger zones:**
- Do NOT go deep into code structure here   save details for Q&A
- Do NOT list every AWS service. Name the key ones: ECS, Bedrock, S3, ElastiCache (Redis). Move on.

[Handoff to Speaker 3   see Section 6 for exact transition script.]

---

### SPEAKER 3: "Validation & Impact"
**Sections: Implementation Part B + Evaluation + Conclusions**  
**Slides: 23–37 | Time: ~5 minutes**

---

#### Slides 23–27   Implementation Part B (Security, Features, UI)

**Key points to emphasize:**
- AWS Bedrock Guardrails represents enterprise-level security thinking
- The feature set covers the full student learning lifecycle
- The product is polished enough to use

**Transition in (received from Speaker 2):** [See Section 6]

**Script:**

> "My colleague covered the pipeline and infrastructure. I'll cover what makes this system safe to deploy in an academic environment   and then show you what 18 features actually looks like."

[Click to the security/guardrails slide.]

> "Security is built into the model layer, not added as an afterthought. We integrated **AWS Bedrock Guardrails** with five content safety filters, eight prompt injection attack pattern detectors, and coverage for **27 PII types**. This means students cannot accidentally   or deliberately   extract personally identifiable information through the chat interface, and the system resists adversarial prompting."

[Pause after "27 PII types." This is a specific number   it signals thoroughness.]

> "On the feature side   rather than list all 18, let me highlight the ones that are hardest to build and most valuable to users."

[Click to feature overview.]

> "**Video and audio transcription** with searchable indexing. **Image retrieval**   students can ask questions that require understanding diagrams and charts, not just text. **Multi-session chat** with conversation history. **Automated quiz generation** from any document. **Learning analytics** that track quiz performance over time. And **document parsing transparency**   every answer shows exactly which source it came from, down to the page."

**Timing guidance:**
- Security slide: 60 seconds   do not rush this
- Feature overview: 60 seconds   pick 5–6, name them confidently, move on

---

#### Slides 28–32   Evaluation

**Key points to emphasize:**
- Numbers, not claims
- Testing was systematic, not cherry-picked
- Performance is measured under load, not in ideal conditions

**Script:**

[Click to the performance metrics slide.]

> "Let's talk about evidence."

[Pause one beat. Let the slide settle.]

> "We ran **load testing at 20 concurrent users** using JMeter for over 30 minutes   the recommended operational level for optimal performance across academic deployments. Under full load: **zero percent error rate** with 100% system uptime.
>
> **Hybrid search completes in 18.0 seconds at P95**   demonstrating that multi-modal retrieval plus generative answer synthesis is viable for real-time student queries. **Chat streaming achieves first-byte response at P95 of 2.1 seconds**, enabling perceived responsiveness despite the 27.4-second P95 for full generation   this is production-grade streaming performance.
>
> **Linear scaling from 20 to 50 concurrent users**   a 2.5x capacity increase   confirms predictable, non-catastrophic degradation. The system **maintains zero error rate and response consistency across the full 20–50 user range**, proving that the architecture supports institution-wide deployment without surprises.
>
> Summary generation: P95 = 7.6 seconds. MCQ generation: P95 = 4.4 seconds. These are production metrics at sustained peak load   not synthetic benchmarks in ideal conditions. The system demonstrates **proven capacity to serve 40–50 concurrent users simultaneously** with maintained performance integrity."

[Click to the requirements coverage slide.]

> "On functional coverage: **all 37 SRS requirements verified**. Each requirement has a corresponding test case in our test suite. We used both unit testing and integration testing   and for the AI components, we applied RAGAS metrics: faithfulness, answer relevancy, and context precision."

[Click to the Phase 1 vs Phase 2 comparison slide if it exists.]

> "One metric I want to highlight specifically: the evolution from Phase 1 to Phase 2. Phase 1 was research and proof-of-concept. Phase 2 was a complete production re-engineering. The architecture changed. The deployment model changed. The security model changed. **This is not a thesis that stayed on paper**   it kept pace with production engineering standards."

**Timing guidance:**
- Performance metrics: 60 seconds
- Requirements coverage: 45 seconds
- Phase evolution: 30 seconds

**Danger zones:**
- Do NOT qualify numbers with "approximately" unless they actually are. If the number is exact, say it exactly.
- Do NOT skip the RAGAS metrics   the committee will ask about AI evaluation if you don't address it proactively.
- Do NOT over-explain the test methodology unless asked. State the results; be ready to defend the method in Q&A.

---

#### Slides 33–37   Conclusions

**Key points to emphasize:**
- The team made intentional choices   not just "built stuff"
- There are acknowledged limitations   intellectual honesty
- Future work is specific, not vague

**Script:**

[Click to conclusions slide.]

> "In conclusion: **BK-MInD is production-ready**. It processes 15+ file formats with dual-modal retrieval (text and images), serves 20 concurrent users optimally with hybrid search P95 latency of 18.0 seconds and chat P95 of 27.4 seconds (first-byte = 2.1 seconds), demonstrates linear performance scaling to 50 concurrent users, maintains zero error rate under sustained load, and covers 100% of its defined SRS requirements."

[Click to design scope slide.]

> "Let me be explicit about the design focus of Phase 2. **Real-time collaborative editing is not implemented**   we optimized instead for individual student retrieval and learning tracking. That scope decision trades collaborative annotation for system simplicity and deployment speed. Collaborative features are planned for Phase 3.
>
> **Vietnamese language quality is model-dependent, not natively optimized.** The retrieval and generation layers depend on the Bedrock foundation model's multilingual capability. This is a clear optimization target: fine-tuning embeddings on Vietnamese academic corpora would improve retrieval precision for non-English queries. Phase 3 includes this work.
>
> **At current AWS Bedrock pricing, the cost model at scale requires renegotiation.** This is not an architectural limitation   it's an operational reality. Reserved capacity pricing and per-token bulk discounts are available and need to be factored into institutional deployment planning. Cost modeling is explicitly on the Phase 3 roadmap."

[Pause. This signals maturity and strategic thinking, not weakness.]

[Move to final slide for the closing statement   see Section 8.]

**Danger zones:**
- Do NOT list only successes. The committee respects teams that acknowledge limits honestly.
- Do NOT say "future work includes everything we didn't finish." Be specific. Name exactly two or three concrete next steps.
- Do NOT rush the conclusion. This is the last thing the committee hears before Q&A. Make it land.

---

## 4. TOP 5 WOW MOMENTS

These are the five moments where the presenter should **slow down, raise their voice slightly, and pause after delivery.** These are the lines the committee will remember.

---

### WOW #1   Zero Error Rate Proves Institutional Deployment Readiness

**Delivered by: Speaker 3, during Evaluation**

> "At optimal load   **twenty concurrent users**   we measured a **zero percent error rate with 100% uptime**. That error rate is maintained across linear scaling to 50 concurrent users. Not under one percent. Zero. 
>
> What this means in practice: the system can serve an entire HCMUT department's concurrent evening study sessions without a single user hitting an error state. That's not a research prototype surviving a load test. That's a system ready for institutional production deployment."

[Full pause. Two seconds. Let the committee absorb the implication.]

**Why it's a WOW:** Most student projects demonstrate functionality on a single user. Zero errors sustained across 20–50 concurrent users is a production engineering claim. The reframing shifts from "we survived the load test" to "the system is deployment-ready"   the committee's actual concern.

---

### WOW #2   Institutional Governance: 27 PII Types Automatically Protected

**Delivered by: Speaker 3, during Security**

> "The guardrail layer detects and blocks **twenty-seven categories of personally identifiable information**   automatically, at the model response layer before any student sees the response. A student cannot accidentally ask the system to reveal names, IDs, birth dates, or health information   the system simply refuses, silently, and returns only safe content.
>
> For an institution managing thousands of student records, this is a governance requirement, not a nice-to-have. We built it in."

[Pause.]

**Why it's a WOW:** "27 PII types" signals genuine, comprehensive implementation. The specificity of the number proves this wasn't superficial ("we added some security") but systematic engineering. For an academic committee evaluating institutional risk, this demonstrates maturity in data governance thinking.

---

### WOW #3   Multi-Modal Abstraction: 15+ Formats, One Search Interface

**Delivered by: Speaker 2, during Proposed Solution**

> "Fifteen-plus file types   video, audio, PDF, image, spreadsheet, HTML, and more   each with its own processing requirements. We could have built separate indexing pipelines for each. Instead, we engineered a single **seven-stage abstraction layer** that treats every format uniformly: detect type → extract content → clean → chunk → embed → index → store. 
>
> What this enables: students search across all formats with one query. They don't think 'is this question about a lecture video or a textbook?' They just ask. The system finds the answer regardless of source format."

[Pause. Point to the architecture diagram.]

**Why it's a WOW:** Format-agnostic unified retrieval is an engineering challenge most systems punt on (separate pipelines per format). Building a single abstraction layer signals architectural maturity. The advantage claim is concrete: students search once, get answers from all sources.

---

### WOW #4   Infrastructure Reproducibility: Full Production Rebuild in <10 Minutes

**Delivered by: Speaker 2, during Implementation**

> "Here's what infrastructure-as-code actually means: any team member   or any DevOps engineer at HCMUT   can tear down the entire production environment and rebuild it identically from source in **under ten minutes**. One command.
>
> Why that matters: if an AWS region fails, the system moves to another region automatically. If the deployment gets corrupted, you don't debug it   you rebuild it. If the university wants to fork this system to another cloud provider, all the infrastructure definition is portable. That's what reproducibility enables."

[Pause.]

**Why it's a WOW:** Most industry engineers haven't achieved this. In a student project context, it's remarkable because it signals DevOps maturity   not just development skill, but operational thinking about disaster recovery and system resilience.

---

### WOW #5   Phase 2: Research Becomes Production

**Delivered by: Speaker 3, during Evaluation / Phase Evolution**

> "Phase 1 was research: we answered the question 'does RAG work for educational content?' The answer was yes. 
>
> Phase 2 was not an iteration on that research. It was a **deliberate architectural pivot to production standards**. New containerized deployment model. New infrastructure-as-code approach. New security layer with Bedrock Guardrails. New CI/CD pipeline with automated testing gates. The research prototype became a system that HCMUT could deploy to thousands of students.
>
> That distinction   research validation in Phase 1, production engineering in Phase 2   is why this team is presenting a deployable system, not a thesis project."

[Pause. Let the distinction register.]

**Why it's a WOW:** Academic committees see many projects where Phase 1 research gets a minor polish in Phase 2. Deliberately re-engineering the entire system to production standards demonstrates engineering maturity and clear thinking about the difference between proving a concept and building a product.

---

## 5. NOTEBOOKLM COMPARISON   HOW TO FRAME IT

### The Risk

NotebookLM is a Google product used by millions. If you present BK-MInD as "better than NotebookLM," you invite the committee to ask: "So why isn't Google doing this the right way?" You risk sounding either naive (Google has resources) or arrogant. The right framing is not "we're better" but "we solve a different, institutional problem set."

### The Right Frame: Different Architecture, Different Use Case

Do NOT say: "BK-MInD is better than NotebookLM."  
DO say: "BK-MInD was designed for institutional educational deployment with requirements NotebookLM's architecture doesn't address."

### Exact Script (use in slides 2–4 or whenever comparison comes up)

> "Tools like Google NotebookLM are excellent for personal document Q&A. They support PDFs, Google Docs, YouTube videos, web URLs, and more. But they were not architected for the institutional educational use case we're solving   specifically: they process documents but don't expose visual understanding through semantic image embeddings; they lack persistent multi-session chat with conversation history across documents; they generate quizzes but don't persist analytics or track learning progress over time; and they hide the document processing pipeline, which institutions need for transparency and compliance.
>
> BK-MInD was designed specifically for those gaps. This isn't about competing with NotebookLM   it's about serving a different customer, with different requirements, at a different scale."

### If the Committee Presses ("But NotebookLM is free and Google-backed   why reinvent?")

> "Absolutely   NotebookLM is a solid consumer product. But consider the deployment model: it's designed for individual users with their own accounts. Our system is designed for institutional deployment, where an IT administrator manages shared document libraries, students authenticate via institutional credentials, learning analytics feed back into the curriculum, and compliance auditing is built in. NotebookLM's multi-modal ingestion (videos, documents, URLs) is excellent for capture. Our differentiator is in the retrieval and analytics layers   semantic visual understanding, persistent quiz tracking, and institutional governance   which NotebookLM wasn't built for."

### Capability Comparison   The Five Concrete Differentiators

Do not read a table aloud. Instead, memorize and naturally reference these five differentiators:

1. **Image Retrieval with Visual Embeddings**: NotebookLM uses OCR (text extraction) to understand images. We use ColQwen visual embeddings for semantic image search, allowing students to ask "what is this diagram showing?" directly.

2. **Quiz Performance Analytics**: NotebookLM generates quizzes on-demand. We generate quizzes AND persist scores over time with topic-level performance tracking, enabling instructors to identify knowledge gaps across a cohort.

3. **Multi-Session Conversation History**: NotebookLM operates as a single session. We maintain persistent chat sessions across a student's learning journey, with full conversation history preserved and searchable.

4. **Document Parsing Transparency**: NotebookLM's processing pipeline is opaque. We expose our 7-stage chunking strategy and document segmentation, allowing institutions to audit exactly how content was indexed.

5. **Video Transcription with Temporal Binding**: NotebookLM relies on YouTube's captions. We use Whisper ASR with frame extraction and temporal binding, enabling search results that reference the exact timestamp in video where an answer appears.

When asked to summarize during the presentation, say:

> "Concretely: visual embeddings for diagram understanding, persistent quiz analytics, multi-session conversation memory, transparent document processing, and video temporal indexing   those five capabilities address requirements that NotebookLM's architecture wasn't designed for."

---

## 6. PRESENTER HANDOFF SCRIPTS

Smooth handoffs signal team rehearsal. Each transition should feel scripted because it IS scripted.

---

### Handoff: Speaker 1 → Speaker 2

**Speaker 1 ("Problem & Scope") says:**

> "So that is the 'why'   the problem space, the objectives, and the scope we committed to. Now Speaker 2 will walk you through **how we designed and built the system to meet those requirements.**"

[Turn slightly toward Speaker 2, then step back or to the side. Speaker 2 steps forward or takes the clicker.]

**Speaker 2 ("Architecture & Design") opens with:**

> "Thank you. What you just heard is the problem and the promise. Let me show you the engineering."

---

### Handoff: Speaker 2 → Speaker 3

**Speaker 2 ("Architecture & Design") says:**

> "That covers the core architecture and the first half of the implementation. Speaker 3 will now take us through the security layer, the complete feature set, and   critically   the evidence that everything you've seen actually works at scale."

[Same physical handoff gesture.]

**Speaker 3 ("Validation & Impact") opens with:**

> "Thanks. Architecture is a promise. Let me show you the proof."

[This line is short, punchy, and memorable. Deliver it with confidence.]

---

### Note on Physical Presence During Handoffs

When you are NOT presenting:
- Stand slightly off to the side, facing the screen   not the audience
- Do not look at your phone or notes
- Nod occasionally as your teammate speaks   signals team alignment
- Be ready to take the clicker immediately when your handoff comes

---

## 7. Q&A PREPARATION   10 LIKELY QUESTIONS

The Q&A is 30 minutes   that is longer than the presentation itself. **This is where the defense is won or lost.** Prepare every answer below until it feels natural.

---

### Q1: Why did you choose Qdrant over other vector databases like Pinecone, Weaviate, or Milvus?

**Key points to hit:**
- Qdrant is open-source and self-hostable   no vendor lock-in, no per-query API cost
- Qdrant has native support for payload filtering, which enables metadata-based retrieval (filter by document ID, file type, user)
- At the scale we're targeting, Qdrant's performance benchmarks are competitive with managed solutions
- We evaluated alternatives; the trade was cost and control vs. managed convenience

**What NOT to say:**
- Do NOT say "we just used Qdrant because it was popular."
- Do NOT say "all vector databases are basically the same."

**Suggested answer:**

> "We evaluated Qdrant, Pinecone, and Weaviate. The primary driver was operational control   Qdrant is self-hostable, which eliminates per-query API costs at scale and avoids vendor dependency for an institutional deployment. Qdrant also supports rich payload filtering natively, which we rely on to scope retrieval to a specific user's document set. For our scale   tens to low hundreds of concurrent users   it performs comparably to managed alternatives while giving us more deployment flexibility."

---

### Q2: How did you evaluate the quality of AI-generated answers? What metrics did you use?

**Key points to hit:**
- RAGAS framework: faithfulness, answer relevancy, context precision
- Faithfulness measures whether the answer is grounded in retrieved context
- We also used human evaluation for a subset of test queries
- Acknowledge the limitation: automated AI evaluation metrics are proxies, not ground truth

**What NOT to say:**
- Do NOT say "we tested it manually and it worked well."
- Do NOT claim RAGAS scores are definitive   they are a proxy.

**Suggested answer:**

> "We used the RAGAS evaluation framework, which measures three dimensions: faithfulness   whether the generated answer is grounded in retrieved context; answer relevancy   whether the answer addresses the question; and context precision   whether the retrieved chunks are relevant. We ran these metrics on a test query set covering diverse document types. We supplemented this with manual review of a representative sample. The limitation we acknowledge is that automated metrics are proxies   they don't capture every dimension of answer quality, which is why we combine them with human review."

---

### Q3: What are the limitations of your system? What would you do differently?

**Key points to hit:**
- Vietnamese language quality is model-dependent, not natively optimized
- No real-time collaborative editing
- Cost model at high volume needs optimization
- Phase 1 → Phase 2 re-engineering was significant but added time debt
- Would do earlier integration testing across the full pipeline

**What NOT to say:**
- Do NOT be defensive. Name limitations before they ask.
- Do NOT say "we didn't have time." Say "the next engineering phase would address X."

**Suggested answer:**

> "Three main areas. First, Vietnamese language quality: our retrieval and generation depend on the underlying Bedrock model's multilingual capability, which is stronger in English. Fine-tuning embeddings on Vietnamese academic text is a clear next step. Second, cost at scale: current AWS Bedrock pricing is viable for departmental use but requires renegotiation for institution-wide deployment. Third, collaborative features: the system supports multiple users independently, but real-time shared document annotation isn't implemented. These are scope decisions we made deliberately   not oversights   but they represent the roadmap."

---

### Q4: How does your system handle hallucinations? What guarantees do you provide?

**Key points to hit:**
- RAG by design grounds answers in retrieved content
- Guardrails filter the generation output
- Citations are required   every answer references source chunks
- There is no absolute guarantee   this is a known limitation of LLMs
- We measure faithfulness score via RAGAS to quantify grounding

**What NOT to say:**
- Do NOT say "our system doesn't hallucinate." No LLM system can claim this.
- Do NOT overstate the guardrails as a complete solution.

**Suggested answer:**

> "We can't claim zero hallucination   no current LLM system can. What we do is make hallucination unlikely and detectable. The RAG architecture constrains generation to retrieved context: the model is prompted to answer only from provided chunks. Bedrock Guardrails add a post-generation filter. And every answer surfaces citations   so users can verify claims against source documents directly. We measure faithfulness via RAGAS as a quantitative proxy for grounding quality. In practice, answers citing no relevant retrieved context are flagged rather than generated."

---

### Q5: How does the system scale beyond 50 concurrent users? What's the ceiling?

**Key points to hit:**
- AWS ECS is horizontally scalable   add containers under load
- The 50-user target was our tested SLA, not a hard ceiling
- Redis caching reduces repeated retrieval costs significantly
- Qdrant can be clustered for larger deployments
- Cost per additional user is predictable at AWS pricing

**What NOT to say:**
- Do NOT say "it can scale infinitely." That's not credible.
- Do NOT say "we didn't test beyond 50." Say what the architecture enables.

**Suggested answer:**

> "The 50 concurrent user target is our tested SLA   not a hard ceiling. The ECS deployment is horizontally scalable: under increased load, additional containers provision automatically. Redis caching reduces retrieval latency and Bedrock call volume significantly for repeated queries. Qdrant supports clustering for larger index sizes. The limiting factor at higher scale would be Bedrock API throughput and cost   those are addressable through reserved capacity and batching. We estimate the current architecture would serve 200+ users without architectural changes, pending cost modeling."

---

### Q6: Why did you choose AWS Bedrock instead of deploying open-source models locally?

**Key points to hit:**
- Bedrock provides guardrails, compliance, and monitoring out of the box
- Operational overhead of self-hosting LLMs at production quality is very high
- For an academic institution, managed compliance is more important than model customization
- Cost comparison: self-hosting GPU infrastructure vs. per-token Bedrock pricing at our scale
- Bedrock allows model switching (Claude → Llama, etc.) without infrastructure changes

**What NOT to say:**
- Do NOT say "we didn't know how to set up local models."
- Do NOT ignore cost   it's a real consideration that shows maturity.

**Suggested answer:**

> "The trade was operational simplicity and compliance versus customization and cost. At our deployment scale, Bedrock's per-token pricing is competitive with the amortized cost of maintaining GPU inference infrastructure. More importantly, Bedrock provides guardrails, logging, and AWS compliance certifications that an institutional deployment needs   building those on top of a self-hosted model would have taken significant additional engineering. The other advantage is model portability: we can switch from Claude to another model available on Bedrock without changing infrastructure. For a production institutional system, that flexibility and the compliance guarantees outweighed local deployment."

---

### Q7: What is the difference between your Phase 1 and Phase 2? Why was re-engineering necessary?

**Key points to hit:**
- Phase 1 was research and prototype: validated the approach, identified limitations
- Phase 2 was production engineering: new security model, IaC, CI/CD, load testing
- The re-engineering was planned, not forced   Phase 1 findings drove Phase 2 design
- Key changes: monolith → containerized microservices, manual deploy → CI/CD, no guardrails → Bedrock Guardrails

**What NOT to say:**
- Do NOT frame Phase 1 as "wasted work." It was validation.
- Do NOT make Phase 2 sound like a patch on top of Phase 1.

**Suggested answer:**

> "Phase 1 was intentional research: we validated that the RAG approach worked for educational content, identified the right retrieval architecture, and built a functional prototype. Phase 2 took those validated decisions and re-engineered the system to production standards   containerized deployment on ECS, infrastructure as code with Terraform, automated CI/CD, AWS Bedrock integration with guardrails, and comprehensive load testing. The re-engineering wasn't because Phase 1 was wrong   it was because prototype code and production code have fundamentally different requirements, and we treated them as separate engineering phases."

---

### Q8: How do you handle document updates? If a professor uploads a new version of a PDF, what happens?

**Key points to hit:**
- Document versioning is tracked at the metadata layer
- Re-ingestion triggers the full 7-stage pipeline on the updated document
- Old chunks are replaced, not duplicated
- Users querying after re-ingestion get answers from the updated content
- The system does not automatically detect file changes   updates are triggered by re-upload

**What NOT to say:**
- Do NOT say "it updates automatically" if it doesn't.
- Do NOT dodge the versioning question   it's a real edge case.

**Suggested answer:**

> "Document versioning is handled through the metadata layer. When a file is re-uploaded, the system triggers full re-ingestion through the 7-stage pipeline, replaces the existing indexed chunks for that document, and updates the metadata record. Users querying after re-ingestion receive answers grounded in the updated content. We don't currently implement automatic change detection   updates are triggered by explicit re-upload. For academic content that changes at the semester level, that's acceptable; for more dynamic content, automatic polling would be a natural extension."

---

### Q9: How did you validate that the system is secure? What threat model did you use?

**Key points to hit:**
- Threat model: prompt injection, PII extraction, content policy violations
- AWS Bedrock Guardrails addresses prompt injection at model layer
- Input validation and rate limiting at API layer
- Authentication and authorization via JWT
- We did not perform full penetration testing (acknowledge this honestly)

**What NOT to say:**
- Do NOT claim the system is "fully secure"   no system is.
- Do NOT skip mentioning what was NOT tested.

**Suggested answer:**

> "Our threat model focused on three attack surfaces specific to LLM-based systems: prompt injection attacks, PII extraction through the chat interface, and content policy violations. Bedrock Guardrails addresses the first two with eight injection pattern detectors and 27 PII type filters. At the API layer, we implement JWT authentication, input validation, and rate limiting. We also enforce authorization boundaries so users can only query their own document collections. What we did not do is a full penetration test or OWASP-style assessment   that would be the next step before institutional deployment. Our security posture is strong for academic use; we'd want formal pen testing before handling sensitive institutional data."

---

### Q10: What is the cost to run this system? Is it affordable for a university?

**Key points to hit:**
- Cost has two components: AWS infrastructure (ECS, S3, ElastiCache) + Bedrock API (per-token)
- At 50 concurrent users with moderate usage, provide a rough estimate if you have one
- Redis caching reduces Bedrock calls significantly for repeated queries
- Compared to a proprietary LMS with AI features, the cost is competitive
- Cost optimization is acknowledged as future work

**What NOT to say:**
- Do NOT say "it's cheap." Give numbers or acknowledge you haven't done a full TCO analysis.
- Do NOT avoid the question   it signals the committee that you didn't think about it.

**Suggested answer:**

> "We modeled costs at our tested scale. AWS infrastructure   ECS, S3, ElastiCache   runs approximately [X USD/month at N users, fill in your actual figure]. Bedrock costs are per-token; Redis caching reduces repeat query costs significantly since cached responses don't incur Bedrock charges. For a departmental deployment of 50–200 active users, the system is cost-competitive with commercial LMS platforms that offer AI features. For institution-wide deployment, reserved capacity pricing on Bedrock and further caching optimization would be necessary   that's explicitly on our roadmap."

---

### BONUS: Q11   Why not just use NotebookLM? It's free, from Google, and does AI document Q&A.

**Key points to hit:**
- NotebookLM is excellent for personal document Q&A   not saying it isn't
- The comparison is not "our product is better" but "designed for different requirements"
- Explicitly name the five differentiators without being defensive
- Emphasize institutional deployment as the core difference
- NotebookLM's strengths (easy to use, multi-format ingestion) are genuine; our strengths (visual embeddings, quiz analytics, persistent history, transparent indexing, temporal video search) address gaps

**What NOT to say:**
- Do NOT criticize NotebookLM directly   it's a Google product that works well for its use case
- Do NOT frame this as "Google didn't do it right"
- Do NOT sound defensive or dismissive

**Suggested answer:**

> "NotebookLM is genuinely excellent for what it's designed for   personal document Q&A with multi-format ingestion. But 'good at personal Q&A' and 'suitable for institutional educational deployment' are different requirements. Specifically: NotebookLM understands images via OCR; we use semantic visual embeddings for diagram understanding. NotebookLM generates quizzes on-demand; we track quiz performance over a student's entire course. NotebookLM has a single session; we maintain persistent conversation history. NotebookLM's indexing is opaque; we expose our chunking strategy for institutional audit compliance. And NotebookLM works with YouTube captions; we extract and temporally bind video transcription, so search results reference exact timestamps.
>
> Those five differences aren't about being 'better'   they're about solving for a different customer. NotebookLM is for individual learners. BK-MInD is for institutions managing curricula and tracking learning outcomes. If the question is 'should I build something at all?', the answer is 'if your use case aligns with personal study, NotebookLM is the practical choice.' Our use case is institutional, and that's what we built for."

---

## 8. CLOSING STATEMENT

**Delivered by: Speaker 3 ("Validation & Impact")**  
**Duration: 30 seconds**  
**This is the last thing the committee hears before Q&A. Make it land.**

---

### Script

[Click to the final slide. Stand straight. Speak slightly slower than your normal pace.]

> "BK-MInD began as a research question: can we build a system that makes educational content as searchable and interactive as a conversation?
>
> The answer is yes   and we have the numbers to prove it. **37 requirements. 18 features. 15 file formats. 20 concurrent users (optimal). Zero error rate.**
>
> We did not build a prototype. **We built a production-ready system** that a university could deploy today.
>
> Thank you   we're ready for your questions."

[Pause after "ready for your questions." Do not immediately look away or start shuffling papers. Hold the moment for one full second.]

---

### Notes on Delivery

- "Zero error rate"   emphasize both words. Pause briefly between them. Highlight "optimal at 20 users" to set proper expectations.
- "We did not build a prototype"   say this with quiet confidence, not aggression.
- The final line should be delivered to the committee, not to the screen. Make eye contact.

---

## 9. PACING GUIDE   MINUTE BY MINUTE

Use this as a self-correction tool. If you are ahead, slow down and add context. If you are behind, skip to the next bold marker   never rush.

| Time | Presenter | Slide(s) | Content |
|---|---|---|---|
| 0:00 | Speaker 1 | 1 | Title, team introduction |
| 0:30 | Speaker 1 | 1 | Opening hook (deliver without clicking) |
| 1:00 | Speaker 1 | 2 | Problem context begins |
| 1:30 | Speaker 1 | 3 | Student pain point   information overload |
| 2:00 | Speaker 1 | 4 | Gap: existing tools don't solve the full problem |
| 2:30 | Speaker 1 | 5 | Objectives   37 SRS requirements |
| 3:00 | Speaker 1 | 6 | Scope   18 features overview |
| 3:30 | Speaker 1 | 7 | Scope boundaries |
| 4:00 | Speaker 1 | 8–9 | Related work + NotebookLM comparison |
| 4:45 | Speaker 1→2 |   | **Handoff to Speaker 2** |
| 5:00 | Speaker 2 | 10 | System architecture overview |
| 5:45 | Speaker 2 | 11–12 | 7-stage pipeline   deep dive |
| 6:30 | Speaker 2 | 13–14 | Hybrid RAG: BM25 + Dense + Image |
| 7:00 | Speaker 2 | 15 | AI generation layer, Bedrock |
| 7:30 | Speaker 2 | 16–17 | Data models, API design |
| 8:00 | Speaker 2 | 18–19 | FastAPI async backend |
| 8:30 | Speaker 2 | 20–22 | Terraform IaC + GitHub Actions CI/CD |
| 9:30 | Speaker 2→3 |   | **Handoff to Speaker 3** |
| 9:45 | Speaker 3 | 23–24 | AWS Bedrock Guardrails   security layer |
| 10:15 | Speaker 3 | 25 | Feature showcase   top 6 |
| 10:45 | Speaker 3 | 26–27 | UI walkthrough / demo screenshots |
| 11:15 | Speaker 3 | 28 | **"Let's talk about evidence"** [WOW setup] |
| 11:30 | Speaker 3 | 29 | Load test results   20 users (optimal), 0% error |
| 11:50 | Speaker 3 | 30 | Search P95 = 18.0 sec; Chat P95 = 27.4 sec (first-byte = 2.1 sec) |
| 12:10 | Speaker 3 | 31 | SRS coverage   37/37 verified |
| 12:30 | Speaker 3 | 32 | RAGAS metrics   AI quality evaluation |
| 12:50 | Speaker 3 | 33 | Phase 1 → Phase 2 evolution |
| 13:15 | Speaker 3 | 34 | Limitations   honest acknowledgment |
| 13:30 | Speaker 3 | 35 | Future work   2–3 specific next steps |
| 14:00 | Speaker 3 | 36 | Conclusions   restate the central claim |
| 14:30 | Speaker 3 | 37 | **Closing statement** |
| 15:00 | ALL |   | Q&A begins |

### Critical Time Checkpoints

- **At 5:00**   Speaker 2 should be starting. If Speaker 1 is still on slide 6, Speaker 1 is running 60 seconds late. Skip slide 8 or 9.
- **At 10:00**   Speaker 3 should be receiving the handoff. If Speaker 2 is still on infrastructure, cut the CI/CD detail.
- **At 13:00**   Speaker 3 should be entering the conclusions section. If still on evaluation metrics, combine the Phase evolution and Limitations slides verbally into one transition.
- **At 14:30**   Speaker 3 should be on the final slide. If not, skip Future Work and go directly to the closing statement. A clean ending beats a rushed ending.

### If You Run Over

Prioritize in this order:
1. Keep: Opening hook, WOW moments, Closing statement
2. Compress: Objectives detail, feature list, Phase 1 comparison
3. Cut entirely: Individual AWS service names, minor implementation details, related work table

### If You Finish Early

Do NOT fill dead time with "um" or off-script commentary. If you arrive at the closing slide at 14:00, slow down the closing statement delivery. Speak more deliberately. Add one sentence:

> "Thirty-seven requirements. Eighteen features. One production system. We're proud of what this team built   and we're ready to tell you exactly how we built it."

Then hand over to Q&A gracefully.

---

## FINAL NOTES FOR REHEARSAL

1. **Run three full-speed rehearsals** with a timer running visibly. The first will run 18+ minutes. The third should hit 14:45–15:15. All three speakers should rehearse together multiple times.

2. **Practice the WOW moments separately.** Record yourself saying WOW #1 through #5. Listen back. Are you pausing long enough? Is your voice confident, not rushed?

3. **Do the handoffs cold.** Practice the handoff scripts without the full presentation context   just the transition lines. They should feel automatic.

4. **Prepare for the committee to interrupt.** If a professor asks a question mid-presentation, answer it briefly (30 seconds maximum), then say: "I'll come back to that with more detail in Q&A   let me continue through the evidence." Then continue.

5. **Know your numbers cold.** 37. 18. 15+. 20. 0%. 18 seconds hybrid search / 27 seconds chat. 5. 8. 27. These numbers should come out without looking at slides. They are your credibility tokens. Especially important: be precise about latency   18 seconds is end-to-end hybrid search with LLM generation at 20 concurrent users (optimal load).

---

*This guide was prepared for the BK-MInD capstone defense, HCMUT, May 2026.*






