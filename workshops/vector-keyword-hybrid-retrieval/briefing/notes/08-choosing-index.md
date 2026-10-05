# 08 - Choosing your vector index

**Target: ~30 seconds. Space: highlights Flat, then HNSW, then DiskBBQ.**

Here's the cheat sheet for the three you just watched. Flat is exact and best when the set is small or you've filtered it down first. Quantized HNSW is the in-memory option: fast, approximate, and the one to pick when you need 99 percent plus recall, as long as most of the vector data fits in RAM. DiskBBQ keeps the vectors on disk, holds up when memory is tight, and is good to roughly 95 percent recall. It went GA in 9.2, it needs an Enterprise license, and it's the default dense_vector type from 9.4 where licensed. The footer is the point for today: in this workshop's index, semantic_text picked and quantized the index for you, so you won't be choosing.
