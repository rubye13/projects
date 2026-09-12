"""Проверка локального сервиса одним запросом"""

import json
import urllib.request

payload = {
    "sqft": 1800,
    "baths_n": 2,
    "beds_n": 3,
    "stories_n": 1,
    "year_built": 1998,
    "lotsize": 6000,
    "school_rating": 6.5,
    "school_dist": 1.2,
    "pool": 0,
    "fireplace_flg": 1,
    "remodeled": 0,
    "has_heating": 1,
    "has_cooling": 1,
    "has_parking": 1,
    "type_grp": "single_family",
    "status_grp": "for_sale",
    "state": "FL",
    "city": "Miami",
    "zip_code": "33131",
    "listed_price": 320000,
}
req = urllib.request.Request(
    "http://127.0.0.1:5001/predict",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode("utf-8"))
