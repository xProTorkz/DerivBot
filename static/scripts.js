document.addEventListener("DOMContentLoaded", function () {
  const modoSelect = document.getElementById("modo");
  const metaInput = document.getElementById("meta");
  const logTemp = document.getElementById("log-temporario");
  const botaoControle = document.getElementById("bot-control-btn");
  const statusDeriv = document.getElementById("status-deriv");
  const saldoValor = document.getElementById("saldo-valor");
  const lucroValor = document.getElementById("lucro-valor");
  const metaValor = document.getElementById("meta-valor");
  const operacoesDiarias = document.getElementById("operacoes-diarias");
  const historicoTabela = document.getElementById("historico-tabela-body");
  let roboAtivo = false;
  let metaDiaria = 50.0;
  let modoOperacao = "iniciante";
  let atualizacaoTimer = null;
  let verificacaoStatusTimer = null;
  let verificacaoDerivTimer = null;
  let saldoAtual = 0;
  let lucroAtual = 0;
  let metaDefinida = 0;
  let tempoAtivoSegundos = 0;
  let contadorOperacoes = 0;
  let timerAtualizacao;

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
      // Atualiza texto da meta no cabeçalho imediatamente
      const metaHeaderEl = document.getElementById("meta-valor");
      if (metaHeaderEl) metaHeaderEl.textContent = "/" + config.meta;
      atualizarLogTemp(
        `Modo selecionado: ${modo.toUpperCase()} - Assertividade média de ${
          config.assertividade
        }%`
      );
    }
  });

  // Se o usuário editar manualmente a meta, refletir no cabeçalho
  metaInput.addEventListener("input", () => {
    const metaHeaderEl = document.getElementById("meta-valor");
    if (metaHeaderEl) metaHeaderEl.textContent = "/" + metaInput.value;
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
            const msg = data.mensagem ? ` (${data.mensagem})` : "";
            statusDeriv.textContent = `🔴 Erro na conexão com Deriv${msg}`;
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

          // Só atualiza meta se o robô estiver ativo; caso contrário mantemos valor local
          if (roboAtivo) {
            const meta = parseFloat(data.meta).toFixed(2);
            metaEl.textContent = "/" + meta;
            if (metaInput && !roboAtivo) {
              metaInput.value = meta;
            }
          }

          lucroEl.textContent = lucro;
          lucroEl.className = lucro >= 0 ? "positivo" : "negativo";
        }
      });
  }

  function atualizarOperacoesDiarias() {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        const operacoesDiarias = document.getElementById("operacoes-diarias");
        if (operacoesDiarias) {
          operacoesDiarias.textContent = data.operacoes_realizadas || "0";
        }
      })
      .catch((err) => {
        console.warn("Erro ao atualizar operações diárias:", err);
      });
  }

  window.trocarAba = function (aba) {
    // Oculta todos os painéis
    document.getElementById("tabela-historico").style.display = "none";
    document.getElementById("resumo-diario").style.display = "none";
    document.getElementById("grafico-diario").style.display = "none";
    document.getElementById("historico-completo").style.display = "none";

    // Mostra o painel selecionado
    if (aba === "tabela")
      document.getElementById("tabela-historico").style.display = "block";
    else if (aba === "resumo")
      document.getElementById("resumo-diario").style.display = "block";
    else if (aba === "grafico")
      document.getElementById("grafico-diario").style.display = "block";
    else if (aba === "historico-completo")
      document.getElementById("historico-completo").style.display = "block";

    // Remove a classe 'ativo' de todos os botões
    document.querySelectorAll(".icone-historico").forEach((btn) => {
      btn.classList.remove("ativo");
    });

    // Adiciona a classe 'ativo' ao botão correspondente
    let botaoAtivo;
    switch (aba) {
      case "tabela":
        botaoAtivo = document.getElementById("btn-historico-atual");
        break;
      case "historico-completo":
        botaoAtivo = document.getElementById("btn-historico-completo");
        break;
      case "grafico":
        botaoAtivo = document.getElementById("btn-graficos");
        break;
    }

    if (botaoAtivo) {
      botaoAtivo.classList.add("ativo");
    }
  };

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

  // Funções para status detalhado e barra de progresso
  function atualizarStatusDetalhado() {
    fetch("/status_detalhado")
      .then((res) => res.json())
      .then((data) => {
        // Atualiza o log personalizado
        if (data.mensagem_log) {
          atualizarLogTemp(data.mensagem_log);
        }

        // Atualiza a barra de progresso e as bolinhas
        atualizarStatusOperacao(data.status_operacao);
      })
      .catch((err) => {
        console.error("Erro ao buscar status detalhado:", err);
      });
  }

  function atualizarStatusOperacao(statusOp) {
    if (!statusOp) return;

    const etapa = statusOp.etapa;
    const progresso = statusOp.progresso;

    // Atualiza a barra de progresso
    const barraProgresso = document.getElementById("barra-progresso");
    if (barraProgresso) {
      // Cria ou atualiza a barra de preenchimento
      let preenchimento = document.getElementById("preenchimento-barra");
      if (!preenchimento) {
        preenchimento = document.createElement("div");
        preenchimento.id = "preenchimento-barra";
        preenchimento.style.height = "100%";
        preenchimento.style.backgroundColor = "#00d67b";
        preenchimento.style.borderRadius = "3px";
        preenchimento.style.transition = "width 0.5s ease-in-out";
        barraProgresso.appendChild(preenchimento);
      }
      preenchimento.style.width = progresso + "%";
      barraProgresso.setAttribute("aria-valuenow", progresso);
    }

    // Atualiza as bolinhas indicativas
    atualizarBolinhasStatus(etapa);
  }

  function atualizarBolinhasStatus(etapa) {
    // Remove todas as classes ativas
    document.querySelectorAll(".bolinha").forEach((bolinha) => {
      bolinha.classList.remove("ativa");
      bolinha.classList.remove("pisca");
    });

    // Define progresso da barra conectora com base na etapa
    const statusEtapas = document.querySelector(".status-etapas");
    let progresso = 0;

    // Define qual etapa está ativa baseada no status
    switch (etapa) {
      case "parado":
        // Nenhuma bolinha ativa
        progresso = 0;
        break;
      case "analisando":
        progresso = 0;
        ativarBolinha("bolinha-analisando");
        document.getElementById("bolinha-analisando").classList.add("pisca");
        break;
      case "abrindo":
        progresso = 50;
        ativarBolinha("bolinha-analisando");
        ativarBolinha("bolinha-abrindo");
        document.getElementById("bolinha-abrindo").classList.add("pisca");
        break;
      case "finalizado":
        progresso = 100;
        ativarBolinha("bolinha-analisando");
        ativarBolinha("bolinha-abrindo");
        ativarBolinha("bolinha-finalizado");
        document.getElementById("bolinha-finalizado").classList.add("pisca");
        break;
    }

    // Atualiza a largura da barra de progresso
    if (statusEtapas) {
      statusEtapas.style.setProperty("--progresso-barra", `${progresso}%`);
    }
  }

  function ativarBolinha(id) {
    const bolinha = document.getElementById(id);
    if (bolinha) {
      bolinha.classList.add("ativa");
    }
  }

  // Inicializações
  modoSelect.dispatchEvent(new Event("change"));
  atualizarSaldoEmTempoReal();
  verificarConexaoDeriv();
  atualizarStatusRobo();
  atualizarLucroEMeta();
  atualizarOperacoesDiarias();
  atualizarStatusDetalhado(); // Inicializa status detalhado

  // Atualizações periódicas
  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(verificarConexaoDeriv, 5000);
  setInterval(atualizarStatusRobo, 4000);
  setInterval(atualizarLucroEMeta, 4000);
  setInterval(atualizarOperacoesDiarias, 4000);
  setInterval(atualizarStatusDetalhado, 3000); // Atualiza status detalhado a cada 3 segundos
  setInterval(() => {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        if (data.ativo) {
          atualizarTabelaResultados();
        }
      });
  }, 5000);

  const btnConectarDemo = document.getElementById("btn-conectar-demo");
  if (btnConectarDemo) {
    btnConectarDemo.addEventListener("click", () => {
      fetch("/conectar_demo", { method: "POST" })
        .then((res) => res.json())
        .then((data) => {
          if (data.status === "ok") {
            window.location.reload();
          } else {
            alert(data.mensagem || "Erro ao conectar à conta demo.");
          }
        });
    });
  }

  window.trocarContaDemo = function () {
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

  window.trocarContaReal = function () {
    fetch("/conectar_real", { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          window.location.reload();
        } else {
          alert(data.mensagem || "Erro ao conectar à conta real.");
        }
      });
  };

  function trocarContaSair() {
    fetch("/trocar_conta", { method: "POST" }).then(
      () => (window.location.href = "/login")
    );
  }

  // ---------- Dropdown Conta ---------
  const dropdownToggle = document.getElementById("dropdown-toggle");
  const dropdownMenu = document.getElementById("dropdown-conta");

  if (dropdownToggle && dropdownMenu) {
    // Previne o problema de propagação de evento
    dropdownToggle.addEventListener("click", function (event) {
      event.stopPropagation(); // Impede que o clique se propague

      // Toggle do menu dropdown
      dropdownMenu.classList.toggle("visible");
    });

    // Fechar o dropdown ao clicar em qualquer lugar da página
    document.addEventListener("click", function (event) {
      // Verificar se o clique não foi no botão de toggle
      if (event.target !== dropdownToggle) {
        dropdownMenu.classList.remove("visible");
      }
    });

    // Prevenir que cliques no próprio dropdown o fechem
    dropdownMenu.addEventListener("click", function (event) {
      event.stopPropagation();
    });
  }

  // Função para desconectar o usuário
  window.desconectar = function () {
    if (confirm("Tem certeza que deseja sair?")) {
      fetch("/logout", { method: "POST" })
        .then(() => {
          window.location.href = "/login";
        })
        .catch((erro) => {
          console.error("Erro ao desconectar:", erro);
          alert("Erro ao tentar desconectar. Tente novamente.");
        });
    }
  };

  // Inicialização
  function inicializar() {
    // Define valor inicial da meta
    if (metaInput) {
      metaInput.value = metaDiaria.toString();
    }

    // Verificação inicial do status do Deriv
    verificarStatusDeriv();

    // Inicia timers de verificação
    verificacaoDerivTimer = setInterval(verificarStatusDeriv, 10000);
    verificacaoStatusTimer = setInterval(verificarStatusRobo, 5000);

    // Atualiza saldo inicial
    atualizarSaldo();
  }

  // Iniciar o robô
  function iniciarRobo() {
    // Obtem valores atuais de modo e meta
    if (modoSelect) modoOperacao = modoSelect.value;
    if (metaInput) metaDiaria = parseFloat(metaInput.value);

    // Valida meta
    if (isNaN(metaDiaria) || metaDiaria < 10) {
      adicionarLog("⚠️ Meta inválida! Mínimo: $10.00");
      return;
    }

    // Configuração do botão
    botaoControle.textContent = "Parando...";
    botaoControle.disabled = true;

    // Envia comando para o servidor
    fetch("/toggle_bot", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        modo: modoOperacao,
        meta: metaDiaria,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "iniciado") {
          roboAtivo = true;
          botaoControle.textContent = "Parar Robô";
          botaoControle.classList.add("ativo");
          adicionarLog("🚀 Robô iniciado no modo " + modoOperacao);

          // Atualiza valores na interface
          if (metaValor) metaValor.textContent = "/" + metaDiaria.toFixed(2);
          document.getElementById("modo-selecionado").style.display = "block";
          document.getElementById("modo-texto").textContent =
            modoOperacao.toUpperCase();

          // Inicia atualização contínua
          atualizacaoTimer = setInterval(atualizarStatusRobo, 1000);
        } else {
          adicionarLog(
            "⚠️ Erro ao iniciar: " + (data.mensagem || "Falha desconhecida")
          );
        }
        botaoControle.disabled = false;
      })
      .catch((error) => {
        adicionarLog("⚠️ Erro de conexão");
        console.error("Erro:", error);
        botaoControle.disabled = false;
      });
  }

  // Parar o robô
  function pararRobo() {
    botaoControle.textContent = "Parando...";
    botaoControle.disabled = true;

    fetch("/toggle_bot", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "parado") {
          roboAtivo = false;
          botaoControle.textContent = "Iniciar Robô";
          botaoControle.classList.remove("ativo");
          adicionarLog("🛑 Robô parado");

          // Para atualização contínua
          if (atualizacaoTimer) {
            clearInterval(atualizacaoTimer);
            atualizacaoTimer = null;
          }

          // Atualiza uma última vez
          atualizarStatusRobo();
        }
        botaoControle.disabled = false;
      })
      .catch((error) => {
        adicionarLog("⚠️ Erro de conexão");
        console.error("Erro:", error);
        botaoControle.disabled = false;
      });
  }

  // Verifica status atual do robô
  function verificarStatusRobo() {
    fetch("/status_robo")
      .then((response) => response.json())
      .then((data) => {
        if (data.ativo && !roboAtivo) {
          // Robô está rodando mas interface não reflete
          roboAtivo = true;
          botaoControle.textContent = "Parar Robô";
          botaoControle.classList.add("ativo");

          // Inicia atualização contínua
          if (!atualizacaoTimer) {
            atualizacaoTimer = setInterval(atualizarStatusRobo, 1000);
          }
        } else if (!data.ativo && roboAtivo) {
          // Robô está parado mas interface não reflete
          roboAtivo = false;
          botaoControle.textContent = "Iniciar Robô";
          botaoControle.classList.remove("ativo");

          // Para atualização contínua
          if (atualizacaoTimer) {
            clearInterval(atualizacaoTimer);
            atualizacaoTimer = null;
          }
        }
      })
      .catch((error) => {
        console.error("Erro ao verificar status:", error);
      });
  }

  // Atualiza informações em tempo real
  function atualizarStatusRobo() {
    fetch("/status_robo")
      .then((response) => response.json())
      .then((data) => {
        // Atualiza saldo e lucro
        if (saldoValor) saldoValor.textContent = data.saldo.toFixed(2);
        if (lucroValor) {
          lucroValor.textContent = data.lucro.toFixed(2);
          if (data.lucro > 0) {
            lucroValor.classList.add("positivo");
            lucroValor.classList.remove("negativo");
          } else if (data.lucro < 0) {
            lucroValor.classList.add("negativo");
            lucroValor.classList.remove("positivo");
          }
        }

        // Atualiza total de operações
        if (operacoesDiarias) operacoesDiarias.textContent = data.operacoes;

        // Atualiza progresso da barra
        const progresso = (data.lucro / metaDiaria) * 100;
        const barraProgresso = document.getElementById("barra-progresso");
        if (barraProgresso) {
          if (progresso < 0) {
            barraProgresso.style.width = "0%";
            barraProgresso.style.backgroundColor = "var(--cor-vermelha)";
          } else if (progresso >= 100) {
            barraProgresso.style.width = "100%";
            barraProgresso.style.backgroundColor = "var(--cor-verde)";
          } else {
            barraProgresso.style.width = progresso + "%";
            barraProgresso.style.backgroundColor = "var(--amarelo-dourado)";
          }
        }

        // Atualiza histórico se necessário
        atualizarHistorico();
      })
      .catch((error) => {
        console.error("Erro ao atualizar status:", error);
      });
  }

  // Verifica status da conexão com Deriv
  function verificarStatusDeriv() {
    fetch("/status_deriv")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "ok") {
          statusDeriv.textContent = "✅ Conectado ao servidor Deriv";
          statusDeriv.style.color = "var(--cor-verde)";
        } else {
          statusDeriv.textContent =
            "❌ " + (data.mensagem || "Erro de conexão com Deriv");
          statusDeriv.style.color = "var(--cor-vermelha)";
        }
      })
      .catch((error) => {
        statusDeriv.textContent = "❌ Falha ao verificar conexão";
        statusDeriv.style.color = "var(--cor-vermelha)";
      });
  }

  // Atualiza o saldo atual
  function atualizarSaldo() {
    fetch("/saldo_atual")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "ok" && saldoValor) {
          saldoAtual = parseFloat(data.saldo);
          saldoValor.textContent = saldoAtual.toFixed(2);
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar saldo:", error);
      });
  }

  // Atualiza a tabela de histórico
  function atualizarHistorico() {
    fetch("/historico_resultados")
      .then((response) => response.json())
      .then((data) => {
        if (historicoTabela && data.length > 0) {
          // Verifica se o histórico precisa ser atualizado
          const ultimaLinha = historicoTabela.lastElementChild;
          const ultimoRegistro = data[data.length - 1];

          if (
            !ultimaLinha ||
            ultimaLinha.children[0].textContent !== ultimoRegistro.data ||
            ultimaLinha.children[1].textContent !== ultimoRegistro.hora
          ) {
            // Adiciona novas linhas na tabela
            data.forEach((op, idx) => {
              // Verifica se já existe na tabela para evitar duplicatas
              let existe = false;
              for (let i = 0; i < historicoTabela.children.length; i++) {
                const linha = historicoTabela.children[i];
                if (
                  linha.children[0].textContent === op.data &&
                  linha.children[1].textContent === op.hora
                ) {
                  existe = true;
                  break;
                }
              }

              if (!existe) {
                // Cria nova linha
                const linha = document.createElement("tr");

                // Data
                const celulaData = document.createElement("td");
                celulaData.textContent = op.data;
                linha.appendChild(celulaData);

                // Hora
                const celulaHora = document.createElement("td");
                celulaHora.textContent = op.hora;
                linha.appendChild(celulaHora);

                // Tipo
                const celulaTipo = document.createElement("td");
                celulaTipo.textContent = op.tipo.toUpperCase();
                linha.appendChild(celulaTipo);

                // Valor
                const celulaValor = document.createElement("td");
                celulaValor.textContent = "$" + op.valor.toFixed(2);
                linha.appendChild(celulaValor);

                // Resultado
                const celulaResultado = document.createElement("td");
                celulaResultado.textContent =
                  "$" + op.resultado_real.toFixed(2);
                celulaResultado.classList.add("resultado");
                if (op.resultado_real > 0) {
                  celulaResultado.classList.add("positivo");
                  celulaResultado.classList.add("destaque-resultado");
                } else if (op.resultado_real < 0) {
                  celulaResultado.classList.add("negativo");
                }
                linha.appendChild(celulaResultado);

                // Adiciona linha na tabela
                historicoTabela.appendChild(linha);

                // Mantém rolagem no final
                const tabela = document.getElementById("tabela-historico");
                if (tabela) {
                  tabela.scrollTop = tabela.scrollHeight;
                }
              }
            });
          }
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar histórico:", error);
      });
  }

  // Adiciona log temporário na interface
  function adicionarLog(mensagem) {
    if (logTemp) {
      logTemp.textContent = mensagem;

      // Efeito de fade
      logTemp.style.opacity = "1";
      setTimeout(() => {
        logTemp.style.opacity = "0.7";
      }, 3000);
    }
  }

  // Inicializa a página
  inicializar();
});
