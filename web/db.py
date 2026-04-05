"""Async wrappers around synchronous db/connection.py queries."""

import asyncio
from functools import partial

from db.connection import get_db


def _query(sql: str, params: tuple = ()) -> list[dict]:
    db = get_db()
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    db = get_db()
    row = db.execute(sql, params).fetchone()
    return dict(row) if row else None


def _execute(sql: str, params: tuple = ()) -> None:
    db = get_db()
    db.execute(sql, params)
    db.commit()


async def query(sql: str, params: tuple = ()) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_query, sql, params))


async def query_one(sql: str, params: tuple = ()) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_query_one, sql, params))


async def execute(sql: str, params: tuple = ()) -> None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_execute, sql, params))
