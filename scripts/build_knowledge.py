# scripts/build_knowledge.py
import json
import chromadb
from sentence_transformers import SentenceTransformer
import pickle

def chunk_text(text, chunk_size=500, overlap=50):
    """Dividi testo in chunk con overlap"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if len(chunk) > 100:  # Skip chunk troppo piccoli
            chunks.append(chunk)
    
    return chunks

def main():
    # Carica documenti processati
    with open('documents/index.json', 'r') as f:
        documents = json.load(f)
    
    # Inizializza ChromaDB
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(
        name="scuola_docs",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Modello embeddings
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    
    # Processa ogni documento
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    for doc in documents:
        text = doc.get('text', '')
        if not text or len(text) < 100:
            continue
        
        # Chunking
        chunks = chunk_text(text)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc['hash'][:12]}_chunk_{i}"
            
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadatas.append({
                'source_url': doc['url'],
                'title': doc['title'],
                'source_type': doc['source'],
                'date': doc['date'],
                'chunk_index': i
            })
    
    # Genera embeddings (in batch)
    print(f"Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=True)
    
    # Aggiungi a ChromaDB
    collection.add(
        ids=all_ids,
        embeddings=embeddings.tolist(),
        documents=all_chunks,
        metadatas=all_metadatas
    )
    
    # Salva tutto
    data = {
        'collection': collection,
        'model_name': 'paraphrase-multilingual-MiniLM-L12-v2',
        'total_docs': len(documents),
        'total_chunks': len(all_chunks)
    }
    
    with open('knowledge.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print(f"✅ Built knowledge base: {len(documents)} docs → {len(all_chunks)} chunks")

if __name__ == '__main__':
    main()
