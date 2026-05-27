# Retrieval & Generation Pipeline

A system that retrieves relevant documents and generates answers from them.

---

## Pipeline Flow

```
USER QUERY
    ↓
QUERY REWRITING (Resolve context)
    ↓
CACHE CHECK (Return if cached)
    ↓
PARALLEL RETRIEVAL (Text + Image)
    ↓
CONTEXT AGGREGATION (Combine results)
    ↓
SAVE TO CACHE
    ↓
GENERATION (LLM creates answer)
    ↓
FINAL RESPONSE
```

---

## Stage 1: Query Rewriting

Transform context-dependent questions into standalone queries.

**Example:**
```
Previous conversation: "What is BM25?"
User asks: "How does it differ from dense retrieval?"

Rewritten: "How does BM25 differ from dense retrieval?"
```

---

## Stage 2: Cache Check

Check if we've seen this query before for this user.
- If found: Return cached results immediately
- If not found: Continue to retrieval

---

## Stage 3: Parallel Retrieval

Search for relevant documents using two methods simultaneously:

**Text Search:**
- Method 1: BM25 (Keyword matching)
- Method 2: Dense Vector Search (Semantic similarity)
- Output: Top 10 text results

**Image Search:**
- Method: ColQwen (Visual model)
- Output: Top 10 image pages

Both run at the same time (~800ms total)

---

## Stage 4: Context Aggregation

Prepare search results for the LLM.

**Example Output:**
```
[1] Dense retrieval encodes queries and documents into 
    vector representations (384-dimensional). These are 
    compared using cosine similarity to find relevant 
    documents. (From: Lecture 3, Page 5)

[2] Unlike BM25 which matches keywords, dense retrieval 
    captures semantic meaning and handles synonyms better. 
    (From: Reference Paper, Page 3)

[Image: BM25 vs Dense Retrieval Comparison Chart]
(From: Lecture 3, Page 7)
```

---

## Stage 5: Save to Cache

Store retrieval results for 10 minutes.
- Same query repeated: Answer in 50-100ms
- Different query: Run full pipeline

---

## Stage 6: Generation

LLM creates a human-readable answer with citations.

**Example:**
```
Q: "How does dense retrieval work?"

A: Dense retrieval encodes queries and documents into 
vector representations [1]. The query vector is compared 
against document vectors using similarity scores [2]. This 
allows it to capture semantic meaning and handle synonyms 
better than keyword-based methods [3].

[1] Lecture 3 - Retrieval Methods
[2] Reference Paper - Dense Passage Retrieval
[3] Study Notes - Information Retrieval
```

---

## Key Points

- **Speed:** Parallel search (text + image together)
- **Caching:** Repeated queries answered instantly
- **Accuracy:** Two search methods + LLM generation
- **Robustness:** If one search fails, use the other

---

## Performance

- First query: 4-8 seconds
- Cached query: 50-100 milliseconds
- Text search: ~300ms
- Image search: ~800ms
