# 13 - Recall, then precision

**Target: ~30 seconds. Space: stage 2, then the rerank. Everything here is illustrative.**

Think of retrieval as two jobs. Stage one is recall: FORK and FUSE pull a pile of candidates so the right doc is somewhere in the top 50. It may not be at the top yet, and that's fine. Press Space for stage two, precision: RERANK runs a cross-encoder that reads the query and each doc together and reorders the top N. Press Space again and the right doc climbs from fourth to first. The v2 reranker scores each pair alone, pointwise; v3 scores the candidates together, listwise. Gotcha at the bottom: RERANK rewrites the score but doesn't reorder, so always follow it with SORT on `_score` descending.
