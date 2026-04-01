from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Revenda(Base):
    __tablename__ = "revendas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False, unique=True)
    telefone = Column(String(20), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    protocolos = relationship("Protocolo", back_populates="revenda_rel")


class Protocolo(Base):
    __tablename__ = "protocolos"

    id = Column(Integer, primary_key=True, index=True)
    numero_protocolo = Column(String(100), nullable=False, unique=True, index=True)
    datahora = Column(DateTime(timezone=True), nullable=False)
    revenda = Column(String(200), nullable=True)
    revenda_id = Column(Integer, ForeignKey("revendas.id"), nullable=True)
    analista = Column(String(200), nullable=True)
    problema = Column(Text, nullable=True)
    solucao = Column(Text, nullable=True)
    observacao = Column(Text, nullable=True)
    concluido = Column(Boolean, default=False)
    importado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())

    revenda_rel = relationship("Revenda", back_populates="protocolos")
