from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional
import csv
import io
from datetime import datetime

from app.database import get_db
from app import models, schemas

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

COLUNAS_ESPERADAS = {
    "protocolo": ["protocolo", "numero_protocolo", "número", "numero", "nº"],
    "datahora":  ["datahora", "data_hora", "data hora", "data/hora", "abertura", "data"],
    "revenda":   ["revenda", "cliente", "empresa"],
    "analista":  ["analista", "responsavel", "responsável", "atendente"],
    "problema":  ["problema", "descricao", "descrição", "assunto", "ocorrencia", "ocorrência"],
    "solucao":   ["solucao", "solução", "resolucao", "resolução", "fechamento"],
}

STATUS_PENDENTE = ["pendente", "aberto", "em aberto", "aguardando", "em andamento", "open"]


def mapear_coluna(headers: list[str], variantes: list[str]) -> Optional[str]:
    """Encontra o nome da coluna no CSV baseado em variantes conhecidas."""
    for h in headers:
        if h.strip().lower() in variantes:
            return h
    return None


def parse_datahora(valor: str) -> Optional[datetime]:
    formatos = [
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        "%d/%m/%Y", "%Y-%m-%d",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(valor.strip(), fmt)
        except ValueError:
            continue
    return None


# ── Revendas ──────────────────────────────────────────────────────────────────

@router.get("/revendas", response_model=list[schemas.RevendaOut])
def listar_revendas(db: Session = Depends(get_db)):
    return db.query(models.Revenda).order_by(models.Revenda.nome).all()


@router.post("/revendas", response_model=schemas.RevendaOut, status_code=201)
def criar_revenda(data: schemas.RevendaCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Revenda).filter(
        models.Revenda.nome.ilike(data.nome)
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Revenda já cadastrada.")
    revenda = models.Revenda(**data.model_dump())
    db.add(revenda)
    db.commit()
    db.refresh(revenda)
    return revenda


@router.put("/revendas/{revenda_id}", response_model=schemas.RevendaOut)
def atualizar_revenda(revenda_id: int, data: schemas.RevendaUpdate, db: Session = Depends(get_db)):
    revenda = db.query(models.Revenda).filter(models.Revenda.id == revenda_id).first()
    if not revenda:
        raise HTTPException(status_code=404, detail="Revenda não encontrada.")
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(revenda, campo, valor)
    db.commit()
    db.refresh(revenda)
    return revenda


@router.delete("/revendas/{revenda_id}", status_code=204)
def deletar_revenda(revenda_id: int, db: Session = Depends(get_db)):
    revenda = db.query(models.Revenda).filter(models.Revenda.id == revenda_id).first()
    if not revenda:
        raise HTTPException(status_code=404, detail="Revenda não encontrada.")
    db.delete(revenda)
    db.commit()


# ── Protocolos ────────────────────────────────────────────────────────────────

@router.get("/protocolos", response_model=list[schemas.ProtocoloOut])
def listar_protocolos(
    concluido: Optional[bool] = Query(None),
    busca: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Protocolo)
    if concluido is not None:
        q = q.filter(models.Protocolo.concluido == concluido)
    if busca:
        termo = f"%{busca}%"
        q = q.filter(
            models.Protocolo.numero_protocolo.ilike(termo) |
            models.Protocolo.revenda.ilike(termo) |
            models.Protocolo.analista.ilike(termo) |
            models.Protocolo.problema.ilike(termo)
        )
    return q.order_by(models.Protocolo.datahora.desc()).all()


@router.get("/protocolos/{protocolo_id}", response_model=schemas.ProtocoloOut)
def obter_protocolo(protocolo_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Protocolo).filter(models.Protocolo.id == protocolo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
    return p


@router.patch("/protocolos/{protocolo_id}", response_model=schemas.ProtocoloOut)
def atualizar_protocolo(protocolo_id: int, data: schemas.ProtocoloUpdate, db: Session = Depends(get_db)):
    p = db.query(models.Protocolo).filter(models.Protocolo.id == protocolo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    p.atualizado_em = datetime.now()
    db.commit()
    db.refresh(p)
    return p


@router.delete("/protocolos/{protocolo_id}", status_code=204)
def deletar_protocolo(protocolo_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Protocolo).filter(models.Protocolo.id == protocolo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
    db.delete(p)
    db.commit()


# ── Import CSV ────────────────────────────────────────────────────────────────

@router.post("/protocolos/importar", response_model=schemas.ImportResult)
async def importar_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv")

    conteudo = await file.read()

    # Detectar encoding
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=400, detail="Não foi possível decodificar o arquivo.")

    # Detectar delimitador
    amostra = texto[:2048]
    delimitador = ";" if amostra.count(";") > amostra.count(",") else ","

    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    headers = reader.fieldnames or []

    col = {k: mapear_coluna(headers, v) for k, v in COLUNAS_ESPERADAS.items()}

    total = 0
    pendentes = 0
    inseridos = 0
    ja_existentes = 0
    erros = []

    for i, row in enumerate(reader, start=2):
        total += 1

        # Verificar coluna de status (se existir coluna "status")
        status_col = mapear_coluna(headers, ["status", "situacao", "situação", "estado"])
        if status_col:
            status_val = (row.get(status_col) or "").strip().lower()
            if status_val not in STATUS_PENDENTE:
                continue

        pendentes += 1

        # Extrair número do protocolo
        num = (row.get(col["protocolo"]) or "").strip() if col["protocolo"] else ""
        if not num:
            erros.append(f"Linha {i}: protocolo vazio, ignorado.")
            continue

        # Verificar duplicata
        existente = db.query(models.Protocolo).filter(
            models.Protocolo.numero_protocolo == num
        ).first()
        if existente:
            ja_existentes += 1
            continue

        # Data/hora
        dh_raw = (row.get(col["datahora"]) or "").strip() if col["datahora"] else ""
        dh = parse_datahora(dh_raw) if dh_raw else datetime.now()
        if not dh:
            erros.append(f"Linha {i}: data '{dh_raw}' não reconhecida, usando agora.")
            dh = datetime.now()

        protocolo = models.Protocolo(
            numero_protocolo=num,
            datahora=dh,
            revenda=(row.get(col["revenda"]) or "").strip() if col["revenda"] else None,
            analista=(row.get(col["analista"]) or "").strip() if col["analista"] else None,
            problema=(row.get(col["problema"]) or "").strip() if col["problema"] else None,
            solucao=(row.get(col["solucao"]) or "").strip() if col["solucao"] else None,
        )
        db.add(protocolo)
        inseridos += 1

    db.commit()

    return schemas.ImportResult(
        total_lidos=total,
        pendentes_encontrados=pendentes,
        novos_inseridos=inseridos,
        ja_existentes=ja_existentes,
        erros=erros,
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def obter_stats(db: Session = Depends(get_db)):
    total = db.query(models.Protocolo).count()
    pendentes = db.query(models.Protocolo).filter(models.Protocolo.concluido == False).count()
    concluidos = db.query(models.Protocolo).filter(models.Protocolo.concluido == True).count()
    revendas = db.query(models.Revenda).count()
    return {
        "total_protocolos": total,
        "pendentes": pendentes,
        "concluidos": concluidos,
        "revendas_cadastradas": revendas,
    }
