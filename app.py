"""
Interfaccia Gradio per il bot RAG scuola
Posizione: /app.py (root del repository)
"""

import gradio as gr
import pickle
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime


# Configurazione globale
MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
KNOWLEDGE_FILE = 'knowledge.pkl'


class RAGBot:
    """Bot RAG con ChromaDB locale"""
    
    def __init__(self):
        self.model = None
        self.collection = None
        self.loaded = False
        
    def load_knowledge_base(self):
        """Carica il database da knowledge.pkl"""
        
        if not Path(KNOWLEDGE_FILE).exists():
            raise FileNotFoundError(
                f"❌ File {KNOWLEDGE_FILE} non trovato!\n"
                "Esegui prima gli script di scraping e build."
            )
        
        print("📂 Caricamento knowledge base...")
        
        with open(KNOWLEDGE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Carica modello embeddings
        print(f"🤖 Caricamento modello: {MODEL_NAME}")
        self.model = SentenceTransformer(MODEL_NAME)
        
        # Ricostruisci ChromaDB in memoria
        print("🗄️  Ricostruzione ChromaDB...")
        client = chromadb.EphemeralClient()  # In memoria (più veloce)
        
        self.collection = client.create_collection(
            name="scuola_docs",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Popola collection
        self.collection.add(
            ids=data['ids'],
            embeddings=data['embeddings'],
            documents=data['documents'],
            metadatas=data['metadatas']
        )
        
        # Stats
        total_docs = self.collection.count()
        created_at = data.get('created_at', 'N/A')
        
        print(f"✅ Knowledge base caricata:")
        print(f"   - Documenti: {total_docs}")
        print(f"   - Creata il: {created_at}")
        
        self.loaded = True
        
        return f"✅ Caricati {total_docs} documenti"
    
    def retrieve(self, query, top_k=5):
        """Recupera documenti rilevanti"""
        
        if not self.loaded:
            return []
        
        # Genera embedding della query
        query_embedding = self.model.encode(query).tolist()
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Formatta risultati
        documents = []
        
        for i in range(len(results['ids'][0])):
            doc = {
                'id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None
            }
            documents.append(doc)
        
        return documents
    
    def generate_answer(self, query, documents):
        """Genera risposta citando le fonti"""
        
        if not documents:
            return (
                "❌ Non ho trovato informazioni rilevanti nella knowledge base.\n\n"
                "Prova a riformulare la domanda o chiedi su un argomento diverso."
            ), []
        
        # Costruisci contesto
        context_parts = []
        sources = []
        
        for i, doc in enumerate(documents[:3], 1):  # Top 3
            metadata = doc['metadata']
            
            context_parts.append(f"[Fonte {i}] {doc['text'][:500]}...")
            
            sources.append({
                'title': metadata.get('title', 'N/A'),
                'url': metadata.get('source_url', ''),
                'source': metadata.get('source', 'N/A'),
                'date': metadata.get('date', 'N/A')
            })
        
        context = "\n\n".join(context_parts)
        
        # Risposta strutturata (senza LLM esterno - risposta diretta)
        answer_parts = [
            f"📚 **Informazioni trovate sulla tua domanda:** \"{query}\"\n",
            "---\n"
        ]
        
        # Mostra top 3 risultati
        for i, doc in enumerate(documents[:3], 1):
            metadata = doc['metadata']
            text_preview = doc['text'][:400].strip()
            
            answer_parts.append(f"**{i}. {metadata.get('title', 'Documento')}**")
            answer_parts.append(f"   *Fonte: {metadata.get('source', 'N/A')}*")
            answer_parts.append(f"   *Data: {metadata.get('date', 'N/A')}*\n")
            answer_parts.append(f"   {text_preview}...\n")
            answer_parts.append(f"   🔗 [Leggi tutto]({metadata.get('source_url', '#')})\n")
        
        answer_parts.append("\n---")
        answer_parts.append("💡 *Clicca sui link per leggere i documenti completi.*")
        
        answer = "\n".join(answer_parts)
        
        return answer, sources


# Inizializza bot globale
bot = RAGBot()


def chat(message, history):
    """Funzione principale di chat"""
    
    if not bot.loaded:
        return "⚠️ Knowledge base non caricata. Premi 'Carica Knowledge Base' prima di iniziare."
    
    if not message or len(message.strip()) < 3:
        return "⚠️ Per favore scrivi una domanda più specifica."
    
    # Retrieve documenti
    documents = bot.retrieve(message, top_k=5)
    
    # Genera risposta
    answer, sources = bot.generate_answer(message, documents)
    
    return answer


def load_kb_button():
    """Carica knowledge base al click"""
    try:
        result = bot.load_knowledge_base()
        return f"✅ {result}"
    except Exception as e:
        return f"❌ Errore: {str(e)}"


# Interfaccia Gradio
with gr.Blocks(
    title="🎓 Bot Scuola RAG",
    theme=gr.themes.Soft()
) as demo:
    
    gr.Markdown("""
    # 🎓 Bot Scuola RAG - Assistente Normativa
    
    **Fonti monitorate:**
    - 📜 Ministero dell'Istruzione e del Merito (normativa)
    - 📰 Orizzonte Scuola (news insegnanti, ATA, mobilità)
    - 🏢 CISL Scuola Roma e Rieti
    - 🔴 FLC CGIL
    - 🏛️ USR Lazio
    
    **Aggiornamento automatico ogni 6 ore via GitHub Actions**
    """)
    
    with gr.Row():
        load_btn = gr.Button("🔄 Carica Knowledge Base", variant="primary")
        status_text = gr.Textbox(
            label="Status",
            value="⏳ Premi 'Carica Knowledge Base' per iniziare",
            interactive=False
        )
    
    load_btn.click(
        fn=load_kb_button,
        outputs=status_text
    )
    
    gr.Markdown("---")
    
    chatbot = gr.ChatInterface(
        fn=chat,
        examples=[
            "Quali sono le ultime circolari del MIM?",
            "Novità su concorsi e reclutamento docenti",
            "Informazioni su mobilità ATA 2024",
            "Comunicazioni USR Lazio recenti",
            "Notizie sui contratti scuola",
        ],
        title="💬 Fai una domanda",
        description="Chiedi informazioni su normativa, concorsi, mobilità, contratti...",
        retry_btn=None,
        undo_btn=None,
        clear_btn="🗑️ Pulisci chat"
    )
    
    gr.Markdown("""
    ---
    ### ℹ️ Come funziona
    
    1. Il bot cerca nella knowledge base i documenti più rilevanti
    2. Ti mostra i top 3 risultati con estratti
    3. Ogni risposta include link ai documenti originali
    4. **Zero allucinazioni**: solo informazioni presenti nei documenti
    
    ### 🔧 Tecnologie
    - **RAG**: ChromaDB + Sentence Transformers
    - **Fonti**: RSS feeds + web scraping
    - **Update**: Automatico ogni 6h (GitHub Actions)
    - **Costo**: €0/mese (100% gratuito)
    
    ---
    *Ultimo aggiornamento: controllato automaticamente ogni 6 ore*
    """)


# Avvio
if __name__ == "__main__":
    demo.launch()
