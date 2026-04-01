from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

@router.get("/")
def home():
    return {"mensagem": "API funcionando"}


class Usuario(BaseModel):
    nome: str
    email: str

@router.post("/usuarios")
def criar_usuario(usuario: Usuario):
    return {
        "mensagem": f"Usuário {usuario.nome} criado com sucesso"
    }