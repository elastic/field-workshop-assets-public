# 16 - Same model, same question, only the retrieval changed

**Target: ~55 seconds. Space: the good answer, the bad answer, then the punchline.**

We ran this today on the workshop index with the Haiku completion endpoint. The question: how does ILM move data through hot, warm, and cold phases? Two runs, same model, same prompt. On the left we retrieved doc-017, the ILM overview. Press Space: a grounded answer with hot, warm, and cold, and the actual thresholds. On the right we forced retrieval onto an off-topic doc, the 9.x what's new page. Press Space: "I do not have enough information." That is the model behaving well, by the way. It didn't make something up. It just had nothing to work with. Press Space for the point: the model didn't get dumber, the retrieval got worse. In Lab 4 you'll do exactly this experiment yourself.

*Good answer is trimmed to the key points. Model and run are in the small print.*
