from __future__ import annotations

import oracledb
from contextlib import contextmanager
from core.config import settings
from core.logger import get_logger

log = get_logger("db.oracle")


class OracleDB:
    def __init__(self) -> None:
        if not (settings.oracle_user and settings.oracle_password and settings.oracle_dsn):
            raise RuntimeError("Oracle credentials missing. Please set ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN in .env")

        self.pool = oracledb.create_pool(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
            min=1,
            max=5,
            increment=1,
            getmode=oracledb.POOL_GETMODE_WAIT,
        )
        log.info("Oracle pool created")

    @contextmanager
    def conn(self):
        c = self.pool.acquire()
        try:
            yield c
        finally:
            self.pool.release(c)

    def fetch_df(self, sql: str, binds: dict | None = None):
        import pandas as pd

        with self.conn() as c:
            cur = c.cursor()
            cur.execute(sql, binds or {})
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)

    def fetch_rows(self, sql: str, binds: dict | None = None, max_rows: int | None = None):
        with self.conn() as c:
            cur = c.cursor()
            cur.execute(sql, binds or {})
            if max_rows is None:
                return cur.fetchall()
            return cur.fetchmany(max_rows)

    def execute_scalar(self, sql: str, binds: dict | None = None):
        with self.conn() as c:
            cur = c.cursor()
            cur.execute(sql, binds or {})
            row = cur.fetchone()
            return row[0] if row else None


db = OracleDB()
