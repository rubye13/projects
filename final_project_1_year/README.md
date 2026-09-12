# Прогноз цены жилья для агентства недвижимости

Итоговый проект 1 года SkillFactory DSPR. Бриф 1.

На тесте победил CatBoost: **MAE 127 тыс., MAPE 0.24, R2 0.77**. Сервис Flask отдаёт оценку цены и флаг, дешевле ли лот модели.

- Ноутбук: [`notebooks/final_project_rubinshtein.ipynb`](notebooks/final_project_rubinshtein.ipynb)
- Если Preview на GitHub не откроется: [nbviewer](https://nbviewer.org/github/rubye13/projects/blob/master/final_project_1_year/notebooks/final_project_rubinshtein.ipynb)

## Оглавление

1. [Цели и задачи](#цели-и-задачи)
2. [Данные](#данные)
3. [Что в папке](#что-в-папке)
4. [Результаты](#результаты)
5. [Как запустить](#как-запустить)

## Цели и задачи

Риелторы долго сортируют объявления и ищут выгодные лоты. Нужна модель справедливой цены и сервис, который её считает

1. Почистить сырой датасет объявлений США
2. Проверить гипотезы статистикой и графиками и использовать выводы в признаках
3. Сравнить медиану с линейной моделью, лесом, стекингом и бустингом
4. Понять, какие признаки тянут цену, сохранить модель и поднять сервис

## Данные

Файл `data/data.csv` в git не кладу (около 285 МБ, 377 185 строк, выдаётся в LMS). Поля: статус, тип, адрес, ванные, факты о доме, камин, город, школы, площадь, индекс, спальни, штат, этажи, MLS, два столбца бассейна, цена строкой. Датасет заранее не чистили

После очистки остаётся около 336 тысяч жилых лотов с ценой от 10 тысяч до 5 млн долларов. Для пересчёта ноутбука csv положить в `data/data.csv`. Сервис с готовой моделью в `models/` поднимается без датасета

## Что в папке

```
.
├── notebooks/final_project_rubinshtein.ipynb   # решение, с графиками
├── src/cleaning.py                             # разбор сырых полей
├── src/features.py                             # признаки для ноутбука и сервиса
├── web/app.py                                  # GET /health, POST /predict
├── web/client.py                               # пример запроса
├── models/price_model.joblib                   # обученный CatBoost
├── requirements.txt
├── Dockerfile
└── setup_mac.sh                                # опционально, macOS + uv
```

Очистка одна и та же в ноутбуке и в сервисе

## Результаты

Метрики на тесте 20%, `random_state=42`:

| модель | MAE | MAPE | R2 |
|---|---|---|---|
| медиана | 335k | 0.97 | -0.10 |
| медиана по штату | 308k | 0.86 | 0.04 |
| линейка / Ridge | 234k | 0.57 | 0.39 |
| случайный лес | 183k | 0.42 | 0.63 |
| бустинг sklearn | 199k | 0.46 | 0.55 |
| стекинг Ridge+лес | 182k | 0.42 | 0.64 |
| **CatBoost** | **127k** | **0.24** | **0.77** |

Город и индекс в лес не тащил: слишком много значений. CatBoost взял их как категории. По SHAP сильнее всего индекс, площадь, штат и город. 3 фолда на обучении, сетка у леса, Optuna у CatBoost

Если в запрос передать цену объявления (`listed_price`), сервис скажет, дешевле ли лот модели. Пример (Miami, индекс 33131, в объявлении 320 тыс.):

```json
{"predicted_price": 662672.23, "listed_price": 320000.0, "delta": -342672.23, "undervalued": true}
```

## Как запустить

Python 3.12. Команды ниже из корня этой папки.

Окружение:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

На Windows активация: `.venv\Scripts\activate`. На маке вместо этих трёх строк можно `zsh setup_mac.sh`

### Сервис (csv не нужен)

```bash
python web/app.py
```

Порт 5001: на маке 5000 часто занят трансляцией экрана. В другом окне:

```bash
curl -s http://127.0.0.1:5001/health
```

```bash
curl -s http://127.0.0.1:5001/predict \
  -H "Content-Type: application/json" \
  -d '{"sqft":1800,"baths_n":2,"beds_n":3,"stories_n":1,"year_built":1998,"lotsize":6000,"school_rating":6.5,"school_dist":1.2,"pool":0,"fireplace_flg":1,"remodeled":0,"has_heating":1,"has_cooling":1,"has_parking":1,"type_grp":"single_family","status_grp":"for_sale","state":"FL","city":"Miami","zip_code":"33131","listed_price":320000}'
```

Или `python web/client.py` - тот же запрос

Docker:

```bash
docker build -t realty-price .
docker run -p 5001:5001 realty-price
```

### Ноутбук (нужен data.csv из LMS)

```bash
pip install notebook ipykernel
jupyter notebook notebooks/final_project_rubinshtein.ipynb
```

Пересчитывать не обязательно: выходы и графики уже сохранены
