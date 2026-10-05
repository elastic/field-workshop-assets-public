# Vector Search: Vector, Keyword, and Hybrid Retrieval — instructor deck outline

Plain-text outline (human reference). `index.html` is authoritative.
Format: self-paced labs, instructor regroups after each lab with a brief for the next one.
Timings are suggestions for a ~2.5–3h slot — adjust to the room.

---

## 1. Title  [title]
Vector Search: Vector, Keyword, and Hybrid Retrieval
Hands-on with Elasticsearch ES|QL · ElasticON New York
Jeff Vestal · Elastic

## 2. Show of hands  [problem]
- Who's shipped something with RAG or an agent in the last year?
- Who's had it give a confident, wrong answer?
- "Use a better model" is the reflex. Usually the model is fine — **the retrieval is wrong.**
Speaker: RAG went into the background; agents now retrieve many times per task. Every retrieval call is a chance to feed the model garbage.

## 3. The thesis  [problem]
**Retrieval quality, not model quality, bounds answer quality.**
"The model didn't get dumber. The retrieval got worse."
We prove it live — your own cluster, not slides.

## 4. What you'll do today  [done]
1. Vector search — match on meaning (~20 min)
2. Where vector breaks — and where keyword breaks (~25 min)
3. Hybrid search — FORK + FUSE, measured (~25 min)
4. Why it matters — one-query RAG + a multi-hop agent (~30 min)
5. Bonus: reranking (~15 min)
You leave with: a public repo — corpus, ingest script, every query, every notebook.

## 5. How the lab works  [concept]
Left: diagram of the Instruqt window — assignment on the left, tabs on the right.
- **Kibana Discover** — paste ES|QL, click **Search**. Labs 1–3, 5.
- **Python Notebook** — same ideas in code, run cells top to bottom.
- **Agent Builder** — Lab 4 only: chat with an agent.
- Each lab: read the assignment → run the queries → **Next**.
- Your own Elastic Cloud Serverless project. Already loaded: 62 Elastic docs pages.
- Stuck? Raise a hand. Ahead? Do the notebook, then the bonus.
Getting in: [EVENT INVITE LINK / QR — fill in]

## 6. ES|QL in 60 seconds  [concept]
```
FROM aiewf-workshop-docs METADATA _score
| WHERE MATCH(body_semantic, "securing cluster traffic")
| SORT _score DESC
| LIMIT 5
| KEEP id, title, _score
```
- A pipe: source, then `|` stages.
- `METADATA _score` — ask for relevance. Without it, MATCH is just a filter.
- `MATCH` on a `semantic_text` field = vector search. On a `text` field = BM25 keyword search. **The field decides.**

## 7. Lab 1 brief — Vector search  [concept]
Diagram: query text → EIS (Jina v5 embeddings) → dense vector → nearest neighbours → docs.
- Embeddings are generated **server-side** — you write zero ML code.
- Try: "securing cluster traffic" → TLS doc, no shared keywords.
- Try your own everyday questions.
Look for: how good it feels. Next lab we break it.

## 8. Lab 1 recap  [done]
- Semantic search matched on **meaning**.
- `semantic_text` + Jina v5 did the embedding — query and documents.
- Feels like magic. Hold that thought.

## 9. Lab 2 brief — Where vector breaks  [problem]
Two failure modes, opposite query shapes:
| Query | Semantic | BM25 |
|---|---|---|
| `exit code 137` | right doc, but by a hair | real distance — but a boosted title wins #1 |
| `new_primaries` | plausible **wrong** doc | pins the settings doc |
| `8.18 breaking changes` | right | **wrong** doc #1 (boosted common words) |
| `notify me when something goes wrong` | right | buries it (no shared words) |
Look for: *why* — split title-only vs body-only to read the score.

## 10. Lab 2 recap  [done]
- Semantic **blurs** exact tokens: error codes, versions, config values.
- BM25 **mis-ranks** on boosted common words and is blind to paraphrase.
- You read the scores — you didn't take my word for it.
- Neither is safe alone → hybrid.

