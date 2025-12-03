import os, feedparser, requests, pickle, imaplib, email, re
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

FEEDS = {
    "orizzontescuola": "https://www.orizzontescuola.it/feed/",
    "usr_lazio": "https://www.lazio.istruzione.it/feed.xml"
}
IMAP_SERVER = "imap.gmail.com"
MODEL = SentenceTransformer("all-MiniLM-L6-v2")
CHUNKSZ = 500
OVERLAP = 50

def scrape_html(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    except:
        return ""

def load_feeds():
    docs=[]
    for name, url in FEEDS.items():
        f = feedparser.parse(url)
        for e in f.entries[:20]:
            txt = e.title + " " + (e.summary if "summary" in e else "") + " " + scrape_html(e.link)
            docs.append({"text": txt, "source": e.link})
    return docs

def load_emails():
    docs=[]
    user, pwd = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASS")
    if not user or not pwd: return docs
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(user, pwd)
        mail.select("INBOX")
        typ, data = mail.search(None, '(UNSEEN)')
        for num in data[0].split():
            typ, msg = mail.fetch(num, '(RFC822)')
            msg_obj = email.message_from_bytes(msg[0][1])
            subj = msg_obj["Subject"]
            body = ""
            if msg_obj.is_multipart():
                for part in msg_obj.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode(errors="ignore")
            else:
                body = msg_obj.get_payload(decode=True).decode(errors="ignore")
            docs.append({"text": subj+" "+body, "source": "email:"+subj})
            mail.store(num, '+FLAGS', '\\Seen')
        mail.logout()
    except: pass
    return docs

def chunk_text(text, size, overlap):
    return [text[i:i+size] for i in range(0, len(text)-overlap, size-overlap)]

def build_db(docs):
    client = chromadb.Client(Settings(anonymized_telemetry=False))
    coll = client.get_or_create_collection("scuola")
    ids, texts, metas, embs = [], [], [], []
    for d in docs:
        chunks = chunk_text(d["text"], CHUNKSZ, OVERLAP)
        for i, c in enumerate(chunks):
            ids.append(f"{d['source']}_{i}")
            texts.append(c)
            metas.append({"source": d["source"]})
            embs.append(MODEL.encode(c).tolist())
    if ids:
        coll.add(documents=texts, metadatas=metas, ids=ids, embeddings=embs)
    return client

def main():
    docs = load_feeds() + load_emails()
    if not docs: return
    db = build_db(docs)
    with open("knowledge.pkl", "wb") as f:
        pickle.dump(db._client.get_collection("scuola").get(), f)
    print("DB aggiornato ->", len(docs), "documenti")

if __name__ == "__main__":
    main()
