"""Gather real corpus data for the briefing deck's interactive slides.

Outputs briefing-data/data.json:
  docs:    62 docs, each with a 3D PCA point and a cluster
  chunks:  ~250 sentence chunks, each with a 3D point, a cluster, and the doc id
  centroids, edges (kNN graph, computed in the full 1024-d space)
  queries: per query, its 3D point, its nearest docs, BM25 top 5, semantic top 5,
           and RRF top 5 with real scores
  idf:     document frequency per term for the BM25 slide
"""
import json, os, re, urllib.request
import numpy as np

ES = os.environ["ES_ENDPOINT"].rstrip("/")
KEY = os.environ["ES_API_KEY"]
OUT = os.path.join(os.path.dirname(__file__), "data.json")
EMB = ".jina-embeddings-v5-text-small"


def req(method, path, body=None):
    r = urllib.request.Request(ES + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": f"ApiKey {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode(), strict=False)


def embed(texts):
    out = []
    for i in range(0, len(texts), 16):
        r = req("POST", f"/_inference/text_embedding/{EMB}", {"input": texts[i:i + 16]})
        out += [e["embedding"] for e in r["text_embedding"]]
    v = np.array(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def esql(q):
    r = req("POST", "/_query", {"query": q})
    cols = [c["name"] for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["values"]]


# ── docs ──
hits = req("POST", "/aiewf-workshop-docs/_search",
           {"size": 100, "_source": ["id", "title", "body", "product"], "sort": [{"id": "asc"}]})["hits"]["hits"]
docs = [h["_source"] for h in hits]
print("docs", len(docs))

# ── chunks: ~3 sentences each ──
chunks = []
for d in docs:
    sents = re.split(r"(?<=[.!?])\s+", d["body"].strip())
    for i in range(0, len(sents), 3):
        t = " ".join(sents[i:i + 3]).strip()
        if len(t) > 40:
            chunks.append({"doc": d["id"], "text": t[:300]})
print("chunks", len(chunks))

D = embed([f'{d["title"]}. {d["body"][:2000]}' for d in docs])
C = embed([c["text"] for c in chunks])

QUERIES = ["securing cluster traffic", "exit code 137", "notify me when something goes wrong",
           "how do I make search results more relevant"]
Q = embed(QUERIES)

# ── PCA on chunks + docs together, so they share one space ──
allv = np.vstack([C, D, Q])
mu = allv[:len(C) + len(D)].mean(0)
_, _, Vt = np.linalg.svd(allv[:len(C) + len(D)] - mu, full_matrices=False)
P = (allv - mu) @ Vt[:3].T
P = P / np.abs(P[:len(C) + len(D)]).max(0)  # scale to [-1, 1] per axis
Pc, Pd, Pq = P[:len(C)], P[len(C):len(C) + len(D)], P[len(C) + len(D):]

# ── k-means (k=7) on chunk vectors in full dim, cosine ──
rng = np.random.default_rng(7)
K = 7
cent = C[rng.choice(len(C), K, replace=False)]
for _ in range(50):
    lab = (C @ cent.T).argmax(1)
    cent = np.array([C[lab == k].mean(0) if (lab == k).any() else cent[k] for k in range(K)])
    cent /= np.linalg.norm(cent, axis=1, keepdims=True)
lab = (C @ cent.T).argmax(1)
dlab = (D @ cent.T).argmax(1)
cent3 = np.array([Pc[lab == k].mean(0) for k in range(K)])

# ── kNN edges (k=4) among chunks for the HNSW graph ──
S = C @ C.T
np.fill_diagonal(S, -1)
edges = set()
for i in range(len(C)):
    for j in np.argsort(-S[i])[:4]:
        edges.add(tuple(sorted((int(i), int(j)))))

# ── per query: nearest docs + real retrieval results ──
qout = []
for qi, q in enumerate(QUERIES):
    sims = D @ Q[qi]
    near = [{"id": docs[j]["id"], "title": docs[j]["title"], "cos": round(float(sims[j]), 4)}
            for j in np.argsort(-sims)[:5]]
    ql = q.replace('"', '\\"')
    bm25 = esql(f'FROM aiewf-workshop-docs METADATA _score | WHERE MATCH(title, "{ql}", {{"boost":3}}) OR MATCH(body, "{ql}") '
                f'| SORT _score DESC | LIMIT 5 | KEEP id, title, _score')
    sem = esql(f'FROM aiewf-workshop-docs METADATA _score | WHERE MATCH(body_semantic, "{ql}") '
               f'| SORT _score DESC | LIMIT 5 | KEEP id, title, _score')
    rrf = esql(f'FROM aiewf-workshop-docs METADATA _score, _id, _index '
               f'| FORK ( WHERE MATCH(body, "{ql}") | SORT _score DESC | LIMIT 50 ) '
               f'( WHERE MATCH(body_semantic, "{ql}") | SORT _score DESC | LIMIT 50 ) '
               f'| FUSE | SORT _score DESC | LIMIT 5 | KEEP id, title, _score')
    qout.append({"q": q, "xyz": [round(float(x), 4) for x in Pq[qi]], "nearest_docs": near,
                 "bm25": bm25, "semantic": sem, "rrf": rrf})

# ── document frequency for the BM25 / IDF slide ──
def df(term):
    t = term.lower()
    return sum(1 for d in docs if re.search(r"\b" + re.escape(t) + r"\b", (d["title"] + " " + d["body"]).lower()))

idf_terms = ["exit", "code", "137", "the", "cluster", "traffic", "securing", "notify", "alert"]
N = len(docs)
idf = {t: {"df": df(t), "idf": round(float(np.log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))), 3)} for t in idf_terms}

r4 = lambda v: [round(float(x), 4) for x in v]
json.dump({
    "N": N,
    "docs": [{"id": d["id"], "title": d["title"], "product": d.get("product"), "xyz": r4(Pd[i]), "cluster": int(dlab[i])}
             for i, d in enumerate(docs)],
    "chunks": [{"doc": c["doc"], "xyz": r4(Pc[i]), "cluster": int(lab[i])} for i, c in enumerate(chunks)],
    "centroids": [r4(c) for c in cent3],
    "edges": sorted(edges),
    "queries": qout,
    "idf": idf,
}, open(OUT, "w"), indent=1)
print("wrote", OUT, "edges", len(edges))
for q in qout:
    print("\n##", q["q"])
    for k in ("bm25", "semantic", "rrf"):
        print(" ", k, [(r["id"], round(r["_score"], 3)) for r in q[k]])
print(json.dumps(idf))