## 11. Lab 3 brief — Hybrid with FORK + FUSE  [concept]
Diagram: FORK → (BM25 branch, semantic branch) → FUSE → one ranked list.
```
FROM aiewf-workshop-docs METADATA _score, _id, _index
| FORK ( WHERE MATCH(body, ?q)          | SORT _score DESC | LIMIT 50 )
       ( WHERE MATCH(body_semantic, ?q) | SORT _score DESC | LIMIT 50 )
| FUSE
| SORT _score DESC | LIMIT 5
```
- **RRF** (default): score = Σ 1/(k + rank). Ranks, not raw scores. Zero tuning.
- **FUSE LINEAR**: MinMax-normalize each branch, then weight. Powerful — and brittle.
Look for: every trap from Lab 2 lands at #1. Then measure it (MRR, heatmap).

## 12. Lab 3 recap  [done]
- RRF wins on **every** query that broke the others — measured, not eyeballed.
- Linear can tie RRF — after you tune the weights. Those weights go stale when the corpus or model changes.
- **RRF is your production default.** Filter inside the FORK branches to scope.

## 13. Lab 4 brief — The whole RAG pipeline in one query  [concept]
```
FROM aiewf-workshop-docs METADATA _score, _id, _index
| FORK ( WHERE MATCH(body, ?q) | SORT _score DESC | LIMIT 50 )
       ( WHERE MATCH(body_semantic, ?q) | SORT _score DESC | LIMIT 50 )
| FUSE | SORT _score DESC | LIMIT 20
| RERANK ?q ON body WITH {"inference_id": ".jina-reranker-v3"}
| SORT _score DESC | LIMIT 1
| EVAL prompt = CONCAT(...)
| COMPLETION answer = prompt WITH {"inference_id": ".anthropic-claude-4.5-haiku-completion"}
```
Retrieve → fuse → rerank → generate. No orchestration code.
The experiment: same model, same question — good retrieval vs deliberately bad retrieval.

## 14. Lab 4 brief — Then hand it to an agent  [concept]
- The same hybrid query becomes an **Agent Builder tool**.
- A multi-hop agent: search the symptom → search the fix → cited answer.
- In the **Agent Builder** tab: leave the default model. The agent's **Diagnose and Fix** skill drives the searches.
- Ask a two-part question. Watch for **two** `tool: search-workshop-docs-hybrid` chips.

## 15. Lab 4 recap  [problem]
**Same model. Good retrieval → great answer. Bad retrieval → "I don't have enough information."**
The model never changed.
One-shot RAG → hand-rolled loop → real agent: the framework is swappable. Retrieval quality is not.

## 16. Bonus — Reranking  [concept]
- Stage 1 (FORK + FUSE) = **recall**. Stage 2 (RERANK) = **precision** on the top N.
- Pointwise (`jina-reranker-v2`) scores each doc alone; listwise (`jina-reranker-v3`) compares candidates together.
- Gotcha: `RERANK` rewrites `_score` but doesn't reorder — always `| SORT _score DESC` after it.
- Worth the latency when the exact top result matters.

## 17. Which retriever, when  [done]
| Situation | Use |
|---|---|
| Default for search / RAG / agent tools | Hybrid **RRF** (`FORK … | FUSE`) |
| Exact IDs, codes, config keys dominate | Make sure BM25 is in the mix |
| You've measured weights on your data | `FUSE LINEAR` — re-measure when things change |
| The #1 result must be right | Add `RERANK` on the top 20–50 |
| Scope / multi-tenant | Filter inside every FORK branch (and real RBAC/DLS for security) |

## 18. Take it home  [done]
- Repo: github.com/jeffvestal/elastic-vectorsearch-workshop — corpus, ingest, notebooks, every query.
- Try it on your own data: swap the index, keep the queries.
- Docs: ES|QL search (MATCH, FORK/FUSE, RERANK, COMPLETION) · Agent Builder.
- Questions? Find me at the booth.

## 19. Troubleshooting (backup slide)  [problem]
- Discover shows a classic KQL bar → switch the query language to ES|QL.
- Query error near `--` → ES|QL comments are `//`.
- Agent did only one search → New chat, ask again.
- Notebook cell failed → re-run the setup cell at the top, then continue.
- Lab 4 Discover peek spins for a while → expected: reranker + LLM call.
