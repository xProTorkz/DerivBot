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

  botaoControle.addEventListener("click", async () => {
    const modo = modoSelect.value;
    const meta = parseFloat(metaInput.value);

    // ✅ Garante que a aba da tabela esteja visível
    trocarAba("tabela");

    // ✅ Limpa somente o corpo da tabela
    const tabelaBody = document.getElementById("historico-tabela-body");
    if (tabelaBody) tabelaBody.innerHTML = "";

    // ✅ Limpa os campos de resumo
    document.getElementById("resumo-total").innerText = "--";
    document.getElementById("resumo-lucros").innerText = "--";
    document.getElementById("resumo-prejuizos").innerText = "--";
    document.getElementById("resumo-assertividade").innerText = "--";
    document.getElementById("resumo-lucro-total").innerText = "--";

    // ✅ Atualiza texto temporário
    document.getElementById("log-temporario").textContent = "Robô iniciado!";

    // ✅ Troca pra aba "Histórico 📄" automaticamente
    if (typeof trocarAba === "function") {
      trocarAba("tabela");
    }

    try {
      const resposta = await fetch("/toggle_bot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ modo, meta }),
      });

      const dados = await resposta.json();

      // Alterna o estado do botão
      roboAtivo = dados.status === "iniciado";
      botaoControle.textContent = roboAtivo ? "Parar Robô" : "Iniciar Robô";
      botaoControle.classList.toggle("ativo", roboAtivo);

      // 👇 atualiza exibição do modo
      atualizarExibicaoModo(modo, roboAtivo);

      // 🔄 Atualiza lucro/meta imediatamente após iniciar
      atualizarLucroEMeta();

      // 🔀 Troca de aba pro histórico
      if (roboAtivo) {
        trocarAba("tabela");
      }
    } catch (erro) {
      console.error("Erro ao alternar robô:", erro);
    }
  });

  function atualizarLogTemp(mensagem) {
    document.getElementById("log-temporario").textContent = mensagem;
  }

  function atualizarStatusEtapas(etapa) {
    // Remove pisca de todas as bolinhas
    document
      .querySelectorAll(".bolinha")
      .forEach((b) => b.classList.remove("pisca"));

    // Define etapas e índice
    const etapas = ["analisando", "abrindo", "finalizado", "completo"];
    const idx = etapas.indexOf(etapa);

    // Atualiza barra de preenchimento
    const preenchimento = document.getElementById("preenchimento-barra");
    if (preenchimento) {
      // 0 etapas = 0%, 1 = 33%, 2 = 66%, 3 = 100%
      const percentuais = [0, 33, 66, 100];
      preenchimento.style.width = percentuais[idx] + "%";
    }

    // Cores das bolinhas
    etapas.forEach((nome, i) => {
      const bolinha = document.getElementById("bolinha-" + nome);
      if (bolinha) {
        if (i < idx) {
          bolinha.style.background = "#ffd700";
          bolinha.style.borderColor = "#fff";
        } else if (i === idx) {
          bolinha.style.background = "#fff";
          bolinha.style.borderColor = "#ffd700";
          bolinha.classList.add("pisca");
        } else {
          bolinha.style.background = "#fff";
          bolinha.style.borderColor = "#ffd700";
        }
      }
    });
  }

  window.atualizarTabelaResultadosSeRoboAtivo = function () {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        if (data.ativo) {
          atualizarTabelaResultados();
        }
      })
      .catch((err) => {
        console.warn("Erro ao verificar status do robô:", err);
      });
  };

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
            <td>${item.data}</td>
            <td>${item.hora}</td>

            <td>${item.tipo.toUpperCase()}</td>
            <td>$${parseFloat(item.valor).toFixed(2)}</td>
            <td class="resultado ${
              item.resultado_real >= 0 ? "positivo" : "negativo"
            }">
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

  window.limparHistorico = function () {
    if (!confirm("Tem certeza que deseja limpar o histórico?")) return;

    fetch("/limpar_historico", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: "{}", // pode ser um objeto vazio
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          document.getElementById("historico-tabela-body").innerHTML = "";
          console.log("🧹 Histórico apagado com sucesso.");
        } else {
          alert("Erro ao limpar histórico: " + data.mensagem);
        }
      })
      .catch(() => {
        alert("Erro ao tentar limpar o histórico.");
      });
  };
  function atualizarStatusRobo() {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        roboAtivo = data.ativo;
        if (roboAtivo) {
          atualizarLogTemp("⚙️ Robô está rodando...");
          atualizarStatusEtapas("analisando");
          botaoControle.textContent = "⛔ Parar Robô";
          botaoControle.style.backgroundColor = "#ff3b3b"; // vermelho
          botaoControle.style.color = "#fff";
        } else {
          atualizarLogTemp("🟡 Robô parado.");
          atualizarStatusEtapas("finalizado");
          botaoControle.textContent = "✅ Iniciar Robô";
          botaoControle.style.backgroundColor = "#00d67b"; // verde
          botaoControle.style.color = "#000";
        }
      })
      .catch(() => {
        atualizarLogTemp("❌ Erro ao consultar status do robô.");
      });
  }

  function atualizarLucroEMeta() {
    fetch("/lucro_meta")
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          const lucroEl = document.getElementById("lucro-valor");
          const metaEl = document.getElementById("meta-valor");
          const metaInput = document.getElementById("meta");

          const lucro = parseFloat(data.lucro).toFixed(2);
          const meta = parseFloat(data.meta).toFixed(2);

          lucroEl.textContent = lucro;
          metaEl.textContent = "/" + meta;

          // Atualiza o input de meta para refletir o valor real do backend
          if (metaInput && !roboAtivo) {
            metaInput.value = meta;
          }

          lucroEl.className = lucro >= 0 ? "positivo" : "negativo";
        }
      });
  }

  function trocarAba(aba) {
    // Oculta todos
    document.getElementById("tabela-historico").style.display = "none";
    document.getElementById("resumo-diario").style.display = "none";
    document.getElementById("grafico-diario").style.display = "none";

    // Mostra a selecionada
    if (aba === "tabela")
      document.getElementById("tabela-historico").style.display = "block";
    if (aba === "resumo")
      document.getElementById("resumo-diario").style.display = "block";
    if (aba === "grafico")
      document.getElementById("grafico-diario").style.display = "block";

    // Marca a aba como ativa
    document
      .querySelectorAll(".aba")
      .forEach((el) => el.classList.remove("active"));
    const icone = {
      tabela: "📄",
      resumo: "📊",
      grafico: "📈",
    }[aba];

    document.querySelectorAll(".aba").forEach((el) => {
      if (el.textContent.trim() === icone) el.classList.add("active");
    });
  }

  function atualizarExibicaoModo(modoSelecionado, roboAtivo) {
    const containerModoMeta = document.querySelector(".modo-meta-wrapper");
    const modoSelecionadoBox = document.getElementById("modo-selecionado");
    const modoTextoSpan = document.getElementById("modo-texto");

    if (!containerModoMeta || !modoSelecionadoBox || !modoTextoSpan) return;

    if (roboAtivo) {
      containerModoMeta.style.display = "none";
      modoSelecionadoBox.style.display = "block";

      const emojis = {
        iniciante: "🌱",
        conservador: "🛡️",
        agressivo: "🔥",
      };

      const modoCapitalizado =
        modoSelecionado.charAt(0).toUpperCase() + modoSelecionado.slice(1);
      modoTextoSpan.innerText = `${modoCapitalizado} ${
        emojis[modoSelecionado] || ""
      }`;
    } else {
      containerModoMeta.style.display = "flex";
      modoSelecionadoBox.style.display = "none";
    }
  }

  // Inicializações
  modoSelect.dispatchEvent(new Event("change"));
  atualizarSaldoEmTempoReal();
  verificarConexaoDeriv();
  atualizarStatusRobo();
  atualizarLucroEMeta();

  // Atualizações periódicas
  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(verificarConexaoDeriv, 5000);
  setInterval(atualizarStatusRobo, 4000);
  setInterval(atualizarLucroEMeta, 4000); // Atualiza a cada 4 segundos
  setInterval(() => {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        if (data.ativo) {
          atualizarTabelaResultados();
        }
      });
  }, 5000);

  document.getElementById("btn-conectar-demo").onclick = function () {
    fetch("/conectar_demo", { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          window.location.reload();
        } else {
          alert(data.mensagem || "Erro ao conectar à conta demo.");
        }
      });
  };

  function trocarContaDemo() {
    fetch("/conectar_demo", { method: "POST" })
      .then((res) => res.json())
      .then((data) => window.location.reload());
  }
  function trocarContaReal() {
    fetch("/conectar_real", { method: "POST" })
      .then((res) => res.json())
      .then((data) => window.location.reload());
  }
  function trocarContaSair() {
    fetch("/trocar_conta", { method: "POST" }).then(
      () => (window.location.href = "/login")
    );
  }
});
