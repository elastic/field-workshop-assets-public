# 12 · Recall, then precision (~45 sec)

**Click:** "1 · Retrieve candidates", then "2 · Rerank the top N". Both are illustrative.

Think of retrieval as two jobs. Stage one is recall: FORK and FUSE pull a pile of candidates so the right doc is somewhere in the top 50. It may not be at the top yet, and that's fine. Click Retrieve to see it land in the pile. Stage two is precision: RERANK runs a cross-encoder that reads the query and each doc together and reorders the top N. Click Rerank and the right doc climbs from fourth to first. The v2 reranker scores each pair alone, pointwise; v3 scores the candidates together, listwise. Gotcha at the bottom: RERANK rewrites the score but doesn't reorder, so always follow it with SORT on `_score` descending.
