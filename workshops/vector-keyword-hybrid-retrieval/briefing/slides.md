# Vector search: the briefing — talk track

Pre-Lab-1 concept deck (~10 min). Presented live by the instructor; also served in every lab's **Briefing** tab (port 5000) for self-paced learners.
Build: `./build.sh` → `index.html` (single self-contained file, speaker notes baked in, press **N**). Present with notes: `cd src && fslides serve`.
Interactive slides are click-driven (buttons on the slide); ←/→ move between slides. Data on slides 03–05, 07, 10 is real output from the workshop index `aiewf-workshop-docs` (Jina v5 via EIS), gathered 2026-10-05.

# 01 - Title

**Target: ~15 seconds. Click: nothing.**

Welcome, everyone. This is a ten-minute briefing, and its only job is to make sure nobody walks into a lab step without knowing the idea behind it. We'll cover how keyword search and vector search each find documents, how they combine, and what happens after retrieval. You don't need to memorize anything. This tab stays open next to every lab, so you can come back to any slide whenever a step feels fuzzy. Let's go.

# 02 - Elasticsearch is a vector database

**Target: ~45 seconds. Click: nothing (the pills animate in on their own).**

Let me say the quiet part plainly: Elasticsearch is a vector database. You don't bolt one on next to it. Three things make that true, and they're the three pills. First, lexical and vector search live in one engine, so one query can use both. Second, the embedding model runs inside the platform through EIS, the Elastic Inference Service, so you never stand up a separate model server. Third, vectors get compressed with BBQ and, when they outgrow memory, DiskBBQ, so you can scale past RAM. The line at the bottom is the promise for today: you'll use all three in the labs, and you won't configure any of it.

# 03 · Words vs meaning (~50 sec)

**Click:** "Keyword (BM25)", then "Semantic (vector)". Ask the room first.

Here is the query: "notify me when something goes wrong." Two docs in our 62-doc index are in play, A and B. Show of hands: which one should win? Now click Keyword. BM25 puts the container exit codes doc first, because it shares words with the query. The Watcher alerting doc, which is the doc you actually want, is stuck at number five. Click Semantic and the Watcher doc jumps to number one, even though it never uses the word "notify." That is the whole idea: BM25 finds words, vectors find meaning.

*Numbers on screen are real `_score` values from the workshop index.*

# 04 · Rare words count more, IDF (~55 sec)

**Click:** "Next token" four times (or click each chip). The last click is the ghost word "the".

BM25 is the keyword side, and its one big trick is that rare words count more. Take the query "exit code 137" and split it into tokens. "Exit" shows up in 3 of our 62 docs, "code" in 4, and "137" in exactly one, so 137 gets the highest weight. Now click "the": it's in all 62 docs, so its weight is basically zero. On the right, a boost lets you say a hit in the title counts three times a hit in the body. Strength: exact tokens like error codes, versions, config keys. Blind spot: different words for the same idea, which is what the next slides fix. *Don't preview how Lab 2 ranks 137; that's the lab's reveal.*

# 05 · Text to vector (~75 sec)

**Click:** "Embed & ingest 62 docs" (wait ~6 sec), then the "Search" button. Drag the 3D view if you want to show depth.

These are the 62 docs we'll search, colored by topic. Click Embed and each doc goes through Jina v5, which turns the text into 1,024 numbers; the 3D view is a simplified projection of those real vectors. Notice that security docs cluster together, search and vector docs cluster together. Close in space means close in meaning. Now click Search with "notify me when something goes wrong." The query gets embedded by the same model, and the five nearest docs light up with their cosine score. The Watcher alerting doc is on top at 0.51. That cosine number is the `_score` you will see in the labs. *The lines look long in 3D because we squashed 1,024 dimensions into three; the cosine in the list is the truth.*

# 06 · semantic_text and EIS (~40 sec)

**Click:** nothing, it's a static diagram.

This is all the setup there is. One field of type `semantic_text` pointing at the Jina v5 embedding endpoint. On ingest it chunks the text into sentences, up to 250 words each, sends them to EIS, our managed inference service, and stores the vectors, quantized automatically. At query time `MATCH` on that field runs the same model on your question and does the kNN. Over on the right are the endpoints you'll meet: embeddings in every lab, rerankers in Labs 4 and 5, and the Haiku completion endpoint in Lab 4. One gotcha to flag now: `COMPLETION` needs a `completion` endpoint, not `chat_completion`. And you write zero ML code.

# 07 - Three ways Elasticsearch searches vectors

**Target: ~90 seconds. Click: Flat, then Quantized HNSW, then DiskBBQ. Let each animation finish (about 10 seconds each) before the next click. Reset is just clicking another button.**

These dots are real: 416 sentence chunks from the workshop docs, embedded with Jina v5, squashed from 1,024 dimensions down to 3 so we can see them. The red dot is a query: "how do I make search results more relevant." Click Flat first. Flat is brute force. Filters drop what doesn't qualify, then it scores every remaining vector, so the answer is exact. That's perfect for small sets or heavily filtered ones, and it gets expensive as the data grows. Now HNSW. It links each vector to its neighbors and walks that graph toward the query, so it checks a handful of nodes instead of all 416. It's approximate: you trade a little accuracy for a lot of speed, and it's happiest when the graph fits in memory. Last, DiskBBQ. It groups vectors into clusters with k-means, finds the nearest centroids to the query, and compares only the vectors in those clusters. The vectors stay on disk, so it degrades gracefully when RAM runs short. Which one do you get? Next slide.

