import chromadb
from sentence_transformers import SentenceTransformer
import os

# --- Configurazione del Progetto ---
DB_PATH = '../chroma_db'
COLLECTION_NAME = 'normativa_scuola'
EMBEDDING_MODEL = 'all-MiniLM-L6-v2' 
K_RESULTS = 5 # Numero di blocchi di testo pertinenti da recuperare

def retrieve_and_augment(user_query, collection, model):
    """
    Esegue la ricerca RAG e crea il prompt potenziato per l'LLM.
    """
    
    print(f"\nRicerca in corso per: '{user_query}'")
    
    # 1. Vettorizza la query
    query_embedding = model.encode([user_query], convert_to_tensor=False).tolist()
    
    # 2. Cerca i risultati più simili (i blocchi di testo pertinenti)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=K_RESULTS,
        include=['documents', 'metadatas', 'distances'] # Include 'distances' per mostrare la pertinenza
    )
    
    # 3. Formatta il contesto per l'LLM
    context_list = []
    
    for doc, metadata, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
        source = metadata['title']
        link = metadata['link']
        
        # Un contesto chiaro e ben formattato è la chiave per un buon RAG
        context_list.append(f"### Fonte Recuperata: {source} (Distanza: {dist:.4f})\nContenuto: {doc}\n[Link per verifica: {link}]\n---\n")
        
    context_string = "\n".join(context_list)
    
    # 4. Crea il prompt finale
    SYSTEM_INSTRUCTIONS = (
        "Sei un assistente sindacale per la scuola. Rispondi alla DOMANDA UTENTE "
        "in modo professionale e conciso. Devi basare la tua risposta "
        "SOLO ed ESCLUSIVAMENTE sulle informazioni contenute nel CONTESTO fornito. "
        "Non inventare nulla. Se il contesto non contiene la risposta, indica che l'informazione non è disponibile tra le fonti attuali."
    )
    
    AUGMENTED_PROMPT = f"""
    {SYSTEM_INSTRUCTIONS}
    
    CONTESTO (Fornito dai documenti normativi):
    {context_string}
    
    DOMANDA UTENTE: {user_query}
    
    RISPOSTA (Basata solo sul contesto fornito):
    """
    
    print("\n--- PROMPT FINALE PRONTO PER IL TUO GEM ---")
    print(AUGMENTED_PROMPT)
    
    return AUGMENTED_PROMPT

if __name__ == "__main__":
    
    # Verifica esistenza DB
    if not os.path.exists(DB_PATH):
        print(f"ERRORE: Database vettoriale non trovato in {DB_PATH}. Esegui prima rag_ingest.py.")
    else:
        # Inizializzazione
        chroma_client = chromadb.PersistentClient(path=DB_PATH)
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        model = SentenceTransformer(EMBEDDING_MODEL)

        # Ciclo di interrogazione
        while True:
            domanda = input("\nInserisci la tua domanda sindacale (o 'esci' per terminare): ")
            if domanda.lower() == 'esci':
                break
            
            prompt_finale = retrieve_and_augment(domanda, collection, model)
            
            # --- SIMULAZIONE RISPOSTA LLM ---
            print("\n------------------------------------------------")
            print("SIMULAZIONE: Il tuo Gem (LLM) riceverebbe il prompt qui sopra e genererebbe la risposta.")
            # Qui dovresti inserire la chiamata all'API di Gemini con il prompt_finale
            print("------------------------------------------------")
