# 10 · Scores don't mix (~60 sec)

**Click:** "Just add them", then "RRF: 1/(60 + rank)", then "Linear".

Same index, new query: "how do I make search results more relevant." BM25 scores run into the teens; vector cosine scores sit around 0.75. If you just add them, BM25 wins every time and the semantic list barely registers. Click "Just add them" to see that. RRF skips scores and uses rank only: each list gives a doc one over sixty plus its rank. Hybrid search is number two in both lists, so it scores 1/62 plus 1/62 and takes first place. Linear fusion normalizes then weights; it's powerful but touchy, and you'll try it in Lab 3. In ES|QL it's FORK, two branches, then FUSE.
