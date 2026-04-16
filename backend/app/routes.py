from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import csv
import io
from datetime import datetime, date
from pathlib import Path

from app.database import get_db
from app import models, schemas

router = APIRouter()

# ── Usuários hardcoded ────────────────────────────────────────────────────────

USUARIOS = {
    "analista":   {"senha": "Digisat123", "perfil": "analista"},
    "consultora": {"senha": "digisat",    "perfil": "leitura"},
    "revenda":    {"senha": "revenda",    "perfil": "leitura"},
}


@router.post("/login")
def login(data: dict):
    login_str = (data.get("login") or "").strip().lower()
    senha = (data.get("senha") or "").strip()
    usuario = USUARIOS.get(login_str)
    if not usuario or usuario["senha"] != senha:
        raise HTTPException(status_code=401, detail="Login ou senha inválidos.")
    return {"login": login_str, "perfil": usuario["perfil"]}


# ── Mapeamento EXATO das colunas do CSV ──────────────────────────────────────
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
    "revcelular":       "REVCELULAR",
    "revtelefone":      "REVTELEFONE",
}

SITUACOES_PENDENTE = {"pendente", "aberto", "em aberto", "aguardando", "em andamento", "open", "1"}


def _col(row: dict, headers_lower: dict, campo: str) -> str:
    nome_csv = CSV_COLUNAS.get(campo, "")
    chave = headers_lower.get(nome_csv.lower(), nome_csv)
    return (row.get(chave) or "").strip()


