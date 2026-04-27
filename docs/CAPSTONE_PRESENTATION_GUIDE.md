# Capstone Presentation - Documentation Guide for Team

**For BK-MInD AI Learning Platform Capstone Project Defense**  
**HCMUT CS251 - April 28, 2026**

---

## 🎯 **PRESENTATION STRATEGY**

Your capstone presentation needs to convey:
1. **What is BK-MInD?** (Product vision, scope)
2. **How does it work?** (Architecture, technical design)
3. **What did you build?** (18 features, comprehensive implementation)
4. **Does it work?** (Testing evidence, performance metrics)
5. **Is it safe?** (Guardrails, security measures)
6. **Can it scale?** (Deployment, cost projections)

**Total presentation time:** 20-25 minutes (typically)
**Time allocation:** 4-5 min intro + 10-12 min demo + 5 min results + 2-3 min Q&A

---

## 📚 **ESSENTIAL DOCUMENTS FOR PRESENTATION**

### **Tier 1: MUST-READ (for all team members)**

Read these first — they establish the foundation:

#### 1. **[README.md](README.md)** — The Project Snapshot
- **What to extract:**
  - Project title, mission, overview
  - 37 SRS requirements breakdown (FR, NFR, TR)
  - System architecture diagram (Mermaid)
  - Core components summary
  - Tech stack highlights
  
- **Use in presentation:**
  - Opening slide: "BK-MInD transforms videos, slides, documents into searchable knowledge"
  - Architecture slide: Use the Mermaid diagram
  - Scope slide: "37 requirements across 4 categories"
  
- **Time to read:** 5-10 minutes
- **Key quote:** "Educational content processing and Retrieval-Augmented Generation system"

---

#### 2. **[docs/FEATURES.md](docs/FEATURES.md)** — Feature Completeness Evidence
- **What to extract:**
  - All 18 features with descriptions
  - Implementation status (all ✅ Active)
  - API endpoints for each feature
  - SRS requirement mapping (bottom of document)
  
- **Use in presentation:**
  - Features slide: "18 comprehensive features implemented"
  - Demo demonstration: Pick 3-5 key features (chat, search, quiz, summary, visualization)
  - Evidence slide: Show features table with "FEATURES.md Reference"
  
- **Time to read:** 15-20 minutes
- **Key stats:**
  - 18 features total
  - 100% SRS FR/NFR coverage
  - Active + tested

**Select 5 features to demo:**
1. Chat Assistant (interactive demo)
2. Search (text + image)
3. Quiz Generation (shows AI understanding)
4. Learning Summary (shows text generation quality)
5. Quiz Performance Analytics (shows data tracking)

---

#### 3. **[docs/technical/APPLICATION_OVERVIEW.md](docs/technical/APPLICATION_OVERVIEW.md)** — Architecture & Workflows
- **What to extract:**
  - Mission statement
  - Core capabilities (8 items)
  - User-facing workflows (6 steps)
  - High-level architecture table
  - Quality attributes and current assessment
  
- **Use in presentation:**
  - Intro/mission slide: Direct quote from "Mission" section
  - Architecture slide: Use the architecture table
  - Workflow slide: Show the 6-step user journey
  - Quality slide: Highlight reliability, performance, scalability
  
- **Time to read:** 10 minutes
- **Key diagrams:** None (text-only, but well-structured)

---

#### 4. **[docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)** — PROOF IT WORKS
- **What to extract:**
  - Executive summary / Test results overview
  - Capacity analysis (concurrent users, throughput)
  - Performance metrics (latency percentiles)
  - Key findings and recommendations
  - Graphs/tables showing test evidence
  
- **Use in presentation:**
  - Validation slide: "Tested up to 50 concurrent users"
  - Performance metrics: "P95 latency for search: XXms"
  - Capacity slide: "Supports XXX requests/second"
  - Credibility: "JMeter stress tests confirm stability"
  
