
import random
import streamlit as st
import pandas as pd

st.set_page_config(page_title="FRESH STOCK — Академия склада", page_icon="🚘", layout="wide")

# Prototype data only. Replace/import the live branch inventory in the next integration step.
DEMO_CARS = [
    {"Марка и модель":"Volkswagen Polo", "Год":2019, "Цена":1425000, "Пробег":107910, "Двигатель":"1.6", "КПП":"AT", "Мощность":110, "Топливо":"Бензин", "Привод":"Передний", "Кузов":"Седан"},
    {"Марка и модель":"OMODA C5", "Год":2023, "Цена":1790000, "Пробег":40644, "Двигатель":"1.5", "КПП":"CVT", "Мощность":147, "Топливо":"Бензин", "Привод":"Передний", "Кузов":"Кроссовер"},
    {"Марка и модель":"Sollers ST6", "Год":2023, "Цена":2050000, "Пробег":27141, "Двигатель":"2.0d", "КПП":"MT", "Мощность":136, "Топливо":"Дизель", "Привод":"Полный", "Кузов":"Пикап"},
    {"Марка и модель":"Kia Sorento", "Год":2018, "Цена":2850000, "Пробег":180934, "Двигатель":"2.2d", "КПП":"AT", "Мощность":200, "Топливо":"Дизель", "Привод":"Полный", "Кузов":"Кроссовер"},
    {"Марка и модель":"Mitsubishi Outlander", "Год":2021, "Цена":2780000, "Пробег":53591, "Двигатель":"2.4", "КПП":"CVT", "Мощность":167, "Топливо":"Бензин", "Привод":"Полный", "Кузов":"Кроссовер"},
    {"Марка и модель":"BMW X5", "Год":2016, "Цена":3525000, "Пробег":108552, "Двигатель":"3.0d", "КПП":"AT", "Мощность":258, "Топливо":"Дизель", "Привод":"Полный", "Кузов":"Кроссовер"},
]
FIELDS = ["Год", "Пробег", "Двигатель", "КПП", "Мощность", "Топливо", "Привод", "Кузов"]

if "cars" not in st.session_state:
    st.session_state.cars = pd.DataFrame(DEMO_CARS)
if "scores" not in st.session_state:
    st.session_state.scores = {"Карточки": 0, "Викторина": 0, "Угадай цену": 0, "Запрос клиента": 0, "Сравнение": 0, "Экзамен": 0}
if "flash_index" not in st.session_state:
    st.session_state.flash_index = 0
if "flash_reveal" not in st.session_state:
    st.session_state.flash_reveal = False

cars = st.session_state.cars.copy()

def rub(value):
    return f"{int(value):,}".replace(",", " ") + " ₽"

