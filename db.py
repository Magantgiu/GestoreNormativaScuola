import pickle, chromadb, os
from chromadb.config import Settings

PKL = "knowledge.pkl"

def save(coll):
    with open(PKL, "wb") as f:
        pickle.dump(coll.get(), f)

def load():
    client = chromadb.Client(Settings(anonymized_telemetry=False))
    if not os.path.exists(PKL):
        return client.get_or_create_collection("scuola")
    with open(PKL, "rb") as f:
        data = pickle.load(f)
    coll = client.get_or_create_collection("scuola")
    if data["ids"]:
        coll.add(
            documents=data["documents"],
            metadatas=data["metadatas"],
            ids=data["ids"],
            embeddings=data["embeddings"],
        )
    return coll
