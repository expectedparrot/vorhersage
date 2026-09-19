"""Discover candidate definitions without persisting or displaying market prices."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from vorhersage import market_data
from vorhersage.common import now, require

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "Refusing to overwrite a discovery receipt.")
    path.write_text(json.dumps(value, indent=2) + "\n")


def catalog(category):
    try:
        response = market_data.get(market_data.KALSHI + "/series?" + urlencode(
            {"category": category, "include_volume": "false", "include_product_metadata": "false"}))
        return {"category": category, "retrieved_at": response["retrieved_at"],
                "request_url": response["url"], "response_sha256": response["response_sha256"],
                "series": [{k: s.get(k) for k in ("ticker", "title", "category", "frequency")}
                           for s in response["data"]["series"]]}
    except ValueError as exc:
        return {"category": category, "failed_at": now(), "error": str(exc)}


def definitions(series):
    try:
        value = market_data.browse("kalshi", series=series, limit=50, pages=2)
        return {"series": series, "retrieved_at": now(), **value}
    except ValueError as exc:
        return {"series": series, "failed_at": now(), "error": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("catalog", "definitions"))
    parser.add_argument("items", nargs="+")
    args = parser.parse_args()
    function = catalog if args.action == "catalog" else definitions
    with ThreadPoolExecutor(max_workers=3) as pool:
        for item, result in zip(args.items, pool.map(function, args.items)):
            write(HERE / args.action / (item.replace(" ", "_") + ".json"), result)
            print(item, len(result.get("series" if args.action == "catalog" else "candidates", [])), result.get("error", "ok"))
