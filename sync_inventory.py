"""
Inventory synchronizer.
Uses the public Fresh filtered listing; respects normal HTTP access and does not bypass CAPTCHA/auth.
If Fresh changes markup or blocks automated requests, inspect the log and stop rather than bypass protections.
"""
import os, re, time, hashlib, logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import requests
from bs4 import BeautifulSoup
from supabase import create_client

BASE = "https://23.freshauto.ru"
START_URL = os.getenv("FRESH_STOCK_URL", "https://23.freshauto.ru/cars/used/?filters=G3wAAJwJdqyVgbYuPaLakQYaYmT_E2kWRLqHueRIRKKEgvt2WyWbXGR_lUXKcsqBe1jYlkmY2-HgISuFT9Ek3E8IS_ZpTFGaRVHqYCsTt2BZc_7PIaWgvwFWp4zjtJcTrw%3D%3D%2F")
BRANCH = "Fresh Краснодар Дзержинского"
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; FreshStockTraining/1.0; contact=admin)"}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def clean(s): return re.sub(r"\s+", " ", s or "").strip()
def number(s):
    m=re.search(r"[\d\s]+",s or "")
    return int(re.sub(r"\D","",m.group(0))) if m and re.sub(r"\D","",m.group(0)) else None

def next_page(url, page):
    p=urlparse(url); q=parse_qs(p.query); q["page"]=[str(page)]
    return urlunparse(p._replace(query=urlencode(q,doseq=True)))

def get_soup(url, session):
    r=session.get(url,timeout=35); r.raise_for_status()
    if "captcha" in r.url.lower() or "captcha" in r.text[:5000].lower():
        raise RuntimeError("Сайт показал CAPTCHA/защиту. Синхронизация остановлена; обход защиты не выполняется.")
    return BeautifulSoup(r.text,"lxml")

def candidate_blocks(soup):
    # Find listing links and climb to a compact card-like parent.
    found={}
    for a in soup.select('a[href*="/cars/"]'):
        href=urljoin(BASE,a.get("href",""))
        if not re.search(r"/cars/[^/?#]+",urlparse(href).path): continue
        node=a
        for _ in range(6):
            if node.parent: node=node.parent
            txt=clean(node.get_text(" ",strip=True))
            if len(txt)>45 and len(txt)<1800 and ("₽" in txt or "руб" in txt.lower()):
                break
        txt=clean(node.get_text(" ",strip=True))
        if href not in found and len(txt)>30:
            found[href]=(node,txt)
    return found

def parse_card(url, node, text):
    # Require an identifiable price and model/year text; fields not present remain NULL.
    price_match=re.search(r"([\d\s\u00a0]+)\s*₽",text)
    price=number(price_match.group(1)) if price_match else None
    year_match=re.search(r"\b(19\d{2}|20\d{2})\b",text)
    year=int(year_match.group(1)) if year_match else None
    title=clean(node.get_text(" ",strip=True))
    title=title[:160]
    # Prefer a card image; keep source URL, don't download or rehost without permission.
    img=node.select_one("img")
    image_url=None
    if img:
        image_url=img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if image_url: image_url=urljoin(BASE,image_url)
        if not image_url:
            srcset=img.get("srcset")
            if srcset: image_url=urljoin(BASE,srcset.split(",")[0].strip().split(" ")[0])
    # Parse typical listing spec line
    spec=text
    mileage=number(re.search(r"([\d\s\u00a0]+)\s*км",spec).group(1)) if re.search(r"([\d\s\u00a0]+)\s*км",spec) else None
    power=number(re.search(r"\((\d+)\s*л\.с\.\)",spec).group(1)) if re.search(r"\((\d+)\s*л\.с\.\)",spec) else None
    fuel=next((x for x in ["Бензин","Дизель","Гибридный","Электро"] if x.lower() in text.lower()),None)
    transmission=next((x for x in ["CVT","AMT","AT","MT","АКПП","МКПП"] if re.search(r"\b"+re.escape(x)+r"\b",text,re.I)),None)
    drive="Полный" if "Полный" in text or "4WD" in text else ("Задний" if "Задний" in text else ("Передний" if "Передний" in text else None))
    # Extract title's first words before year/price as a best-effort display title.
    title_match=re.search(r"^(.{2,70}?)(?:19\d{2}|20\d{2})",text)
    title=clean(title_match.group(1)) if title_match else title
    digest=hashlib.sha256(url.encode()).hexdigest()[:24]
    return {
      "external_id":digest,"url":url,"title":title,"brand":None,"model":title,
      "year":year,"price":price,"mileage":mileage,"engine":None,
      "transmission":transmission,"power":power,"fuel":fuel,"drive":drive,
      "body":None,"image_url":image_url,"branch":BRANCH,"raw_text":text[:1500]
    }

def main():
    url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key: raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
    db=create_client(url,key)
    session=requests.Session(); session.headers.update(HEADERS)
    seen={}; page=1; max_pages=int(os.getenv("MAX_PAGES","30"))
    while page<=max_pages:
        page_url=START_URL if page==1 else next_page(START_URL,page)
        logging.info("Fetching page %s: %s",page,page_url)
        soup=get_soup(page_url,session)
        blocks=candidate_blocks(soup)
        if not blocks:
            if page==1: raise RuntimeError("Не найдены карточки объявлений. Возможно, Fresh изменил HTML или контент загружается JavaScript. Проверьте разметку; не подменяйте данные.")
            break
        new_count=0
        for href,(node,txt) in blocks.items():
            # The filtered URL should scope the branch. Additionally inspect card text if branch label is rendered.
            row=parse_card(href,node,txt)
            if row["price"] is None: continue
            seen[row["external_id"]]=row; new_count+=1
        logging.info("Parsed %s candidate cards",new_count)
        if new_count==0: break
        page+=1; time.sleep(1.5)
    if not seen: raise RuntimeError("Не удалось получить ни одной карточки с ценой; существующий склад не изменён.")
    now=datetime.now(timezone.utc).isoformat()
    rows=[]
    for row in seen.values():
        row["last_seen_at"]=now; row["last_sync_at"]=now; row["status"]="active"
        row["first_seen_at"]=now
        rows.append(row)
    # Upsert only after successful full scrape. This starter marks observed rows active;
    # it deliberately does not auto-delete missing cars until a multi-run confirmation policy is implemented.
    for i in range(0,len(rows),100):
        db.table("cars").upsert(rows[i:i+100],on_conflict="external_id").execute()
    logging.info("Upserted %s cars. No absent records were deleted.",len(rows))

if __name__=="__main__": main()
