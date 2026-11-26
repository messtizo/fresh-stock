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
    return BeautifulSoup(r.text, "html.parser")

def candidate_blocks(soup):
    found = {}

    for a in soup.select('a[href*="/cars/"]'):
        href = urljoin(BASE, a.get("href", ""))
        path = urlparse(href).path

        # Берём только ссылки на конкретные объявления:
        # в конце адреса должен быть числовой ID.
        if not re.search(r"/cars/[^/]+-\d+/?$", path):
            continue

        node = a
        card = None

        # Ищем ближайший компактный блок с признаками автомобиля.
        for _ in range(8):
            if node.parent:
                node = node.parent

            txt = clean(node.get_text(" ", strip=True))

            has_price = bool(re.search(
                r"(?<!\d)(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d{5,9})\s*₽",
                txt
            ))
            has_year = bool(re.search(r"\b(?:19|20)\d{2}\b", txt))
            has_mileage = bool(re.search(r"\d[\d \u00a0]*\s*км", txt, re.I))

            if (
                40 <= len(txt) <= 700
                and has_price
                and has_year
                and has_mileage
            ):
                card = (node, txt)
                break

        if card and href not in found:
            found[href] = card

    return found


def parse_card(url, node, text):
    price_match = re.search(
        r"(?<!\d)(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d{5,9})\s*₽",
        text
    )
    price = number(price_match.group(0)) if price_match else None

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else None

    title = clean(node.get_text(" ", strip=True))[:160]

    img = node.select_one("img")
    image_url = None

    if img:
        image_url = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
        )

        if not image_url and img.get("srcset"):
            image_url = img.get("srcset").split(",")[0].strip().split(" ")[0]

        if image_url:
            image_url = urljoin(BASE, image_url)

    mileage_match = re.search(r"([\d\s\u00a0]+)\s*км", text, re.I)
    mileage = number(mileage_match.group(1)) if mileage_match else None

    power_match = re.search(r"\((\d+)\s*л\.с\.\)", text)
    power = number(power_match.group(1)) if power_match else None

    fuel = next(
        (x for x in ["Бензин", "Дизель", "Гибридный", "Электро"]
         if x.lower() in text.lower()),
        None
    )

    transmission = next(
        (x for x in ["CVT", "AMT", "AT", "MT", "АКПП", "МКПП"]
         if re.search(r"\b" + re.escape(x) + r"\b", text, re.I)),
        None
    )

    drive = (
        "Полный" if "Полный" in text or "4WD" in text
        else "Задний" if "Задний" in text
        else "Передний" if "Передний" in text
        else None
    )

    title_match = re.search(r"^(.{2,70}?)(?:19\d{2}|20\d{2})", text)
    if title_match:
        title = clean(title_match.group(1))

    digest = hashlib.sha256(url.encode()).hexdigest()[:24]

    return {
        "external_id": digest,
        "url": url,
        "title": title,
        "brand": None,
        "model": title,
        "year": year,
        "price": price,
        "mileage": mileage,
        "engine": None,
        "transmission": transmission,
        "power": power,
        "fuel": fuel,
        "drive": drive,
        "body": None,
        "image_url": image_url,
        "branch": BRANCH,
        "raw_text": text[:1500]
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
