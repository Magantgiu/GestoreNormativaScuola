"""
Script per scaricare documenti completi (PDF/HTML) dai link trovati
Posizione: /scripts/fetch_documents.py
"""

import json
import requests
from pathlib import Path
from urllib.parse import urlparse
import hashlib
from datetime import datetime

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    print("⚠️  PyPDF2 non installato. PDF non verranno processati.")
    PDF_AVAILABLE = False

from bs4 import BeautifulSoup


def download_pdf(url, save_dir):
    """Scarica PDF e estrae testo"""
    
    if not PDF_AVAILABLE:
        print(f"  ⚠️  Skip PDF (PyPDF2 mancante): {url}")
        return None
    
    try:
        print(f"  📄 Downloading PDF: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        # Genera nome file univoco
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        filename = f"{url_hash}.pdf"
        filepath = save_dir / filename
        
        # Salva PDF
        filepath.write_bytes(response.content)
        
        # Estrai testo
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = '\n'.join([page.extract_text() for page in reader.pages])
                
                return {
                    'filepath': str(filepath),
                    'text': text,
                    'pages': len(reader.pages),
                    'size_bytes': len(response.content),
                    'success': True
                }
        except Exception as e:
            print(f"    ⚠️  Errore estrazione testo: {e}")
            return {
                'filepath': str(filepath),
                'text': '',
                'pages': 0,
                'size_bytes': len(response.content),
                'success': False,
                'error': str(e)
            }
            
    except Exception as e:
        print(f"    ❌ Errore download: {e}")
        return None


def fetch_html_content(url):
    """Scarica pagina HTML ed estrae testo principale"""
    
    try:
        print(f"  🌐 Fetching HTML: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Rimuovi elementi non informativi
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
            element.decompose()
        
        # Cerca contenuto principale
        main_content = None
        
        # Prova diversi selettori comuni per contenuto principale
        selectors = [
            'article',
            'main',
            '[role="main"]',
            '.content',
            '.post-content',
            '.entry-content',
            '#content',
            '.main-content'
        ]
        
        for selector in selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Se non trovato, usa body
        if not main_content:
            main_content = soup.body or soup
        
        # Estrai testo
        text = main_content.get_text(separator='\n', strip=True)
        
        # Pulisci linee vuote multiple
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # Estrai titolo
        title = soup.title.string if soup.title else ''
        
        return {
            'text': text,
            'title': title,
            'size_chars': len(text),
            'success': True
        }
        
    except Exception as e:
        print(f"    ❌ Errore fetch: {e}")
        return None


def should_fetch_document(url, existing_ids):
    """Determina se un documento deve essere scaricato"""
    
    # Genera ID univoco per URL
    doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    
    # Skip se già processato
    if doc_id in existing_ids:
        return False, doc_id
    
    return True, doc_id


def fetch_all_documents(max_docs=100):
    """Scarica tutti i documenti dalla lista scraped"""
    
    print("📥 Avvio download documenti...\n")
    
    # Carica lista documenti scoperti
    input_file = Path('data') / 'scraped_documents.json'
    
    if not input_file.exists():
        print(f"❌ File non trovato: {input_file}")
        print("   Esegui prima: python scripts/scrape_sources.py")
        return []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = data.get('documents', [])
    print(f"📋 Trovati {len(documents)} documenti da processare")
    
    # Carica documenti già processati (se esistono)
    fetched_file = Path('data') / 'fetched_documents.json'
    existing_ids = set()
    
    if fetched_file.exists():
        with open(fetched_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            existing_ids = {doc['id'] for doc in existing.get('documents', [])}
        print(f"♻️  {len(existing_ids)} documenti già in cache\n")
    
    # Crea directory per documenti
    docs_dir = Path('documents')
    docs_dir.mkdir(exist_ok=True)
    
    pdf_dir = docs_dir / 'pdfs'
    pdf_dir.mkdir(exist_ok=True)
    
    # Processa documenti
    processed = []
    stats = {
        'total': len(documents),
        'fetched': 0,
        'skipped': 0,
        'failed': 0,
        'pdfs': 0,
        'html': 0
    }
    
    for i, doc in enumerate(documents[:max_docs], 1):
        url = doc['url']
        
        print(f"[{i}/{min(len(documents), max_docs)}] {doc['source']}")
        
        # Check se già processato
        should_fetch, doc_id = should_fetch_document(url, existing_ids)
        
        if not should_fetch:
            print(f"  ⏭️  Skip: già processato")
            stats['skipped'] += 1
            continue
        
        # Determina tipo documento
        is_pdf = url.lower().endswith('.pdf') or '.pdf' in url.lower()
        
        result = None
        
        if is_pdf:
            result = download_pdf(url, pdf_dir)
            if result:
                stats['pdfs'] += 1
        else:
            result = fetch_html_content(url)
            if result:
                stats['html'] += 1
        
        if result and result.get('success'):
            # Aggiungi metadati
            full_doc = {
                **doc,
                **result,
                'id': doc_id,
                'fetched_at': datetime.now().isoformat(),
                'document_type': 'pdf' if is_pdf else 'html'
            }
            
            processed.append(full_doc)
            existing_ids.add(doc_id)
            stats['fetched'] += 1
            
        else:
            stats['failed'] += 1
        
        print()
    
    # Carica documenti esistenti e aggiorna
    all_documents = []
    
    if fetched_file.exists():
        with open(fetched_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            all_documents = existing_data.get('documents', [])
    
    # Aggiungi nuovi documenti
    all_documents.extend(processed)
    
    # Salva risultati
    output = {
        'last_fetch': datetime.now().isoformat(),
        'stats': stats,
        'total_documents': len(all_documents),
        'documents': all_documents
    }
    
    with open(fetched_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Report
    print("=" * 60)
    print("📊 REPORT DOWNLOAD")
    print("=" * 60)
    print(f"Documenti totali:     {stats['total']}")
    print(f"Nuovi scaricati:      {stats['fetched']}")
    print(f"  - PDF:              {stats['pdfs']}")
    print(f"  - HTML:             {stats['html']}")
    print(f"Già in cache:         {stats['skipped']}")
    print(f"Falliti:              {stats['failed']}")
    print(f"Totale in database:   {len(all_documents)}")
    print(f"Output salvato in:    {fetched_file}")
    print("=" * 60)
    
    return all_documents


if __name__ == '__main__':
    # Limita a 100 documenti per run per evitare timeout
    fetch_all_documents(max_docs=100)
