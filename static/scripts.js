// DerivBot - Código Principal
// Carrega mobile.js para funcionalidades específicas para dispositivos móveis
// O mobile.js é responsável por detectar e ajustar a interface para dispositivos móveis

document.addEventListener("DOMContentLoaded", function () {
  // Código para garantir que a barra de progresso termine nas bolinhas
  (function fixProgressBar() {
    // Adicionar um estilo específico que force os limites da barra
    const styleEl = document.createElement("style");
    styleEl.id = "progress-bar-fix";
    styleEl.textContent = `
      .status-etapas::before {
        left: 20px !important;
        right: 18px !important;
      }
      .status-etapas::after {
        left: 20px !important;
        max-width: calc(100% - 38px) !important;
      }
    `;
    document.head.appendChild(styleEl);

    // Forçar recálculo
    setTimeout(() => {
      const statusEl = document.querySelector(".status-etapas");
      if (statusEl) {
        void statusEl.offsetWidth;
      }
    }, 500);
  })();

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

  // Novo: variável para controlar se precisamos restaurar o estado
  let precisaRestaurarEstado = false;

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
      atualizarLog(
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

      // Demonstrar o progresso quando for ativado
      demonstrarProgresso();
    } catch (erro) {
      console.error("Erro ao alternar robô:", erro);
    }
  });

  function atualizarLog(mensagem, tipo = "info") {
    const logElement = document.getElementById("log-temporario");
    const emojis = {
      info: "🔍",
      aviso: "⚠️",
      erro: "❌",
      sucesso: "✅",
      analise: "🔎",
      contrato: "📝",
      ganho: "💰",
      perda: "📉",
      espera: "⏳",
      conexao: "🔌",
      servidor: "🖥️",
      config: "⚙️",
    };

    // Define o emoji padrão se o tipo não estiver no objeto
    const emoji = emojis[tipo] || emojis["info"];

    // Limpa classes anteriores
    logElement.className = "log-temp";

    // Adiciona classe correspondente ao tipo
    logElement.classList.add(tipo);

    // Atualiza o conteúdo com emoji e mensagem
    logElement.innerHTML = `
      <span class="log-emoji">${emoji}</span>
      <span class="log-texto">${mensagem}</span>
    `;
  }

  // Função centralizada para manipular bolinhas e barras de progresso
  function atualizarProgressoBolinhas(
    etapa,
    mensagemLog = null,
    tipoLog = null
  ) {
    // Verifica se o robô está ativo antes de atualizar as bolinhas
    if (!roboAtivo && etapa !== "parado") {
      // Se o robô não estiver ativo, ignoramos atualizações exceto para o estado "parado"
      return;
    }

    // Limpa estado atual
    document.querySelectorAll(".bolinha").forEach((b) => {
      b.classList.remove("ativa");
      b.classList.remove("pisca");
    });

    const statusEtapas = document.querySelector(".status-etapas");
    let progresso = 0;

    // Configurações de acordo com a etapa
    switch (etapa) {
      case "analisando":
        progresso = 0;
        ativarBolinha("bolinha-analisando", true); // Com efeito pisca
        if (!mensagemLog)
          mensagemLog = "Analisando mercado em busca do melhor momento...";
        if (!tipoLog) tipoLog = "analise";
        break;

      case "medio":
        progresso = 33;
        ativarBolinha("bolinha-analisando");
        if (!mensagemLog)
          mensagemLog = "Sinal identificado, preparando entrada...";
        if (!tipoLog) tipoLog = "info";
        break;

      case "abrindo":
        progresso = 50;
        ativarBolinha("bolinha-analisando");
        ativarBolinha("bolinha-abrindo", true); // Com efeito pisca
        if (!mensagemLog) mensagemLog = "Abrindo contrato agora!";
        if (!tipoLog) tipoLog = "contrato";
        break;

      case "aguardando":
        progresso = 75;
        ativarBolinha("bolinha-analisando");
        ativarBolinha("bolinha-abrindo");
        if (!mensagemLog)
          mensagemLog = "Contrato aberto, aguardando resultado...";
        if (!tipoLog) tipoLog = "espera";
        break;

      case "finalizado":
      case "finalizado-win":
      case "finalizado-loss":
        progresso = 100;
        ativarBolinha("bolinha-analisando");
        ativarBolinha("bolinha-abrindo");
        ativarBolinha(
          "bolinha-finalizado",
          etapa === "finalizado-win" || etapa === "finalizado"
        ); // Pisca no caso de win ou finalizado genérico

        if (etapa === "finalizado-win") {
          if (!mensagemLog) mensagemLog = "Operação finalizada com GANHO! 💸";
          if (!tipoLog) tipoLog = "sucesso";
        } else if (etapa === "finalizado-loss") {
          if (!mensagemLog)
            mensagemLog =
              "Operação finalizada com perda. Preparando recuperação...";
          if (!tipoLog) tipoLog = "perda";
        }
        break;

      case "parado":
      default:
        // Quando parado ou estado desconhecido, resetar as bolinhas e a barra
        resetarProgressoBolinhas();
        if (!mensagemLog) mensagemLog = "Robô pronto para iniciar operações.";
        if (!tipoLog) tipoLog = "config";
        return; // Saímos aqui para não atualizar a barra
    }

    // Atualiza a barra de progresso - Versão melhorada para mobile
    if (statusEtapas) {
      // Primeiro, determina se estamos em dispositivo móvel
      const isMobileDevice =
        window.innerWidth <= 768 ||
        document.body.classList.contains("mobile-device");

      // Calcula o valor para desktop - padrão
      let widthValue =
        progresso === 0
          ? "0"
          : progresso === 100
          ? "calc(100% - 32px)"
          : `calc(${progresso}% * (100% - 32px) / 100)`;

      // Utiliza a função do mobile.js se disponível
      if (
        window.mobileUtils &&
        typeof window.mobileUtils.calcularWidthProgressoBarra === "function"
      ) {
        widthValue = window.mobileUtils.calcularWidthProgressoBarra(progresso);
      }

      // Usa a função de atualização direta em dispositivos móveis (maior garantia)
      if (
        isMobileDevice &&
        window.atualizarLarguraBarraProgresso &&
        typeof window.atualizarLarguraBarraProgresso === "function"
      ) {
        // Chamada direta para maior garantia em mobile
        window.atualizarLarguraBarraProgresso(progresso);
      } else {
        // Fallback para o método tradicional
        // Aplicar diretamente usando CSS inline
        const styleElement = document.getElementById("barra-progresso-style");
        if (!styleElement) {
          // Criar elemento de estilo se não existir
          const style = document.createElement("style");
          style.id = "barra-progresso-style";
          document.head.appendChild(style);
        }

        // Atualizar o CSS diretamente
        const styleSheet = document.getElementById(
          "barra-progresso-style"
        ).sheet;
        // Limpar regras anteriores
        while (styleSheet.cssRules.length > 0) {
          styleSheet.deleteRule(0);
        }
        // Adicionar nova regra
        styleSheet.insertRule(
          `.status-etapas::after { width: ${widthValue} !important; }`,
          0
        );

        // Força um reflow para garantir que a alteração seja aplicada imediatamente
        void statusEtapas.offsetWidth;
      }
    }

    // Atualiza o log se houver mensagem
    if (mensagemLog && tipoLog) {
      atualizarLog(mensagemLog, tipoLog);
    }
  }

  // Função auxiliar para ativar uma bolinha (com ou sem efeito pisca)
  function ativarBolinha(id, comPisca = false) {
    const bolinha = document.getElementById(id);
    if (bolinha) {
      bolinha.classList.add("ativa");
      if (comPisca) {
        bolinha.classList.add("pisca");
      }
    }
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
    // Verificar status do robô antes de atualizar o saldo
    fetch("/status_robo")
      .then((statusRes) => statusRes.json())
      .then((statusData) => {
        // Só atualiza se o robô estiver ativo ou for a primeira vez
        const saldoEl = document.getElementById("saldo-valor");
        if (
          statusData.ativo ||
          saldoEl.getAttribute("data-inicializado") !== "true"
        ) {
          // Busca o saldo atual
          fetch("/saldo_atual")
            .then((res) => res.json())
            .then((data) => {
              if (data.status === "ok") {
                const saldoAtual = parseFloat(
                  saldoEl.textContent.replace(/,/g, "") || "0"
                );
                const novoSaldo = parseFloat(data.saldo);

                // Atualiza o saldo
                saldoEl.textContent = novoSaldo.toFixed(2);

                // Marca como inicializado
                saldoEl.setAttribute("data-inicializado", "true");
              }
            })
            .catch((err) => {
              console.warn("Erro ao atualizar saldo:", err);
            });
        }
      })
      .catch((err) => {
        console.warn("Erro ao verificar status do robô:", err);
      });
  }

  function verificarConexaoDeriv() {
    fetch("/status_deriv")
      .then((res) => res.json())
      .then((data) => {
        if (statusDeriv) {
          if (data.status === "ok") {
            // Mostra informações da conta conectada
            let textoStatus = "✅ ";

            // Se temos dados da conta, mostramos eles
            if (data.conta_nome && data.conta_tipo) {
              textoStatus += `${data.conta_nome} (${data.conta_tipo})`;
            } else {
              textoStatus += "Conectado à Deriv";
            }

            // Se tem saldo, mostra
            if (data.saldo) {
              textoStatus += ` - Saldo: $${parseFloat(data.saldo).toFixed(2)}`;
            }

            statusDeriv.textContent = textoStatus;
            statusDeriv.style.color = "var(--cor-verde)";
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
    // Usa a nova implementação para manter consistência
    atualizarHistorico();
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
      .then((response) => response.json())
      .then((data) => {
        roboAtivo = data.ativo;

        // Atualiza o botão de controle
        if (botaoControle) {
          botaoControle.disabled = false;
          if (roboAtivo) {
            atualizarLog("⚙️ Robô está rodando...", "servidor");
            // Removemos a atualização automática das bolinhas aqui, elas devem ser atualizadas apenas durante operações
            botaoControle.textContent = "⛔ Parar Robô";
            botaoControle.style.backgroundColor = "#ff3b3b"; // vermelho
            botaoControle.style.color = "#000"; // preto

            // Oculta os controles de configuração quando robô está ativo
            document.querySelector(".modo-meta-wrapper").style.display = "none";

            // Mostra o modo selecionado
            if (modoOperacao) {
              document.getElementById("modo-selecionado").style.display =
                "block";
              document.getElementById("modo-texto").textContent =
                modoOperacao.toUpperCase();
            }

            // Salvar estado para persistência
            salvarEstadoRobo();
          } else {
            atualizarLog("🟡 Robô parado.", "config");
            // Quando o robô estiver parado, resetamos as bolinhas e barra
            resetarProgressoBolinhas();
            botaoControle.textContent = "✅ Iniciar Robô";
            botaoControle.style.backgroundColor = "#00d67b"; // verde
            botaoControle.style.color = "#000"; // preto

            // Mostra os controles de configuração quando robô está inativo
            document.querySelector(".modo-meta-wrapper").style.display = "flex";
            document.getElementById("modo-selecionado").style.display = "none";

            // Remover estado salvo quando o robô está parado
            localStorage.removeItem("derivbot_estado");

            // Para timer de atualização contínua se existir
            if (atualizacaoTimer) {
              clearInterval(atualizacaoTimer);
              atualizacaoTimer = null;
            }
          }
        }

        // Atualiza saldo e lucro com animação
        if (saldoValor) {
          const saldoAtual = parseFloat(saldoValor.textContent || "0");
          animarValor(saldoValor, saldoAtual, data.saldo, 1000);
        }

        if (lucroValor) {
          const lucroAtual = parseFloat(lucroValor.textContent || "0");
          animarValor(lucroValor, lucroAtual, data.lucro, 1200);
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

        // Atualiza exibição de modo
        atualizarExibicaoModo(data.modo || modoOperacao, roboAtivo);

        // Atualiza histórico se necessário
        atualizarHistorico();

        // Atualizar dados para persistência, apenas se estiver ativo
        if (data.ativo) {
          // Atualizar valores para persistência
          saldoAtual = data.saldo;
          lucroAtual = data.lucro;
          contadorOperacoes = data.operacoes;
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar status:", error);
      });
  }

  function atualizarLucroEMeta() {
    fetch("/lucro_meta")
      .then((response) => response.json())
      .then((data) => {
        if (data.status !== "ok") return;

        const lucroEl = document.getElementById("lucro-valor");
        const metaEl = document.getElementById("meta-valor");

        // Atualizar o valor da meta apenas se o robô estiver ativo
        // Se o robô não estiver ativo, mantém o valor que o usuário definiu na interface
        if (metaEl && data.robo_ativo) {
          metaEl.textContent = "/" + parseFloat(data.meta).toFixed(2);
        }

        // Verificar se o robô está ativo antes de atualizar o lucro
        if (lucroEl) {
          // Só atualiza o lucro se o robô estiver ativo ou for a primeira vez
          if (
            data.robo_ativo ||
            lucroEl.getAttribute("data-inicializado") !== "true"
          ) {
            const lucroAtual = parseFloat(lucroEl.textContent || "0");
            const novoLucro = parseFloat(data.lucro || "0");

            // Atualiza o valor do lucro
            lucroEl.textContent = novoLucro.toFixed(2);

            // Marca como inicializado para futuras verificações
            lucroEl.setAttribute("data-inicializado", "true");

            // Limpa qualquer configuração de fonte que possa ter sido definida
            if (lucroEl.style.fontFamily) {
              lucroEl.style.fontFamily = "";
            }
            if (lucroEl.style.fontWeight) {
              lucroEl.style.fontWeight = "";
            }

            // Adiciona estilo para garantir que a fonte não mude
            lucroEl.style.fontFamily = "inherit !important";
            lucroEl.style.fontWeight = "bold !important";

            // Aplica a classe de estilo correspondente ao valor
            if (novoLucro > 0) {
              lucroEl.className = "positivo";
            } else if (novoLucro < 0) {
              lucroEl.className = "negativo";
            } else {
              lucroEl.className = "neutro";
            }
          }
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar lucro/meta:", error);
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

  // Adicionar a função trocarAba à janela para chamar do HTML
  window.trocarAba = function (aba) {
    // Oculta todas as abas
    document.getElementById("tabela-historico").style.display = "none";
    document.getElementById("historico-completo").style.display = "none";
    document.getElementById("grafico-diario").style.display = "none";

    // Remove a classe ativo de todos os botões
    document.getElementById("btn-historico-atual").classList.remove("ativo");
    document.getElementById("btn-historico-completo").classList.remove("ativo");
    document.getElementById("btn-graficos").classList.remove("ativo");
    document.getElementById("btn-limpar").classList.remove("ativo");

    // Exibe a aba selecionada e marca o botão correspondente como ativo
    if (aba === "tabela") {
      document.getElementById("tabela-historico").style.display = "block";
      document.getElementById("btn-historico-atual").classList.add("ativo");
    } else if (aba === "historico-completo") {
      document.getElementById("historico-completo").style.display = "block";
      document.getElementById("btn-historico-completo").classList.add("ativo");
      atualizarHistoricoCompleto(); // Atualiza os dados ao mudar para esta aba
    } else if (aba === "grafico") {
      document.getElementById("grafico-diario").style.display = "block";
      document.getElementById("btn-graficos").classList.add("ativo");
      atualizarGraficoTempoReal(); // Atualiza o gráfico ao mudar para esta aba
    } else if (aba === "limpar") {
      document.getElementById("btn-limpar").classList.add("ativo");
      zerarTudo(); // Chama a função para zerar tudo
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
          atualizarLog(data.mensagem_log);
        }

        // Atualiza a barra de progresso e as bolinhas
        atualizarStatusOperacao(data.status_operacao);

        // Força a atualização da barra em dispositivos móveis
        if (
          window.mobileUtils &&
          typeof window.mobileUtils.forcarAtualizacaoBarraProgresso ===
            "function"
        ) {
          // Pequeno atraso para garantir que ocorra após o CSS ter sido aplicado
          setTimeout(window.mobileUtils.forcarAtualizacaoBarraProgresso, 100);
        }
      })
      .catch((err) => {
        console.error("Erro ao buscar status detalhado:", err);
      });
  }

  function atualizarStatusOperacao(statusOp) {
    if (!statusOp) return;
    const etapa = statusOp.etapa;
    // Usa a função centralizada para atualizar bolinhas e barra de progresso
    atualizarProgressoBolinhas(etapa);

    // Chama a função específica para dispositivos móveis
    if (
      window.mobileUtils &&
      typeof window.mobileUtils.atualizarBarraProgressoMobile === "function"
    ) {
      window.mobileUtils.atualizarBarraProgressoMobile(etapa);
    }
  }

  function atualizarBolinhasStatus(etapa) {
    // Usa a função centralizada para atualizar bolinhas e barra de progresso
    atualizarProgressoBolinhas(etapa);

    // Chama a função específica para dispositivos móveis
    if (
      window.mobileUtils &&
      typeof window.mobileUtils.atualizarBarraProgressoMobile === "function"
    ) {
      window.mobileUtils.atualizarBarraProgressoMobile(etapa);
    }
  }

  // Função para resetar as bolinhas e barra de progresso para o estado inicial
  function resetarProgressoBolinhas() {
    // Limpa estado atual de todas as bolinhas
    document.querySelectorAll(".bolinha").forEach((b) => {
      b.classList.remove("ativa");
      b.classList.remove("pisca");
    });

    // Reseta a barra de progresso para 0%
    const statusEtapas = document.querySelector(".status-etapas");
    if (statusEtapas) {
      // Aplica diretamente usando CSS inline
      const styleElement = document.getElementById("barra-progresso-style");
      if (!styleElement) {
        // Criar elemento de estilo se não existir
        const style = document.createElement("style");
        style.id = "barra-progresso-style";
        document.head.appendChild(style);
      }

      // Atualizar o CSS diretamente para 0%
      const styleSheet = document.getElementById("barra-progresso-style").sheet;
      // Limpar regras anteriores
      while (styleSheet.cssRules.length > 0) {
        styleSheet.deleteRule(0);
      }

      // Adicionar nova regra
      styleSheet.insertRule(
        `.status-etapas::after { width: 0 !important; }`,
        0
      );

      // Força um reflow para garantir que a alteração seja aplicada imediatamente
      void statusEtapas.offsetWidth;
    }
  }

  // Função para animar transição de valores numéricos
  function animarValor(
    elemento,
    valorInicial,
    valorFinal,
    duracaoMS = 1000,
    prefixo = "",
    sufixo = "",
    formatoDecimais = 2
  ) {
    if (!elemento) return;

    // Converte para números para garantir cálculo correto
    valorInicial = parseFloat(valorInicial);
    valorFinal = parseFloat(valorFinal);

    // Se os valores forem iguais, não precisamos animar
    if (valorInicial === valorFinal) {
      elemento.textContent =
        prefixo + valorFinal.toFixed(formatoDecimais) + sufixo;
      return;
    }

    // Se o elemento já tiver uma animação em andamento, cancela
    if (elemento._animacaoTimer) {
      clearInterval(elemento._animacaoTimer);
    }

    const inicio = Date.now();
    const incremento = valorFinal - valorInicial;
    const passos = duracaoMS / 16; // ~60fps
    const incrementoPorPasso = incremento / passos;

    // Aplica classe de animação somente nos resultados, não no saldo
    if (!elemento.id.includes("saldo")) {
      elemento.classList.add("valor-animando");

      // Remove classes de cores anteriores
      elemento.classList.remove("positivo", "negativo", "neutro");

      // Adiciona classe baseada no valor
      if (valorFinal > 0) {
        elemento.classList.add("positivo");
      } else if (valorFinal < 0) {
        elemento.classList.add("negativo");
      } else {
        elemento.classList.add("neutro");
      }
    }

    // Função de animação
    elemento._animacaoTimer = setInterval(() => {
      const decorrido = Date.now() - inicio;
      const fracao = Math.min(decorrido / duracaoMS, 1);

      // Efeito de ease-out para suavizar o final
      const progresso = 1 - Math.pow(1 - fracao, 3);
      const valorAtual = valorInicial + incremento * progresso;

      // Atualiza o texto
      elemento.textContent =
        prefixo + valorAtual.toFixed(formatoDecimais) + sufixo;

      // Se chegou ao fim, limpa o timer
      if (fracao === 1) {
        clearInterval(elemento._animacaoTimer);
        elemento._animacaoTimer = null;

        // Garante que o valor final seja exatamente o que queremos
        elemento.textContent =
          prefixo + valorFinal.toFixed(formatoDecimais) + sufixo;

        // Remove a classe de animação
        if (!elemento.id.includes("saldo")) {
          setTimeout(() => {
            elemento.classList.remove("valor-animando");
          }, 300);
        }
      }
    }, 16);
  }

  // Função para animar resultados com fade
  function animarResultado(elemento, valor, formatoDecimais = 2) {
    if (!elemento) return;

    // Remove animações anteriores
    elemento.classList.remove("destaque-resultado");

    // Converte para número
    const valorNum = parseFloat(valor);

    // Limpa classes de cor anteriores
    elemento.classList.remove("positivo", "negativo", "neutro");

    // Formata valor com $ e aplica classes
    if (valorNum > 0) {
      elemento.classList.add("positivo");
      elemento.innerHTML = `$${valorNum.toFixed(formatoDecimais)}`;
    } else if (valorNum < 0) {
      elemento.classList.add("negativo");
      elemento.innerHTML = `$${valorNum.toFixed(formatoDecimais)}`;
    } else {
      elemento.classList.add("neutro");
      elemento.innerHTML = `$${valorNum.toFixed(formatoDecimais)}`;

      // Removido - Não alteramos mais a fonte de nenhum elemento
    }

    // Aplica animação
    requestAnimationFrame(() => {
      elemento.classList.add("destaque-resultado");
    });
  }

  // Função para salvar o estado atual do robô no localStorage
  function salvarEstadoRobo() {
    if (!roboAtivo) return; // Não salva se o robô estiver inativo

    const estadoRobo = {
      roboAtivo,
      metaDiaria,
      modoOperacao,
      saldoAtual,
      lucroAtual,
      tempoAtivoSegundos,
      contadorOperacoes,
      timestamp: Date.now(),
      // Informações adicionais para melhor restauração
      statusOperacao: document.querySelector(".status-operacao")
        ? document.querySelector(".status-operacao").textContent
        : "",
      statusConta: document.querySelector(".tipo-conta")
        ? document.querySelector(".tipo-conta").textContent
        : "",
      numeroConta: document.querySelector(".numero-conta")
        ? document.querySelector(".numero-conta").textContent
        : "",
      historicoOperacoes: [], // Para armazenar o histórico recente (será preenchido abaixo)
    };

    // Capturar o histórico recente (últimas 5 operações)
    if (historicoTabela) {
      const linhas = historicoTabela.querySelectorAll("tr");
      const limite = Math.min(linhas.length, 5); // Limita a 5 operações recentes

      for (let i = 0; i < limite; i++) {
        const celulas = linhas[i].querySelectorAll("td");
        if (celulas.length >= 5) {
          estadoRobo.historicoOperacoes.push({
            data: celulas[0].textContent,
            hora: celulas[1].textContent,
            tipo: celulas[2].textContent,
            valor: celulas[3].textContent,
            resultado: celulas[4].textContent,
          });
        }
      }
    }

    localStorage.setItem("derivbot_estado", JSON.stringify(estadoRobo));
    console.log("Estado do robô salvo no localStorage");
  }

  // Função para restaurar o estado do robô do localStorage
  function restaurarEstadoRobo() {
    const estadoSalvo = localStorage.getItem("derivbot_estado");
    if (!estadoSalvo) return false;

    try {
      const estado = JSON.parse(estadoSalvo);

      // Verificar se o estado é recente (menos de 5 minutos)
      const agora = Date.now();
      const diferenca = agora - estado.timestamp;
      const cincominutosMs = 5 * 60 * 1000;

      if (diferenca > cincominutosMs) {
        console.log("Estado salvo expirado, não será restaurado");
        localStorage.removeItem("derivbot_estado");
        return false;
      }

      // Restaurar os valores
      metaDiaria = estado.metaDiaria;
      modoOperacao = estado.modoOperacao;
      saldoAtual = estado.saldoAtual;
      lucroAtual = estado.lucroAtual;
      tempoAtivoSegundos = estado.tempoAtivoSegundos;
      contadorOperacoes = estado.contadorOperacoes;

      // Atualizar a interface com os valores restaurados
      if (metaInput) metaInput.value = metaDiaria.toString();
      if (modoSelect) modoSelect.value = modoOperacao;
      if (saldoValor) saldoValor.textContent = saldoAtual.toFixed(2);
      if (lucroValor) lucroValor.textContent = lucroAtual.toFixed(2);
      if (metaValor) metaValor.textContent = "/" + metaDiaria.toFixed(2);
      if (operacoesDiarias)
        operacoesDiarias.textContent = contadorOperacoes.toString();

      // Restaurar o histórico de operações se disponível
      if (estado.historicoOperacoes && estado.historicoOperacoes.length > 0) {
        restaurarHistoricoOperacoes(estado.historicoOperacoes);
      }

      console.log("Estado do robô restaurado com sucesso");

      // MODIFICADO: Não definimos mais a flag de restauração automática
      // aqui, isso será decidido com base no status real do servidor

      return true;
    } catch (erro) {
      console.error("Erro ao restaurar estado:", erro);
      localStorage.removeItem("derivbot_estado");
      return false;
    }
  }

  // Nova função para restaurar o histórico de operações
  function restaurarHistoricoOperacoes(historicoSalvo) {
    if (!historicoTabela || !historicoSalvo || historicoSalvo.length === 0)
      return;

    // Limpa o histórico atual
    historicoTabela.innerHTML = "";

    // Adiciona as operações salvas
    historicoSalvo.forEach((op) => {
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
      celulaTipo.textContent = op.tipo;
      linha.appendChild(celulaTipo);

      // Valor
      const celulaValor = document.createElement("td");
      celulaValor.textContent = op.valor;
      linha.appendChild(celulaValor);

      // Resultado
      const celulaResultado = document.createElement("td");
      celulaResultado.classList.add("resultado");
      celulaResultado.textContent = op.resultado;

      // Aplicar classe baseada no valor
      const valorNumerico = parseFloat(op.resultado.replace("$", "").trim());
      if (valorNumerico > 0) {
        celulaResultado.classList.add("positivo");
      } else if (valorNumerico < 0) {
        celulaResultado.classList.add("negativo");
      } else {
        celulaResultado.classList.add("neutro");
      }

      linha.appendChild(celulaResultado);

      // Adiciona linha na tabela
      historicoTabela.appendChild(linha);
    });

    console.log("Histórico de operações restaurado");
  }

  // Inicializações
  function inicializar() {
    // Define valor inicial da meta
    if (metaInput) {
      metaInput.value = metaDiaria.toString();
    }

    // Verificação inicial do status do Deriv
    verificarStatusDeriv();

    // Inicia timers de verificação
    verificacaoDerivTimer = setInterval(verificarStatusDeriv, 10000);
    verificacaoStatusTimer = setInterval(atualizarStatusRobo, 5000);

    // Atualiza saldo inicial
    atualizarSaldo();

    // Verifica primeiro status do robô no servidor antes de restaurar qualquer estado
    fetch("/status_robo")
      .then((response) => response.json())
      .then((data) => {
        // Restaura o estado do robô apenas se ele estiver realmente rodando no servidor
        if (data && data.ativo) {
          console.log("Robô está rodando no servidor - restaurando interface");
          roboAtivo = true;
          atualizarStatusRobo(); // Isso vai atualizar a interface
        } else {
          // Robô não está rodando, apenas restaurar configurações
          restaurarEstadoRobo();
        }
      })
      .catch((error) => {
        console.error("Erro ao verificar status do robô:", error);
        // Em caso de erro, tenta restaurar o estado mesmo assim
        restaurarEstadoRobo();
      });

    // Adiciona estilos para análise da IA e inicia atualização
    adicionarEstilosAnaliseIA();
    atualizarAnaliseIA();

    // Atualizações periódicas
    setInterval(atualizarSaldoEmTempoReal, 5000);
    setInterval(atualizarStatusRobo, 4000);
    setInterval(atualizarLucroEMeta, 3000);
    setInterval(atualizarOperacoesDiarias, 30000);
    setInterval(atualizarAnaliseIA, 4000); // Atualiza análise da IA a cada 4 segundos
  }

  // Função para atualizar os dados em tempo real
  function atualizarDadosOperacao() {
    fetch("/status_detalhado")
      .then((response) => response.json())
      .then((data) => {
        if (!data || data.status !== "ok") return;

        // Atualiza informações de operação atual (se existir)
        const operacaoAtual = data.operacao_atual;
        if (operacaoAtual) {
          // Atualiza data e hora da última operação
          const dataOperacao =
            operacaoAtual.timestamp || new Date().toISOString();
          const dataObj = new Date(dataOperacao);

          // Formata a data e hora no formato brasileiro
          const dataFormatada = dataObj.toLocaleDateString("pt-BR");
          const horaFormatada = dataObj.toLocaleTimeString("pt-BR");

          // Atualiza os dados no histórico (primeira linha da tabela)
          const tabela = document.getElementById("historico-tabela-body");
          if (tabela && tabela.rows.length > 0) {
            const primeiraLinha = tabela.rows[0];

            // Atualiza a data e hora
            if (primeiraLinha.cells[0])
              primeiraLinha.cells[0].textContent = dataFormatada;
            if (primeiraLinha.cells[1])
              primeiraLinha.cells[1].textContent = horaFormatada;

            // Atualiza tipo de operação
            if (primeiraLinha.cells[2] && operacaoAtual.tipo) {
              primeiraLinha.cells[2].textContent =
                operacaoAtual.tipo.toUpperCase();
            }

            // Atualiza valor de entrada
            if (primeiraLinha.cells[3] && operacaoAtual.valor) {
              primeiraLinha.cells[3].textContent = `$${parseFloat(
                operacaoAtual.valor
              ).toFixed(2)}`;
            }

            // Atualiza resultado (se disponível)
            if (
              primeiraLinha.cells[4] &&
              operacaoAtual.resultado !== undefined
            ) {
              const resultado = parseFloat(operacaoAtual.resultado);
              primeiraLinha.cells[4].textContent = `$${resultado.toFixed(2)}`;
              primeiraLinha.cells[4].className =
                resultado >= 0 ? "positivo" : "negativo";
            }
          }
        }

        // Atualiza gráfico se estivermos na aba de gráfico
        if (
          document.getElementById("grafico-diario").style.display !== "none"
        ) {
          atualizarGraficoTempoReal(data.par_atual);
        }
      })
      .catch((error) =>
        console.error("Erro ao atualizar dados da operação:", error)
      );
  }

  // Função para atualizar o gráfico em tempo real do ativo
  function atualizarGraficoTempoReal(ativo) {
    const graficoEl = document.getElementById("grafico-diario");
    if (!graficoEl) return;

    // Verifica se o iframe já existe
    let iframe = document.getElementById("grafico-tradingview");

    // Se não existir, cria um novo
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = "grafico-tradingview";
      iframe.width = "100%";
      iframe.height = "400px";
      iframe.style.border = "none";
      iframe.allowFullscreen = true;
      graficoEl.innerHTML = ""; // Limpa o conteúdo anterior
      graficoEl.appendChild(iframe);
    }

    // Atualiza o src do iframe com o ativo atual
    const ativoFormatado = ativo || "R_10";
    iframe.src = `https://br.tradingview.com/chart/?symbol=DERIV:${ativoFormatado}&interval=1`;
  }

  // Função para limpar todos os dados do robô
  function zerarTudo() {
    if (
      confirm(
        "Tem certeza que deseja zerar todos os dados do robô? Esta ação não pode ser desfeita."
      )
    ) {
      fetch("/limpar_historico", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "ok") {
            // Limpa a tabela de histórico
            const tabela = document.getElementById("historico-tabela-body");
            if (tabela) tabela.innerHTML = "";

            // Reseta o lucro
            const lucroEl = document.getElementById("lucro-valor");
            if (lucroEl) lucroEl.textContent = "0.00";

            // Atualiza o resumo
            const resumoTotal = document.getElementById("resumo-total");
            const resumoLucros = document.getElementById("resumo-lucros");
            const resumoPrejuizos = document.getElementById("resumo-prejuizos");
            const resumoAssertividade = document.getElementById(
              "resumo-assertividade"
            );
            const resumoLucroTotal =
              document.getElementById("resumo-lucro-total");

            if (resumoTotal) resumoTotal.textContent = "0";
            if (resumoLucros) resumoLucros.textContent = "0";
            if (resumoPrejuizos) resumoPrejuizos.textContent = "0";
            if (resumoAssertividade) resumoAssertividade.textContent = "0";
            if (resumoLucroTotal) resumoLucroTotal.textContent = "$0.00";

            // Exibe mensagem de sucesso
            const log = document.getElementById("log-temporario");
            if (log) {
              log.innerHTML =
                '<span class="log-emoji">✅</span><span class="log-texto">Todos os dados foram zerados com sucesso!</span>';
              log.className = "log-temp sucesso";
            }
          }
        })
        .catch((error) => console.error("Erro ao zerar dados:", error));
    }
  }

  // Adiciona a função à janela para chamar do HTML
  window.zerarTudo = zerarTudo;

  // Adiciona a chamada para atualizar dados em tempo real
  setInterval(atualizarDadosOperacao, 1000); // Atualiza a cada segundo

  // Função para atualizar o histórico completo
  function atualizarHistoricoCompleto() {
    fetch("/historico_resultados")
      .then((response) => response.json())
      .then((dados) => {
        const historicoEl = document.getElementById("historico-completo");
        if (!historicoEl) return;

        if (dados.length === 0) {
          historicoEl.innerHTML = "<p>Nenhuma operação registrada ainda.</p>";
          return;
        }

        // Cria a tabela HTML
        let html = `
          <div class="tabela-wrapper">
            <table role="table">
              <thead>
                <tr>
                  <th scope="col">Data</th>
                  <th scope="col">Hora</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Entrada</th>
                  <th scope="col">Resultado</th>
                </tr>
              </thead>
              <tbody>
        `;

        // Adiciona as linhas de dados
        dados.forEach((op) => {
          const resultado = parseFloat(op.resultado_real || 0);
          const classeResultado = resultado >= 0 ? "positivo" : "negativo";

          html += `
            <tr>
              <td>${op.data || "--"}</td>
              <td>${op.hora || "--"}</td>
              <td>${(op.tipo || "--").toUpperCase()}</td>
              <td title="Valor da entrada">$${parseFloat(op.valor || 0).toFixed(
                2
              )}</td>
              <td class="resultado ${classeResultado}">$${resultado.toFixed(
            2
          )}</td>
            </tr>
          `;
        });

        html += `
              </tbody>
            </table>
          </div>
        `;

        historicoEl.innerHTML = html;
      })
      .catch((error) =>
        console.error("Erro ao carregar histórico completo:", error)
      );
  }

  // Inicializações - Modificado para garantir que as bolinhas estejam desativadas no início
  modoSelect.dispatchEvent(new Event("change"));
  atualizarSaldoEmTempoReal();
  atualizarStatusRobo();
  atualizarLucroEMeta();
  atualizarOperacoesDiarias();
  // Resetamos explicitamente as bolinhas no início
  resetarProgressoBolinhas();
  // Verificamos o status detalhado depois, mas só atualizará bolinhas se o robô estiver ativo
  atualizarStatusDetalhado();

  // Atualizações periódicas
  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(atualizarStatusRobo, 4000);
  setInterval(atualizarLucroEMeta, 3000); // Mais frequente
  setInterval(atualizarOperacoesDiarias, 4000);
  setInterval(atualizarStatusDetalhado, 3000);
  setInterval(atualizarHistorico, 2000); // Mais frequente
  setInterval(verificarStatusDeriv, 5000); // Mantendo apenas uma verificação de status

  const btnConectarDemo = document.getElementById("btn-conectar-demo");
  if (btnConectarDemo) {
    btnConectarDemo.addEventListener("click", () => {
      fetch("/conectar_demo", { method: "POST" })
        .then((res) => res.json())
        .then((data) => {
          if (data.status === "ok") {
            // Se bem-sucedido, atualizamos a interface antes de recarregar a página
            if (data.conta_id) {
              // Atualiza o tipo de conta e número da conta no card
              const tipoConta = document.querySelector(".tipo-conta");
              const numeroConta = document.querySelector(".numero-conta");

              if (tipoConta) tipoConta.textContent = "Conta Demo";
              if (numeroConta) numeroConta.textContent = data.conta_id;

              // Adiciona efeito de destaque ao card para mostrar a mudança
              const cardConta = document.querySelector(".card-conta");
              if (cardConta) {
                cardConta.classList.add("destacar-card");
                setTimeout(() => {
                  cardConta.classList.remove("destacar-card");
                }, 1500);
              }
            } else {
              // Se não tiver o ID da conta, recarrega a página
              window.location.reload();
            }
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
          // Recarrega a página para aplicar todas as mudanças corretamente
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
          // Recarrega a página para aplicar todas as mudanças corretamente
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
  inicializar();

  // Simular sequência de operações para demonstração (remover em produção)
  function demonstrarProgresso() {
    // Não executamos a demonstração se o robô não estiver ativo
    if (!roboAtivo) {
      return;
    }

    // Obtém o valor da meta para calcular o valor da operação
    const metaValor = parseFloat(
      document.getElementById("meta-valor").textContent.replace("/", "") || "50"
    );
    const modoSelecionado =
      document.getElementById("modo").value || "iniciante";

    // Calcula o valor da entrada baseado no modo selecionado (similar ao backend)
    let percentEntrada = 0.01; // Padrão 1%
    switch (modoSelecionado) {
      case "iniciante":
        percentEntrada = 0.005; // 0.5% da meta
        break;
      case "conservador":
        percentEntrada = 0.01; // 1% da meta
        break;
      case "agressivo":
        percentEntrada = 0.05; // 5% da meta
        break;
    }

    // Calcula o valor de entrada e garante que seja pelo menos 0,35 (mínimo para R_10)
    let valorEntrada = Math.max(metaValor * percentEntrada, 0.35);
    valorEntrada = valorEntrada.toFixed(2);

    // Define etapas da demonstração para operações de 1 segundo (micro scalping)
    const etapas = [
      {
        id: "analisando",
        mensagem: "Analisando padrões de mercado...",
        tempo: 1500,
        classe: "info",
      },
      {
        id: "sinal",
        mensagem: `Sinal identificado! Possível tendência de ALTA em R_10`,
        tempo: 2000,
        classe: "info",
      },
      {
        id: "executando",
        mensagem: `Executando MULTUP $${valorEntrada} em R_10 (micro scalping 1s)`,
        tempo: 1500,
        classe: "processing",
      },
      {
        id: "aguardando",
        mensagem: "Aguardando fechamento automático (1s)...",
        tempo: 1500,
        classe: "processing",
      },
      {
        id: "resultado",
        mensagem: `✅ GANHO! +$${(valorEntrada * 0.9).toFixed(2)}`,
        tempo: 2500,
        classe: "success",
      },
      {
        id: "pronto",
        mensagem: "Analisando próxima oportunidade...",
        tempo: 2000,
        classe: "info",
      },
    ];

    // Adaptação para dispositivos móveis se necessário
    const etapasDemo = verificarMobile()
      ? adaptarMensagensDemo(etapas)
      : etapas;

    // Mostra cada etapa em sequência
    const progresso = document.getElementById("progresso");
    let atual = 0;

    // Limpa qualquer intervalo anterior
    if (window.demoInterval) clearInterval(window.demoInterval);

    // Atualiza o contador de operações
    if (document.getElementById("operacoes-diarias")) {
      const operacoes = parseInt(
        document.getElementById("operacoes-diarias").textContent || "0"
      );
      document.getElementById("operacoes-diarias").textContent = operacoes + 1;
    }

    // Inicia o ciclo de demonstração
    window.demoInterval = setInterval(() => {
      // Verifica novamente se o robô está ativo
      if (!roboAtivo) {
        clearInterval(window.demoInterval);
        resetarProgressoBolinhas();
        return;
      }

      const etapa = etapasDemo[atual];

      // Usa a função centralizada para atualizar bolinhas e barra de progresso
      atualizarProgressoBolinhas(etapa.id, etapa.mensagem, etapa.classe);

      // Chama a função específica para dispositivos móveis
      if (
        window.mobileUtils &&
        typeof window.mobileUtils.atualizarBarraProgressoMobile === "function"
      ) {
        window.mobileUtils.atualizarBarraProgressoMobile(etapa.id);
      }

      // Se for etapa de ganho, atualiza o lucro no cabeçalho
      if (etapa.id === "resultado") {
        const lucroEl = document.getElementById("lucro-valor");
        if (lucroEl) {
          const lucroAtual = parseFloat(lucroEl.textContent || "0");
          lucroEl.textContent = (lucroAtual + parseFloat(valorEntrada)).toFixed(
            2
          );
          lucroEl.classList.add("destaque-resultado");

          // Remove a classe após a animação
          setTimeout(() => {
            lucroEl.classList.remove("destaque-resultado");
          }, 2000);
        }
      }

      // Avança para a próxima etapa
      atual = (atual + 1) % etapasDemo.length;

      // Se chegarmos à etapa final (parado), fazemos uma pausa maior
      if (atual === 0) {
        clearInterval(window.demoInterval);
        setTimeout(() => demonstrarProgresso(), 3000);
      }
    }, 2000);
  }

  // Inicialização
  document.addEventListener("DOMContentLoaded", function () {
    // Detecta se é dispositivo móvel - removido, agora gerenciado pelo mobile.js
    // ... resto do código existente ...
  });

  // Adicionar funções para exibir análise da IA
  function atualizarAnaliseIA() {
    fetch("/ultima_analise")
      .then((response) => response.json())
      .then((data) => {
        if (data.status !== "ok") return;

        // Verifica se o elemento de área de análise existe, se não, cria
        let areaAnalise = document.getElementById("area-analise-ia");
        if (!areaAnalise) {
          // Cria área de análise e adiciona à tela
          const infoBar = document.querySelector(".info-bar");
          areaAnalise = document.createElement("div");
          areaAnalise.id = "area-analise-ia";
          areaAnalise.className = "analise-ia-container";

          // Adiciona após a info-bar
          if (infoBar && infoBar.parentNode) {
            infoBar.parentNode.insertBefore(areaAnalise, infoBar.nextSibling);
          } else {
            // Fallback: adiciona ao topo da área de conteúdo
            const areaConteudo = document.querySelector(".content-area");
            if (areaConteudo) {
              areaConteudo.prepend(areaAnalise);
            }
          }

          // Adiciona o título e container interno
          areaAnalise.innerHTML = `
            <h3>Análise da IA <span class="atualizacao-timestamp"></span></h3>
            <div class="analise-detalhes">
              <div class="analise-coluna">
                <div class="analise-item">
                  <label>Preço Atual:</label>
                  <span id="preco-atual-ia">-</span>
                </div>
                <div class="analise-item">
                  <label>Suportes Detectados:</label>
                  <span id="suportes-ia">-</span>
                </div>
                <div class="analise-item">
                  <label>Resistências:</label>
                  <span id="resistencias-ia">-</span>
                </div>
              </div>
              <div class="analise-coluna">
                <div class="analise-item">
                  <label>Sinal Recomendado:</label>
                  <span id="sinal-ia">-</span>
                </div>
                <div class="analise-item">
                  <label>Confiança:</label>
                  <span id="confianca-ia">-</span>
                </div>
                <div class="analise-item">
                  <label>Análise:</label>
                  <span id="razao-ia">-</span>
                </div>
              </div>
            </div>
            <div class="analise-ponto-otimo"></div>
          `;
        }

        // Atualiza os dados da análise
        document.getElementById("preco-atual-ia").textContent =
          data.preco.toFixed(5);

        // Exibe suportes detectados
        const suportesEl = document.getElementById("suportes-ia");
        if (data.suportes && data.suportes.length > 0) {
          suportesEl.textContent = data.suportes
            .map((s) => s.toFixed(5))
            .join(", ");
        } else {
          suportesEl.textContent = "Nenhum detectado";
        }

        // Exibe resistências detectadas
        const resistenciasEl = document.getElementById("resistencias-ia");
        if (data.resistencias && data.resistencias.length > 0) {
          resistenciasEl.textContent = data.resistencias
            .map((r) => r.toFixed(5))
            .join(", ");
        } else {
          resistenciasEl.textContent = "Nenhuma detectada";
        }

        // Exibe sinal atual
        const sinalEl = document.getElementById("sinal-ia");
        if (data.sinal) {
          const textoSinal =
            data.sinal === "compra" ? "CALL (COMPRA)" : "PUT (VENDA)";
          sinalEl.innerHTML = `<strong>${textoSinal}</strong>`;
          sinalEl.className =
            data.sinal === "compra" ? "sinal-compra" : "sinal-venda";
        } else {
          sinalEl.textContent = "Aguardar";
          sinalEl.className = "";
        }

        // Exibe confiança
        const confiancaEl = document.getElementById("confianca-ia");
        if (data.confianca) {
          const confiancaPercent = (data.confianca * 100).toFixed(1);
          confiancaEl.textContent = `${confiancaPercent}%`;

          // Adiciona classe baseada na confiança
          confiancaEl.className = "";
          if (data.confianca >= 0.7) confiancaEl.className = "confianca-alta";
          else if (data.confianca >= 0.5)
            confiancaEl.className = "confianca-media";
          else confiancaEl.className = "confianca-baixa";
        } else {
          confiancaEl.textContent = "-";
          confiancaEl.className = "";
        }

        // Exibe razão
        document.getElementById("razao-ia").textContent = data.razao || "-";

        // Destaca ponto ótimo se estiver em suporte ou resistência
        const pontOtimoEl = document.querySelector(".analise-ponto-otimo");
        if (data.em_suporte || data.em_resistencia) {
          const tipo = data.em_suporte ? "suporte" : "resistência";
          const acao = data.em_suporte ? "CALL" : "PUT";
          pontOtimoEl.innerHTML = `<div class="ponto-otimo-alerta">🎯 Ponto de ${tipo} detectado! Oportunidade para ${acao}</div>`;
          pontOtimoEl.style.display = "block";
        } else {
          pontOtimoEl.style.display = "none";
        }

        // Atualiza timestamp
        const timestampEl = document.querySelector(".atualizacao-timestamp");
        if (data.timestamp) {
          const dataObj = new Date(data.timestamp);
          const hora = dataObj.toLocaleTimeString("pt-BR");
          timestampEl.textContent = `(Atualizado: ${hora})`;
        }
      })
      .catch((error) => {
        console.error("Erro ao obter análise da IA:", error);
      });
  }

  // Adiciona CSS para a área de análise da IA
  function adicionarEstilosAnaliseIA() {
    const estilos = `
      .analise-ia-container {
        margin: 15px 0;
        padding: 15px;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
      }
      
      .analise-ia-container h3 {
        margin-top: 0;
        margin-bottom: 10px;
        font-size: 1.2em;
        color: #f0f0f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .atualizacao-timestamp {
        font-size: 0.8em;
        opacity: 0.7;
        font-weight: normal;
      }
      
      .analise-detalhes {
        display: flex;
        flex-wrap: wrap;
        gap: 20px;
      }
      
      .analise-coluna {
        flex: 1;
        min-width: 180px;
      }
      
      .analise-item {
        margin-bottom: 10px;
      }
      
      .analise-item label {
        display: block;
        font-size: 0.8em;
        opacity: 0.8;
        margin-bottom: 2px;
      }
      
      .analise-item span {
        font-size: 0.95em;
        word-break: break-word;
      }
      
      .sinal-compra {
        color: #4CAF50;
      }
      
      .sinal-venda {
        color: #F44336;
      }
      
      .confianca-alta {
        color: #4CAF50;
        font-weight: bold;
      }
      
      .confianca-media {
        color: #FFC107;
      }
      
      .confianca-baixa {
        color: #F44336;
      }
      
      .ponto-otimo-alerta {
        margin-top: 10px;
        padding: 8px 12px;
        background-color: rgba(76, 175, 80, 0.2);
        border-left: 4px solid #4CAF50;
        border-radius: 4px;
        font-weight: bold;
      }
      
      @media (max-width: 768px) {
        .analise-detalhes {
          flex-direction: column;
          gap: 10px;
        }
        
        .analise-item {
          margin-bottom: 8px;
        }
      }
    `;

    // Adiciona os estilos ao documento
    const style = document.createElement("style");
    style.textContent = estilos;
    document.head.appendChild(style);
  }

  function atualizarHistorico() {
    fetch("/historico_resultados")
      .then((response) => response.json())
      .then((dados) => {
        // Se nenhum dado foi retornado, não fazemos nada
        if (!dados || dados.length === 0) return;

        // Recupera a tabela
        const tabela = document.getElementById("historico-tabela-body");
        if (!tabela) return;

        // Limpa tabela antes de adicionar novos dados
        tabela.innerHTML = "";

        // Log para debug
        console.log(`Recebidos ${dados.length} registros de histórico`);

        // Contador para operações com lucro e perda
        let contadorLucros = 0;
        let contadorPerdas = 0;
        let totalResultados = 0;

        // Percorre os dados recebidos (limitando a 20 por questão de performance)
        const dadosLimitados = dados.slice(0, 20);
        dadosLimitados.forEach((operacao, index) => {
          // Cria a linha da tabela
          const linha = document.createElement("tr");

          // Adiciona as colunas com os dados da operação
          // Data
          const colunaData = document.createElement("td");
          colunaData.textContent = operacao.data || "--";
          linha.appendChild(colunaData);

          // Hora
          const colunaHora = document.createElement("td");
          colunaHora.textContent = operacao.hora || "--";
          linha.appendChild(colunaHora);

          // Tipo (CALL/PUT)
          const colunaTipo = document.createElement("td");
          colunaTipo.textContent = operacao.tipo || "--";
          linha.appendChild(colunaTipo);

          // Valor
          const colunaValor = document.createElement("td");
          colunaValor.textContent = operacao.valor
            ? `$${parseFloat(operacao.valor).toFixed(2)}`
            : "--";
          linha.appendChild(colunaValor);

          // Resultado
          const colunaResultado = document.createElement("td");
          const resultado = parseFloat(operacao.resultado_real || 0);
          colunaResultado.textContent = `$${resultado.toFixed(2)}`;

          // Adiciona classe apropriada baseada no resultado
          if (resultado > 0) {
            colunaResultado.classList.add("positivo");
            contadorLucros++;
          } else if (resultado < 0) {
            colunaResultado.classList.add("negativo");
            contadorPerdas++;
          } else {
            colunaResultado.classList.add("neutro");
          }

          linha.appendChild(colunaResultado);

          // Adiciona a linha à tabela
          tabela.appendChild(linha);

          // Acumula o total para cálculos
          totalResultados += resultado;
        });

        // Atualiza o resumo
        const totalOperacoes = contadorLucros + contadorPerdas;
        const assertividade =
          totalOperacoes > 0
            ? ((contadorLucros / totalOperacoes) * 100).toFixed(1)
            : "0.0";

        // Atualiza os campos de resumo
        document.getElementById("resumo-total").textContent = totalOperacoes;
        document.getElementById("resumo-lucros").textContent = contadorLucros;
        document.getElementById("resumo-prejuizos").textContent =
          contadorPerdas;
        document.getElementById(
          "resumo-assertividade"
        ).textContent = `${assertividade}%`;
        document.getElementById(
          "resumo-lucro-total"
        ).textContent = `$${totalResultados.toFixed(2)}`;

        // Destaca o resumo com animação se houver mudanças
        const resumoLucroTotal = document.getElementById("resumo-lucro-total");
        resumoLucroTotal.classList.add("destaque-resultado");
        setTimeout(
          () => resumoLucroTotal.classList.remove("destaque-resultado"),
          1000
        );
      })
      .catch((erro) => {
        console.error("Erro ao atualizar histórico:", erro);
      });
  }
});