st.markdown("""
<style>
:root { --fresh:#d71920; }
.block-container {padding-top: 1.5rem; max-width: 1400px;}
.brand {font-size: 13px; letter-spacing: .22em; color:#d71920; font-weight:800;}
.hero {padding: 22px 24px; border-radius: 16px; background: linear-gradient(115deg,#171717,#343434); color:white; margin-bottom:18px;}
.hero h1 {font-size: clamp(28px,4vw,44px); margin:5px 0;}
.hero p {color:#dedede; margin-bottom:0;}
div.stButton > button[kind="primary"] {background:#d71920; border-color:#d71920;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand">FRESH AUTO</div>', unsafe_allow_html=True)
    st.title("Академия склада")
    page = st.radio("Раздел", ["Главная", "Каталог склада", "Флеш-карточки", "Викторина по фото", "Угадай цену", "Запрос клиента", "Сравнение", "Экзамен", "Мой прогресс", "Руководитель"])
    st.divider()
    st.caption("Прототип · демонстрационные данные")
    st.caption("Склад: Fresh Краснодар Дзержинского")

st.markdown('<div class="hero"><div class="brand">FRESH STOCK</div><h1>Академия склада</h1><p>Изучайте автомобили. Запоминайте характеристики. Подбирайте точнее.</p></div>', unsafe_allow_html=True)

if page == "Главная":
    st.subheader("Панель обучения")
    a,b,c = st.columns(3)
    a.metric("Автомобилей в демо-каталоге", len(cars))
    b.metric("Режимов обучения", 6)
    c.metric("Баллы за тренировки", sum(st.session_state.scores.values()))
    st.info("Сейчас показан демонстрационный набор из 6 автомобилей. Это не полная выгрузка текущего склада и не актуальный онлайн-остаток.")
    st.markdown("#### Начните с одного из режимов")
    x,y,z = st.columns(3)
    x.write("**Каталог**\n\nИзучите цены и характеристики всех доступных машин.")
    y.write("**Карточки**\n\nВспоминайте автомобиль по названию и характеристикам.")
    z.write("**Экзамен**\n\nПроверьте знания в формате контрольной.")

elif page == "Каталог склада":
    st.subheader("Каталог автомобилей")
    q = st.text_input("Поиск по марке или модели")
    c1,c2,c3 = st.columns(3)
    fuel = c1.multiselect("Топливо", sorted(cars["Топливо"].unique()))
    trans = c2.multiselect("Коробка", sorted(cars["КПП"].unique()))
    drive = c3.multiselect("Привод", sorted(cars["Привод"].unique()))
    price_max = st.slider("Максимальная цена, ₽", 500000, 5000000, 5000000, 50000)
    view = cars.copy()
    if q: view = view[view["Марка и модель"].str.contains(q, case=False, na=False)]
    if fuel: view = view[view["Топливо"].isin(fuel)]
    if trans: view = view[view["КПП"].isin(trans)]
    if drive: view = view[view["Привод"].isin(drive)]
    view = view[view["Цена"] <= price_max]
    st.caption(f"Найдено: {len(view)}")
    for _, car in view.iterrows():
        with st.container(border=True):
            left,right = st.columns([3,2])
            left.markdown(f"**{car['Марка и модель']} · {int(car['Год'])}**")
            left.markdown(f"### {rub(car['Цена'])}")
            left.write(f"Пробег: {int(car['Пробег']):,} км".replace(",", " "))
            right.write(f"**{car['Двигатель']} · {car['КПП']} · {int(car['Мощность'])} л.с.**")
            right.write(f"{car['Топливо']} · {car['Привод']} привод · {car['Кузов']}")

elif page == "Флеш-карточки":
    st.subheader("Флеш-карточки")
    if len(cars):
        idx = st.session_state.flash_index % len(cars)
        car = cars.iloc[idx]
        st.caption(f"Карточка {idx+1} из {len(cars)}")
        st.markdown(f"## {car['Марка и модель']}")
        st.markdown("Вспомните цену, год, пробег и характеристики, затем откройте ответ.")
        if st.button("Показать ответ", type="primary"):
            st.session_state.flash_reveal = True
        if st.session_state.flash_reveal:
            st.success(f"{int(car['Год'])} год · {rub(car['Цена'])} · {int(car['Пробег']):,} км".replace(",", " "))
            st.write(" · ".join(f"{f}: {car[f]}" for f in FIELDS))
            good,bad = st.columns(2)
            if good.button("Знаю ✓"):
                st.session_state.scores["Карточки"] += 5
                st.session_state.flash_index += 1
                st.session_state.flash_reveal = False
                st.rerun()
            if bad.button("Повторить позже"):
                st.session_state.flash_index += 1
                st.session_state.flash_reveal = False
                st.rerun()

elif page == "Викторина по фото":
    st.subheader("Викторина по характеристикам")
    st.warning("Фотографии подключим при импорте реальных объявлений. Пока режим работает на текстовой карточке.")
    car = cars.sample(1).iloc[0]
    st.markdown(f"### Какой тип коробки у {car['Марка и модель']}?")
    opts = sorted(cars["КПП"].unique())
    answer = st.radio("Выберите вариант", opts, horizontal=True)
    if st.button("Ответить", type="primary"):
        if answer == car["КПП"]:
            st.success("Верно! +10 баллов")
            st.session_state.scores["Викторина"] += 10
        else:
            st.error(f"Правильный ответ: {car['КПП']}")

elif page == "Угадай цену":
    st.subheader("Угадай цену")
    car = cars.sample(1).iloc[0]
    st.markdown(f"### {car['Марка и модель']} · {int(car['Год'])} год")
    st.write(f"{int(car['Пробег']):,} км · {car['Двигатель']} · {car['КПП']}".replace(",", " "))
    guess = st.number_input("Ваша оценка цены, ₽", min_value=0, max_value=20000000, step=10000, value=1000000)
    if st.button("Проверить цену", type="primary"):
        delta = abs(int(guess)-int(car["Цена"]))
        if delta <= 40000:
            points = 20
        else:
            points = max(0, 20 - delta // 100000)
        st.session_state.scores["Угадай цену"] += int(points)
        st.write(f"Цена склада: **{rub(car['Цена'])}**")
        st.success(f"Начислено баллов: {int(points)}")

elif page == "Запрос клиента":
    st.subheader("Подбор под запрос клиента")
    budget = st.number_input("Бюджет до, ₽", min_value=300000, max_value=20000000, value=2000000, step=50000)
    year = st.number_input("Год выпуска не старше (минимум)", min_value=2000, max_value=2026, value=2019)
    gearbox = st.selectbox("Коробка передач", ["Любая"] + sorted(cars["КПП"].unique()))
    fuel_choice = st.selectbox("Топливо", ["Любое"] + sorted(cars["Топливо"].unique()))
    if st.button("Подобрать автомобили", type="primary"):
        result = cars[(cars["Цена"] <= budget) & (cars["Год"] >= year)]
        if gearbox != "Любая": result = result[result["КПП"] == gearbox]
        if fuel_choice != "Любое": result = result[result["Топливо"] == fuel_choice]
        st.write(f"Подходящих автомобилей: **{len(result)}**")
        if len(result):
            st.dataframe(result[["Марка и модель","Год","Цена","Пробег","КПП","Топливо","Привод"]], use_container_width=True, hide_index=True)
            st.session_state.scores["Запрос клиента"] += 5

elif page == "Сравнение":
    st.subheader("Сравнение двух автомобилей")
    names = cars["Марка и модель"].tolist()
    c1,c2 = st.columns(2)
    one = c1.selectbox("Первый автомобиль", names, key="compare1")
    two = c2.selectbox("Второй автомобиль", names, index=min(1,len(names)-1), key="compare2")
    first = cars[cars["Марка и модель"] == one].iloc[0]
    second = cars[cars["Марка и модель"] == two].iloc[0]
    st.dataframe(pd.DataFrame({"Параметр":[ "Цена","Год","Пробег","Мощность","КПП","Привод"], one:[rub(first["Цена"]),first["Год"],first["Пробег"],first["Мощность"],first["КПП"],first["Привод"]], two:[rub(second["Цена"]),second["Год"],second["Пробег"],second["Мощность"],second["КПП"],second["Привод"]]}), use_container_width=True, hide_index=True)
    if st.button("Кто дороже?"):
        st.info(f"Дороже: {one if first['Цена'] > second['Цена'] else two if second['Цена'] > first['Цена'] else 'Одинаковая цена'}")

elif page == "Экзамен":
    st.subheader("Экзамен")
    count = st.slider("Количество вопросов", 5, 30, 10)
    st.write("В этой версии экзамен демонстрационный: проверяется знание характеристик случайных автомобилей.")
    if st.button("Начать экзамен", type="primary"):
        st.session_state.exam = random.sample(range(len(cars)), min(count, len(cars)))
        st.session_state.exam_pos = 0
        st.session_state.exam_score = 0
    if "exam" in st.session_state and st.session_state.exam_pos < len(st.session_state.exam):
        car = cars.iloc[st.session_state.exam[st.session_state.exam_pos]]
        st.caption(f"Вопрос {st.session_state.exam_pos+1} из {len(st.session_state.exam)}")
        field = st.selectbox("Что нужно определить?", FIELDS, key=f"field_{st.session_state.exam_pos}")
        options = list(dict.fromkeys(cars[field].tolist()))
        choice = st.selectbox("Ваш ответ", options, key=f"choice_{st.session_state.exam_pos}")
        if st.button("Ответить на вопрос"):
            if str(choice) == str(car[field]):
                st.session_state.exam_score += 1
                st.success("Верно")
            else:
                st.error(f"Правильный ответ: {car[field]}")
            st.session_state.exam_pos += 1
            st.rerun()
    elif "exam" in st.session_state:
        st.success(f"Экзамен завершён: {st.session_state.exam_score} из {len(st.session_state.exam)}")
        st.session_state.scores["Экзамен"] += st.session_state.exam_score * 10
        del st.session_state.exam

elif page == "Мой прогресс":
    st.subheader("Мой прогресс")
    st.dataframe(pd.DataFrame([{"Режим":k,"Баллы":v} for k,v in st.session_state.scores.items()]), use_container_width=True, hide_index=True)
    st.metric("Всего баллов", sum(st.session_state.scores.values()))
    st.caption("В прототипе прогресс хранится в сессии браузера. Для команды подключим постоянную базу и отдельные аккаунты.")

elif page == "Руководитель":
    st.subheader("Кабинет руководителя")
    st.warning("Администраторская авторизация и управление сотрудниками появятся после подключения базы данных. Не используйте этот прототип для хранения персональных данных.")
    st.write("Здесь будут: список менеджеров, прогресс по каждому режиму, история экзаменов, слабые темы и запуск экзамена.")
    st.dataframe(pd.DataFrame([{"Режим":k,"Демо-баллы":v} for k,v in st.session_state.scores.items()]), use_container_width=True, hide_index=True)

st.divider()
st.caption("FRESH STOCK · Прототип интерфейса. Данные демонстрационные; синхронизация с сайтом Fresh пока не подключена.")
