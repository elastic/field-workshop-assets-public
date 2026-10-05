# 05 · Text to vector (~75 sec)

**Click:** "Embed & ingest 62 docs" (wait ~6 sec), then the "Search" button. Drag the 3D view if you want to show depth.

These are the 62 docs we'll search, colored by topic. Click Embed and each doc goes through Jina v5, which turns the text into 1,024 numbers; the 3D view is a simplified projection of those real vectors. Notice that security docs cluster together, search and vector docs cluster together. Close in space means close in meaning. Now click Search with "notify me when something goes wrong." The query gets embedded by the same model, and the five nearest docs light up with their cosine score. The Watcher alerting doc is on top at 0.51. That cosine number is the `_score` you will see in the labs. *The lines look long in 3D because we squashed 1,024 dimensions into three; the cosine in the list is the truth.*
