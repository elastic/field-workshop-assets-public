# 10 - Scores don't mix

**Target: ~50 seconds. Space: Just add them, then RRF, then Linear.**

Same index, new query: "how do I make search results more relevant." BM25 scores run into the teens; vector scores top out around 0.75. Press Space to just add them: BM25 wins every time and the semantic list barely registers. Press Space for RRF, and note the header: this is a fusion score, not Elasticsearch's relevance _score. RRF ignores the scores entirely. Only each doc's rank in each list counts: one over sixty plus the rank. Hybrid search is number two in both lists, so it gets 1/62 plus 1/62 and takes first place. One more Space for Linear fusion: it normalizes each list, then weights them. It needs manual tuning per dataset to beat RRF, and you'll try it in Lab 3. In ES|QL it's FORK, two branches, then FUSE.
