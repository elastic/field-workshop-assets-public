# Vector search: the briefing — talk track

Concept deck for the whole workshop (~10 min), presented live before Lab 1 and available in every lab's **Briefing** tab (port 5000).

- **Build:** `python3 build.py` → `index.html` (one self-contained file: elastic-web kit CSS/JS from `vendor/`, fonts base64 from `fonts/`, data from `data/data.json`). Zero runtime network requests.
- **Present:** open `index.html`. Space / → advances in-slide steps, then slides. ← back. `#N` or `#N.S` deep links. **N** toggles speaker notes.
- **Edit:** slides in `src/slides/NN-*.html`, notes in `notes/NN-*.md`, shared styles in `src/deck.css`, player in `src/player.js`.
- **Data:** slides 03–05, 07 and 10 use real output from the workshop index `aiewf-workshop-docs` (Jina v5 via EIS), gathered 2026-10-05 with `tools/gather_data.py` and `tools/lab4_good_bad.py` (needs ES_ENDPOINT / ES_API_KEY env vars).
- **Ship:** commit + push, then repin `ASSETS_SHA` in the track's Lab 1 `setup-kubernetes-vm` and `instruqt track push`.

# 01 - Title

**Target: ~10 seconds. Space: nothing, the cubes assemble on their own.**

Welcome, everyone. This is a ten-minute briefing, and its only job is to make sure nobody walks into a lab step without knowing the idea behind it. We'll cover how keyword search and vector search each find documents, how they combine, and what happens after retrieval. You don't need to memorize anything. This tab stays open next to every lab, so you can come back to any slide whenever a step feels fuzzy. Let's go.

# 02 - Elasticsearch is a vector database

**Target: ~30 seconds. Space: three times, one card each.**

Let me say the quiet part plainly: Elasticsearch is a vector database. You don't bolt one on next to it. Three things make that true. First, lexical and vector search live in one engine, so one query can use both. Second, the embedding model runs inside the platform through EIS, the Elastic Inference Service, so you never stand up a separate model server. Third, vectors get compressed with BBQ and, when they outgrow memory, DiskBBQ, so you can scale past RAM. The line at the bottom is the promise for today: you'll use all three in the labs, and you won't configure any of it.

# 03 - Words vs meaning

**Target: ~40 seconds. Space: BM25 results, then semantic results. Ask the room first.**

Here is the query: "notify me when something goes wrong." Show of hands: which doc in our 62-doc index should win? Press Space for Keyword. BM25 puts the container exit codes doc first, because it shares words with the query. The Watcher alerting doc, which is the doc you actually want, is stuck at number five. Press Space again for Semantic and the Watcher doc jumps to number one, even though it never uses the word "notify." That is the whole idea: BM25 finds words, vectors find meaning.

*Numbers on screen are real `_score` values from the workshop index.*

# 04 - Rare words count more (IDF)

**Target: ~40 seconds. Space: once per token (exit, code, 137, then the ghost word "the"), then once more for the boost and the strengths.**

BM25 is the keyword side, and its one big trick is that rare words count more. Take the query "exit code 137" and split it into tokens. "Exit" shows up in 3 of our 62 docs, "code" in 4, and "137" in exactly one, so 137 gets the highest weight. Now the ghost word "the": it's in all 62 docs, so its weight is basically zero. On the right, a boost lets you say a hit in the title counts three times a hit in the body. Strength: exact tokens like error codes, versions, config keys. Blind spot: different words for the same idea, which is what the next slides fix.

*Don't preview how Lab 2 ranks 137; that's the lab's reveal.*

# 05 - Text to vector

**Target: ~45 seconds. Space: fly the docs in, then drop in the query.**

Here is the query we'll follow, top left: "notify me when something goes wrong." On the right is the list of the 62 docs we'll search. Press Space and each one is embedded by Jina v5, turned into 1,024 numbers, and flies into the space, colored by topic. The view is a simplified projection of those real vectors, and it keeps slowly turning. Security docs cluster together, and so do search and vector docs. Close in space means close in meaning. Press Space once more and the big blue dot, our query, drops in. It gets embedded by the same model, and bold blue lines draw to its five nearest docs with their cosine score. The Watcher alerting doc is on top at 0.51. Elasticsearch reports the score as one plus cosine, divided by two, so 0.51 shows up as about 0.75 in the labs.

*Lines look long because we squashed 1,024 dimensions into three; the cosine in the list is the truth.*

# 06 - semantic_text and EIS

**Target: ~30 seconds. Space: twice, for the query flow and then the endpoints.**

This is all the setup there is. One field of type `semantic_text` pointing at the Jina v5 embedding endpoint. On ingest it chunks the text into sentences, up to 250 words each, sends them to EIS, our managed inference service, and stores the vectors, quantized automatically. Press Space: at query time `MATCH` on that field runs the same model on your question and does the kNN. Press Space again for the endpoints you'll meet: embeddings in every lab, the v3 reranker in Labs 4 and 5, the v2 reranker in Lab 5 only, and the Haiku completion endpoint in Lab 4. One gotcha to flag now: `COMPLETION` needs a `completion` endpoint, not `chat_completion`. And you write zero ML code.

