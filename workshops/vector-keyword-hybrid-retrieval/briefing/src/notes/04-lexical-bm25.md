# 04 · Rare words count more, IDF (~55 sec)

**Click:** "Next token" four times (or click each chip). The last click is the ghost word "the".

BM25 is the keyword side, and its one big trick is that rare words count more. Take the query "exit code 137" and split it into tokens. "Exit" shows up in 3 of our 62 docs, "code" in 4, and "137" in exactly one, so 137 gets the highest weight. Now click "the": it's in all 62 docs, so its weight is basically zero. On the right, a boost lets you say a hit in the title counts three times a hit in the body. Strength: exact tokens like error codes, versions, config keys. Blind spot: different words for the same idea, which is what the next slides fix. *Don't preview how Lab 2 ranks 137; that's the lab's reveal.*
