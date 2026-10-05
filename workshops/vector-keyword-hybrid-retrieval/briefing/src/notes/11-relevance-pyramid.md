# 11 - The relevance pyramid

**Target: ~50 seconds. Click: the glowing button four times, once per layer, then once more for the RAG and agents line. The circular arrow resets.**

This is the shape of the labs from here on, built bottom to top. Click the first button. The base is Retrieve: BM25 and vector search, fused, which is Labs 1 through 3. It works across everything, so it has to be cheap per document. Click again for Tune: filters, weights, and field boosts, mostly in Lab 3. Click again for the tip: rerank the top N with a cross-encoder, which is the bonus Lab 5. Each layer sees fewer documents and spends more per document, which is why the arrow on the left reads cost per doc. One last click: everything above feeds RAG and agents in Lab 4, and the quality of what the pyramid hands them decides the quality of the answer.
