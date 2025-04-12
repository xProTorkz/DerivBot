document.addEventListener("DOMContentLoaded", function () {
  const modoSelect = document.getElementById("modo");
  const metaInput = document.getElementById("meta");
  const logTemp = document.getElementById("log-temporario");
  const botaoControle = document.getElementById("bot-control-btn");
  const statusDeriv = document.getElementById("status-deriv");
  let roboAtivo = false;

  const modosConfig = {
    iniciante: { meta: 20, entrada: 1, stop: 10, assertividade: 95 },
    conservador: { meta: 50, entrada: 5, stop: 25, assertividade: 85 },
    agressivo: { meta: 100, entrada: 10, stop: 50, assertividade: 80 },
  };

  modoSelect.addEventListener("change", () => {
    const modo = modoSelect.value;
    const config = modosConfig[modo];
    if (config) {
      metaInput.value = config.meta;
      atualizarLogTemp(
        `Modo selecionado: ${modo.toUpperCase()} - Assertividade média de ${
          config.assertividade
        }%`
      );
    }
  });

  botaoControle.addEventListener("click", () => {
    const modo = modoSelect.value;
    const meta = parseFloat(metaInput.value);

    fetch("/toggle_bot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modo, meta }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "iniciado") {
          atualizarLogTemp("✅ Robô iniciado com sucesso!");
          atualizarStatusEtapas("contrato");
        } else {
          atualizarLogTemp("⛔ Robô foi parado!");
          atualizarStatusEtapas("finalizado");
        }
        atualizarStatusRobo(); // atualiza o botão
      })
      .catch(() => {
        atualizarLogTemp("❌ Erro ao alternar o status do robô.");
      });
  });

  function atualizarLogTemp(mensagem) {
    if (logTemp) {
      logTemp.textContent = mensagem;
    }
  }

  function atualizarStatusEtapas(etapa) {
    document.querySelectorAll(".bolinha").forEach((b) => {
      b.style.backgroundColor = "#666";
    });

    if (etapa === "iniciando") {
      document.getElementById("bolinha-analisando").style.backgroundColor =
        "orange";
    } else if (etapa === "contrato") {
      document.getElementById("bolinha-abrindo").style.backgroundColor = "gold";
    } else if (etapa === "finalizado") {
      document.getElementById("bolinha-finalizado").style.backgroundColor =
        "#15ff82";
    }
  }

  function atualizarStatusRobo() {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        if (!botaoControle) return;
        if (data.ativo) {
          botaoControle.textContent = "⛔ Parar Robô";
          botaoControle.classList.remove("start-btn");
          botaoControle.classList.add("stop-btn");
          roboAtivo = true;
        } else {
          botaoControle.textContent = "✅ Iniciar Robô";
          botaoControle.classList.remove("stop-btn");
          botaoControle.classList.add("start-btn");
          roboAtivo = false;
        }
      });
  }

  function atualizarSaldoEmTempoReal() {
    fetch("/saldo_atual")
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          document.getElementById("saldo-valor").textContent = parseFloat(
            data.saldo
          ).toFixed(2);
        }
      })
      .catch((err) => {
        console.warn("Erro ao atualizar saldo:", err);
      });
  }

  function verificarConexaoDeriv() {
    fetch("/status_deriv")
      .then((res) => res.json())
      .then((data) => {
        if (statusDeriv) {
          if (data.status === "ok") {
            statusDeriv.textContent = "🟢 Conectado ao Deriv";
            statusDeriv.style.color = "#00d67b";
          } else {
            statusDeriv.textContent = "🔴 Erro na conexão com Deriv";
            statusDeriv.style.color = "#ff444f";
          }
        }
      })
      .catch(() => {
        statusDeriv.textContent = "⚠️ Erro ao verificar conexão.";
        statusDeriv.style.color = "orange";
      });
  }

  function atualizarTabelaResultados() {
    fetch("/historico_resultados")
      .then((res) => res.json())
      .then((data) => {
        const tbody = document.getElementById("historico-tabela-body");
        tbody.innerHTML = "";

        data.reverse().forEach((item) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${item.data.split(" ")[0]}</td>
            <td>${item.data.split(" ")[1].slice(0, 5)}</td>
            <td>${item.tipo.toUpperCase()}</td>
            <td>$${parseFloat(item.valor).toFixed(2)}</td>
            <td class="${item.resultado_real >= 0 ? "positivo" : "negativo"}">
              $${parseFloat(item.resultado_real).toFixed(2)}
            </td>

          `;
          tbody.appendChild(row);
        });
      })
      .catch((err) => {
        console.warn("Erro ao atualizar histórico de resultados:", err);
      });
  }

  const botaoTrocar = document.getElementById("trocar-conta");
  if (botaoTrocar) {
    botaoTrocar.addEventListener("click", () => {
      fetch("/trocar_conta", { method: "POST" })
        .then(() => {
          window.location.reload();
        })
        .catch(() => {
          alert("Erro ao trocar de conta.");
        });
    });
  }

  function limparHistorico() {
    console.log("🧹 Clicou em limpar histórico"); // só pra debug

    if (!confirm("Tem certeza que deseja limpar o histórico?")) return;

    fetch("/limpar_historico", { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          document.getElementById("historico-tabela-body").innerHTML = "";
          atualizarLogTemp("🧹 Histórico apagado com sucesso.");
        } else {
          alert("Erro ao limpar histórico: " + data.mensagem);
        }
      })
      .catch(() => {
        alert("Erro ao tentar limpar o histórico.");
      });
  }

  // Inicializações
  modoSelect.dispatchEvent(new Event("change"));
  atualizarSaldoEmTempoReal();
  verificarConexaoDeriv();
  atualizarStatusRobo();
  atualizarTabelaResultados();

  // Atualizações periódicas
  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(verificarConexaoDeriv, 5000);
  setInterval(atualizarStatusRobo, 4000);
  setInterval(() => {
    if (roboAtivo) {
      atualizarTabelaResultados();
    }
  }, 5000);
});
