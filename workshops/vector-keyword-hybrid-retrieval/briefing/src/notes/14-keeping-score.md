# 14 · Keeping score, MRR (~45 sec)

**Click:** the "Score row" button four times, then "Average them → MRR", then "Show the heatmap". Everything on this slide is an example, not workshop results.

How do you know a retriever is good? You keep score. A judgment set is a list of queries, each paired with the one doc we know is right. For each query, ask where that doc landed. Rank one scores 1, rank two scores a half, rank five scores 0.2, not found scores zero. Average those and you get MRR, here 0.425. In the labs you'll see this as a heatmap: green is rank one, red is a miss, and a column of green is a retriever you can trust. *Labs reveal the real numbers, so don't spoil them here.*
