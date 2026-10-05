# 12 - The relevance pyramid

**Target: ~35 seconds. Space: four times, one slab drops in each time, then the RAG and agents line.**

This is the shape of the labs from here on, built bottom to top. The first slab to land is Retrieve: BM25 and vector search, fused, which is Labs 1 through 3. It works across everything, so it has to be cheap per document. Next, Tune: filters, weights, and field boosts, mostly in Lab 3. Then the top slab: rerank the top N with a cross-encoder, the bonus Lab 5. Each layer sees fewer documents and spends more per document. One last Space: everything above feeds RAG and agents in Lab 4, and that's where we're going next.
