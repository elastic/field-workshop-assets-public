# 02 - Elasticsearch is a vector database

**Target: ~45 seconds. Click: nothing (the pills animate in on their own).**

Let me say the quiet part plainly: Elasticsearch is a vector database. You don't bolt one on next to it. Three things make that true, and they're the three pills. First, lexical and vector search live in one engine, so one query can use both. Second, the embedding model runs inside the platform through EIS, the Elastic Inference Service, so you never stand up a separate model server. Third, vectors get compressed with BBQ and, when they outgrow memory, DiskBBQ, so you can scale past RAM. The line at the bottom is the promise for today: you'll use all three in the labs, and you won't configure any of it.
