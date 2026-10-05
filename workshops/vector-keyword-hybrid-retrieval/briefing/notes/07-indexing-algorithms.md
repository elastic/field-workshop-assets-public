# 07 - Three ways Elasticsearch searches vectors

**Target: ~60 seconds. Space: Flat, then HNSW, then DiskBBQ. Let each animation finish; the big number is the work done.**

These dots are real: 416 sentence chunks from the workshop docs, squashed from 1,024 dimensions down to 3, colored by topic, slowly turning. The ringed dot is a query. Flat is brute force: watch the sweep, it compares the query to every single vector, so it's exact and the counter climbs to 416. Press Space for HNSW. It links each vector to its neighbors, then walks that graph toward the query. Blue hops are accepted; the orange flashes are neighbors it checked and rejected. It touches only about 41 vectors, but it's approximate and happiest when the graph fits in memory. Press Space for DiskBBQ. Centroids pop in, the nearest two clusters light up, everything else dims, and only 147 vectors get scored. The vectors stay on disk, so it holds up when RAM runs short.

*The graph walk is illustrative, drawn on the real neighbor graph.*
