import feedparser
import pandas as pd
from datetime import datetime
import os

# --- Configurazione ---
RSS_URL = 'https://www.orizzontescuola.it/feed/'
OUTPUT_FILE = 'articoli_os.csv'
# Data minima di pubblicazione da considerare (es: solo articoli degli ultimi 30 giorni)
# Puoi cambiarla o caricarla dall'ultima esecuzione.
DATA_LIMITE = datetime(2025, 10, 1) # Esempio: articoli pubblicati dopo il 1° Ottobre 2025

def load_existing_data(file_path):
    """Carica i dati esistenti per evitare duplicati."""
    if os.path.exists(file_path):
        # Carica il CSV esistente
        df = pd.read_csv(file_path)
        # Converte la colonna 'Link' in un set per una ricerca veloce
        return set(df['Link'])
    return set()

def fetch_rss_feed(url, data_limite, existing_links):
    """Esegue il fetch del feed RSS e filtra i nuovi articoli."""
    
    print(f"Acquisizione feed da: {url}...")
    
    # 1. Parsing del feed
    feed = feedparser.parse(url)
    nuovi_articoli = []

    # 2. Iterazione sugli elementi (entries) del feed
    for entry in feed.entries:
        
        # 3. Estrazione delle informazioni base
        title = entry.get('title')
        link = entry.get('link')
        
        # 4. Gestione della data (converte da formato RSS a datetime standard)
        try:
            # entry.published_parsed è una tupla time.struct_time
            pub_date = datetime(*entry.published_parsed[:6])
        except Exception:
            # Fallback se la data non è ben formattata
            pub_date = datetime.now() 

        # 5. Filtro per data e duplicati
        if pub_date >= data_limite and link not in existing_links:
            nuovi_articoli.append({
                'Titolo': title,
                'Link': link,
                'Data_Pubblicazione': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
                'Contenuto_RAW': entry.get('summary', 'Non disponibile') # Testo iniziale (utile per il RAG)
                # Qui potresti aggiungere 'Contenuto_Estratto_Completo' dopo un eventuale secondo scraping (se necessario)
            })
            existing_links.add(link) # Aggiunge il link per evitare che venga riprocessato
            
    print(f"Trovati {len(nuovi_articoli)} nuovi articoli.")
    return nuovi_articoli

def save_new_data(new_data, file_path):
    """Appende i nuovi dati al file CSV esistente o ne crea uno nuovo."""
    if not new_data:
        return

    new_df = pd.DataFrame(new_data)
    
    if os.path.exists(file_path):
        # Carica il vecchio dataframe e concatena i nuovi dati
        existing_df = pd.read_csv(file_path)
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        print(f"Totale articoli salvati nel file: {len(updated_df)}")
    else:
        updated_df = new_df
        print(f"Creato nuovo file CSV con {len(updated_df)} articoli.")
        
    # Salva il file
    updated_df.to_csv(file_path, index=False)


if __name__ == "__main__":
    
    # 1. Carica i link già presenti per evitare duplicati
    existing_links = load_existing_data(OUTPUT_FILE)
    
    # 2. Esegue il fetch del feed
    data_trovati = fetch_rss_feed(RSS_URL, DATA_LIMITE, existing_links)
    
    # 3. Salva i nuovi dati
    save_new_data(data_trovati, OUTPUT_FILE)
    
    print("\nProcesso RSS completato.")
