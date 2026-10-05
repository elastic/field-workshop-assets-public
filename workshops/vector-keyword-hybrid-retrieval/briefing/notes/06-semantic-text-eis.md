# 06 - semantic_text and EIS

**Target: ~30 seconds. Space: twice, for the query flow and then the endpoints.**

This is all the setup there is. One field of type `semantic_text` pointing at the Jina v5 embedding endpoint. On ingest it chunks the text into sentences, up to 250 words each, sends them to EIS, our managed inference service, and stores the vectors, quantized automatically. Press Space: at query time `MATCH` on that field runs the same model on your question and does the kNN. Press Space again for the endpoints you'll meet: embeddings in every lab, the v3 reranker in Labs 4 and 5, the v2 reranker in Lab 5 only, and the Haiku completion endpoint in Lab 4. One gotcha to flag now: `COMPLETION` needs a `completion` endpoint, not `chat_completion`. And you write zero ML code.
