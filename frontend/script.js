const botao = document.getElementById("salvar")
const resultado = document.getElementById("resultado")

botao.addEventListener("click", async () => {
    const nome = document.getElementById("nome").value
    const email = document.getElementById("email").value

    const resposta = await fetch("http://127.0.0.1:8000/usuarios", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            nome: nome,
            email: email
        })
    })

    const dados = await resposta.json()

    resultado.innerText = dados.mensagem
})