- **Time to read:** 10 minutes
- **Critical stats:** Read the first 2-3 pages for executive summary

---

#### 5. **[docs/technical/GUARDRAIL_CONFIGURATION.md](docs/technical/GUARDRAIL_CONFIGURATION.md)** — Safety & Responsibility
- **What to extract:**
  - Guardrail ID and configuration
  - Content filter categories (hate, insults, sexual, violence, misconduct)
  - Prompt attack filters (8 types covered)
  - PII masking (27 types protected)
  - How it integrates into the application
  
- **Use in presentation:**
  - Responsibility slide: "AWS Bedrock Guardrails protect against harmful content"
  - Feature: "Multi-layer safety: hate speech, violence, sexual, misconduct filters"
  - Feature: "PII protection: 27 types masked automatically"
  - Compliance: "Educational platform designed with safety first"
  
- **Time to read:** 8-10 minutes
- **Key talking point:** "We don't just build, we build responsibly"

---

### **Tier 2: SHOULD-READ (supporting documents)**

Read these for depth and to answer expected questions:

#### 6. **[docs/technical/API_REFERENCE.md](docs/technical/API_REFERENCE.md)** — Technical Credibility
- **When needed:** If you get technical Q&A
- **Key sections to know:**
  - Main endpoint categories (Auth, Files, Processing, Search, Chat, Insights)
  - Example requests/responses format
  - How user isolation works
  
- **Use in Q&A:**
  - "How does the API work?" → "We have REST APIs with OpenAPI documentation"
  - "How many endpoints?" → Reference table (15+ core endpoints)
  - "How does auth work?" → "Firebase OAuth or local, with proper tenant scoping"
  
