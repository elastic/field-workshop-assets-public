# 05 - Text to vector

**Target: ~45 seconds. Space: fly the docs in, then drop in the query.**

Here is the query we'll follow, top left: "notify me when something goes wrong." On the right is the list of the 62 docs we'll search. Press Space and each one is embedded by Jina v5, turned into 1,024 numbers, and flies into the space, colored by topic. The view is a simplified projection of those real vectors, and it keeps slowly turning. Security docs cluster together, and so do search and vector docs. Close in space means close in meaning. Press Space once more and the big blue dot, our query, drops in. It gets embedded by the same model, and bold blue lines draw to its five nearest docs with their cosine score. The Watcher alerting doc is on top at 0.51. Elasticsearch reports the score as one plus cosine, divided by two, so 0.51 shows up as about 0.75 in the labs.

*Lines look long because we squashed 1,024 dimensions into three; the cosine in the list is the truth.*
