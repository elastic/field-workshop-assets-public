# 03 - Words vs meaning

**Target: ~40 seconds. Space: BM25 results, then semantic results. Ask the room first.**

Here is the query: "notify me when something goes wrong." Show of hands: which doc in our 62-doc index should win? Press Space for Keyword. BM25 puts the container exit codes doc first, because it shares words with the query. The Watcher alerting doc, which is the doc you actually want, is stuck at number five. Press Space again for Semantic and the Watcher doc jumps to number one, even though it never uses the word "notify." That is the whole idea: BM25 finds words, vectors find meaning.

*Numbers on screen are real `_score` values from the workshop index.*