# 07 - Three ways Elasticsearch searches vectors

**Target: ~60 seconds. Space: Flat, then HNSW, then DiskBBQ. Let each animation finish; the big number is the work done.**

These dots are real: 416 sentence chunks from the workshop docs, squashed from 1,024 dimensions down to 3, colored by topic, slowly turning. The ringed dot is a query. Flat is brute force: watch the sweep, it compares the query to every single vector, so it's exact and the counter climbs to 416. Press Space for HNSW. It links each vector to its neighbors, then walks that graph toward the query. Blue hops are accepted; the orange flashes are neighbors it checked and rejected. It touches only about 41 vectors, but it's approximate and happiest when the graph fits in memory. Press Space for DiskBBQ. Centroids pop in, the nearest two clusters light up, everything else dims, and only 147 vectors get scored. The vectors stay on disk, so it holds up when RAM runs short.

*The graph walk is illustrative, drawn on the real neighbor graph.*

# 08 - Choosing your vector index

**Target: ~30 seconds. Space: highlights Flat, then HNSW, then DiskBBQ.**

Here's the cheat sheet for the three you just watched. Flat is exact and best when the set is small or you've filtered it down first. Quantized HNSW is the in-memory option: fast, approximate, and the one to pick when you need 99 percent plus recall, as long as most of the vector data fits in RAM. DiskBBQ keeps the vectors on disk, holds up when memory is tight, and is good to roughly 95 percent recall. It went GA in 9.2, it needs an Enterprise license, and it's the default dense_vector type from 9.4 where licensed. The footer is the point for today: in this workshop's index, semantic_text picked and quantized the index for you, so you won't be choosing.

# 09 - BBQ: 32x smaller vectors

**Target: ~40 seconds. Space: Quantize, then the oversample-and-rescore flow. The picture is an illustration.**

This is one Jina vector, 1,024 numbers, each one a 4-byte float, drawn as 1,024 cells. That's 4 kilobytes per vector, and it adds up fast across millions of chunks. Press Space. BBQ, Better Binary Quantization, keeps one bit per dimension, so the vector shrinks about 32 times: 128 bytes plus 14 bytes of corrective data. The dashed box is the space the float version used to need. The worry is accuracy, so press Space again. BBQ oversamples by 3: for the top 10 you asked for, it pulls 30 candidates using the tiny vectors, rescores them against the original vectors, and returns the best 10. Smaller vectors, same answers. And you don't turn it on: semantic_text quantizes dense embeddings to BBQ automatically.

# 10 - Scores don't mix

**Target: ~50 seconds. Space: Just add them, then RRF, then Linear.**

Same index, new query: "how do I make search results more relevant." BM25 scores run into the teens; vector scores top out around 0.75. Press Space to just add them: BM25 wins every time and the semantic list barely registers. Press Space for RRF, and note the header: this is a fusion score, not Elasticsearch's relevance _score. RRF ignores the scores entirely. Only each doc's rank in each list counts: one over sixty plus the rank. Hybrid search is number two in both lists, so it gets 1/62 plus 1/62 and takes first place. One more Space for Linear fusion: it normalizes each list, then weights them. It needs manual tuning per dataset to beat RRF, and you'll try it in Lab 3. In ES|QL it's FORK, two branches, then FUSE.

# 11 - Keeping score: MRR

**Target: ~30 seconds. Space: the 1/rank scores, then why you care, then the heatmap. Everything here is an example, not workshop results.**

How do you know a retriever is good? You keep score. MRR stands for Mean Reciprocal Rank. A judgment set pairs each query with the one doc we know is right. For each query, take one divided by the rank where that doc landed: rank one is 1, rank two is a half, rank five is 0.2, a miss is zero. Then average over all the queries. Press Space: here that gives 0.425. Press Space again for why you care: it's one number for how high the right answer lands, and 1.0 means always number one. RAG and agents mostly read only the top few results, so number one versus number five is a right answer versus a wrong one. So 0.425 means the right doc lands around second or third on average, and one query missed entirely. Last Space: the heatmap, teal is rank one, red is a miss. In Lab 3 you compute MRR for BM25, semantic and hybrid.

*Labs reveal the real numbers, so don't spoil them here.*

# 12 - The relevance pyramid

**Target: ~35 seconds. Space: four times, one slab drops in each time, then the RAG and agents line.**

This is the shape of the labs from here on, built bottom to top. The first slab to land is Retrieve: BM25 and vector search, fused, which is Labs 1 through 3. It works across everything, so it has to be cheap per document. Next, Tune: filters, weights, and field boosts, mostly in Lab 3. Then the top slab: rerank the top N with a cross-encoder, the bonus Lab 5. Each layer sees fewer documents and spends more per document. One last Space: everything above feeds RAG and agents in Lab 4, and that's where we're going next.

