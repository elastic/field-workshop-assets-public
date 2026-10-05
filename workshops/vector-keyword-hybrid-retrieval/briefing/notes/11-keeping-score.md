# 11 - Keeping score: MRR

**Target: ~30 seconds. Space: the 1/rank scores, then why you care, then the heatmap. Everything here is an example, not workshop results.**

How do you know a retriever is good? You keep score. MRR stands for Mean Reciprocal Rank. A judgment set pairs each query with the one doc we know is right. For each query, take one divided by the rank where that doc landed: rank one is 1, rank two is a half, rank five is 0.2, a miss is zero. Then average over all the queries. Press Space: here that gives 0.425. Press Space again for why you care: it's one number for how high the right answer lands, and 1.0 means always number one. RAG and agents mostly read only the top few results, so number one versus number five is a right answer versus a wrong one. So 0.425 means the right doc lands around second or third on average, and one query missed entirely. Last Space: the heatmap, teal is rank one, red is a miss. In Lab 3 you compute MRR for BM25, semantic and hybrid.

*Labs reveal the real numbers, so don't spoil them here.*
