# PROJECT-3. Предсказание рейтинга отеля (Booking)

Блок EDA SkillFactory DSPR. Соревнование [sf-booking](https://www.kaggle.com/competitions/sf-booking).

Ноутбук: [EDA_Project_3_model.ipynb](EDA_Project_3_model.ipynb)

## Цели

По отзывам гостей предсказать `reviewer_score`. Если факт сильно уезжает от модели, отель можно проверить на накрутку рейтинга.

## Данные

`hotels_train.csv` с Kaggle (около 170 МБ, 386 803 строки, как LMS `hotels.csv`) в git не кладу. Куда скачать — в [data/README.md](data/README.md).

В репозитории уже есть таблицы населения и площади стран из EDA-3 и готовый сабмит `data/submission_predict.csv`.

## Как открыть ноутбук

```bash
cd project_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt notebook
jupyter notebook EDA_Project_3_model.ipynb
```

## Что получилось

- База (только числа, пропуски нулём): MAPE около **0.141**
- После признаков из EDA-3 (город, теги, текст, население, `BinaryEncoder`, RobustScaler): MAPE около **0.126**
- Лес из шаблона курса, `n_estimators=100`, `random_state=42`