- **Time to read:** 10 minutes (skim, don't memorize)

---

#### 7. **[docs/requirements.md](docs/requirements.md)** — SRS Compliance
- **When needed:** If asked about requirements traceability
- **Key sections:**
  - FR (Functional Requirements): FR-001 to FR-027
  - NFR (Non-functional): NFR-001 to NFR-008
  - TR (Technical): TR-001 to TR-007
  
- **Use in Q&A:**
  - "How many requirements?" → "37 total: 22 functional, 8 non-functional, 7 technical"
  - "Are all implemented?" → Reference [FEATURES.md](docs/FEATURES.md#-feature-compliance-with-srs) compliance table
  
- **Time to read:** 20-30 minutes (reference document)

---

#### 8. **[Phase_2_FE_AI_Merge/terraform/README.md](Phase_2_FE_AI_Merge/terraform/README.md)** — Deployment Credibility
- **When needed:** If asked about cloud deployment, scalability, production-readiness
- **Key talking points:**
  - "Infrastructure-as-Code via Terraform"
  - "AWS deployment: ECS, ALB, ECR, optional HTTPS"
  - "Scalable architecture ready for 100+ users"
  
- **Use in presentation:**
  - Deployment slide: "Terraform-based infrastructure"
  - Credibility: "Production-ready cloud architecture"
  
- **Time to read:** 5 minutes (overview)

---

#### 9. **[Phase_2_FE_AI_Merge/backend/README.md](Phase_2_FE_AI_Merge/backend/README.md)** — Backend Details
- **When needed:** For backend-specific Q&A
- **Key sections:**
  - Architecture layers
  - Database schema
  - Configuration examples
  
- **Use in Q&A:** Backend-specific questions about implementation details

- **Time to read:** 10 minutes (skim)

---

#### 10. **[docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx](docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx)** — Economics & Scalability
- **When needed:** If asked about deployment cost, scalability, business viability
- **Key insight:** Show the spreadsheet with cost breakdown
  - Per-user active cost
  - Monthly/annual projections
  - Scaling to 100+ users (small cost increase)
  
- **Use in presentation:**
  - Scalability slide: "Scales cost-efficiently from 50 to 500+ users"
  - Economics: "Reasonable cloud costs for university deployment"
  
- **Time to review:** 5 minutes

---

### **Tier 3: OPTIONAL (deep dives if needed)**

- **[docs/usecases.md](docs/usecases.md)** — If you want to emphasize user stories
- **[docs/system_modeling.md](docs/system_modeling.md)** — If presenting system design details
- **JMeter test reports** — If showing detailed performance test methodology
- Weekly research folders — If presenting research contributions

---

## 🎤 **PRESENTATION STRUCTURE (20-25 min)**

### **Minute 0-2: Introduction**
**Key documents:** [README.md](README.md), [APPLICATION_OVERVIEW.md](docs/technical/APPLICATION_OVERVIEW.md)

```
Title slide: "BK-MInD: AI Learning Platform for Educational Content Processing"
Subtitle: "Transforms videos, slides, documents into searchable knowledge with AI assistance"

Quick facts:
- 37 requirements (22 FR, 8 NFR, 7 TR)
- 18 comprehensive features
- Tested up to 50 concurrent users
- Production-ready AWS deployment
```

---

### **Minute 2-5: What is BK-MInD?**
**Key documents:** [APPLICATION_OVERVIEW.md](docs/technical/APPLICATION_OVERVIEW.md), [README.md](README.md)

```
Slide: Mission & Core Capabilities
- Help students convert unstructured learning materials into interactive knowledge
- Upload materials → Process → Index → Search → Learn
- 8 core capabilities: upload, processing, retrieval, Q&A, chat, insights, testing, deployment

Slide: System Architecture
- Use the Mermaid diagram from README.md
- Highlight layers: Frontend (React) → API (FastAPI) → Processing → Retrieval → Generation → Infrastructure (AWS)
```

---

### **Minute 5-15: How Does It Work? (DEMO)**
**Key documents:** [FEATURES.md](docs/FEATURES.md), [API_REFERENCE.md](docs/technical/API_REFERENCE.md)

**Demo 5 features in sequence:**

1. **Upload & Search** (2 min)
   - Show file upload
   - Search using text + image
   - Reference: [FEATURES.md#2-file-upload--management](docs/FEATURES.md#2-file-upload--management)

2. **Chat Assistant** (2 min)
   - Ask a question
   - Show tool usage (search retrieval)
   - Show streaming response
   - Reference: [FEATURES.md#8-chat-assistant](docs/FEATURES.md#8-chat-assistant)

3. **Quiz Generation** (1 min)
   - Generate quiz from lecture
   - Show MCQ format
   - Reference: [FEATURES.md#9-quiz-generation](docs/FEATURES.md#9-quiz-generation)

4. **Lecture Summary** (1 min)
   - Generate summary
   - Show formatting
   - Reference: [FEATURES.md#10-lecture-summaries](docs/FEATURES.md#10-lecture-summaries)

5. **Learning Visualization** (1 min)
   - Show mind map / infographic
   - Reference: [FEATURES.md#13-learning-visualizations](docs/FEATURES.md#13-learning-visualizations)

---

### **Minute 15-18: Does It Work? (VALIDATION)**
**Key documents:** [FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md](docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md), [FEATURES.md](docs/FEATURES.md)

```
Slide: Testing & Performance
- Tested with JMeter at 50 concurrent users
- Capacity analysis: XXX requests/second
- P95 latency: XXms for search, XXms for chat
- 0 errors under stress test

Slide: Feature Completeness
- 18/18 features implemented (100%)
- All 37 SRS requirements mapped to features
- Table: Feature list with status
```

---

### **Minute 18-20: Why Does It Matter?**
**Key documents:** [GUARDRAIL_CONFIGURATION.md](docs/technical/GUARDRAIL_CONFIGURATION.md), [AWS_Cost_Estimation_50_Users_Professional.xlsx](docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx)

```
Slide: Safety & Responsibility
- AWS Bedrock Guardrails filter harmful content
- PII protection on 27 data types
- Educational platform designed with safety first
- Multi-layer protection: content filters, prompt attack detection

Slide: Scalability & Deployment
- Production-ready AWS infrastructure (Terraform IaC)
- Scales from 50 to 500+ users with minimal cost increase
- Container-based deployment (Docker, ECS)
- Cloud-ready, ready for university production use
```

---

### **Minute 20-25: Q&A Preparation**

**Expected questions you should be ready for:**

1. **"Why this approach? Why Retrieval-Augmented Generation?"**
   - Answer from [APPLICATION_OVERVIEW.md](docs/technical/APPLICATION_OVERVIEW.md): "RAG provides grounded answers with citations directly from student materials, unlike hallucination-prone generative models"

2. **"How does the search work?"**
   - Answer from [FEATURES.md](#6-hybrid-search): "Hybrid approach: BM25 (keyword) + Dense (semantic) merged via RRF ranking"

3. **"Is it safe? What about harmful prompts?"**
   - Answer from [GUARDRAIL_CONFIGURATION.md](docs/technical/GUARDRAIL_CONFIGURATION.md): "AWS Bedrock Guardrails with 5 content filters + 8 prompt attack patterns + PII masking"

4. **"How does it scale?"**
   - Answer from [AWS_Cost_Estimation_50_Users_Professional.xlsx](docs/others/AWS_Cost_Estimation_50_Users_Professional.xlsx): "Tested to 50 users, cost-linear scaling to 500+ users"

5. **"What's the tech stack?"**
   - Answer from [README.md](README.md): "FastAPI backend, React frontend, Qdrant vectors, S3 storage, AWS Bedrock LLM, Terraform IaC"

6. **"How long did this take?"**
   - Answer from [README.md](README.md): "9+ weeks of research (Week 03-09) + 4+ weeks of integration (Phase 2)"

---

## 📋 **PRE-PRESENTATION CHECKLIST**

**1 Week Before:**
- [ ] Read all Tier 1 documents (1-5) — 2 hours total
- [ ] Prepare 3-5 features for demo (test them beforehand)
- [ ] Create presentation slides from the documents
- [ ] Practice demo (run through locally 3+ times)
- [ ] Skim API_REFERENCE for Q&A prep

**2 Days Before:**
- [ ] Full presentation run-through (timed, 25 minutes)
- [ ] Verify live demo works (test endpoints, DB connection)
- [ ] Prepare backup slides (screenshots if demo fails)
- [ ] Print out reference cards with key facts

**Day Before:**
- [ ] Final demo test
- [ ] Rehearse opening & closing
- [ ] Prepare for Q&A (know answers to 10 common questions)

**Day Of:**
- [ ] Arrive early, test A/V
- [ ] Open documents on backup laptop for reference
- [ ] Take deep breath, you've built something amazing 🚀

---

## 📊 **PRESENTATION SLIDE STRUCTURE (Recommended)**

```
1. Title slide
   - BK-MInD: AI Learning Platform
   - Team names, date

2. Problem statement
   - Students struggle with unstructured learning materials
   - Need: searchable, AI-assisted knowledge base

3. Solution overview (README.md)
   - BK-MInD system overview
   - System architecture diagram

4. Core capabilities (APPLICATION_OVERVIEW.md)
   - 8 core features list

5. DEMO (5 features, 8-10 minutes)
   - Upload & Search
   - Chat Assistant
   - Quiz Generation
   - Lecture Summary
   - Learning Visualization

6. 18 Features complete (FEATURES.md)
   - Table showing all features + status

7. Performance results (FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)
   - Capacity analysis
   - Latency metrics
   - Stress test results

8. Safety & responsibility (GUARDRAIL_CONFIGURATION.md)
   - Content filters
   - PII protection
   - Safety-first design

9. Deployment & scalability (AWS_Cost_Estimation_50_Users_Professional.xlsx, terraform/)
   - AWS infrastructure
   - Cost projections
   - Scaling capability

10. Conclusion & impact
    - Educational innovation
    - Production-ready system
    - Future opportunities

11. Q&A
```

---

## 🎓 **TALKING POINTS BY TEAM MEMBER**

### **Team Lead / Project Manager**
**Focus:** Vision, scope, requirements, timeline
**Key documents:** README.md, APPLICATION_OVERVIEW.md, requirements.md
**Main message:** "A comprehensive AI learning platform with 37 requirements delivered"

### **Backend Engineer**
**Focus:** Architecture, APIs, implementation, performance
**Key documents:** API_REFERENCE.md, FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md, Phase_2_FE_AI_Merge/backend/README.md
**Main message:** "Scalable, performant FastAPI backend handling retrieval and generation"

### **Frontend Engineer**
**Focus:** User experience, features, interactivity
**Key documents:** FEATURES.md, Phase_2_FE_AI_Merge/frontend/README.md, APPLICATION_OVERVIEW.md
**Main message:** "Intuitive React UI enabling students to search, chat, and learn effectively"

### **DevOps / Infrastructure**
**Focus:** Deployment, scalability, cost efficiency
**Key documents:** terraform/README.md, AWS_Cost_Estimation_50_Users_Professional.xlsx, DOCS_deployment-alb-acm-custom-domain.md
**Main message:** "Production-ready, scalable, cost-efficient AWS deployment"

### **AI/ML / Research**
**Focus:** Retrieval, generation, safety, model selection
**Key documents:** FEATURES.md (retrieval, generation, guardrails), GUARDRAIL_CONFIGURATION.md, research folders
**Main message:** "State-of-the-art RAG pipeline with safety guardrails and multi-model support"

---

## ✅ **DOCUMENT VERIFICATION CHECKLIST**

Before presenting, verify:

- [ ] All links in README.md are clickable and correct
- [ ] FEATURES.md completeness (18 features documented)
- [ ] GUARDRAIL_CONFIGURATION.md has correct AWS ID (`42ay3u3pr8vr`)
- [ ] FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md has test results
- [ ] AWS_Cost_Estimation_50_Users_Professional.xlsx opens and shows cost data
- [ ] API_REFERENCE.md lists all main endpoints
- [ ] requirements.md shows 37 requirements with SRS structure
- [ ] terraform/README.md shows deployment commands

---

## 🎁 **What to Give Your Team**

**Minimum package for each team member:**

```
1. /docs/INDEX.md — Full navigation guide
2. /README.md — Project overview
3. /docs/FEATURES.md — Feature reference
4. /docs/technical/APPLICATION_OVERVIEW.md — Architecture
5. /docs/technical/API_REFERENCE.md — API endpoints (backend only)
6. /docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md — Performance proof
7. /docs/technical/GUARDRAIL_CONFIGURATION.md — Safety measures
8. /docs/requirements.md — SRS compliance
9. Phase_2_FE_AI_Merge/terraform/README.md — Deployment
```

**Time to prepare for presentation:** 3-4 hours for team (sharing reading load)

---

## 🚀 **FINAL WORDS**

> "BK-MInD is not just a school project—it's a production-ready AI learning platform that demonstrates:
> - Comprehensive software engineering (37 requirements, 18 features)
> - Rigorous testing (JMeter capacity tests, 50+ concurrent users)
> - Responsible AI design (AWS Bedrock guardrails, PII protection)
> - Cloud-ready scalability (Terraform infrastructure, cost-efficient)
> - Real educational value (students can actually use this)"

**Your capstone defense is your chance to showcase all of this. Use the documents as your evidence. You've built something real. Go show them.** 🎓

---

**Version:** 1.0  
**Last Updated:** April 28, 2026  
**For:** HCMUT CS251 Capstone Project Team
