document.addEventListener("DOMContentLoaded", function () {
  const modoSelect = document.getElementById("modo");
  const metaInput = document.getElementById("meta");
  const logTemp = document.getElementById("log-temporario");
  const botaoControle = document.getElementById("bot-control-btn");
  const statusDeriv = document.getElementById("status-deriv");

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

    atualizarLogTemp("Iniciando operações...");
    atualizarStatusEtapas("iniciando");

    fetch("/iniciar_bot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modo, meta }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          atualizarLogTemp("Robô iniciado com sucesso!");
          atualizarStatusEtapas("contrato");
        } else {
          atualizarLogTemp("Erro ao iniciar robô: " + data.mensagem);
          atualizarStatusEtapas("erro");
        }
      })
      .catch((err) => {
        atualizarLogTemp("Erro de comunicação com o servidor.");
        console.error(err);
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
        console.warn("Erro ao atualizar saldo em tempo real:", err);
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
      .catch((err) => {
        if (statusDeriv) {
          statusDeriv.textContent = "⚠️ Erro ao verificar conexão.";
          statusDeriv.style.color = "orange";
        }
      });
  }

  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(verificarConexaoDeriv, 5000);

  atualizarSaldoEmTempoReal();
  verificarConexaoDeriv();
  modoSelect.dispatchEvent(new Event("change"));

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
});
