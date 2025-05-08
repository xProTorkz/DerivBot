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
    fetch("/saldo_atual")
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          const saldoEl = document.getElementById("saldo-valor");
          const saldoAtual = parseFloat(saldoEl.textContent || "0");
          const novoSaldo = parseFloat(data.saldo);

          // Anima a transição do saldo
          animarValor(saldoEl, saldoAtual, novoSaldo, 1000);
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
          } else {
            atualizarLog("🟡 Robô parado.", "config");
            // Quando o robô estiver parado, resetamos as bolinhas e barra
            resetarProgressoBolinhas();
            botaoControle.textContent = "✅ Iniciar Robô";
            botaoControle.style.backgroundColor = "#00d67b"; // verde
            botaoControle.style.color = "#000"; // preto
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
      })
      .catch((error) => {
        console.error("Erro ao atualizar status:", error);
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

          // Garante que mesmo quando o valor atual é igual ao valor anterior,
          // o display é atualizado
          if (lucroEl) {
            const lucroAtual = parseFloat(lucroEl.textContent || "0");
            const novoLucro = parseFloat(data.lucro || "0");

            // Força a atualização direta do texto, sem alterar estilos
            lucroEl.textContent = novoLucro.toFixed(2);

            // Garante que nenhum estilo de fonte seja aplicado
            if (lucroEl.style.fontFamily) {
              lucroEl.style.fontFamily = "";
            }
            if (lucroEl.style.fontWeight) {
              lucroEl.style.fontWeight = "";
            }

            // Só anima se houver diferença
            if (lucroAtual !== novoLucro) {
              // Usa uma versão modificada que não afeta a fonte
              const valorInicial = lucroAtual;
              const valorFinal = novoLucro;
              const duracao = 1200;
              const inicio = Date.now();
              const incremento = valorFinal - valorInicial;

              if (incremento !== 0) {
                const animarNumero = () => {
                  const decorrido = Date.now() - inicio;
                  const fracao = Math.min(decorrido / duracao, 1);
                  const progresso = 1 - Math.pow(1 - fracao, 3);
                  const valorAtual = valorInicial + incremento * progresso;

                  // Atualiza apenas o texto sem modificar estilos
                  lucroEl.textContent = valorAtual.toFixed(2);

                  if (fracao < 1) {
                    requestAnimationFrame(animarNumero);
                  } else {
                    lucroEl.textContent = valorFinal.toFixed(2);
                  }
                };

                requestAnimationFrame(animarNumero);
              }
            }
          }

          // Só atualiza meta se o robô estiver ativo; caso contrário mantemos valor local
          if (roboAtivo) {
            const meta = parseFloat(data.meta).toFixed(2);
            if (metaEl) metaEl.textContent = "/" + meta;
            if (metaInput && !roboAtivo) {
              metaInput.value = meta;
            }
          }
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

      // Se o robô estava ativo, precisamos reiniciá-lo
      if (estado.roboAtivo) {
        precisaRestaurarEstado = true;
        console.log("Robô estava ativo, marcando para reiniciar");
        atualizarLog("📋 Restaurando sessão anterior do robô...", "info");
      }

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

  // Modificar a função inicializar para verificar se há estado salvo
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

    // Novo: Tenta restaurar o estado salvo
    restaurarEstadoRobo();

    // Novo: Configurar evento para salvar estado quando a página for fechada/atualizada
    window.addEventListener("beforeunload", salvarEstadoRobo);

    // Novo: Verificar a cada 30 segundos para salvar o estado (backup)
    setInterval(salvarEstadoRobo, 30000);

    // Novo: Se o robô estava ativo, reiniciá-lo após alguns segundos
    if (precisaRestaurarEstado) {
      atualizarLog("🔄 Restaurando operações do robô...", "config");
      setTimeout(() => {
        iniciarRoboAutomaticamente();
      }, 3000);
    }
  }

  // Nova função para iniciar o robô automaticamente após restauração de estado
  function iniciarRoboAutomaticamente() {
    if (!precisaRestaurarEstado) return;

    console.log("Iniciando robô automaticamente após restauração de estado");

    // Envia comando para o servidor para iniciar o robô com os valores restaurados
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
          atualizarLog(
            "✅ Robô restaurado com sucesso no modo " + modoOperacao,
            "sucesso"
          );

          // Atualiza valores na interface
          if (metaValor) metaValor.textContent = "/" + metaDiaria.toFixed(2);
          document.getElementById("modo-selecionado").style.display = "block";
          document.getElementById("modo-texto").textContent =
            modoOperacao.toUpperCase();

          // Inicia atualização contínua
          atualizacaoTimer = setInterval(atualizarStatusRobo, 1000);

          // Reset da flag
          precisaRestaurarEstado = false;
        } else {
          atualizarLog(
            "⚠️ Erro ao restaurar robô: " +
              (data.mensagem || "Falha na conexão"),
            "erro"
          );
          precisaRestaurarEstado = false;
        }
      })
      .catch((error) => {
        atualizarLog("⚠️ Erro de conexão ao restaurar robô", "erro");
        console.error("Erro:", error);
        precisaRestaurarEstado = false;
      });
  }

  // Modificar a função iniciarRobo para salvar estado após iniciar
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

          // Salvar estado imediatamente
          salvarEstadoRobo();
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

  // Modificar a função pararRobo para limpar estado ao parar
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

          // Remover estado salvo quando o robô é parado intencionalmente
          localStorage.removeItem("derivbot_estado");
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

          // Salvar o estado quando detectamos que o robô está rodando
          salvarEstadoRobo();
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

          // Remover o estado salvo quando o robô é detectado como parado
          localStorage.removeItem("derivbot_estado");
        }

        // Atualizar dados do robô para persistência, apenas se estiver ativo
        if (data.ativo && roboAtivo) {
          // Atualizar valores para persistência
          saldoAtual = data.saldo;
          lucroAtual = data.lucro;
          contadorOperacoes = data.operacoes;

          // Salvar estado atualizado
          salvarEstadoRobo();
        }
      })
      .catch((error) => {
        console.error("Erro ao verificar status:", error);
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
        if (historicoTabela) {
          // Limpa a tabela atual
          historicoTabela.innerHTML = "";

          // Adiciona as operações na ordem (mais recentes primeiro)
          data.reverse().forEach((op) => {
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
            celulaValor.textContent = "$" + parseFloat(op.valor).toFixed(2);
            linha.appendChild(celulaValor);

            // Resultado - Agora com animação
            const celulaResultado = document.createElement("td");
            celulaResultado.classList.add("resultado");

            // Aplicar classe baseada no valor
            if (op.resultado_real > 0) {
              celulaResultado.classList.add("positivo");
            } else if (op.resultado_real < 0) {
              celulaResultado.classList.add("negativo");
            } else {
              celulaResultado.classList.add("neutro");
            }

            celulaResultado.textContent =
              "$" + parseFloat(op.resultado_real).toFixed(2);

            linha.appendChild(celulaResultado);

            // Adiciona linha na tabela
            historicoTabela.appendChild(linha);
          });

          // Mantém rolagem no final
          const tabela = document.getElementById("tabela-historico");
          if (tabela) {
            tabela.scrollTop = tabela.scrollHeight;
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

  // Inicializações - Modificado para garantir que as bolinhas estejam desativadas no início
  modoSelect.dispatchEvent(new Event("change"));
  atualizarSaldoEmTempoReal();
  verificarConexaoDeriv();
  atualizarStatusRobo();
  atualizarLucroEMeta();
  atualizarOperacoesDiarias();
  // Resetamos explicitamente as bolinhas no início
  resetarProgressoBolinhas();
  // Verificamos o status detalhado depois, mas só atualizará bolinhas se o robô estiver ativo
  atualizarStatusDetalhado();

  // Atualizações periódicas
  setInterval(atualizarSaldoEmTempoReal, 5000);
  setInterval(verificarConexaoDeriv, 5000);
  setInterval(atualizarStatusRobo, 4000);
  setInterval(atualizarLucroEMeta, 3000); // Mais frequente
  setInterval(atualizarOperacoesDiarias, 4000);
  setInterval(atualizarStatusDetalhado, 3000);
  setInterval(atualizarHistorico, 2000); // Mais frequente
  setInterval(() => {
    fetch("/status_robo")
      .then((res) => res.json())
      .then((data) => {
        if (data.ativo) {
          // Usa a nova implementação
          atualizarHistorico();
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

    // Etapas com pontos de progresso e tipos de feedback
    let etapasDemo = [
      {
        nome: "analisando",
        progresso: 0,
        tipo: "analise",
        mensagem: "Analisando mercado em busca de oportunidades ideais...",
      },
      {
        nome: "medio",
        progresso: 33,
        tipo: "info",
        mensagem: "Sinal identificado! Padrão de alta detectado em EUR/USD",
      },
      {
        nome: "abrindo",
        progresso: 50,
        tipo: "contrato",
        mensagem: "Abrindo contrato CALL de $5.00 com expiração de 1 minuto",
      },
      {
        nome: "aguardando",
        progresso: 75,
        tipo: "espera",
        mensagem: "Contrato aberto! Aguardando resultado (30s restantes)",
      },
      {
        nome: "finalizado-win",
        progresso: 100,
        tipo: "ganho",
        mensagem: "✅ Operação finalizada com GANHO! +$4.30 (86% de lucro)",
      },
      {
        nome: "parado",
        progresso: 0,
        tipo: "config",
        mensagem: "Robô pronto para nova análise de mercado",
      },
    ];

    // Adapta mensagens para dispositivos móveis, se disponível
    if (
      window.mobileUtils &&
      typeof window.mobileUtils.adaptarMensagensDemo === "function"
    ) {
      etapasDemo = window.mobileUtils.adaptarMensagensDemo(etapasDemo);
    }

    let etapaAtual = 0;

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

      const etapa = etapasDemo[etapaAtual];

      // Usa a função centralizada para atualizar bolinhas e barra de progresso
      atualizarProgressoBolinhas(etapa.nome, etapa.mensagem, etapa.tipo);

      // Chama a função específica para dispositivos móveis
      if (
        window.mobileUtils &&
        typeof window.mobileUtils.atualizarBarraProgressoMobile === "function"
      ) {
        window.mobileUtils.atualizarBarraProgressoMobile(etapa.nome);
      }

      // Se for etapa de ganho, atualiza o lucro no cabeçalho
      if (etapa.nome === "finalizado-win") {
        const lucroEl = document.getElementById("lucro-valor");
        if (lucroEl) {
          const lucroAtual = parseFloat(lucroEl.textContent || "0");
          lucroEl.textContent = (lucroAtual + 4.3).toFixed(2);
          lucroEl.classList.add("destaque-resultado");

          // Remove a classe após a animação
          setTimeout(() => {
            lucroEl.classList.remove("destaque-resultado");
          }, 2000);
        }
      }

      // Avança para a próxima etapa
      etapaAtual = (etapaAtual + 1) % etapasDemo.length;

      // Se chegarmos à etapa final (parado), fazemos uma pausa maior
      if (etapaAtual === 0) {
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
});
