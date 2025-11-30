import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import time

# --- Configurazione ---
INPUT_FILE = '../data/articoli_os.csv'
OUTPUT_FILE = '../data/articoli_os_completo.csv'

# Importante: Orizzonte Scuola ha una struttura standardizzata.
# Dobbiamo trovare il selettore CSS che contiene il testo dell'articolo.
# Dopo un'analisi rapida, sembra che l'articolo si trovi dentro un div con questa classe:
# Questo selettore è specifico per Orizzonte Scuola, andrà adattato per altri siti!
ARTICLE_BODY_SELECTOR = 'div.entry-content' 

def scrape_article_content(url):
    """
    Scarica l'HTML della pagina e tenta di estrarre il testo principale.
    """
    try:
        # User-Agent per simulare un browser ed evitare blocchi
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lancia un errore per risposte HTTP negative (4xx o 5xx)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Cerca l'elemento principale che contiene il corpo dell'articolo
        article_body = soup.select_one(ARTICLE_BODY_SELECTOR)
        
        if article_body:
            # Pulisce il testo: estrae il testo, elimina spazi extra e doppie interruzioni di riga
            content = article_body.get_text(separator='\n', strip=True)
            return content
        else:
            return "ERRORE: Selettore articolo non trovato (struttura cambiata?)"
            
    except requests.exceptions.RequestException as e:
        return f"ERRORE DI CONNESSIONE: {e}"
    except Exception as e:
        return f"ERRORE GENERICO: {e}"

def process_articles():
    """
    Carica il CSV, esegue lo scraping per gli articoli mancanti e salva il risultato.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"ERRORE: File di input non trovato: {INPUT_FILE}. Esegui prima rss_scraper.py.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Colonna che traccerà il contenuto completo.
    # Se non esiste, la crea (valore di default 'PENDING').
    if 'Contenuto_Estratto_Completo' not in df.columns:
        df['Contenuto_Estratto_Completo'] = 'PENDING'
    
    # Filtra solo gli articoli che devono essere processati
    articles_to_process = df[df['Contenuto_Estratto_Completo'] == 'PENDING']
    
    if articles_to_process.empty:
        print("Nessun nuovo articolo da processare per il contenuto completo.")
        return
        
    print(f"Trovati {len(articles_to_process)} articoli da processare...")

    # Variabile per tracciare i progressi
    processed_count = 0

    for index, row in articles_to_process.iterrows():
        url = row['Link']
        print(f"Scraping di: {row['Titolo']}...")
        
        content = scrape_article_content(url)
        
        # Aggiorna il DataFrame originale (NON la slice filtrata)
        df.loc[index, 'Contenuto_Estratto_Completo'] = content
        
        processed_count += 1
        
        # Ritarda il ciclo per non sovraccaricare il server (politica di buona educazione)
        time.sleep(1) # Aspetta 1 secondo tra una richiesta e l'altra

    # Salva il DataFrame aggiornato con tutti i dati in un nuovo file (o sovrascrivilo)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nCompletato lo scraping. {processed_count} articoli processati. Dati salvati in: {OUTPUT_FILE}")


if __name__ == "__main__":
    # Esegui i processi
    process_articles()
