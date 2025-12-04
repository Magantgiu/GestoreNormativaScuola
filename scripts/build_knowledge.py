"""
Script per costruire il database ChromaDB dal contenuto scaricato
Posizione: /scripts/build_knowledge.py
"""

import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
import pickle
from datetime import datetime


def chunk_text(text, chunk_size=800, overlap=100):
    """
    Divide il testo in chunk con overlap
    
    Args:
        text: testo da dividere
        chunk_size: dimensione chunk in parole
        overlap: sovrapposizione tra chunk consecutivi
    
    Returns:
        lista di chunk
    """
    if not text or len(text.strip()) < 50:
        return []
    
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        
        # Skip chunk troppo piccoli
        if len(chunk.split()) > 20:  # Almeno 20 parole
            chunks.append(chunk)
    
    return chunks


def build_rag_database():
    """Costruisce il database ChromaDB dai documenti fetchati"""
    
    print("🧠 Costruzione Knowledge Base RAG...\n")
    
    # Carica documenti fetchati
    input_file = Path('data') / 'fetched_documents.json'
    
    if not input_file.exists():
        print(f"❌ File non trovato: {input_file}")
        print("   Esegui prima:")
        print("   1. python scripts/scrape_sources.py")
        print("   2. python scripts/fetch_documents.py")
        return None
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = data.get('documents', [])
    
    if not documents:
        print("❌ Nessun documento trovato")
        return None
    
    print(f"📚 Caricati {len(documents)} documenti\n")
    
    # Inizializza ChromaDB
    print("🔧 Inizializzazione ChromaDB...")
    
    # Rimuovi DB esistente se presente
    chroma_path = Path('./chroma_db')
    if chroma_path.exists():
        import shutil
        shutil.rmtree(chroma_path)
        print("   ♻️  DB esistente rimosso")
    
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # Crea collection
    collection = client.get_or_create_collection(
        name="scuola_docs",
        metadata={"hnsw:space": "cosine"}
    )
    
    print("   ✅ Collection creata\n")
    
    # Carica modello embeddings
    print("🤖 Caricamento modello embeddings...")
    model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    model = SentenceTransformer(model_name)
    print(f"   ✅ Modello caricato: {model_name}\n")
    
    # Processa documenti e crea chunk
    print("✂️  Chunking documenti...")
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    stats = {
        'total_docs': len(documents),
        'processed_docs': 0,
        'total_chunks': 0,
        'skipped_docs': 0
    }
    
    for i, doc in enumerate(documents, 1):
        text = doc.get('text', '')
        
        # Skip documenti senza testo
        if not text or len(text.strip()) < 100:
            print(f"  [{i}/{len(documents)}] ⏭️  Skip (testo insufficiente): {doc.get('title', 'N/A')[:50]}")
            stats['skipped_docs'] += 1
            continue
        
        print(f"  [{i}/{len(documents)}] ✂️  {doc.get('source', 'N/A')} - {len(text)} chars")
        
        # Crea chunk
        chunks = chunk_text(text)
        
        if not chunks:
            stats['skipped_docs'] += 1
            continue
        
        # Aggiungi ogni chunk
        for j, chunk in enumerate(chunks):
            chunk_id = f"{doc['id']}_chunk_{j}"
            
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            
            # Metadata per CitedAnswer
            metadata = {
                'source_url': doc['url'],
                'title': doc.get('title', '')[:200],  # Limita lunghezza
                'source': doc.get('source', ''),
                'date': doc.get('date', ''),
                'document_type': doc.get('document_type', 'unknown'),
                'chunk_index': j,
                'total_chunks': len(chunks)
            }
            
            all_metadatas.append(metadata)
        
        stats['processed_docs'] += 1
        stats['total_chunks'] += len(chunks)
    
    print(f"\n   ✅ Creati {stats['total_chunks']} chunk da {stats['processed_docs']} documenti\n")
    
    if not all_chunks:
        print("❌ Nessun chunk creato")
        return None
    
    # Genera embeddings
    print("🔢 Generazione embeddings...")
    print(f"   (questo può richiedere alcuni minuti per {len(all_chunks)} chunk)")
    
    embeddings = model.encode(
        all_chunks,
        show_progress_bar=True,
        batch_size=32
    )
    
    print("   ✅ Embeddings generati\n")
    
    # Aggiungi a ChromaDB
    print("💾 Popolamento database ChromaDB...")
    
    # ChromaDB ha un limite di ~40k documenti per batch
    batch_size = 5000
    
    for i in range(0, len(all_chunks), batch_size):
        end_idx = min(i + batch_size, len(all_chunks))
        
        print(f"   Batch {i//batch_size + 1}: chunk {i+1}-{end_idx}")
        
        collection.add(
            ids=all_ids[i:end_idx],
            embeddings=embeddings[i:end_idx].tolist(),
            documents=all_chunks[i:end_idx],
            metadatas=all_metadatas[i:end_idx]
        )
    
    print("   ✅ Database popolato\n")
    
    # Verifica
    count = collection.count()
    print(f"✅ Verifica: {count} documenti in ChromaDB\n")
    
    # Salva tutto in pickle per Hugging Face Space
    print("📦 Creazione knowledge.pkl...")
    
    knowledge_data = {
        'collection_name': 'scuola_docs',
        'model_name': model_name,
        'created_at': datetime.now().isoformat(),
        'stats': {
            **stats,
            'total_chunks_in_db': count
        },
        # Salviamo i dati necessari per ricostruire
        'documents': all_chunks,
        'metadatas': all_metadatas,
        'embeddings': embeddings.tolist(),
        'ids': all_ids
    }
    
    with open('knowledge.pkl', 'wb') as f:
        pickle.dump(knowledge_data, f)
    
    # Calcola dimensione
    kb_size = Path('knowledge.pkl').stat().st_size / (1024 * 1024)
    
    print(f"   ✅ knowledge.pkl creato ({kb_size:.1f} MB)\n")
    
    # Report finale
    print("=" * 60)
    print("📊 KNOWLEDGE BASE COMPLETATA")
    print("=" * 60)
    print(f"Documenti processati: {stats['processed_docs']}/{stats['total_docs']}")
    print(f"Documenti skippati:   {stats['skipped_docs']}")
    print(f"Chunk totali:         {stats['total_chunks']}")
    print(f"Dimensione DB:        {kb_size:.1f} MB")
    print(f"Modello embeddings:   {model_name}")
    print(f"File output:          knowledge.pkl")
    print("=" * 60)
    print("\n✅ Pronto per il deploy su Hugging Face Space!")
    
    return knowledge_data


if __name__ == '__main__':
    build_rag_database()
