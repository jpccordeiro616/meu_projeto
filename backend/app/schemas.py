from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Revenda ──────────────────────────────────────────────────────────────────

class RevendaBase(BaseModel):
    nome: str
    telefone: str


class RevendaCreate(RevendaBase):
    pass


class RevendaUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None


class RevendaOut(RevendaBase):
    id: int
    criado_em: datetime

    class Config:
        from_attributes = True


# ── Protocolo ─────────────────────────────────────────────────────────────────

class ProtocoloBase(BaseModel):
    numero_protocolo: str
    datahora: datetime
    revenda: Optional[str] = None
    analista: Optional[str] = None
    problema: Optional[str] = None
    solucao: Optional[str] = None


class ProtocoloUpdate(BaseModel):
    observacao: Optional[str] = None
    concluido: Optional[bool] = None


class ProtocoloOut(ProtocoloBase):
    id: int
    observacao: Optional[str] = None
    concluido: bool
    importado_em: datetime
    atualizado_em: Optional[datetime] = None
    revenda_rel: Optional[RevendaOut] = None

    class Config:
        from_attributes = True


# ── Import CSV ────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    total_lidos: int
    pendentes_encontrados: int
    novos_inseridos: int
    ja_existentes: int
    erros: list[str] = []
