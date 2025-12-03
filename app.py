import streamlit as st, chromadb, os
from sentence_transformers import SentenceTransformer
from db import load

st.set_page_config(page_title="Bot Scuola RAG", layout="centered")
st.title("🎓 Chatbot Normativa Scolastica (RAG)")

@st.cache_resource
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2"), load()

model, coll = get_model()

query = st.text_input("Fai la tua domanda:", placeholder="Es: ultima circolare USR Lazio supplenze")
if query:
    emb = model.encode(query).tolist()
    res = coll.query(query_embeddings=[emb], n_results=5, include=["documents", "metadatas"])
    context = "\n".join(res["documents"][0])
    sources = [m["source"] for m in res["metadatas"][0]]
    st.markdown("**Risposta:**")
    st.write(context)
    st.markdown("**Fonti:**")
    for s in sources:
        st.write("- " + s)
