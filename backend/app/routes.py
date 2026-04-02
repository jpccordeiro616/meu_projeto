from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional
import csv
import io
from datetime import datetime
from pathlib import Path

from app.database import get_db
from app import models, schemas

router = APIRouter()

# ── Mapeamento EXATO das colunas do CSV ──────────────────────────────────────
#
#  PROTOCOLO|DATAHORA|SITUACAO|REVENDA|ANALISTA|PROBLEMA|SOLUCAO|ATENDENTE|
#  ATENDIMENTOID|REVENDAID|USUARIOANALISTAID|ATENDIMENTOPROBLEMAID|SITUACAOID|
#  USUARIOATENDENTEID|ATENDIMENTOSOLUCAOID|TECNICONOME|TIPO|CLIENTEID|CNPJ|
#  AVALIACAOREVENDA|RESOLVIDO|AVALIADO|NUMEROTELEFONE|TECNICOREVENDA|MODULO

CSV_COLUNAS = {
    "numero_protocolo": "PROTOCOLO",
    "datahora":         "DATAHORA",
    "situacao":         "SITUACAO",
    "revenda":          "REVENDA",
    "analista":         "ANALISTA",
    "problema":         "PROBLEMA",
    "solucao":          "SOLUCAO",
    "atendente":        "ATENDENTE",
    "atendimento_id":   "ATENDIMENTOID",
    "revenda_csv_id":   "REVENDAID",
    "tecnico_nome":     "TECNICONOME",
    "tipo":             "TIPO",
    "cliente_id":       "CLIENTEID",
    "cnpj":             "CNPJ",
    "avaliacao_revenda":"AVALIACAOREVENDA",
    "resolvido":        "RESOLVIDO",
    "avaliado":         "AVALIADO",
    "numero_telefone":  "NUMEROTELEFONE",
    "tecnico_revenda":  "TECNICOREVENDA",
    "modulo":           "MODULO",
}

# Valores da coluna SITUACAO considerados pendentes
SITUACOES_PENDENTE = {"pendente", "aberto", "em aberto", "aguardando", "em andamento", "open", "1"}


def _col(row: dict, headers_lower: dict, campo: str) -> str:
    """Retorna o valor de uma coluna pelo nome (case-insensitive), ou ''."""
    nome_csv = CSV_COLUNAS.get(campo, "")
    chave = headers_lower.get(nome_csv.lower(), nome_csv)
    return (row.get(chave) or "").strip()


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


# ── Import CSV — DEVE ficar ANTES de /{protocolo_id} para não colidir ────────

@router.post("/protocolos/importar", response_model=schemas.ImportResult)
async def importar_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv")

    conteudo = await file.read()

    # Detectar encoding
    texto = None
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise HTTPException(status_code=400, detail="Não foi possível decodificar o arquivo.")

    # Detectar delimitador: prioriza | (formato do sistema), depois ; e ,
    amostra = texto[:4096]
    contagens = {"|": amostra.count("|"), ";": amostra.count(";"), ",": amostra.count(",")}
    delimitador = max(contagens, key=contagens.get)

    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    headers = list(reader.fieldnames or [])

    # Mapa de header em minúsculo → header original (para busca case-insensitive)
    headers_lower = {h.strip().lower(): h.strip() for h in headers}

    # Verificar se a coluna PROTOCOLO existe
    col_protocolo = headers_lower.get("protocolo")
    if not col_protocolo:
        raise HTTPException(
            status_code=422,
            detail=f"Coluna PROTOCOLO não encontrada. Colunas detectadas: {headers}"
        )

    total = 0
    pendentes = 0
    inseridos = 0
    ja_existentes = 0
    ignorados = 0
    erros: list[str] = []

    for i, row in enumerate(reader, start=2):
        total += 1

        # ── Filtrar: ignora registros onde RESOLVIDO = "Sim" ──────────────
        resolvido_val = _col(row, headers_lower, "resolvido").strip().lower()
        if resolvido_val == "sim":
            ignorados += 1
            continue

        pendentes += 1

        # ── Número do protocolo ────────────────────────────────────────────
        num = _col(row, headers_lower, "numero_protocolo")
        if not num:
            erros.append(f"Linha {i}: coluna PROTOCOLO vazia, ignorado.")
            continue

        # ── Duplicata ──────────────────────────────────────────────────────
        if db.query(models.Protocolo).filter(
            models.Protocolo.numero_protocolo == num
        ).first():
            ja_existentes += 1
            continue

        # ── Data/hora ──────────────────────────────────────────────────────
        dh_raw = _col(row, headers_lower, "datahora")
        dh = parse_datahora(dh_raw) if dh_raw else None
        if not dh:
            if dh_raw:
                erros.append(f"Linha {i}: data '{dh_raw}' não reconhecida, usando agora.")
            dh = datetime.now()

        # ── Tentar vincular Revenda cadastrada pelo nome ───────────────────
        nome_revenda = _col(row, headers_lower, "revenda")
        revenda_obj = None
        if nome_revenda:
            revenda_obj = db.query(models.Revenda).filter(
                models.Revenda.nome.ilike(nome_revenda)
            ).first()

        # ── Criar Protocolo ────────────────────────────────────────────────
        protocolo = models.Protocolo(
            numero_protocolo = num,
            datahora         = dh,
            situacao         = _col(row, headers_lower, "situacao") or None,
            revenda          = nome_revenda or None,
            analista         = _col(row, headers_lower, "analista") or None,
            problema         = _col(row, headers_lower, "problema") or None,
            solucao          = _col(row, headers_lower, "solucao")  or None,
            atendente        = _col(row, headers_lower, "atendente") or None,
            atendimento_id   = _col(row, headers_lower, "atendimento_id") or None,
            revenda_csv_id   = _col(row, headers_lower, "revenda_csv_id") or None,
            tecnico_nome     = _col(row, headers_lower, "tecnico_nome") or None,
            tipo             = _col(row, headers_lower, "tipo") or None,
            cliente_id       = _col(row, headers_lower, "cliente_id") or None,
            cnpj             = _col(row, headers_lower, "cnpj") or None,
            avaliacao_revenda= _col(row, headers_lower, "avaliacao_revenda") or None,
            resolvido        = _col(row, headers_lower, "resolvido") or None,
            avaliado         = _col(row, headers_lower, "avaliado") or None,
            numero_telefone  = _col(row, headers_lower, "numero_telefone") or None,
            tecnico_revenda  = _col(row, headers_lower, "tecnico_revenda") or None,
            modulo           = _col(row, headers_lower, "modulo") or None,
            revenda_id       = revenda_obj.id if revenda_obj else None,
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


# ── Protocolo por ID — APÓS /importar ─────────────────────────────────────────

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