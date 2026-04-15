from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Revenda(Base):
    __tablename__ = "revendas"

    id        = Column(Integer, primary_key=True, index=True)
    nome      = Column(String(200), nullable=False, unique=True)
    cnpj      = Column(String(30), nullable=True)
    telefone  = Column(String(20), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    protocolos = relationship("Protocolo", back_populates="revenda_rel")


class Protocolo(Base):
    __tablename__ = "protocolos"

    id = Column(Integer, primary_key=True, index=True)

    # ── Campos diretos do CSV ──────────────────────────────────────────────────
    numero_protocolo    = Column(String(100), nullable=False, unique=True, index=True)  # PROTOCOLO
    datahora            = Column(DateTime(timezone=True), nullable=False)               # DATAHORA
    situacao            = Column(String(100), nullable=True)                            # SITUACAO
    revenda             = Column(String(200), nullable=True)                            # REVENDA
    analista            = Column(String(200), nullable=True)                            # ANALISTA
    problema            = Column(Text, nullable=True)                                   # PROBLEMA
    solucao             = Column(Text, nullable=True)                                   # SOLUCAO
    atendente           = Column(String(200), nullable=True)                            # ATENDENTE
    atendimento_id      = Column(String(100), nullable=True)                            # ATENDIMENTOID
    revenda_csv_id      = Column(String(100), nullable=True)                            # REVENDAID
    tecnico_nome        = Column(String(200), nullable=True)                            # TECNICONOME
    tipo                = Column(String(100), nullable=True)                            # TIPO
    cliente_id          = Column(String(100), nullable=True)                            # CLIENTEID
    cnpj                = Column(String(30),  nullable=True)                            # CNPJ
    avaliacao_revenda   = Column(String(50),  nullable=True)                            # AVALIACAOREVENDA
    resolvido           = Column(String(10),  nullable=True)                            # RESOLVIDO
    avaliado            = Column(String(10),  nullable=True)                            # AVALIADO
    numero_telefone     = Column(String(30),  nullable=True)                            # NUMEROTELEFONE
    tecnico_revenda     = Column(String(200), nullable=True)                            # TECNICOREVENDA
    modulo              = Column(String(200), nullable=True)                            # MODULO

    # ── Campos de controle interno ─────────────────────────────────────────────
    observacao          = Column(Text, nullable=True)
    concluido           = Column(Boolean, default=False)
    contato_realizado   = Column(Boolean, default=False)
    importado_em        = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em       = Column(DateTime(timezone=True), onupdate=func.now())

    # ── Vínculo com Revenda cadastrada no sistema ──────────────────────────────
    revenda_id          = Column(Integer, ForeignKey("revendas.id"), nullable=True)
    revenda_rel         = relationship("Revenda", back_populates="protocolos")