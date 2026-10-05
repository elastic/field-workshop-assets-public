# 13 · RAG and agents (~50 sec)

**Click:** "Run RAG", then "Run the loop". The loop takes about 6 sec.

Here's RAG in one picture: retrieve the docs, put them in the prompt as context, and the LLM answers grounded in what you gave it, with citations. In ES|QL that's a single query: FORK, FUSE, RERANK, COMPLETION. An agent turns that around: the LLM decides when to call your hybrid search as a tool, and it can call it more than once. Run the loop and watch two hops, first the cause, then the fix. The point: a better model doesn't rescue bad context. Same model, worse retrieval, worse answer, and you'll prove that yourself in Lab 4.
