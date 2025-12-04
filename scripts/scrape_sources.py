"""
Script per scraping automatico di tutte le fonti del bot scuola
Posizione: /scripts/scrape_sources.py
"""

import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import json
from pathlib import Path
import time
import hashlib
import urllib.request

class SourceScraper:
    """Classe base per tutti gli scraper"""
    
    def __init__(self, name, url):
        self.name = name
        self.url = url
    
    def scrape(self):
        raise NotImplementedError
    
    def _make_absolute_url(self, url, base_url):
        """Converte URL relativo in assoluto"""
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            base = base_url.split('/')[0] + '//' + base_url.split('/')[2]
            return base + url
        return base_url.rsplit('/', 1)[0] + '/' + url


class RSSFeedScraper(SourceScraper):
    """Scraper per feed RSS (più affidabile)"""
    
    def scrape(self):
        try:
            print(f"  📡 Fetching RSS: {self.url}")
            
            # Headers per bypassare cookie banner
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cookie': 'cookie_notice_accepted=true'
            }
            
            # Scarica con headers
            import urllib.request
            req = urllib.request.Request(self.url, headers=headers)
            response = urllib.request.urlopen(req)
            feed_data = response.read()
            
            # Parse feed
            feed = feedparser.parse(feed_data)
            
            if not feed.entries:
                print(f"  ⚠️  No entries found in RSS")
                return []
            
            documents = []
            
            for entry in feed.entries[:50]:  # Ultimi 50
                # Estrai data
                date = entry.get('published', entry.get('updated', datetime.now().isoformat()))
                
                # Estrai descrizione
                description = entry.get('summary', entry.get('description', ''))
                if description:
                    # Rimuovi tag HTML dalla descrizione
                    soup = BeautifulSoup(description, 'html.parser')
                    description = soup.get_text()[:300]
                
                doc = {
                    'title': entry.title,
                    'url': entry.link,
                    'date': date,
                    'source': self.name,
                    'type': 'rss_article',
                    'description': description,
                    'content': entry.get('content', [{}])[0].get('value', '') if entry.get('content') else ''
                }
                
                documents.append(doc)
            
            print(f"  ✅ Found {len(documents)} documents")
            return documents
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []


class MIMNormativaScraper(SourceScraper):
    """Scraper per pagina normativa MIM"""
    
    def scrape(self):
        try:
            print(f"  🌐 Scraping HTML: {self.url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []
            
            # Cerca link a PDF o pagine di normativa
            # Il sito MIM ha diverse strutture possibili
            
            # Strategia 1: cerca tutti i link che contengono "normativa" o terminano in .pdf
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                if not text or len(text) < 10:
                    continue
                
                # Filtra link rilevanti
                is_relevant = (
                    '.pdf' in href.lower() or
                    'normativa' in href.lower() or
                    'circolare' in href.lower() or
                    'decreto' in href.lower() or
                    'ordinanza' in href.lower()
                )
                
                if is_relevant:
                    # Trova data (cerca nel parent o nei siblings)
                    date = datetime.now().isoformat()
                    parent = link.find_parent(['div', 'li', 'tr'])
                    if parent:
                        date_text = parent.get_text()
                        # Cerca pattern data (es: 01/12/2024 o 2024-12-01)
                        import re
                        date_match = re.search(r'\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2}', date_text)
                        if date_match:
                            date = date_match.group()
                    
                    doc = {
                        'title': text,
                        'url': self._make_absolute_url(href, self.url),
                        'date': date,
                        'source': self.name,
                        'type': 'normativa',
                        'description': ''
                    }
                    
                    documents.append(doc)
            
            # Deduplicazione per URL
            unique_docs = {doc['url']: doc for doc in documents}
            result = list(unique_docs.values())
            
            print(f"  ✅ Found {len(result)} documents")
            return result
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []


class CISLScuolaScraper(SourceScraper):
    """Scraper per CISL Scuola Roma e Rieti"""
    
    def scrape(self):
        try:
            print(f"  🌐 Scraping HTML: {self.url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(self.url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []
            
            # Cerca articoli/notizie (struttura tipica WordPress/CMS)
            # Prova diversi selettori comuni
            selectors = [
                'article',
                '.post',
                '.news-item',
                '.entry',
                'div[class*="news"]',
                'div[class*="post"]'
            ]
            
            items_found = []
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    items_found = items
                    break
            
            if not items_found:
                # Fallback: cerca tutti i link nella pagina
                items_found = soup.find_all('a', href=True)
            
            for item in items_found[:50]:
                try:
                    # Estrai titolo
                    title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'a'])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Estrai link
                    link_elem = item.find('a', href=True) if item.name != 'a' else item
                    if not link_elem:
                        continue
                    
                    url = link_elem['href']
                    
                    # Filtra link non rilevanti
                    if not url or url.startswith('#') or 'javascript:' in url:
                        continue
                    
                    # Estrai data
                    date = datetime.now().isoformat()
                    date_elem = item.find(['time', 'span', 'div'], class_=lambda x: x and 'date' in x.lower() if x else False)
                    if date_elem:
                        date = date_elem.get_text(strip=True)
                    
                    doc = {
                        'title': title,
                        'url': self._make_absolute_url(url, self.url),
                        'date': date,
                        'source': self.name,
                        'type': 'news',
                        'description': ''
                    }
                    
                    if len(title) > 10:  # Filtra titoli troppo corti
                        documents.append(doc)
                
                except Exception:
                    continue
            
            # Deduplicazione
            unique_docs = {doc['url']: doc for doc in documents}
            result = list(unique_docs.values())
            
            print(f"  ✅ Found {len(result)} documents")
            return result
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []


