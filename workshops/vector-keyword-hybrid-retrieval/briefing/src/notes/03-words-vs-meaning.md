# 03 · Words vs meaning (~50 sec)

**Click:** "Keyword (BM25)", then "Semantic (vector)". Ask the room first.

Here is the query: "notify me when something goes wrong." Two docs in our 62-doc index are in play, A and B. Show of hands: which one should win? Now click Keyword. BM25 puts the container exit codes doc first, because it shares words with the query. The Watcher alerting doc, which is the doc you actually want, is stuck at number five. Click Semantic and the Watcher doc jumps to number one, even though it never uses the word "notify." That is the whole idea: BM25 finds words, vectors find meaning.

*Numbers on screen are real `_score` values from the workshop index.*
