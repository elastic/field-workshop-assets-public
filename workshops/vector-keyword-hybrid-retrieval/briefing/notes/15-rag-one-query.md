# 15 - The whole RAG pipeline is one ES|QL query

**Target: ~50 seconds. Space: five times, one stage lights up each time.**

This is the Lab 4 query, and it really is one query. Press Space through it with me. FROM: 62 docs in the index. FORK: two searches at once, BM25 top 50 and vector top 50. FUSE: merge by rank down to the top 20. RERANK: the Jina v3 reranker reads query and doc together and picks one, here doc-017, Index lifecycle management overview. COMPLETION: the Haiku model writes the answer from that one doc. Notice the order from the lab: FORK, FUSE, RERANK, SORT, COMPLETION. Everything you built in Labs 1 through 3, plus the reranker from Lab 5, in one pipeline, with no glue code.

*Row counts are from the live Lab 4 run on the workshop index.*
