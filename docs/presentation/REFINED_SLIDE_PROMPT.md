# BK-MInD Capstone Defense - Professional Slide Deck Prompt (Refined)

**Project:** BK-MInD - Educational Content Processing & RAG System  
**Event:** HCMUT CS251 Capstone Defense | April 28, 2026  
**Target Audience:** Lecturers, colleagues, evaluation committees  
**Duration:** 20-25 min presentation + Q&A  
**Slide Count:** 28-32 slides (including backup slides)  

---

## 📋 SLIDE OUTLINE (Refined Structure)

### **OPENING (Slides 1-2)**
1. **Cover Slide** — Title, subtitle, institution, team, date
2. **Problem & Solution** — Current gap in educational platforms → AI-powered multimodal system

### **PROJECT SCOPE (Slides 3-4)**
3. **Requirements Breakdown** — 37 total (22 FR, 8 NFR, 7 TR); mapped to 5 functional areas
4. **18 Production Features** — Table with all features, categories, status (✅ all active)

### **ARCHITECTURE & DESIGN (Slides 5-7)**
5. **System Overview** — 6-layer architecture (Presentation → API → Processing → Indexing → Retrieval → Generation)
6. **Content Processing Pipeline** — 4 stages: Normalize → Media Process → Document Understanding → Consolidate
7. **Data Flow & Integration** — Component diagram showing all services, APIs, external integrations

### **CORE CAPABILITIES (Slides 8-10)**
8. **Multi-Modal Search** — BM25 (sparse), Dense (semantic), Hybrid, Visual; latency <200ms
9. **Intelligent Q&A & Chat** — RAG pipeline with guardrails, citations, multi-turn support
10. **Personalized Learning** — Summaries, quiz generation, roadmaps, analytics, visualizations

### **SECURITY & QUALITY (Slides 11-13)**
11. **Safety & Compliance** — AWS Bedrock Guardrails (5 filter categories), PII masking (27 types), authentication
12. **Testing & Validation** — JMeter performance tests (50 concurrent users), latency/throughput metrics, ✅ production certified
13. **Technical Implementation** — Tech stack (FastAPI, React 18, Qdrant, DynamoDB, Redis, AWS), deployment architecture

### **DEPLOYMENT & SCALE (Slides 14-15)**
14. **Infrastructure & DevOps** — Terraform IaC, AWS services (ECS, ALB, ECR, ACM), auto-scaling, high availability
15. **Cost & Scalability** — Per-user costs (~$13/month for 50 users), linear growth to 1000+, ROI analysis

### **EVIDENCE & METRICS (Slides 16-18)**
16. **Performance Results** — P50/P95/P99 latency, throughput, error rates, stability under load
17. **Project Deliverables** — Code stats (5000+ backend lines, 3000+ frontend lines), 15+ docs, 100% SRS coverage
18. **Statistics Dashboard** — Features, requirements, test runs, documentation completeness

### **CLOSING (Slides 19-20)**
19. **Key Achievements** — Innovation, scale validation, quality, deployment-readiness, impact
20. **Lessons Learned & Roadmap** — Technical insights, best practices, future enhancements, sustainability

### **BACKUP SLIDES (21-28 as needed)**
- Detailed API reference (endpoints, parameters, responses)
- Detailed test results (JMeter exports, latency distributions, test plans)
- Cost breakdown (per-service AWS costs)
- Feature deep-dives (chat architecture, quiz generation, visual search)
- Q&A supplementary slides

---

## 🎨 DESIGN SPECIFICATIONS

