const botao = document.getElementById("botao")
const resultado = document.getElementById("resultado")

botao.addEventListener("click", async () => {
    const resposta = await fetch("http://127.0.0.1:8000/")
    const dados = await resposta.json()

    resultado.innerText = dados.mensagem
})