class USRLazioScraper(SourceScraper):
    """Scraper per USR Lazio - Gestisce siti dinamici"""
    
    def scrape(self):
        try:
            print(f"  🌐 Scraping HTML: {self.url}")
            print(f"  ⚠️  Nota: sito potrebbe usare JavaScript (contenuto limitato)")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(self.url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []
            
            # Cerca link a documenti/comunicazioni
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link['href']
                
                if not text or len(text) < 10:
                    continue
                
                # Filtra link rilevanti
                is_relevant = any(keyword in text.lower() for keyword in [
                    'comunicazione', 'circolare', 'avviso', 'decreto',
                    'ordinanza', 'nota', 'bando', 'concorso'
                ])
                
                if is_relevant or '.pdf' in href.lower():
                    doc = {
                        'title': text,
                        'url': self._make_absolute_url(href, self.url),
                        'date': datetime.now().isoformat(),
                        'source': self.name,
                        'type': 'comunicazione',
                        'description': ''
                    }
                    documents.append(doc)
            
            unique_docs = {doc['url']: doc for doc in documents}
            result = list(unique_docs.values())
            
            print(f"  ✅ Found {len(result)} documents")
            if len(result) < 5:
                print(f"  ⚠️  Pochi risultati: il sito potrebbe richiedere JavaScript")
            
            return result
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []


def scrape_all_sources():
    """Esegue scraping di tutte le fonti configurate"""
    
    print("🚀 Avvio scraping multi-sorgente...\n")
    
    # Configurazione scrapers
    scrapers = [
        # Feed RSS (più affidabili)
        RSSFeedScraper(
            name='Orizzonte Scuola - Diventare Insegnanti',
            url='https://www.orizzontescuola.it/diventareinsegnanti/feed/'
        ),
        RSSFeedScraper(
            name='Orizzonte Scuola - ATA',
            url='https://www.orizzontescuola.it/ata/feed/'
        ),
        RSSFeedScraper(
            name='Orizzonte Scuola - Mobilità',
            url='https://www.orizzontescuola.it/mobilita/feed/'
        ),
        RSSFeedScraper(
            name='FLC CGIL',
            url='https://www.flcgil.it/rss/'
        ),
        
        # Scraping HTML
        MIMNormativaScraper(
            name='MIM - Normativa',
            url='https://www.mim.gov.it/web/guest/normativa'
        ),
        CISLScuolaScraper(
            name='CISL Scuola Roma e Rieti',
            url='https://www.cislscuolaromarieti.it/cisl/notizie/'
        ),
        USRLazioScraper(
            name='USR Lazio',
            url='https://www.ufficioscolasticoregionalelazio.it/home/'
        ),
    ]
    
    all_documents = []
    stats = {
        'total_sources': len(scrapers),
        'successful': 0,
        'failed': 0,
        'total_docs': 0
    }
    
    # Esegui ogni scraper
    for i, scraper in enumerate(scrapers, 1):
        print(f"[{i}/{len(scrapers)}] {scraper.name}")
        
        try:
            docs = scraper.scrape()
            all_documents.extend(docs)
            stats['successful'] += 1
            stats['total_docs'] += len(docs)
        except Exception as e:
            print(f"  ❌ Fatal error: {e}")
            stats['failed'] += 1
        
        # Pausa educata tra richieste
        time.sleep(1)
        print()
    
    # Deduplicazione globale per URL
    unique_docs = {}
    for doc in all_documents:
        url = doc['url']
        # Usa URL come chiave (se duplicato, tiene l'ultimo)
        unique_docs[url] = doc
    
    final_docs = list(unique_docs.values())
    
    # Aggiungi hash univoco a ogni documento
    for doc in final_docs:
        doc_str = f"{doc['url']}{doc['title']}"
        doc['id'] = hashlib.sha256(doc_str.encode()).hexdigest()[:16]
    
    # Ordina per data (più recenti prima)
    final_docs.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Salva risultati
    output = {
        'scraped_at': datetime.now().isoformat(),
        'stats': {
            **stats,
            'unique_documents': len(final_docs)
        },
        'documents': final_docs
    }
    
    # Crea directory data se non esiste
    Path('data').mkdir(exist_ok=True)
    
    output_file = 'data/scraped_documents.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Report finale
    print("=" * 60)
    print("📊 REPORT FINALE")
    print("=" * 60)
    print(f"Sorgenti totali:      {stats['total_sources']}")
    print(f"Successi:             {stats['successful']}")
    print(f"Fallimenti:           {stats['failed']}")
    print(f"Documenti trovati:    {stats['total_docs']}")
    print(f"Documenti unici:      {len(final_docs)}")
    print(f"Output salvato in:    {output_file}")
    print("=" * 60)
    
    return final_docs


if __name__ == '__main__':
    scrape_all_sources()