**Color Palette:**
- Primary: Modern Blue (#0066CC) — trust, technology
- Secondary: Vibrant Green (#10B981) — growth, learning
- Accent: Orange (#FF6B35) — energy, innovation
- Neutral: Light Gray (#F3F4F6) — clean backgrounds
- Text: Dark Gray (#1F2937)

**Typography:**
- Headlines: Bold sans-serif, 44-48pt (Inter, Segoe UI, SF Pro)
- Body: Regular sans-serif, 24-28pt
- Data/Code: Monospace, 18-22pt
- Contrast: ≥4.5:1 accessibility ratio

**Visual Elements:**
- Modern flat icons (Feather, Font Awesome)
- Clean flowcharts & architecture diagrams
- Data charts (no grid backgrounds; minimal ornamentation)
- Ample whitespace, 16px grid system
- Subtle transitions (<300ms)

**Format:**
- Aspect ratio: 16:9 widescreen
- Resolution: 1920×1080
- File size: <50MB (optimized images)
- Accessibility: Alt text for all visuals

---

## ⏱️ PRESENTATION TIMING

| Section | Slides | Time |
|---------|--------|------|
| Opening | 1-2 | 2 min |
| Scope | 3-4 | 2 min |
| Architecture | 5-7 | 2.5 min |
| Capabilities | 8-10 | 3 min |
| Security | 11-13 | 2.5 min |
| Deployment | 14-15 | 2 min |
| Evidence | 16-18 | 2 min |
| Closing | 19-20 | 2 min |
| **Optional Demo** | — | 3-5 min |
| **Q&A** | — | 3-5 min |
| **TOTAL** | 20 | 20-25 min |

---

## 🎯 KEY CONTENT HIGHLIGHTS

**Each Slide Must Include:**
- **Title** (clear, concise)
- **Visuals** (diagram, chart, icon set; minimum 40% of slide)
- **Key Points** (3-5 bullets or a focused narrative)
- **Data/Evidence** (numbers, percentages, metrics where applicable)
- **Consistency** (matching design system, color palette, font)

**Critical Evidence to Highlight:**
- ✅ 37 requirements met (100% coverage)
- ✅ 18 features delivered (all production-active)
- ✅ 50+ concurrent users validated via JMeter
- ✅ <200ms search latency, <500ms chat latency
- ✅ Infrastructure-as-Code ready (Terraform)
- ✅ 15+ technical documents (fully documented)

---

## 📊 SLIDE-BY-SLIDE CHECKLIST

**OPENING**
- [ ] Slide 1: Cover (title, subtitle, institution, date, hero image)
- [ ] Slide 2: Problem → Solution (visual comparison or before/after)

**SCOPE**
- [ ] Slide 3: Requirements pie/bar chart (37 total breakdown)
- [ ] Slide 4: Feature table (18 rows, 100% ✅ coverage)

**ARCHITECTURE**
- [ ] Slide 5: 6-layer architecture diagram (color-coded)
- [ ] Slide 6: 4-stage processing pipeline (flowchart with I/O)
- [ ] Slide 7: System integration (components + external services)

**CAPABILITIES**
- [ ] Slide 8: Search comparison (4 methods side-by-side, latency metrics)
- [ ] Slide 9: RAG flowchart (query → retrieval → generation → citation)
- [ ] Slide 10: Learning feature ecosystem (icons + descriptions)

**SECURITY**
- [ ] Slide 11: Guardrails architecture (filter layers + PII protection)
- [ ] Slide 12: Performance metrics chart (P50/P95/P99 latency, throughput)
- [ ] Slide 13: Tech stack grid (backend, frontend, infra, integrations)

**DEPLOYMENT**
- [ ] Slide 14: AWS deployment diagram (ECS, ALB, auto-scaling)
- [ ] Slide 15: Cost/scalability graph (per-user cost vs. users)

**EVIDENCE**
- [ ] Slide 16: Performance test results (load test curves, stability)
- [ ] Slide 17: Code & docs metrics (lines of code, test runs, coverage)
- [ ] Slide 18: Project completion dashboard (visual metrics)

**CLOSING**
- [ ] Slide 19: Achievements + impact
- [ ] Slide 20: Lessons learned + roadmap + Q&A

**BACKUP (as needed)**
- [ ] Slide 21+: API reference, detailed test exports, cost breakdown, feature deep-dives

---

## 🚀 RECOMMENDED CREATION APPROACH

1. **Tool Choice:** Google Slides (collaborative), Canva Pro (templates), or PowerPoint (control)
2. **Template Start:** Choose professional template matching color palette
3. **Build Order:** Slides 1, 2 → 5, 6, 7 (architecture) → 8, 9, 10 → rest
4. **Visuals:** Use Figma/draw.io for custom diagrams, then embed
5. **Review:** Check readability (min 24pt), timing (5 sec per slide), consistency
6. **Backup:** Export as PDF, have notes in speaker view

---

## 📝 TONE & MESSAGING

- **Technical:** Depth in architecture, APIs, infrastructure
- **Evidence-driven:** Back claims with metrics, test results, data
- **Professional:** Suitable for lecturers and evaluation committees
- **Accessible:** Explain complex concepts clearly for mixed audience
- **Impactful:** Emphasize innovation, reliability, real-world applications

**Sample Opening Line:**  
*"BK-MInD transforms how educators manage multimodal learning content—integrating intelligent search, AI-powered Q&A, and personalized learning into a single, scalable platform."*

**Sample Closing Line:**  
*"We've built a production-ready system that's been tested with 50+ concurrent users, documented across 15+ technical reports, and ready to scale to 100,000+ students globally."*

---

**Document Updated:** April 28, 2026  
**Status:** Ready for slide deck creation  
**Questions?** Reference comprehensive docs in `/docs/` folder