# 13 - Recall, then precision

**Target: ~30 seconds. Space: stage 2, then the rerank. Everything here is illustrative.**

Think of retrieval as two jobs. Stage one is recall: FORK and FUSE pull a pile of candidates so the right doc is somewhere in the top 50. It may not be at the top yet, and that's fine. Press Space for stage two, precision: RERANK runs a cross-encoder that reads the query and each doc together and reorders the top N. Press Space again and the right doc climbs from fourth to first. The v2 reranker scores each pair alone, pointwise; v3 scores the candidates together, listwise. Gotcha at the bottom: RERANK rewrites the score but doesn't reorder, so always follow it with SORT on `_score` descending.

# 14 - An LLM only knows what it was trained on

**Target: ~40 seconds. Space: the bridge and the pipeline, then the punchline.**

Here is the real reason for this whole workshop. A large language model is a snapshot. It knows what was in its training data, up to a cutoff, and nothing else. On the other side of that wall is everything about your world: your docs, your tickets, your runbooks, yesterday's incident, your product catalog. None of it got in. Press Space: Elasticsearch is the bridge. The question comes in, we retrieve the right pieces of your data, they go into the prompt as context, and the model gives a grounded answer. Press Space once more for the line to remember: search is how an LLM gets to know your data.

# 15 - The whole RAG pipeline is one ES|QL query

**Target: ~50 seconds. Space: five times, one stage lights up each time.**

This is the Lab 4 query, and it really is one query. Press Space through it with me. FROM: 62 docs in the index. FORK: two searches at once, BM25 top 50 and vector top 50. FUSE: merge by rank down to the top 20. RERANK: the Jina v3 reranker reads query and doc together and picks one, here doc-017, Index lifecycle management overview. COMPLETION: the Haiku model writes the answer from that one doc. Notice the order from the lab: FORK, FUSE, RERANK, SORT, COMPLETION. Everything you built in Labs 1 through 3, plus the reranker from Lab 5, in one pipeline, with no glue code.

*Row counts are from the live Lab 4 run on the workshop index.*

# 16 - Same model, same question, only the retrieval changed

**Target: ~55 seconds. Space: the good answer, the bad answer, then the punchline.**

We ran this today on the workshop index with the Haiku completion endpoint. The question: how does ILM move data through hot, warm, and cold phases? Two runs, same model, same prompt. On the left we retrieved doc-017, the ILM overview. Press Space: a grounded answer with hot, warm, and cold, and the actual thresholds. On the right we forced retrieval onto an off-topic doc, the 9.x what's new page. Press Space: "I do not have enough information." That is the model behaving well, by the way. It didn't make something up. It just had nothing to work with. Press Space for the point: the model didn't get dumber, the retrieval got worse. In Lab 4 you'll do exactly this experiment yourself.

*Good answer is trimmed to the key points. Model and run are in the small print.*

# 17 - Agents use your search as a tool

**Target: ~50 seconds. Space: hop 1, then hop 2 and the answer. The run is illustrative.**

The query you just saw is also the tool for an agent. In Agent Builder the tool is the same FORK and FUSE ES|QL, registered as search-workshop-docs-hybrid. The agent decides when to call it, and it can call it more than once. Ask: my container keeps dying with exit code 137, why, and what JVM settings should I change? Press Space: hop 1, the agent searches for the cause and finds the container exit codes doc, out of memory. Press Space: hop 2, it searches again for the fix and finds the JVM heap and memory settings. Then it answers from both. A tip for Lab 4: Agent Builder auto-loads the Diagnose and Fix skill, and that skill is what drives the second search, so the model you pick doesn't matter. Just watch for two search-workshop-docs-hybrid tool calls: cause, then fix.

# 18 - One engine, keyword to agent

**Target: ~30 seconds. Space: nothing, the cubes drop in on their own.**

So here is where we landed. Remember the opening slide: Elasticsearch is a vector database. It's also the search engine. Keyword search with BM25 in Lab 2. Vector search with semantic_text and Jina on EIS in Lab 1. Hybrid with FORK and FUSE in Lab 3. Reranking in Lab 5. The LLM and agents on top in Lab 4. And BBQ and DiskBBQ quietly keep it all small enough to scale. One engine, one query language, zero ML code. That's the workshop.

# 19 - Ready for the labs

**Target: ~20 seconds. Space: nothing.**

That's the map. Lab 1 is plain vector search, and the idea you need is that semantic_text embeds for you and MATCH runs kNN. Lab 2 shows where vector search struggles, which is exactly where BM25's exact tokens earn their keep. Lab 3 is the hybrid lab with FORK and FUSE, where you fuse by rank because the scores don't mix. Lab 4 is RAG and an agent, the part where your data meets the LLM, and Lab 5 is the bonus: reranking. This Briefing tab stays open in every lab, so come back to any slide whenever you need it. Ready for the labs?
