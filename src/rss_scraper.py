import feedparser
import pandas as pd
from datetime import datetime
import os

# --- Configurazione del Progetto ---
# Il percorso relativo punta alla cartella 'data' (../data/) dalla cartella 'src'
OUTPUT_FILE = '../data/articoli_os.csv'
RSS_URL = 'https://www.orizzontescuola.it/feed/'
# Data minima per iniziare l'acquisizione. Puoi impostarla su una data passata
# o, in un sistema più avanzato, leggerla da un file di configurazione.
DATA_LIMITE_START = datetime(2024, 1, 1) # Articoli dal 1 Gennaio 2024

def load_existing_data(file_path):
    """Carica i dati esistenti per evitare duplicati e traccia l'ultimo link processato."""
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            # Restituisce un set di link già presenti per una ricerca veloce
            return set(df['Link'])
        except Exception as e:
            print(f"Attenzione: Errore nel caricamento di {file_path}. Inizio da zero. Errore: {e}")
            return set()
    return set()

def fetch_rss_feed(url, data_limite, existing_links):
    """Esegue il fetch del feed RSS e filtra i nuovi articoli."""
    
    print(f"Acquisizione feed da: {url}...")
    feed = feedparser.parse(url)
    nuovi_articoli = []
    
    # Se la data è troppo vecchia, potresti non voler scaricare tutto l'archivio
    if not feed.entries:
        print("Nessuna entry trovata nel feed.")
        return []

    for entry in feed.entries:
        
        title = entry.get('title', 'Titolo Sconosciuto')
        link = entry.get('link', None)
        
        # Ignora se manca il link o se è già stato processato
        if not link or link in existing_links:
            continue
            
        # Gestione della data 
        try:
            pub_date = datetime(*entry.published_parsed[:6])
        except Exception:
            # Fallback sicuro se la data non è valida o assente nel feed
            pub_date = datetime.now() 

        # Filtro per data (solo articoli recenti)
        if pub_date >= data_limite:
            nuovi_articoli.append({
                'Titolo': title,
                'Link': link,
                'Data_Pubblicazione': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
                # Aggiunge uno stato iniziale per il prossimo script (article_scraper)
                'Contenuto_RAW': entry.get('summary', 'Non disponibile'), 
                'Contenuto_Estratto_Completo': 'PENDING' 
            })
            existing_links.add(link) # Aggiunge il link per prevenire duplicati nella run corrente
            
    print(f"Trovati {len(nuovi_articoli)} nuovi articoli.")
    return nuovi_articoli

def save_new_data(new_data, file_path):
    """Appende i nuovi dati al file CSV esistente o ne crea uno nuovo."""
    
    # Assicura che la directory di output esista
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    if not new_data:
        print("Nessun dato nuovo da salvare.")
        return

    new_df = pd.DataFrame(new_data)
    
    if os.path.exists(file_path):
        # Carica il vecchio dataframe e concatena i nuovi dati
        existing_df = pd.read_csv(file_path)
        # Rimuove duplicati che potrebbero essersi insinuati
        updated_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=['Link'])
        print(f"Totale articoli salvati nel file: {len(updated_df)}")
    else:
        updated_df = new_df.drop_duplicates(subset=['Link'])
        print(f"Creato nuovo file CSV con {len(updated_df)} articoli.")
        
    # Salva il file
    updated_df.to_csv(file_path, index=False)


if __name__ == "__main__":
    
    # 1. Carica i link già presenti 
    existing_links = load_existing_data(OUTPUT_FILE)
    
    # 2. Esegue il fetch del feed
    data_trovati = fetch_rss_feed(RSS_URL, DATA_LIMITE_START, existing_links)
    
    # 3. Salva i nuovi dati
    save_new_data(data_trovati, OUTPUT_FILE)
    
    print("\nProcesso RSS completato.")
