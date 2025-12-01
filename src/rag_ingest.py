import pandas as pd
from sentence_transformers import SentenceTransformer
import chromadb
import uuid
import os

# --- Configurazione del Progetto ---
# Percorsi relativi dalla cartella 'src'
INPUT_FILE = '../data/articoli_os.csv'
DB_PATH = '../chroma_db' 
COLLECTION_NAME = 'normativa_scuola'

# Modello per creare gli embedding (buon compromesso tra performance e velocità)
EMBEDDING_MODEL = 'all-MiniLM-L6-v2' 

def simple_chunking(text, max_length=500):
    """Suddivide il testo in blocchi di dimensione massima specificata."""
    if not text or pd.isna(text):
        return []
        
    # Semplice suddivisione per parole per rispettare la lunghezza del chunk
    words = text.split()
    chunks = []
    current_chunk = []
    
    for word in words:
        current_chunk.append(word)
        # Se il blocco attuale supera la lunghezza massima, salva il blocco precedente
        if len(" ".join(current_chunk)) > max_length:
            chunks.append(" ".join(current_chunk[:-1]))
            current_chunk = [word]
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

def ingest_data():
    """Carica i dati, li vettorizza e li salva in ChromaDB."""
    
    if not os.path.exists(INPUT_FILE):
        print(f"ERRORE: File di input non trovato: {INPUT_FILE}. Esegui prima gli scraper.")
        return

    print("--- 1. Caricamento Dati ---")
    df = pd.read_csv(INPUT_FILE)
    
    # Filtra solo gli articoli che sono stati raschiati con successo
    df = df[~df['Contenuto_Estratto_Completo'].str.startswith('ERROR', na=False)]
    df = df.dropna(subset=['Contenuto_Estratto_Completo'])
    
    if df.empty:
        print("Nessun contenuto valido da elaborare. Controlla gli scraper.")
        return
    
    # 2. Inizializzazione Database e Modello
    print("--- 2. Inizializzazione ChromaDB e Modello ---")
    os.makedirs(DB_PATH, exist_ok=True) # Crea la cartella del DB se non esiste
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    
    # Rimuovi la vecchia collection e creane una nuova per un aggiornamento completo
    try:
        chroma_client.delete_collection(name=COLLECTION_NAME)
    except:
        pass # Ignora se la collection non esiste
        
    collection = chroma_client.create_collection(name=COLLECTION_NAME)
    
    # Inizializza il modello per gli embedding (scarica i pesi del modello se è la prima volta)
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    # 3. Preparazione dei dati per l'embedding
    documents = [] # I blocchi di testo (chunks)
    metadatas = [] # I metadati associati (Titolo, Link)
    ids = []       # ID univoci per ogni blocco
    
    print("--- 3. Chunking e Preparazione ---")
    
    for index, row in df.iterrows():
        title = row['Titolo']
        link = row['Link']
        content = row['Contenuto_Estratto_Completo']
        
        chunks = simple_chunking(content, max_length=400)
        
        for i, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({
                'title': title,
                'link': link,
                'chunk_index': i 
            })
            ids.append(str(uuid.uuid4()))

    # 4. Generazione Embedding e Inserimento
    print(f"--- 4. Generazione di {len(documents)} embedding... ---")
    
    # Generazione degli embedding
    embeddings = model.encode(documents, convert_to_tensor=False).tolist()
    
    # Aggiungi i dati alla collection
    collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print("\n✅ Ingestione RAG completata con successo.")
    print(f"Database salvato in: {DB_PATH}. Totale blocchi (chunks): {collection.count()}")

if __name__ == "__main__":
    ingest_data()
