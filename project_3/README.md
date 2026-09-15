# PROJECT-3. Предсказание рейтинга отеля (Booking)

Блок EDA SkillFactory DSPR. Соревнование [sf-booking](https://www.kaggle.com/competitions/sf-booking).

Ноутбук: [EDA_Project_3_model.ipynb](EDA_Project_3_model.ipynb)

## Оглавление

1. [Цель](#цель)
2. [Данные](#данные)
3. [Этапы](#этапы)
4. [Результаты](#результаты)
5. [Как запустить](#как-запустить)

## Цель

По отзыву предсказать `reviewer_score`. Если факт сильно уезжает от модели, отель можно проверить на накрутку рейтинга.

## Данные

Train с Kaggle: `data/sf-booking/hotels_train.csv` (~170 МБ, 386 803 строки, как LMS `hotels.csv`). В git не кладу. Куда скачать — [data/README.md](data/README.md).

В репозитории: таблицы населения и площади стран из EDA-3 и сабмит `data/submission_predict.csv`.

## Этапы

1. **Очистка.** Пропуски только в `lat`/`lng` — медианой отеля, иначе города. 307 полных дублей строк снял. Хвосты по числу слов в отзыве клипнул методом Тьюки, сами строки не удалял.
2. **Исследование.** Оценка прибита к 8–10, бизнес ставит ниже leisure, длинный негатив бьёт по баллу. Город почти не разделяет медианы.
3. **Признаки.** Город из адреса, дата, теги, флаги из текста, население и площадь страны гостя.
4. **Отбор.** Спирмен: выкинул `additional_number_of_scoring` (почти копия числа отзывов) и страну отеля (дубль города). chi2 / ANOVA, затем `SelectKBest(k=50)`.
5. **Преобразование.** `OneHotEncoder` на город, `BinaryEncoder` на национальность и имя отеля, `log1p`, `RobustScaler`.
6. **Модель.** `RandomForestRegressor(n_estimators=100)` из шаблона курса.

## Результаты

| этап | MAPE |
|---|---|
| база (числа, пропуски нулём) | 0.141 |
| после очистки, признаков и отбора | **0.126** |

Лес тот же: `n_estimators=100`, `random_state=42`.

Сабмит: `data/submission_predict.csv`.

## Как запустить

```bash
cd project_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt notebook
jupyter notebook EDA_Project_3_model.ipynb
```
