# PROJECT-3. Предсказание рейтинга отеля (Booking)

Блок EDA, соревнование [sf-booking](https://www.kaggle.com/competitions/sf-booking).

Ноутбук: [EDA_Project_3_model.ipynb](EDA_Project_3_model.ipynb)

Считаю `reviewer_score` по отзыву. Если факт сильно уезжает от модели, отель можно проверить на накрутку.

Train с Kaggle в git не кладу, файл тяжёлый. Куда скачать, написал в [data/README.md](data/README.md). Сабмит лежит в `data/submission_predict.csv`.

На голых числах MAPE вышла 0.141. После города, тегов, текста и отбора признаков - 0.126. Лес из шаблона курса, 100 деревьев.

```bash
cd project_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt notebook
jupyter notebook EDA_Project_3_model.ipynb
```
