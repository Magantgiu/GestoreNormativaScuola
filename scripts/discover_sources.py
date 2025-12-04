# scripts/discover_sources.py
import feedparser
import imaplib
import email
import json
import re
from datetime import datetime

def discover_from_rss(feed_url):
    """Estrai URL da feed RSS"""
    feed = feedparser.parse(feed_url)
    urls = []
    
    for entry in feed.entries[:50]:  # Ultimi 50
        urls.append({
            'url': entry.link,
            'title': entry.title,
            'source': 'rss',
            'feed': feed_url,
            'date': entry.published
        })
    return urls

def discover_from_newsletter(imap_server, email_user, email_pass):
    """Estrai URL da newsletter email"""
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_user, email_pass)
    mail.select('inbox')
    
    # Cerca email recenti con link
    _, messages = mail.search(None, '(SINCE "01-Nov-2024")')
    
    urls = []
    for num in messages[0].split()[-50:]:  # Ultime 50
        _, msg = mail.fetch(num, '(RFC822)')
        email_body = email.message_from_bytes(msg[0][1])
        
        # Estrai tutti gli URL
        text = str(email_body.get_payload())
        found_urls = re.findall(r'https?://[^\s<>"]+', text)
        
        for url in found_urls:
            # Filtra solo domini rilevanti
            if any(d in url for d in ['miur.gov.it', 'usrlazio.it', 'cisl', 'uil', 'cgil']):
                urls.append({
                    'url': url,
                    'title': email_body['subject'],
                    'source': 'newsletter',
                    'date': email_body['date']
                })
    
    return urls

def scrape_mim_page():
    """Scraping pagina documenti MIM"""
    from bs4 import BeautifulSoup
    import requests
    
    url = "https://www.miur.gov.it/web/guest/circolari"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    documents = []
    for link in soup.find_all('a', href=True):
        if '.pdf' in link['href'] or 'download' in link['href']:
            documents.append({
                'url': link['href'],
                'title': link.text.strip(),
                'source': 'mim_page',
                'date': datetime.now().isoformat()
            })
    
    return documents

# Aggregazione
def main():
    all_urls = []
    
    # RSS Orizzontescuola (contenuto completo)
    all_urls.extend(discover_from_rss('https://www.orizzontescuola.it/feed/'))
    
    # Newsletter (puntatori)
    all_urls.extend(discover_from_newsletter(
        'imap.gmail.com',
        os.getenv('GMAIL_USER'),
        os.getenv('GMAIL_APP_PASS')
    ))
    
    # Pagine MIM/USR
    all_urls.extend(scrape_mim_page())
    
    # Deduplicazione
    unique_urls = {u['url']: u for u in all_urls}
    
    # Salva per prossimo stadio
    with open('discovered_urls.json', 'w') as f:
        json.dump(list(unique_urls.values()), f, indent=2)
    
    print(f"✅ Discovered {len(unique_urls)} unique URLs")

if __name__ == '__main__':
    main()
