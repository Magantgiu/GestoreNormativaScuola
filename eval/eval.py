import pandas as pd, os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import load
from sentence_transformers import SentenceTransformer

QA = [
    {"q": "Qual è l'ultima circolare USR Lazio sulle supplenze?", "kws": ["supplenze", "USR Lazio"]},
    {"q": "Quando è stato pubblicato l'ultimo bando MIM per i concorsi docenti?", "kws": ["bando", "concorso", "MIM"]},
    {"q": "Cosa prevede la legge sullo smart working per i docenti?", "kws": ["smart working", "docenti"]},
]

model = SentenceTransformer("all-MiniLM-L6-v2")
coll = load()

def eval():
    ok = 0
    for t in QA:
        emb = model.encode(t["q"]).tolist()
        res = coll.query(query_embeddings=[emb], n_results=3, include=["documents"])
        ans = " ".join(res["documents"][0]).lower()
        if any(k.lower() in ans for k in t["kws"]):
            ok += 1
    print(f"Allucinazione rate: {(1-ok/len(QA))*100:.1f} %")

if __name__ == "__main__":
    eval()
