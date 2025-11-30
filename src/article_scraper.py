import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import time

# --- Configurazione del Progetto ---
# Percorsi relativi dalla cartella 'src'
INPUT_FILE = '../data/articoli_os.csv'
# Sovrascriviamo l'input file per mantenere un solo file aggiornato
OUTPUT_FILE = '../data/articoli_os.csv' 

# Importante: Selettore CSS specifico per il sito di Orizzonte Scuola
# Questo identifica l'area del contenuto dell'articolo. VA AGGIORNATO se si cambia sito.
ARTICLE_BODY_SELECTOR = 'div.entry-content' 

def scrape_article_content(url):
    """
    Scarica l'HTML della pagina e tenta di estrarre il testo principale.
    """
    # Ritarda il ciclo per non sovraccaricare il server (politica di buona educazione)
    time.sleep(1) 
    
    try:
        # User-Agent per simulare un browser ed evitare blocchi
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lancia un errore per risposte HTTP negative (4xx o 5xx)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Cerca l'elemento principale
        article_body = soup.select_one(ARTICLE_BODY_SELECTOR)
        
        if article_body:
            # Pulisce il testo: estrae il testo, elimina spazi extra
            content = article_body.get_text(separator='\n', strip=True)
            return content
        else:
            return "ERROR_SELECTOR_NOT_FOUND"
            
    except requests.exceptions.RequestException as e:
        # Codice errore per problemi di connessione o HTTP
        return f"ERROR_CONNECTION_{response.status_code if 'response' in locals() else 'TIMEOUT'}"
    except Exception as e:
        return f"ERROR_GENERIC_{type(e).__name__}"

def process_articles():
    """
    Carica il CSV, esegue lo scraping solo per gli articoli 'PENDING' e aggiorna il file.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"ERRORE: File di input non trovato: {INPUT_FILE}. Esegui prima rss_scraper.py.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Crea la colonna se non esiste (dovrebbe essere stata creata da rss_scraper.py)
    if 'Contenuto_Estratto_Completo' not in df.columns:
        df['Contenuto_Estratto_Completo'] = 'PENDING'
    
    # Filtra solo gli articoli che hanno ancora lo stato 'PENDING'
    # Questo è il cuore dell'ottimizzazione del workflow
    articles_to_process_indices = df[df['Contenuto_Estratto_Completo'] == 'PENDING'].index
    
    if articles_to_process_indices.empty:
        print("Nessun nuovo articolo da processare per il contenuto completo. Database aggiornato.")
        return
        
    print(f"Trovati {len(articles_to_process_indices)} articoli da processare...")

    processed_count = 0

    # Itera sugli indici degli articoli da processare
    for index in articles_to_process_indices:
        url = df.loc[index, 'Link']
        print(f"Scraping di: {df.loc[index, 'Titolo']}...")
        
        content = scrape_article_content(url)
        
        # Aggiorna il DataFrame originale
        df.loc[index, 'Contenuto_Estratto_Completo'] = content
        
        processed_count += 1
        
    # Salva il DataFrame aggiornato con tutti i dati (sovrascriviamo l'input)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Completato lo scraping. {processed_count} articoli processati. Dati aggiornati in: {OUTPUT_FILE}")


if __name__ == "__main__":
    process_articles()
