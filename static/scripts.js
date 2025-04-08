document.addEventListener("DOMContentLoaded", function () {
  const botao = document.getElementById("bot-control-btn");
  const logTemp = document.getElementById("log-temporario");
  const saldoCampo = document.getElementById("saldo-valor");
  const lucroCampo = document.getElementById("lucro-valor");
  const modoSelect = document.getElementById("modo");
  const metaInput = document.getElementById("meta");
  const metaExibida = document.getElementById("meta-valor");
  const barraProgresso = document.getElementById("barra-progresso");
  const tabelaBody = document.getElementById("historico-tabela-body");

  let botAtivo = false;

  botao.addEventListener("click", () => {
    if (!botAtivo) {
      iniciarRobo();
    } else {
      pararRobo();
    }
  });

  function iniciarRobo() {
    const modo = modoSelect.value;
    const meta = parseFloat(metaInput.value) || 0;
    fetch("/iniciar_robo", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `modo=${modo}`,
    })
      .then((res) => res.text())
      .then((data) => {
        botAtivo = true;
        botao.innerText = "🛑 Parar Robô";
        botao.classList.remove("start-btn");
        botao.classList.add("stop-btn");
        logTemp.innerText = data;
        metaExibida.innerText = `/${meta.toFixed(2)}`;
      });
  }

  function pararRobo() {
    // Só visual por enquanto (sem rota de parada ainda)
    botAtivo = false;
    botao.innerText = "✅ Iniciar Robô";
    botao.classList.remove("stop-btn");
    botao.classList.add("start-btn");
    logTemp.innerText = "Robô parado.";
  }

  function atualizarStatus() {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        saldoCampo.innerText = parseFloat(data.saldo).toFixed(2);
        lucroCampo.innerText = calcularLucro(data.logs).toFixed(2);

        logTemp.innerText = data.status || "Aguardando...";

        atualizarHistorico(data.logs);
        atualizarBarra(metaInput.value, lucroCampo.innerText);
      });
  }

  function calcularLucro(logs) {
    let lucro = 0;
    logs.forEach((log) => {
      if (log.includes("Lucro:")) {
        const match = log.match(/Lucro:\s?\$?(-?\d+(\.\d+)?)/);
        if (match) {
          lucro += parseFloat(match[1]);
        }
      }
    });
    return lucro;
  }

  function atualizarHistorico(logs) {
    tabelaBody.innerHTML = "";
    logs
      .slice(-20)
      .reverse()
      .forEach((log) => {
        if (log.includes("Contrato finalizado")) {
          const linha = document.createElement("tr");
          const dataHora = new Date().toLocaleString("pt-BR");
          const [data, hora] = dataHora.split(" ");

          const direcao = log.includes("WIN") ? "✅ WIN" : "❌ LOSS";
          const lucro = log.match(/Lucro:\s?\$?(-?\d+(\.\d+)?)/)[1];

          linha.innerHTML = `
          <td>${data}</td>
          <td>${hora}</td>
          <td>R_100</td>
          <td>$${lucro}</td>
          <td class="${
            direcao.includes("WIN") ? "positivo" : "negativo"
          }">${direcao}</td>
        `;
          tabelaBody.appendChild(linha);
        }
      });
  }

  function atualizarBarra(meta, atual) {
    const porcentagem = Math.min(
      (parseFloat(atual) / parseFloat(meta)) * 100,
      100
    );
    barraProgresso.style.width = isNaN(porcentagem) ? "0%" : `${porcentagem}%`;
  }

  setInterval(atualizarStatus, 2500);
  function atualizarLogs() {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        // Atualiza o SALDO na barra principal do painel
        if (document.getElementById("saldo-valor")) {
          document.getElementById("saldo-valor").innerText =
            data.saldo.toFixed(2);
        }

        // Atualiza o TIPO DE CONTA (opcional, se você usar esse campo no HTML)
        if (data.tipo_conta && document.getElementById("tipo-conta-label")) {
          document.getElementById(
            "tipo-conta-label"
          ).innerText = `Conta: ${data.tipo_conta}`;
        }

        // Atualiza LOGS no painel (se tiver div de logs com id 'log-operacoes')
        const logContainer = document.getElementById("log-operacoes");
        if (logContainer) {
          logContainer.innerHTML = "";
          data.logs
            .slice()
            .reverse()
            .forEach((log) => {
              const div = document.createElement("div");
              div.className = "log-item";
              div.innerText = log;
              logContainer.appendChild(div);
            });
        }
      })
      .catch((err) => {
        console.error("Erro ao buscar status do robô:", err);
      });
  }

  // Chama a função de 2 em 2 segundos pra atualizar tudo em tempo real
  setInterval(atualizarLogs, 2000);
});
