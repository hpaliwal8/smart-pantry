"""DynamoDB service layer. One module, generic CRUD per table.

Schema summary (all tables use user_id as partition key, sk as sort key):
  pantry:   pk=user_id   sk=item_id   attrs: name, quantity, unit, category, expiry_date
  recipes:  pk=user_id   sk=recipe_id attrs: title, ingredients[], instructions[], image_url, tags[]
  grocery:  pk=user_id   sk=item_id   attrs: name, quantity, unit, purchased(bool), source_recipe_id
  meals:    pk=user_id   sk=slot_id   attrs: day(0-6), meal(b/l/d), recipe_id
  chat:     pk=user_id   sk=ts        attrs: role, content (kept simple, not yet persisted in v1)

Note: 'recipes' is also queried for the global library by treating user_id='LIBRARY'
for shared/seeded recipes; per-user recipes use their own user_id. The match engine
queries both.
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from .. import config

_ddb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
_client = boto3.client("dynamodb", region_name=config.AWS_REGION)

ALL_TABLES = [
    config.PANTRY_TABLE,
    config.RECIPES_TABLE,
    config.GROCERY_TABLE,
    config.MEALS_TABLE,
    config.CHAT_TABLE,
]


def _to_ddb(obj: Any) -> Any:
    """Recursively convert floats to Decimal so DynamoDB accepts them."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [_to_ddb(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    return obj


def _from_ddb(obj: Any) -> Any:
    """Recursively convert Decimal back to int/float for JSON output."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, list):
        return [_from_ddb(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _from_ddb(v) for k, v in obj.items()}
    return obj


def ensure_tables() -> dict[str, str]:
    """Create all five tables if missing. Returns a status map."""
    existing = set(_client.list_tables()["TableNames"])
    statuses: dict[str, str] = {}
    for name in ALL_TABLES:
        if name in existing:
            statuses[name] = "exists"
            continue
        _client.create_table(
            TableName=name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
        )
        statuses[name] = "creating"
    # wait for any in CREATING state
    for name, status in statuses.items():
        if status == "creating":
            _client.get_waiter("table_exists").wait(TableName=name)
            statuses[name] = "created"
    return statuses


def _table(name: str):
    return _ddb.Table(name)


def put(table: str, user_id: str, sk: str, attrs: dict) -> dict:
    item = {"user_id": user_id, "sk": sk, **attrs}
    _table(table).put_item(Item=_to_ddb(item))
    return _from_ddb(item)


def get(table: str, user_id: str, sk: str) -> dict | None:
    resp = _table(table).get_item(Key={"user_id": user_id, "sk": sk})
    item = resp.get("Item")
    return _from_ddb(item) if item else None


def query_user(table: str, user_id: str) -> list[dict]:
    items: list[dict] = []
    resp = _table(table).query(KeyConditionExpression=Key("user_id").eq(user_id))
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = _table(table).query(
            KeyConditionExpression=Key("user_id").eq(user_id),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    return [_from_ddb(i) for i in items]


def delete(table: str, user_id: str, sk: str) -> None:
    _table(table).delete_item(Key={"user_id": user_id, "sk": sk})


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def now_ts() -> int:
    return int(time.time() * 1000)