def _telefone_revenda(row: dict, headers_lower: dict) -> str:
    """Pega REVCELULAR; se vazio, usa REVTELEFONE; se vazio, usa NUMEROTELEFONE."""
    cel = _col(row, headers_lower, "revcelular")
    if cel:
        return cel
    tel = _col(row, headers_lower, "revtelefone")
    if tel:
        return tel
    return _col(row, headers_lower, "numero_telefone")


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
def listar_revendas(busca: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Revenda)
    if busca:
        termo = f"%{busca}%"
        q = q.filter(
            models.Revenda.nome.ilike(termo) |
            models.Revenda.cnpj.ilike(termo)
        )
    return q.order_by(models.Revenda.nome).all()


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
    concluido:    Optional[bool] = Query(None),
    busca:        Optional[str]  = Query(None),
    mes:          Optional[int]  = Query(None),
    ano:          Optional[int]  = Query(None),
    data_inicio:  Optional[date] = Query(None),
    data_fim:     Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Protocolo).options(joinedload(models.Protocolo.revenda_rel))
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
    if mes:
        from sqlalchemy import extract
        q = q.filter(extract('month', models.Protocolo.datahora) == mes)
    if ano:
        from sqlalchemy import extract
        q = q.filter(extract('year', models.Protocolo.datahora) == ano)
    if data_inicio:
        q = q.filter(models.Protocolo.datahora >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        q = q.filter(models.Protocolo.datahora <= datetime.combine(data_fim, datetime.max.time()))
    return q.order_by(models.Protocolo.datahora.asc()).all()


# ── Import CSV ────────────────────────────────────────────────────────────────

@router.post("/protocolos/importar", response_model=schemas.ImportResult)
async def importar_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv")

    conteudo = await file.read()

    texto = None
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise HTTPException(status_code=400, detail="Não foi possível decodificar o arquivo.")

    amostra = texto[:4096]
    contagens = {"|": amostra.count("|"), ";": amostra.count(";"), ",": amostra.count(",")}
    delimitador = max(contagens, key=contagens.get)

    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    headers = list(reader.fieldnames or [])
    headers_lower = {h.strip().lower(): h.strip() for h in headers}

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

        resolvido_val = _col(row, headers_lower, "resolvido").strip().lower()
        if resolvido_val == "sim":
            ignorados += 1
            continue

        pendentes += 1

        num = _col(row, headers_lower, "numero_protocolo")
        if not num:
            erros.append(f"Linha {i}: coluna PROTOCOLO vazia, ignorado.")
            continue

        if db.query(models.Protocolo).filter(
            models.Protocolo.numero_protocolo == num
        ).first():
            ja_existentes += 1
            continue

        dh_raw = _col(row, headers_lower, "datahora")
        dh = parse_datahora(dh_raw) if dh_raw else None
        if not dh:
            if dh_raw:
                erros.append(f"Linha {i}: data '{dh_raw}' não reconhecida, usando agora.")
            dh = datetime.now()

        nome_revenda = _col(row, headers_lower, "revenda")
        revenda_obj = None
        if nome_revenda:
            revenda_obj = db.query(models.Revenda).filter(
                models.Revenda.nome.ilike(nome_revenda)
            ).first()
            # Cria automaticamente se não existir
            if not revenda_obj:
                telefone_rev = _telefone_revenda(row, headers_lower)
                if telefone_rev:
                    cnpj_rev = _col(row, headers_lower, "cnpj") or None
                    revenda_obj = models.Revenda(
                        nome=nome_revenda,
                        cnpj=cnpj_rev,
                        telefone=telefone_rev
                    )
                    db.add(revenda_obj)
                    db.flush()
            else:
                if not revenda_obj.cnpj:
                    cnpj_rev = _col(row, headers_lower, "cnpj") or None
                    if cnpj_rev:
                        revenda_obj.cnpj = cnpj_rev

        telefone = _telefone_revenda(row, headers_lower)

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
            numero_telefone  = telefone or None,
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


# ── Protocolo por ID ─────────────────────────────────────────────────────────

@router.get("/protocolos/{protocolo_id}", response_model=schemas.ProtocoloOut)
def obter_protocolo(protocolo_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Protocolo).options(joinedload(models.Protocolo.revenda_rel)).filter(models.Protocolo.id == protocolo_id).first()
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
def obter_stats(mes: Optional[int] = Query(None), db: Session = Depends(get_db)):
    from sqlalchemy import extract, func as sqlfunc, case
    ano_atual = datetime.now().year

    q_base = db.query(models.Protocolo)
    if mes:
        q_base = q_base.filter(extract('month', models.Protocolo.datahora) == mes)

    total      = q_base.count()
    pendentes  = q_base.filter(models.Protocolo.concluido == False).count()
    concluidos = q_base.filter(models.Protocolo.concluido == True).count()
    revendas   = db.query(models.Revenda).count()

    resolvido_dist = db.query(
        models.Protocolo.resolvido,
        sqlfunc.count(models.Protocolo.id).label('total')
    ).group_by(models.Protocolo.resolvido).all()

    contagem = {'Sim': 0, 'Não': 0}
    for r in resolvido_dist:
        label = (r.resolvido or '').strip()
        if label == 'Sim':
            contagem['Sim'] += r.total
        else:
            contagem['Não'] += r.total

    grafico_resolvido = [
        {"label": k, "total": v}
        for k, v in contagem.items() if v > 0
    ]

    conc_mes = db.query(
        extract('month', models.Protocolo.datahora).label('mes'),
        sqlfunc.count(models.Protocolo.id).label('total'),
        sqlfunc.sum(
            case((models.Protocolo.concluido == True, 1), else_=0)
        ).label('conc')
    ).filter(
        extract('year', models.Protocolo.datahora) == ano_atual
    ).group_by(extract('month', models.Protocolo.datahora)
    ).order_by(extract('month', models.Protocolo.datahora)).all()

    grafico_conclusao = []
    for row in conc_mes:
        t = int(row.total or 0)
        c = int(row.conc  or 0)
        grafico_conclusao.append({
            "mes":        int(row.mes),
            "total":      t,
            "concluidos": c,
            "pct":        round(c / t * 100, 1) if t else 0,
        })

    por_analista = db.query(
        models.Protocolo.analista,
        sqlfunc.count(models.Protocolo.id).label('total')
    ).filter(
        models.Protocolo.analista != None,
        models.Protocolo.analista != ''
    )
    if mes:
        por_analista = por_analista.filter(extract('month', models.Protocolo.datahora) == mes)
    por_analista = por_analista.group_by(models.Protocolo.analista
    ).order_by(sqlfunc.count(models.Protocolo.id).desc()).all()

    por_revenda = db.query(
        models.Protocolo.revenda,
        sqlfunc.count(models.Protocolo.id).label('total')
    ).filter(
        models.Protocolo.revenda != None,
        models.Protocolo.revenda != ''
    )
    if mes:
        por_revenda = por_revenda.filter(extract('month', models.Protocolo.datahora) == mes)
    por_revenda = por_revenda.group_by(models.Protocolo.revenda
    ).order_by(sqlfunc.count(models.Protocolo.id).desc()).limit(10).all()

    return {
        "total_protocolos":     total,
        "pendentes":            pendentes,
        "concluidos":           concluidos,
        "revendas_cadastradas": revendas,
        "grafico_resolvido":    grafico_resolvido,
        "grafico_conclusao":    grafico_conclusao,
        "por_analista":         [{"nome": r.analista, "total": r.total} for r in por_analista],
        "por_revenda":          [{"nome": r.revenda,   "total": r.total} for r in por_revenda],
    }