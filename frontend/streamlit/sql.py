# -*- coding: utf-8 -*-
"""
sql.py - Camada de acesso ao PostgreSQL do ChatFGV
Modo real: usa o Postgres do devcontainer/containers.
Modo mock: simula esquema e respostas fixas para desenvolvimento.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import pandas as pd

# ------------------------------------------------------------------
# Configuracao
# ------------------------------------------------------------------
PG_DSN = os.environ.get(
    "CHATFGV_PG_DSN",
    "postgresql://postgres@localhost:5432/public",
)
DEFAULT_USE_MOCK = os.environ.get("CHATFGV_SQL_MOCK", "0").strip() in ("1", "true", "yes")


def get_sql_engine(force_mock: Optional[bool] = None) -> Any:
    """
    Retorna engine SQLAlchemy configurado para o Postgres do ChatFGV.
    Em modo mock, retorna objecto stub que nao conecta.

    Se force_mock for True, usa mock independente da variavel de ambiente.
    Se force_mock for False, usa banco real independente da variavel de ambiente.
    Se force_mock for None, usa a variavel de ambiente CHATFGV_SQL_MOCK.
    """
    if force_mock is None:
        use_mock = DEFAULT_USE_MOCK
    else:
        use_mock = force_mock

    if use_mock:
        return _MockEngine()

    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError(
            "sqlalchemy nao instalado. Instale com: pip install sqlalchemy"
        ) from exc

    return create_engine(PG_DSN)


class _MockEngine:
    """Engine stub para desenvolvimento sem banco real."""

    def __init__(self) -> None:
        self.tables: Dict[str, pd.DataFrame] = _mock_tables()

    def connect(self):
        return _MockConnection(self.tables)


def _mock_tables() -> Dict[str, pd.DataFrame]:
    """Dados ficticios que simulam os schemas do ChatFGV."""
    return {
        "datatran.acidentes_transito": pd.DataFrame(
            {
                "id": [1, 2, 3],
                "data_inversa": ["2024-01-10", "2024-02-15", "2024-03-20"],
                "classificacao_acidente": ["Com Vitimas Fatais", "Com Feridos Graves", "Com Feridos Leves"],
                "causa_acidente": ["Velocidade nao adequada", "Falta de atencao", "Conducao sob influencia de alcool"],
                "br": ["SP", "RJ", "MG"],
            }
        ),
        "censo.br_setores_cd2022": pd.DataFrame(
            {
                "CO_SETOR": [1001, 1002, 1003],
                "NM_UF": ["SP", "RJ", "MG"],
                "populacao": [12000, 8500, 9300],
            }
        ),
        "dnit.contagem_de_trafego_cgplan_dez20": pd.DataFrame(
            {
                "cod_sec": [101, 102],
                "sg_uf": ["SP", "RJ"],
                "vmda_c": [12000, 9500],
            }
        ),
    }


class _MockConnection:
    def __init__(self, tables: Dict[str, pd.DataFrame]) -> None:
        self.tables = tables

    def execute(self, statement: str) -> Any:
        return _MockResult(statement, self.tables)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockResult:
    def __init__(self, statement: str, tables: Dict[str, pd.DataFrame]):
        self._statement = statement
        self._tables = tables
        self._rows = self._resolve()

    def _resolve(self) -> Optional[List[Any]]:
        st = self._statement.strip().upper()
        for tbl_name, df in self._tables.items():
            if tbl_name.replace("."," ") in st or tbl_name.split(".")[-1] in st:
                return df.to_dict(orient="records")
        return []

    def fetchall(self) -> List[Any]:
        return self._rows or []

    def keys(self) -> List[str]:
        if self._rows:
            return list(self._rows[0].keys())
        return []


def list_tables(engine: Any) -> List[str]:
    """Lista tabelas disponiveis (schema.table)."""
    if isinstance(engine, _MockEngine):
        return list(engine.tables.keys())

    from sqlalchemy import inspect
    insp = inspect(engine)
    out: List[str] = []
    for schema in insp.get_schema_names():
        for tbl in insp.get_table_names(schema=schema):
            out.append(f"{schema}.{tbl}")
    return out


def run_query(engine: Any, sql: str, limit_display: int = 50) -> pd.DataFrame:
    """
    Executa uma query SQL e retorna DataFrame (pandas).
    Em modo mock, retorna os dados ficticios correspondentes.
    """
    with engine.connect() as conn:
        if isinstance(engine, _MockEngine):
            result = conn.execute(sql)
        else:
            from sqlalchemy import text
            result = conn.execute(text(sql))
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=list(result.keys()))
        return df.head(limit_display)


def describe_schema_tables(tables: List[str]) -> str:
    """
    Retorna texto curto descritivo dos schemas para alimentar
    o agente SQL (Agent 1: gerador de query).
    """
    lines = ["Esquemas disponiveis no ChatFGV:"]
    for tbl in tables:
        lines.append(f"- {tbl}")
    lines.append("")
    lines.append("Dica: para contar registros use SELECT COUNT(*) ...")
    return "\n".join(lines)
