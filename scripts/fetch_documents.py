# scripts/fetch_documents.py
import json
import requests
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import PyPDF2
from bs4 import BeautifulSoup

def download_pdf(url, save_dir):
    """Scarica e salva PDF"""
    response = requests.get(url, timeout=30)
    
    # Nome file da URL
    filename = urlparse(url).path.split('/')[-1]
    if not filename.endswith('.pdf'):
        filename += '.pdf'
    
    filepath = save_dir / filename
    filepath.write_bytes(response.content)
    
    # Estrai testo
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = '\n'.join([page.extract_text() for page in reader.pages])
    
    return {
        'filepath': str(filepath),
        'text': text,
        'pages': len(reader.pages)
    }

def fetch_html_content(url):
    """Scarica e estrai testo da HTML"""
    response = requests.get(url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Rimuovi script/style
    for script in soup(['script', 'style', 'nav', 'footer']):
        script.decompose()
    
    # Estrai testo pulito
    text = soup.get_text(separator='\n', strip=True)
    
    return {
        'text': text,
        'title': soup.title.string if soup.title else ''
    }

def main():
    # Carica URL da processare
    with open('discovered_urls.json', 'r') as f:
        urls = json.load(f)
    
    # Crea directories
    docs_dir = Path('documents')
    docs_dir.mkdir(exist_ok=True)
    
    processed = []
    
    for item in urls:
        url = item['url']
        print(f"Fetching: {url}")
        
        try:
            # Determina tipo documento
            if url.endswith('.pdf') or 'pdf' in url.lower():
                source = urlparse(url).netloc.replace('www.', '')
                save_dir = docs_dir / source
                save_dir.mkdir(exist_ok=True)
                
                result = download_pdf(url, save_dir)
                
                # Salva metadata
                metadata = {
                    **item,
                    **result,
                    'hash': hashlib.sha256(result['text'].encode()).hexdigest()
                }
                
            else:  # HTML
                result = fetch_html_content(url)
                metadata = {
                    **item,
                    **result,
                    'hash': hashlib.sha256(result['text'].encode()).hexdigest()
                }
            
            # Salva metadata
            meta_file = docs_dir / f"{metadata['hash'][:12]}_meta.json"
            with open(meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            processed.append(metadata)
            
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
    
    # Salva indice
    with open('documents/index.json', 'w') as f:
        json.dump(processed, f, indent=2)
    
    print(f"✅ Fetched {len(processed)} documents")

if __name__ == '__main__':
    main()
