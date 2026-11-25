import os, random, hashlib, hmac
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

st.set_page_config(page_title="FRESH STOCK | Академия склада", page_icon="🚘", layout="wide")

BRANCH = "Fresh Краснодар Дзержинского"
TZ = ZoneInfo("Europe/Moscow")

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

def db_client():
    url, key = secret("SUPABASE_URL"), secret("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None

def load_cars():
    client = db_client()
    if client:
        try:
            rows = client.table("cars").select("*").eq("branch", BRANCH).eq("status", "active").order("price").execute().data
            if rows:
                return pd.DataFrame(rows), True
        except Exception as e:
            st.warning(f"Не удалось прочитать каталог из базы: {e}")
    # Safe empty state: never pretend demo records are live inventory.
    return pd.DataFrame(), False

def load_user(username, password):
    client = db_client()

    if not client:
        st.error("ДИАГНОСТИКА: Supabase не подключён. Проверьте SUPABASE_URL и SUPABASE_KEY.")
        return None

    try:
        rows = (
            client.table("employees")
            .select("*")
            .eq("username", username)
            .eq("active", True)
            .limit(1)
            .execute()
            .data
        )

        if not rows:
            st.error("ДИАГНОСТИКА: Пользователь не найден или active не равен true. Возможно, Streamlit подключён к другой базе.")
            return None

        user = rows[0]
        digest = hashlib.sha256(password.encode()).hexdigest()
        saved_hash = str(user.get("password_hash", ""))

        if hmac.compare_digest(saved_hash, digest):
            return user

        st.error(
            f"ДИАГНОСТИКА: Пользователь найден, но хеш пароля не совпадает. "
            f"Длина хеша в базе: {len(saved_hash)}."
        )
        return None

    except Exception as e:
        st.error(f"ДИАГНОСТИКА: Ошибка обращения к Supabase: {type(e).__name__}: {e}")
        return None


def record_event(username, mode, points, detail=""):
    client = db_client()
    if client:
        try:
            client.table("training_events").insert({
                "username": username, "mode": mode, "points": int(points),
                "detail": detail, "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as e:
            st.error(f"Не удалось сохранить результат: {e}")

def money(v):
    try: return f"{int(float(v)):,}".replace(",", " ") + " ₽"
    except Exception: return "Цена не указана"

def show_car_card(car, compact=False):
    title = f"{car.get('brand','')} {car.get('model','')}".strip() or car.get("title","Автомобиль")
    image_url = car.get("image_url") or car.get("photo_url")
    with st.container(border=True):
        if image_url:
            st.image(image_url, use_container_width=True)
        st.markdown(f"**{title} · {car.get('year','—')}**")
        st.markdown(f"### {money(car.get('price'))}")
        specs = [
            f"{int(car['mileage']):,} км".replace(",", " ") if pd.notna(car.get("mileage")) else "Пробег —",
            str(car.get("engine") or "Двигатель —"),
            str(car.get("transmission") or "КПП —"),
            f"{car.get('power')} л.с." if car.get("power") else "Мощность —",
            str(car.get("fuel") or "Топливо —"),
            str(car.get("drive") or "Привод —"),
        ]
        st.caption(" · ".join(specs))
        if car.get("url"):
            st.link_button("Открыть объявление Fresh", car["url"], use_container_width=True)

def require_login():
    if "user" not in st.session_state:
        st.markdown("<div style='text-align:center;padding:5vh 0 1vh'><div style='color:#d71920;font-weight:900;letter-spacing:.25em'>FRESH AUTO</div><h1>FRESH STOCK</h1><p>Академия склада · Краснодар</p></div>", unsafe_allow_html=True)
        with st.form("login"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", type="primary", use_container_width=True)
        if submitted:
            user = load_user(username.strip(), password)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("Неверный логин или пароль. Проверьте подключение базы и учётную запись.")
        st.info("Первый вход настраивает руководитель через SQL-инструкцию из README. Самостоятельной регистрации нет.")
        st.stop()

def score_board(username):
    client = db_client()
    if not client: return pd.DataFrame()
    try:
        rows = client.table("training_events").select("mode,points").eq("username", username).execute().data
        return pd.DataFrame(rows)
    except Exception: return pd.DataFrame()

# Theme
st.markdown("""
<style>
.block-container{max-width:1450px;padding-top:1.3rem}
.fresh-top{background:linear-gradient(110deg,#171717,#383838);color:white;padding:22px 26px;border-radius:16px;margin-bottom:18px}
.fresh-red{color:#ed1c24;font-weight:900;letter-spacing:.22em;font-size:12px}
div.stButton>button[kind="primary"],button[kind="primaryFormSubmit"]{background:#d71920;border-color:#d71920}
[data-testid="stSidebar"]{border-right:1px solid #eee}
</style>
""", unsafe_allow_html=True)

if secret("SUPABASE_URL") and secret("SUPABASE_KEY"):
    require_login()
else:
    st.error("База данных ещё не подключена. Создайте проект Supabase и добавьте секреты из README в настройки Streamlit.")
    st.stop()

user = st.session_state.user
cars, live = load_cars()
is_admin = user.get("role") == "admin"

with st.sidebar:
    st.markdown('<div class="fresh-red">FRESH AUTO</div>', unsafe_allow_html=True)
    st.title("Академия склада")
    st.caption(f"{user.get('full_name') or user['username']} · {'Руководитель' if is_admin else 'Менеджер'}")
    menu = ["Главная","Каталог склада","Флеш-карточки","Викторина","Угадай цену","Запрос клиента","Сравнение","Экзамен","Мой прогресс"]
    if is_admin: menu += ["Кабинет руководителя"]
    page = st.radio("Раздел", menu)
    if st.button("Выйти", use_container_width=True):
        del st.session_state.user
        st.rerun()

st.markdown('<div class="fresh-top"><div class="fresh-red">FRESH AUTO · КРАСНОДАР</div><h1 style="margin:.3rem 0">FRESH STOCK</h1><div>Академия склада · учим ассортимент, чтобы увереннее подбирать автомобили</div></div>', unsafe_allow_html=True)

if not live or cars.empty:

    st.warning(
        "В базе пока нет автомобилей. "
        "Сначала необходимо выполнить импорт склада Fresh."
    )

    if is_admin:
        st.markdown("**Склад:** " + BRANCH)

    st.markdown(
        "После синхронизации здесь появятся карточки, "
        "фотографии, цены и характеристики."
    )

    car_pages = [
        "Каталог склада",
        "Флеш-карточки",
        "Викторина",
        "Угадай цену",
        "Запрос клиента",
        "Сравнение",
        "Экзамен"
    ]

    if page in car_pages:
        st.info("Этот раздел станет доступен после загрузки автомобилей.")
        st.stop()

# Normalize numeric columns
for col in ["price","year","mileage","power"]:
    if col in cars: cars[col] = pd.to_numeric(cars[col], errors="coerce")

def car_title(c):
    return f"{c.get('brand','')} {c.get('model','')}".strip()

if page == "Главная":
    events = score_board(user["username"])
    c1,c2,c3 = st.columns(3)
    c1.metric("Автомобилей на складе", len(cars))
    c2.metric("Мой балл", int(events.points.sum()) if not events.empty else 0)
    c3.metric("Обновление", str(cars.last_sync_at.dropna().max())[:16] if "last_sync_at" in cars and cars.last_sync_at.notna().any() else "—")
    st.subheader("Новые поступления")
    newest = cars.sort_values("first_seen_at", ascending=False).head(4) if "first_seen_at" in cars else cars.head(4)
    cols = st.columns(4)
    for col, (_, row) in zip(cols, newest.iterrows()):
        with col: show_car_card(row.to_dict(), True)

elif page == "Каталог склада":
    st.subheader("Каталог автомобилей")
    q = st.text_input("Поиск: марка, модель, двигатель")
    f1,f2,f3,f4 = st.columns(4)
    fuel_opts = sorted(cars.fuel.dropna().astype(str).unique()) if "fuel" in cars else []
    trans_opts = sorted(cars.transmission.dropna().astype(str).unique()) if "transmission" in cars else []
    drive_opts = sorted(cars.drive.dropna().astype(str).unique()) if "drive" in cars else []
    fuel = f1.multiselect("Топливо", fuel_opts)
    trans = f2.multiselect("Коробка", trans_opts)
    drive = f3.multiselect("Привод", drive_opts)
    max_price = int(cars.price.max() or 1) if "price" in cars else 1
    budget = f4.number_input("Цена до, ₽", min_value=0, max_value=max(max_price,1), value=max(max_price,1), step=50000)
    filtered = cars.copy()
    if q:
        cols = [c for c in ["brand","model","engine"] if c in filtered]
        filtered = filtered[filtered[cols].fillna("").astype(str).apply(lambda r:r.str.contains(q,case=False).any(),axis=1)]
    for col, values in [("fuel",fuel),("transmission",trans),("drive",drive)]:
        if values and col in filtered: filtered = filtered[filtered[col].isin(values)]
    if "price" in filtered: filtered = filtered[filtered.price <= budget]
    st.caption(f"Найдено автомобилей: {len(filtered)}")
    for start in range(0,len(filtered),3):
        rowcols = st.columns(3)
        for col, (_, row) in zip(rowcols, filtered.iloc[start:start+3].iterrows()):
            with col: show_car_card(row.to_dict())

elif page == "Флеш-карточки":
    st.subheader("Флеш-карточки")
    if "flash_pos" not in st.session_state: st.session_state.flash_pos = 0
    idx = st.session_state.flash_pos % len(cars)
    car = cars.iloc[idx].to_dict()
    show_car_card(car)
    if st.button("Показать характеристики", type="primary"):
        st.session_state.flash_show = True
    if st.session_state.get("flash_show"):
        st.write({k:car.get(k) for k in ["year","price","mileage","engine","transmission","power","fuel","drive","body"]})
        a,b = st.columns(2)
        if a.button("Знаю"):
            record_event(user["username"],"Карточки",5,car_title(car))
            st.session_state.flash_pos += 1; st.session_state.flash_show=False; st.rerun()
        if b.button("Нужно повторить"):
            record_event(user["username"],"Карточки",0,"Повторить: "+car_title(car))
            st.session_state.flash_pos += 1; st.session_state.flash_show=False; st.rerun()
    st.caption(f"Карточка {idx+1} из {len(cars)}")

elif page == "Викторина":
    st.subheader("Викторина по автомобилю")
    if "quiz_car" not in st.session_state: st.session_state.quiz_car = random.randrange(len(cars))
    car = cars.iloc[st.session_state.quiz_car].to_dict()
    show_car_card({**car,"image_url":car.get("image_url")})
    fields = [x for x in ["year","transmission","fuel","drive","power"] if x in cars and cars[x].notna().any()]
    field = st.selectbox("Что определить?", fields, format_func=lambda x:{"year":"Год выпуска","transmission":"Коробка передач","fuel":"Топливо","drive":"Привод","power":"Мощность"}[x])
    options = cars[field].dropna().unique().tolist()
    if len(options)>1:
        choice = st.radio("Выберите ответ", options, horizontal=True)
        if st.button("Проверить",type="primary"):
            ok = str(choice)==str(car[field])
            st.success("Верно · +10 баллов") if ok else st.error(f"Правильный ответ: {car[field]}")
            record_event(user["username"],"Викторина",10 if ok else 0, f"{car_title(car)} · {field}")
            st.session_state.quiz_car=random.randrange(len(cars)); st.rerun()
    else: st.info("Недостаточно разных значений для этого вопроса.")

elif page == "Угадай цену":
    st.subheader("Угадай цену")
    if "price_car" not in st.session_state: st.session_state.price_car=random.randrange(len(cars))
    car=cars.iloc[st.session_state.price_car].to_dict()
    show_car_card({**car,"price":None})
    guess=st.number_input("Ваша оценка, ₽",min_value=0,max_value=100000000,step=10000)
    if st.button("Проверить цену",type="primary"):
        delta=abs(guess-float(car["price"]))
        points=30 if delta<=40000 else max(0,30-int(delta/100000)*3)
        st.markdown(f"Цена склада: **{money(car['price'])}**")
        st.success(f"+{points} баллов" if points else "Баллов за этот ответ нет")
        record_event(user["username"],"Угадай цену",points,car_title(car))
        st.session_state.price_car=random.randrange(len(cars)); st.rerun()

elif page == "Запрос клиента":
    st.subheader("Подбор под запрос клиента")
    c1,c2,c3=st.columns(3)
    budget=c1.number_input("Бюджет до, ₽",min_value=0,value=2000000,step=50000)
    year=c2.number_input("Год от",min_value=1990,max_value=2035,value=2019)
    gearbox=c3.selectbox("Коробка",["Любая"]+sorted(cars.transmission.dropna().unique().tolist()))
    fuel=st.selectbox("Топливо",["Любое"]+sorted(cars.fuel.dropna().unique().tolist()))
    if st.button("Найти подходящие автомобили",type="primary"):
        res=cars[(cars.price<=budget)&(cars.year>=year)]
        if gearbox!="Любая": res=res[res.transmission==gearbox]
        if fuel!="Любое": res=res[res.fuel==fuel]
        st.write(f"Подходят: **{len(res)} автомобилей**")
        for _,r in res.iterrows(): show_car_card(r.to_dict())
        record_event(user["username"],"Запрос клиента",5 if len(res) else 0,f"Найдено {len(res)}")

elif page == "Сравнение":
    st.subheader("Сравнение автомобилей")
    labels={str(i):car_title(r) for i, r in cars.iterrows()}
    i1=st.selectbox("Первый автомобиль",cars.index,key="cmp1",format_func=lambda i:labels[str(i)])
    i2=st.selectbox("Второй автомобиль",cars.index,index=min(1,len(cars)-1),key="cmp2",format_func=lambda i:labels[str(i)])
    a,b=cars.loc[i1],cars.loc[i2]
    compare_fields=[("Цена","price"),("Год","year"),("Пробег","mileage"),("Мощность","power"),("Коробка","transmission"),("Привод","drive"),("Топливо","fuel")]
    table=[]
    for label,key in compare_fields:
        av,bv=a.get(key),b.get(key)
        if key=="price": av,bv=money(av),money(bv)
        table.append({"Параметр":label,car_title(a):av,car_title(b):bv})
    st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True)
    if st.button("Ответить: какой автомобиль дороже?"):
        st.info(f"Дороже: {car_title(a if a.price>b.price else b)}")
        record_event(user["username"],"Сравнение",5,"Сравнение цен")

elif page == "Экзамен":
    st.subheader("Экзамен отдела продаж")
    n=st.slider("Количество вопросов",5,min(30,len(cars)*3),min(20,max(5,len(cars))))
    if st.button("Начать экзамен",type="primary"):
        st.session_state.exam=[random.randrange(len(cars)) for _ in range(n)]
        st.session_state.exam_i=0; st.session_state.exam_score=0
    if "exam" in st.session_state:
        pos=st.session_state.exam_i
        if pos<len(st.session_state.exam):
            car=cars.iloc[st.session_state.exam[pos]].to_dict()
            st.progress(pos/len(st.session_state.exam),text=f"Вопрос {pos+1}/{len(st.session_state.exam)}")
            show_car_card({**car,"price":None})
            field=st.selectbox("Укажите характеристику",["year","transmission","fuel","drive","power"],format_func=lambda x:{"year":"Год","transmission":"КПП","fuel":"Топливо","drive":"Привод","power":"Мощность"}[x],key=f"exam_f{pos}")
            vals=cars[field].dropna().unique().tolist()
            answer=st.selectbox("Ответ",vals,key=f"exam_a{pos}")
            if st.button("Ответить",key=f"exam_submit{pos}"):
                if str(answer)==str(car.get(field)): st.session_state.exam_score+=1
                st.session_state.exam_i+=1; st.rerun()
        else:
            total=len(st.session_state.exam); points=st.session_state.exam_score*10
            st.success(f"Экзамен завершён: {st.session_state.exam_score}/{total}. Баллы: {points}")
            record_event(user["username"],"Экзамен",points,f"{st.session_state.exam_score}/{total}")
            del st.session_state.exam
            if st.button("Пройти ещё раз"): st.rerun()

elif page == "Мой прогресс":
    st.subheader("Моя статистика")
    events=score_board(user["username"])
    if events.empty: st.info("Пока нет сохранённых тренировок.")
    else:
        st.metric("Всего баллов",int(events.points.sum()))
        st.bar_chart(events.groupby("mode").points.sum())
        st.dataframe(events.sort_values("created_at",ascending=False),use_container_width=True,hide_index=True)

elif page == "Кабинет руководителя":
    st.subheader("Кабинет руководителя")
    client=db_client()
    employees=client.table("employees").select("username,full_name,role,active").execute().data
    st.markdown("#### Сотрудники")
    st.dataframe(pd.DataFrame(employees),use_container_width=True,hide_index=True)
    events=client.table("training_events").select("*").order("created_at",desc=True).limit(500).execute().data
    if events:
        df=pd.DataFrame(events)
        st.markdown("#### Результаты обучения")
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.markdown("#### Баллы по режимам")
        st.dataframe(df.groupby(["username","mode"],as_index=False).points.sum().sort_values("points",ascending=False),use_container_width=True,hide_index=True)
    st.caption("Создание пользователей и запуск экзамена администратором выполняются через защищённые SQL-команды из README в этой версии.")
