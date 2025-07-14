import logging
import os
from typing import Any, Mapping, Sequence

import pandas as pd
import psycopg2
from psycopg2.extensions import connection

logger = logging.getLogger("boa-guard")


class SQL_Class:
    def __init__(self) -> None:
        self.connection: connection | None = None
        self.connect()

    def connect(self) -> None:
        if self.connection is None:
            self.connection = psycopg2.connect(
                host=os.environ["METRICS_HOST"],
                database=os.environ["METRICS_DB"],
                user=os.environ["METRICS_USER"],
                password=os.environ["METRICS_PWD"],
                port=os.environ.get("METRICS_PORT", "5432"),
            )

    def execute(
        self, query: str, vars: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        if self.connection is None:
            return pd.DataFrame()

        try:
            with self.connection.cursor() as cur:
                cur.execute(query, vars=vars)
                if cur.description:
                    records = cur.fetchall()
                    column_names = [desc[0] for desc in cur.description]
                    df = pd.DataFrame(records, columns=column_names)
                else:
                    df = pd.DataFrame()
            self.connection.commit()
            return df
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.warning(f"An SQL error occurred ({type(e).__name__}): {e})")
            return pd.DataFrame()

    def __del__(self) -> None:
        if self.connection:
            self.connection.close()


SQL = SQL_Class()