# 08 - Choosing your vector index

**Target: ~45 seconds. Click: nothing.**

Here's the cheat sheet for the three you just watched. Flat is exact and best when the set is small or you've filtered it down first. Quantized HNSW is the in-memory option: fast, approximate, and the one to pick when you need 99 percent plus recall, as long as most of the vector data fits in RAM. DiskBBQ keeps the vectors on disk, holds up when memory is tight, and is good to roughly 95 percent recall. It went GA in 9.2, it needs an Enterprise license, and it's the default dense_vector type from 9.4 and on Serverless. The footer is the point for today: in this workshop's index, semantic_text picked and quantized the index for you, so you won't be choosing.

# 09 - BBQ: 32x smaller vectors

**Target: ~60 seconds. Click: Quantize, wait for the shrink (about 3 seconds), then Search. Use the circular arrow to replay.**

This is one Jina vector, 1,024 numbers, each one a 4-byte float. That's 4 kilobytes per vector, and it adds up fast across millions of chunks. Click Quantize. BBQ, Better Binary Quantization, keeps one bit per dimension, so the vector shrinks about 32 times: 128 bytes plus 14 bytes of corrective data. The big dashed box is the space the float version used to need. The worry is accuracy, so click Search. BBQ oversamples by 3: for the top 10 you asked for, it pulls 30 candidates using the tiny vectors, rescores them against the original vectors, and returns the best 10. Smaller vectors, same answers. And you don't turn it on: semantic_text quantizes dense embeddings to BBQ automatically.

# 10 · Scores don't mix (~60 sec)

**Click:** "Just add them", then "RRF: 1/(60 + rank)", then "Linear".

Same index, new query: "how do I make search results more relevant." BM25 scores run into the teens; vector cosine scores sit around 0.75. If you just add them, BM25 wins every time and the semantic list barely registers. Click "Just add them" to see that. RRF skips scores and uses rank only: each list gives a doc one over sixty plus its rank. Hybrid search is number two in both lists, so it scores 1/62 plus 1/62 and takes first place. Linear fusion normalizes then weights; it's powerful but touchy, and you'll try it in Lab 3. In ES|QL it's FORK, two branches, then FUSE.

# 11 - The relevance pyramid

**Target: ~50 seconds. Click: the glowing button four times, once per layer, then once more for the RAG and agents line. The circular arrow resets.**

This is the shape of the labs from here on, built bottom to top. Click the first button. The base is Retrieve: BM25 and vector search, fused, which is Labs 1 through 3. It works across everything, so it has to be cheap per document. Click again for Tune: filters, weights, and field boosts, mostly in Lab 3. Click again for the tip: rerank the top N with a cross-encoder, which is the bonus Lab 5. Each layer sees fewer documents and spends more per document, which is why the arrow on the left reads cost per doc. One last click: everything above feeds RAG and agents in Lab 4, and the quality of what the pyramid hands them decides the quality of the answer.

# 12 · Recall, then precision (~45 sec)

**Click:** "1 · Retrieve candidates", then "2 · Rerank the top N". Both are illustrative.

Think of retrieval as two jobs. Stage one is recall: FORK and FUSE pull a pile of candidates so the right doc is somewhere in the top 50. It may not be at the top yet, and that's fine. Click Retrieve to see it land in the pile. Stage two is precision: RERANK runs a cross-encoder that reads the query and each doc together and reorders the top N. Click Rerank and the right doc climbs from fourth to first. The v2 reranker scores each pair alone, pointwise; v3 scores the candidates together, listwise. Gotcha at the bottom: RERANK rewrites the score but doesn't reorder, so always follow it with SORT on `_score` descending.

# 13 · RAG and agents (~50 sec)

**Click:** "Run RAG", then "Run the loop". The loop takes about 6 sec.

Here's RAG in one picture: retrieve the docs, put them in the prompt as context, and the LLM answers grounded in what you gave it, with citations. In ES|QL that's a single query: FORK, FUSE, RERANK, COMPLETION. An agent turns that around: the LLM decides when to call your hybrid search as a tool, and it can call it more than once. Run the loop and watch two hops, first the cause, then the fix. The point: a better model doesn't rescue bad context. Same model, worse retrieval, worse answer, and you'll prove that yourself in Lab 4.

# 14 · Keeping score, MRR (~45 sec)

**Click:** the "Score row" button four times, then "Average them → MRR", then "Show the heatmap". Everything on this slide is an example, not workshop results.

How do you know a retriever is good? You keep score. A judgment set is a list of queries, each paired with the one doc we know is right. For each query, ask where that doc landed. Rank one scores 1, rank two scores a half, rank five scores 0.2, not found scores zero. Average those and you get MRR, here 0.425. In the labs you'll see this as a heatmap: green is rank one, red is a miss, and a column of green is a retriever you can trust. *Labs reveal the real numbers, so don't spoil them here.*

# 15 - Ready for Lab 1

**Target: ~25 seconds. Click: nothing.**

That's the map. Lab 1 is plain vector search, and the idea you need is that semantic_text embeds for you and MATCH runs kNN. Lab 2 shows where vector search struggles, which is exactly where BM25's exact tokens earn their keep. Lab 3 is the hybrid lab with FORK and FUSE, where you fuse by rank because the scores don't mix. Lab 4 is RAG and an agent, and Lab 5 is the bonus: reranking. This Briefing tab stays open in every lab, so come back to any slide whenever you need it. Okay, ready for Lab 1?
