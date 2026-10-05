# 17 - Agents use your search as a tool

**Target: ~50 seconds. Space: hop 1, then hop 2 and the answer. The run is illustrative.**

The query you just saw is also the tool for an agent. In Agent Builder the tool is the same FORK and FUSE ES|QL, registered as search-workshop-docs-hybrid. The agent decides when to call it, and it can call it more than once. Ask: my container keeps dying with exit code 137, why, and what JVM settings should I change? Press Space: hop 1, the agent searches for the cause and finds the container exit codes doc, out of memory. Press Space: hop 2, it searches again for the fix and finds the JVM heap and memory settings. Then it answers from both. A tip for Lab 4: Agent Builder auto-loads the Diagnose and Fix skill, and that skill is what drives the second search, so the model you pick doesn't matter. Just watch for two search-workshop-docs-hybrid tool calls: cause, then fix.
