import json, os, urllib.request
ES=os.environ["ES_ENDPOINT"].rstrip("/"); KEY=os.environ["ES_API_KEY"]
CID=".anthropic-claude-4.5-haiku-completion"
def esql(q, params):
    r=urllib.request.Request(ES+"/_query",method="POST",data=json.dumps({"query":q,"params":params}).encode(),
        headers={"Authorization":f"ApiKey {KEY}","Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(r,timeout=180).read().decode(),strict=False)
    cols=[c["name"] for c in d["columns"]]; return [dict(zip(cols,v)) for v in d["values"]]
def run(question, bad):
    filt='WHERE trap_type == "version-specific" AND ' if bad else "WHERE "
    q=("FROM aiewf-workshop-docs METADATA _score, _id, _index\n"
       f"| FORK ( {filt}MATCH(body, ?q) | SORT _score DESC | LIMIT 50 )\n"
       f"       ( {filt}MATCH(body_semantic, ?q) | SORT _score DESC | LIMIT 50 )\n"
       "| FUSE | SORT _score DESC | LIMIT 1\n"
       '| EVAL prompt = CONCAT("Answer the question using ONLY the document below. If it lacks the answer, say you do not have enough information. Title: ", title, " === Document: ", body, " === Question: ", ?q)\n'
       f'| COMPLETION answer = prompt WITH {{"inference_id": "{CID}"}}\n| KEEP id, title, answer')
    return esql(q,[{"q":question}])[0]
# no-retrieval baseline: model alone, a question about THIS corpus' facts
def bare(question):
    q=('ROW prompt = ?q | COMPLETION answer = prompt WITH {"inference_id": "%s"} | KEEP answer' % CID)
    return esql(q,[{"q":question}])[0]
question="How does Index Lifecycle Management move data through hot, warm, and cold phases?"
out={"question":question,"model":CID,"good":run(question,False),"bad":run(question,True)}
json.dump(out,open(os.path.join(os.path.dirname(__file__),"lab4_good_bad.json"),"w"),indent=1)
for k in ("good","bad"): print("==",k,out[k]["id"],out[k]["title"]); print(out[k]["answer"][:900]); print()
