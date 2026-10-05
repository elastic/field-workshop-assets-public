# 09 - BBQ: 32x smaller vectors

**Target: ~40 seconds. Space: Quantize, then the oversample-and-rescore flow. The picture is an illustration.**

This is one Jina vector, 1,024 numbers, each one a 4-byte float, drawn as 1,024 cells. That's 4 kilobytes per vector, and it adds up fast across millions of chunks. Press Space. BBQ, Better Binary Quantization, keeps one bit per dimension, so the vector shrinks about 32 times: 128 bytes plus 14 bytes of corrective data. The dashed box is the space the float version used to need. The worry is accuracy, so press Space again. BBQ oversamples by 3: for the top 10 you asked for, it pulls 30 candidates using the tiny vectors, rescores them against the original vectors, and returns the best 10. Smaller vectors, same answers. And you don't turn it on: semantic_text quantizes dense embeddings to BBQ automatically.
