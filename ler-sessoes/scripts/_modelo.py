"""Modelo comum de sessao e evento que todo leitor devolve."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Evento:
    """Um evento resumido de uma sessao."""

    n: int
    instante: datetime | None
    tipo: str
    duracao_s: float | None
    exit: int | None
    texto: str
    detalhe: str


@dataclass
class Sessao:
    """Metadados de uma sessao e, quando lidos, os seus eventos."""

    id: str
    ferramenta: str
    pai: str | None = None
    nome: str | None = None
    modelo: str | None = None
    esforco: str | None = None
    cwd: str | None = None
    inicio: datetime | None = None
    duracao_s: float | None = None
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    termino: str = "sem-fim"
    caminho: Path | None = None
    eventos: list[Evento] = field(default_factory=list)
