// DerivBot - Código Principal
// Carrega mobile.js para funcionalidades específicas para dispositivos móveis
// O mobile.js é responsável por detectar e ajustar a interface para dispositivos móveis

// JavaScript carregado com sucesso
console.log("✅ DerivBot JavaScript carregado e executando!");

document.addEventListener("DOMContentLoaded", function () {
  // Código para garantir que a barra de progresso termine nas bolinhas
  (function fixProgressBar() {
    // Adicionar um estilo específico que force os limites da barra exatamente no centro das bolinhas
    const styleEl = document.createElement("style");
    styleEl.id = "progress-bar-fix";
    styleEl.textContent = `
      .status-etapas::before {
        left: 35px !important;
        right: 35px !important;
        top: 7.5px !important;
      }
      .status-etapas::after {
        left: 35px !important;
        max-width: calc(100% - 70px) !important;
        top: 7.5px !important;
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
  let metaDiaria = 20.0; // Será atualizada na inicialização baseada no modo
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

  // Configurações dos modos (sincronizado com catalogador.py)
  const modosConfig = {
    iniciante: {
      meta: 20,
      maxMeta: 20,
      maxOperacoes: 1,
      confiancaMin: 85,
    },
    conservador: {
      meta: 50,
      maxMeta: 50,
      maxOperacoes: 3,
      confiancaMin: 80,
    },
    agressivo: {
      meta: 100,
      maxMeta: null,
      maxOperacoes: 5,
      confiancaMin: 75,
    },
  };

  modoSelect.addEventListener("change", () => {
    const modo = modoSelect.value;
    const config = modosConfig[modo];

    if (config) {
      metaInput.value = config.meta;
      metaDiaria = config.meta; // Atualiza a variável global

      // Atualiza texto da meta no cabeçalho imediatamente
      const metaHeaderEl = document.getElementById("meta-valor");
      if (metaHeaderEl) {
        metaHeaderEl.textContent = "/" + config.meta;
      }

      // Salva a nova meta no localStorage
      localStorage.setItem("meta_diaria", config.meta);

      // Atualiza gestão de riscos se disponível
      if (window.logsAvancados && window.logsAvancados.gestaoRiscos) {
        window.logsAvancados.gestaoRiscos.definirModo(modo);
      }

      atualizarLog(
        `Modo selecionado: ${modo.toUpperCase()} - Meta: $${
          config.meta
        } - Máx operações: ${config.maxOperacoes} - Confiança mín: ${
          config.confiancaMin
        }%`
      );
    }
  });

  // Se o usuário editar manualmente a meta, refletir no cabeçalho
  metaInput.addEventListener("input", () => {
    const novaMetaValor = parseInt(metaInput.value) || 0;
    const modoAtual = modoSelect.value;
    const configAtual = modosConfig[modoAtual];

    // Validação de meta máxima
    if (
      configAtual &&
      configAtual.maxMeta !== null &&
      novaMetaValor > configAtual.maxMeta
    ) {
      metaInput.value = configAtual.maxMeta;
      atualizarLog(
        `Meta limitada a $${
          configAtual.maxMeta
        } no modo ${modoAtual.toUpperCase()}`,
        "aviso"
      );
      return;
    }

    metaDiaria = novaMetaValor; // Atualiza a variável global

    // Salva no localStorage para persistir
    localStorage.setItem("meta_diaria", novaMetaValor);

    const metaHeaderEl = document.getElementById("meta-valor");
    if (metaHeaderEl) metaHeaderEl.textContent = "/" + novaMetaValor;
  });

  // Debug: Verificar se o botão foi encontrado
  console.log("Botão controle encontrado:", botaoControle);
  console.log("Modo select encontrado:", modoSelect);
  console.log("Meta input encontrado:", metaInput);

  if (!botaoControle) {
    console.error("ERRO: Botão de controle não encontrado!");
    return;
  }

  // O controle de clique é gerenciado exclusivamente por iniciarRoboSeguro() no painel.html
  // Evita listeners concorrentes que causavam alternância indevida de ícones e estados
  if (botaoControle && !botaoControle.hasAttribute("onclick") && !window.iniciarRoboSeguro) {
    botaoControle.addEventListener("click", async () => {
      console.log("🔥 BOTÃO CLICADO! Iniciando processo...");

    const modo = modoSelect.value;
    const meta = parseFloat(metaInput.value);
    const configAtual = modosConfig[modo];

    console.log("Dados:", { modo, meta, configAtual });

    // Validação de meta antes de iniciar
    if (
      configAtual &&
      configAtual.maxMeta !== null &&
      meta > configAtual.maxMeta
    ) {
      atualizarLog(
        `Erro: Meta de $${meta} excede o limite de $${
          configAtual.maxMeta
        } para o modo ${modo.toUpperCase()}`,
        "erro"
      );
      return;
    }

    // ✅ Garante que a aba da tabela esteja visível
    if (typeof trocarAba === "function") {
      trocarAba("tabela");
    } else if (typeof window.trocarAba === "function") {
      window.trocarAba("tabela");
    }

    // ✅ Limpa somente o corpo da tabela
    const tabelaBody = document.getElementById("historico-tabela-body");
    if (tabelaBody) tabelaBody.innerHTML = "";

    // ✅ Limpa os campos de resumo com verificação
    ["resumo-total", "resumo-lucros", "resumo-prejuizos", "resumo-assertividade", "resumo-lucro-total"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerText = "--";
    });

    // ✅ Atualiza texto temporário
    const elLog = document.getElementById("log-temporario") || document.getElementById("log-temp");
    if (elLog) elLog.textContent = "Robô iniciado!";

    try {
      console.log("🚀 Enviando requisição para /toggle_bot...");
      console.log("Dados enviados:", { modo, meta });

      const resposta = await fetch("/toggle_bot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ modo, meta }),
      });

      console.log(
        "📡 Resposta recebida:",
        resposta.status,
        resposta.statusText
      );

      if (!resposta.ok) {
        console.error(
          "❌ Erro na resposta:",
          resposta.status,
          resposta.statusText
        );
        const textoErro = await resposta.text();
        console.error("Texto do erro:", textoErro);
        return;
      }

      const dados = await resposta.json();
      console.log("📦 Dados da resposta:", dados);

      // Alterna o estado do botão
      roboAtivo = dados.status === "iniciado";
      botaoControle.textContent = roboAtivo ? "⛔ Parar Robô" : "🚀 Iniciar Robô";
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
  }

  function atualizarLog(mensagem, tipo = "info") {
    const logElement = document.getElementById("log-temporario") || document.getElementById("log-temp");
    if (!logElement) return;

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

    // Atualiza stepper vazado moderno (Issue #25)
    if (typeof window.definirProgressoCanaleta === "function") {
      window.definirProgressoCanaleta(progresso, etapa);
    }

    // Atualiza a barra de progresso - Versão melhorada para mobile
    if (statusEtapas) {
      // Primeiro, determina se estamos em dispositivo móvel
      const isMobileDevice =
        window.innerWidth <= 768 ||
        document.body.classList.contains("mobile-device");

      // Calcula o valor para desktop - padrão (conectando exatamente nos centros das bolinhas)
      let widthValue =
        progresso === 0
          ? "0"
          : progresso === 100
          ? "calc(100% - 70px)"
          : `calc(${progresso}% * (100% - 70px) / 100)`;

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

  // Função para resetar o progresso das bolinhas
  function resetarProgressoBolinhas() {
    if (typeof window.definirProgressoCanaleta === "function") {
      window.definirProgressoCanaleta(0, "parado");
    }

    document.querySelectorAll(".bolinha").forEach((b) => {
      b.classList.remove("ativa");
      b.classList.remove("pisca");
    });

    // Resetar a barra de progresso
    const styleElement = document.getElementById("barra-progresso-style");
    if (styleElement) {
      const styleSheet = styleElement.sheet;
      // Limpar regras anteriores
      while (styleSheet.cssRules.length > 0) {
        styleSheet.deleteRule(0);
      }
      // Adicionar regra para largura zero
      styleSheet.insertRule(
        `.status-etapas::after { width: 0 !important; }`,
        0
      );
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

                // Atualiza o saldo (com centavos)
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

  // Função para trocar de conta (demo/real)
  function trocarContaDemo() {
    fetch("/selecionar_conta", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ tipo: "demo" }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          window.location.reload();
        } else {
          alert("Erro ao trocar para conta demo: " + data.mensagem);
        }
      })
      .catch(() => {
        alert("Erro ao trocar para conta demo.");
      });
  }

  function trocarContaReal() {
    fetch("/selecionar_conta", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ tipo: "real" }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          window.location.reload();
        } else {
          alert("Erro ao trocar para conta real: " + data.mensagem);
        }
      })
      .catch(() => {
        alert("Erro ao trocar para conta real.");
      });
  }

  // Função para adicionar token
  function adicionarToken() {
    const tipoToken = prompt(
      "Que tipo de token deseja adicionar?\n\nDigite 'demo' para token demo ou 'real' para token real:"
    );

    if (
      !tipoToken ||
      (tipoToken.toLowerCase() !== "demo" && tipoToken.toLowerCase() !== "real")
    ) {
      alert("Tipo de token inválido");
      return;
    }

    const token = prompt(`Digite o token ${tipoToken.toUpperCase()}:`);

    if (!token || token.trim().length < 5) {
      alert("Token inválido");
      return;
    }

    fetch("/adicionar_token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tipo: tipoToken.toLowerCase(),
        token: token.trim(),
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          alert(`Token ${tipoToken} adicionado com sucesso!`);
          window.location.reload();
        } else {
          alert("Erro ao adicionar token: " + data.mensagem);
        }
      })
      .catch(() => {
        alert("Erro ao adicionar token.");
      });
  }

  // Expor funções para uso global
  window.trocarContaDemo = trocarContaDemo;
  window.trocarContaReal = trocarContaReal;
  window.adicionarToken = adicionarToken;

  function desconectar() {
    if (confirm("Tem certeza que deseja desconectar?")) {
      window.location.href = "/logout";
    }
  }

  // Expor função para uso global
  window.desconectar = desconectar;

  // Funções do modal de configurações
  function abrirConfiguracoes() {
    document.getElementById("modal-configuracoes").style.display = "flex";
  }

  function fecharConfiguracoes() {
    document.getElementById("modal-configuracoes").style.display = "none";
  }

  // Fechar modal clicando fora dele
  document.addEventListener("click", function (e) {
    const modal = document.getElementById("modal-configuracoes");
    if (e.target === modal) {
      fecharConfiguracoes();
    }
  });

  // Funções das opções de configuração
  function abrirWhatsApp() {
    const numeroWhatsApp = "5511999999999"; // Substitua pelo número real
    const mensagem = encodeURIComponent(
      "Olá! Preciso de suporte com o DerivBot."
    );
    window.open(`https://wa.me/${numeroWhatsApp}?text=${mensagem}`, "_blank");
  }

  function abrirUpgrade() {
    // Redirecionar para página de upgrade ou abrir modal específico
    alert("Funcionalidade de upgrade em desenvolvimento!");
  }

  function abrirTokens() {
    // Redirecionar para página de tokens
    window.location.href = "/tokens";
  }

  function limparCache() {
    if (
      confirm(
        "Tem certeza que deseja limpar o cache? Isso pode afetar o desempenho temporariamente."
      )
    ) {
      // Limpar localStorage
      localStorage.clear();

      // Limpar sessionStorage
      sessionStorage.clear();

      // Recarregar a página
      window.location.reload(true);
    }
  }

  // Expor funções para uso global
  window.abrirConfiguracoes = abrirConfiguracoes;
  window.fecharConfiguracoes = fecharConfiguracoes;
  window.abrirWhatsApp = abrirWhatsApp;
  window.abrirUpgrade = abrirUpgrade;
  window.abrirTokens = abrirTokens;
  window.limparCache = limparCache;

  window.limparHistorico = function () {
    if (!confirm("Tem certeza que deseja limpar o histórico desta sessão?")) return;

    fetch("/limpar_historico", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: "{}",
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          const tbody = document.getElementById("historico-tabela-body");
          if (tbody) {
            tbody.innerHTML = `
              <tr id="linha-sem-operacao">
                <td colspan="6" style="text-align: center; color: #888; padding: 12px;">Nenhuma operação em andamento</td>
              </tr>
            `;
          }
          const tbodyComp = document.getElementById("historico-completo-body");
          if (tbodyComp) {
            tbodyComp.innerHTML = `
              <tr>
                <td colspan="6" style="text-align: center; color: #888; padding: 14px;">Nenhuma operação finalizada nesta sessão.</td>
              </tr>
            `;
          }
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
            botaoControle.classList.add("ativo");
          } else {
            if (data.session_stopped && data.session_stop_reason) {
              atualizarLog("🛑 " + data.session_stop_reason, "config");
            } else {
              atualizarLog("⏸️ Robô está parado.", "config");
            }
            resetarProgressoBolinhas();
            botaoControle.textContent = "🚀 Iniciar Robô";
            botaoControle.classList.remove("ativo");
          }
        }

        // Atualiza o contador de operações
        if (operacoesDiarias) {
          operacoesDiarias.textContent = data.operacoes || "0";
        }

        // Atualiza o lucro e meta
        if (lucroValor && metaValor) {
          lucroAtual = parseFloat(data.lucro || 0);
          // Usa a meta local (metaDiaria) em vez da meta do servidor
          metaDefinida = metaDiaria;

          lucroValor.textContent = lucroAtual.toFixed(2);
          // Não atualiza a meta no cabeçalho aqui, pois ela é controlada localmente

          // Atualiza a cor do lucro
          if (lucroAtual > 0) {
            lucroValor.className = "positivo";
          } else if (lucroAtual < 0) {
            lucroValor.className = "negativo";
          } else {
            lucroValor.className = "";
          }
        }

        // Atualiza o status de operação
        if (data.status_operacao) {
          const statusOp = data.status_operacao.toLowerCase();
          if (statusOp.includes("analisando")) {
            atualizarProgressoBolinhas("analisando");
          } else if (statusOp.includes("abrindo")) {
            atualizarProgressoBolinhas("abrindo");
          } else if (statusOp.includes("aguardando")) {
            atualizarProgressoBolinhas("aguardando");
          } else if (statusOp.includes("finalizado")) {
            if (statusOp.includes("ganho") || statusOp.includes("win")) {
              atualizarProgressoBolinhas("finalizado-win");
            } else if (
              statusOp.includes("perda") ||
              statusOp.includes("loss")
            ) {
              atualizarProgressoBolinhas("finalizado-loss");
            } else {
              atualizarProgressoBolinhas("finalizado");
            }
          }
        }

        // Atualiza o log com a última mensagem
        if (data.mensagem_log) {
          // Determina o tipo de log com base no conteúdo da mensagem
          let tipoLog = "info";
          if (data.mensagem_log.toLowerCase().includes("erro")) {
            tipoLog = "erro";
          } else if (data.mensagem_log.toLowerCase().includes("aviso")) {
            tipoLog = "aviso";
          } else if (
            data.mensagem_log.toLowerCase().includes("ganho") ||
            data.mensagem_log.toLowerCase().includes("lucro")
          ) {
            tipoLog = "ganho";
          } else if (
            data.mensagem_log.toLowerCase().includes("perda") ||
            data.mensagem_log.toLowerCase().includes("prejuízo")
          ) {
            tipoLog = "perda";
          } else if (data.mensagem_log.toLowerCase().includes("analisando")) {
            tipoLog = "analise";
          } else if (data.mensagem_log.toLowerCase().includes("contrato")) {
            tipoLog = "contrato";
          } else if (data.mensagem_log.toLowerCase().includes("aguardando")) {
            tipoLog = "espera";
          }

          atualizarLog(data.mensagem_log, tipoLog);
        }

        // Atualiza o modo selecionado
        if (data.modo) {
          atualizarExibicaoModo(data.modo, roboAtivo);
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar status do robô:", error);
      });
  }

  function atualizarExibicaoModo(modo, ativo) {
    const modoTextoEl = document.getElementById("modo-texto");
    const modoSelecionadoEl = document.getElementById("modo-selecionado");

    if (modoTextoEl && modoSelecionadoEl) {
      if (ativo) {
        let emoji = "🌱";
        if (modo === "conservador") emoji = "🛡️";
        if (modo === "agressivo") emoji = "🔥";

        modoTextoEl.textContent = `${emoji} ${modo.toUpperCase()}`;
        modoSelecionadoEl.style.display = "block";
      } else {
        modoSelecionadoEl.style.display = "none";
      }
    }
  }

  function atualizarLucroEMeta() {
    fetch("/status_detalhado")
      .then((response) => response.json())
      .then((data) => {
        if (lucroValor && metaValor) {
          lucroAtual = parseFloat(data.lucro || 0);
          // Usa a meta local (metaDiaria) em vez da meta do servidor
          metaDefinida = metaDiaria;

          lucroValor.textContent = lucroAtual.toFixed(2);
          // Não atualiza a meta no cabeçalho aqui, pois ela é controlada localmente

          // Atualiza a cor do lucro
          if (lucroAtual > 0) {
            lucroValor.className = "positivo";
          } else if (lucroAtual < 0) {
            lucroValor.className = "negativo";
          } else {
            lucroValor.className = "";
          }
        }

        // Atualiza o saldo também
        if (data.saldo !== undefined) {
          const saldoElement = document.getElementById("saldo-valor");
          if (saldoElement) {
            saldoElement.textContent = parseFloat(data.saldo || 0).toFixed(2);
          }
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar lucro e meta:", error);
      });
  }

  function atualizarSaldo() {
    fetch("/saldo_atual")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "ok" && data.saldo !== undefined) {
          const saldoElement = document.getElementById("saldo-valor");
          if (saldoElement) {
            saldoElement.textContent = parseFloat(data.saldo || 0).toFixed(2);
          }
        }
      })
      .catch((error) => {
        console.error("Erro ao atualizar saldo:", error);
      });
  }

  function atualizarHistorico() {
    fetch("/historico")
      .then((response) => response.json())
      .then((data) => {
        const hist = Array.isArray(data) ? data : (data && Array.isArray(data.historico) ? data.historico : []);
        // Atualiza apenas o resumo estatístico, sem interferir na tabela de operações ativas (historico-tabela-body)
        if (typeof atualizarResumo === "function") {
          atualizarResumo(hist);
        }
      })
      .catch((error) => {
        console.warn("Erro ao atualizar histórico de resumo:", error);
      });
  }

  function atualizarResumo(historico) {
    if (!historico || !historico.length) return;

    // Calcula estatísticas
    const total = historico.length;
    let lucros = 0;
    let prejuizos = 0;
    let lucroTotal = 0;

    historico.forEach((op) => {
      let resultado = op.resultado_real !== undefined ? op.resultado_real : (op.resultado !== undefined ? op.resultado : (op.lucro || 0));
      resultado = parseFloat(resultado);

      if (resultado > 0) {
        lucros++;
      } else if (resultado < 0) {
        prejuizos++;
      }

      lucroTotal += resultado;
    });

    // Calcula assertividade
    const assertividade = total > 0 ? (lucros / total) * 100 : 0;

    // Atualiza os elementos de resumo defensivamente
    const elTotal = document.getElementById("resumo-total");
    if (elTotal) elTotal.innerText = total;
    const elLucros = document.getElementById("resumo-lucros");
    if (elLucros) elLucros.innerText = lucros;
    const elPrejuizos = document.getElementById("resumo-prejuizos");
    if (elPrejuizos) elPrejuizos.innerText = prejuizos;
    const elAssert = document.getElementById("resumo-assertividade");
    if (elAssert) elAssert.innerText = assertividade.toFixed(1);
    const elLucroTotal = document.getElementById("resumo-lucro-total");
    if (elLucroTotal) elLucroTotal.innerText = "$" + lucroTotal.toFixed(2);
  }

  // Função para trocar entre abas do histórico (Totalmente defensiva contra nós ausentes)
  window.trocarAba = function (aba) {
    const abas = [
      "tabela-historico",
      "resumo-diario",
      "grafico-diario",
      "historico-completo",
      "logs-tempo-real"
    ];
    abas.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "none";
    });

    const botoes = [
      "btn-historico-atual",
      "btn-historico-completo",
      "btn-graficos",
      "btn-logs",
      "btn-limpar"
    ];
    botoes.forEach(id => {
      const btn = document.getElementById(id);
      if (btn) btn.classList.remove("ativo");
    });

    switch (aba) {
      case "tabela": {
        const el = document.getElementById("tabela-historico");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-historico-atual");
        if (btn) btn.classList.add("ativo");
        break;
      }
      case "resumo": {
        const el = document.getElementById("resumo-diario");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-historico-completo");
        if (btn) btn.classList.add("ativo");
        break;
      }
      case "grafico": {
        const el = document.getElementById("grafico-diario");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-graficos");
        if (btn) btn.classList.add("ativo");
        carregarGrafico();
        break;
      }
      case "logs": {
        const el = document.getElementById("logs-tempo-real");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-logs");
        if (btn) btn.classList.add("ativo");
        carregarLogsTempoReal();
        break;
      }
      case "historico-completo": {
        const el = document.getElementById("historico-completo");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-historico-completo");
        if (btn) btn.classList.add("ativo");
        carregarHistoricoCompleto();
        break;
      }
      case "limpar": {
        const el = document.getElementById("tabela-historico");
        if (el) el.style.display = "block";
        const btn = document.getElementById("btn-historico-atual");
        if (btn) btn.classList.add("ativo");
        limparHistorico();
        break;
      }
    }
  };

  function carregarGrafico() {
    const container = document.getElementById("grafico-diario");
    if (!container) return;

    fetch("/historico")
      .then((res) => res.json())
      .then((data) => {
        const operacoes = Array.isArray(data) ? data : (data && Array.isArray(data.historico) ? data.historico : []);
        if (!operacoes || operacoes.length === 0) {
          container.innerHTML = `
            <div style="padding: 30px; text-align: center; color: #888;">
              <span style="font-size: 2rem; display: block; margin-bottom: 8px;">📈</span>
              <p>Nenhuma operação finalizada na sessão para exibir o gráfico de performance.</p>
            </div>
          `;
          return;
        }

        let vitorias = 0;
        let derrotas = 0;
        let lucroAcumulado = 0.0;
        const pontos = [];

        const opsCronologicas = [...operacoes].reverse();
        opsCronologicas.forEach((op, index) => {
          const res = parseFloat(op.resultado_real !== undefined ? op.resultado_real : (op.lucro || 0.0));
          if (res > 0) vitorias++;
          else if (res < 0) derrotas++;
          lucroAcumulado += res;
          pontos.push({
            idx: index + 1,
            lucro: res,
            acumulado: lucroAcumulado,
            ativo: op.ativo || "1HZ75V",
            hora: op.hora_fechamento || op.hora || ""
          });
        });

        const total = vitorias + derrotas;
        const winRate = total > 0 ? ((vitorias / total) * 100).toFixed(1) : "0.0";
        const lucroTotalStr = (lucroAcumulado >= 0 ? "+$" : "-$") + Math.abs(lucroAcumulado).toFixed(2);
        const lucroClass = lucroAcumulado >= 0 ? "positivo" : "negativo";

        const minVal = Math.min(0, ...pontos.map(p => p.acumulado));
        const maxVal = Math.max(1, ...pontos.map(p => p.acumulado));
        const range = (maxVal - minVal) || 1;
        const svgW = 460;
        const svgH = 130;
        const padding = 20;

        const coords = pontos.map((p, i) => {
          const x = padding + (i / Math.max(1, pontos.length - 1)) * (svgW - padding * 2);
          const y = svgH - padding - ((p.acumulado - minVal) / range) * (svgH - padding * 2);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        const pointsAttr = coords.join(" ");

        container.innerHTML = `
          <div style="padding: 12px; text-align: center;">
            <div style="display: flex; justify-content: center; gap: 14px; margin-bottom: 14px; flex-wrap: wrap;">
              <div style="background: rgba(255,255,255,0.05); padding: 6px 14px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">
                <span style="font-size: 0.75rem; color: #888; display: block;">Total Trades</span>
                <strong style="color: #fff; font-size: 1rem;">${total}</strong>
              </div>
              <div style="background: rgba(76, 175, 80, 0.1); padding: 6px 14px; border-radius: 6px; border: 1px solid rgba(76, 175, 80, 0.2);">
                <span style="font-size: 0.75rem; color: #4CAF50; display: block;">Vitórias</span>
                <strong style="color: #4CAF50; font-size: 1rem;">${vitorias} (${winRate}%)</strong>
              </div>
              <div style="background: rgba(244, 67, 54, 0.1); padding: 6px 14px; border-radius: 6px; border: 1px solid rgba(244, 67, 54, 0.2);">
                <span style="font-size: 0.75rem; color: #f44336; display: block;">Derrotas</span>
                <strong style="color: #f44336; font-size: 1rem;">${derrotas}</strong>
              </div>
              <div style="background: rgba(255,255,255,0.05); padding: 6px 14px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">
                <span style="font-size: 0.75rem; color: #888; display: block;">Lucro da Sessão</span>
                <strong class="${lucroClass}" style="font-size: 1rem;">${lucroTotalStr}</strong>
              </div>
            </div>
            <div style="background: rgba(0, 0, 0, 0.35); border-radius: 8px; padding: 12px; border: 1px solid rgba(255,255,255,0.08); margin: 0 auto; max-width: 520px;">
              <span style="font-size: 0.75rem; color: #aaa; margin-bottom: 6px; display: block;">Curva de Patrimônio / Lucro Acumulado ($)</span>
              <svg width="100%" height="130" viewBox="0 0 ${svgW} ${svgH}" style="overflow: visible;">
                <polyline fill="none" stroke="${lucroAcumulado >= 0 ? '#00E676' : '#f44336'}" stroke-width="2.5" points="${pointsAttr}" stroke-linecap="round" stroke-linejoin="round"/>
                ${pontos.map((p, i) => {
                  const [cx, cy] = coords[i].split(",");
                  return `<circle cx="${cx}" cy="${cy}" r="4" fill="${p.lucro >= 0 ? '#00E676' : '#f44336'}" stroke="#fff" stroke-width="1.5"><title>Trade #${p.idx}: ${p.ativo} | $${p.acumulado.toFixed(2)}</title></circle>`;
                }).join("")}
              </svg>
            </div>
          </div>
        `;
      })
      .catch((err) => {
        container.innerHTML = `<p style="color: #ff444f; padding: 15px;">Erro ao carregar gráfico: ${err.message}</p>`;
      });
  }

  function carregarLogsTempoReal() {
    fetch("/logs_tempo_real")
      .then((res) => res.json())
      .then((data) => {
        const listaLogs = document.getElementById("lista-logs");
        if (!listaLogs) return;
        listaLogs.innerHTML = "";

        if (!data || !data.logs || data.logs.length === 0) {
          listaLogs.innerHTML =
            '<p style="color: #888; text-align: center; padding: 12px;">Nenhum log disponível nesta sessão</p>';
          return;
        }

        const logsArray = [...data.logs].reverse();
        logsArray.forEach((log) => {
          const logElement = document.createElement("div");
          const logColor = getLogColor(log.tipo);
          logElement.style.cssText = `
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 4px;
            border-left: 3px solid ${logColor};
            background: rgba(255,255,255,0.04);
            font-family: monospace;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
          `;

          logElement.innerHTML = `
            <span style="color: #78909C; font-size: 11px;">[${log.timestamp || "--"}]</span>
            <span style="color: ${logColor}; flex-grow: 1;">${log.mensagem || ""}</span>
          `;

          listaLogs.appendChild(logElement);
        });

        const container = document.getElementById("container-logs");
        if (container) container.scrollTop = 0;
      })
      .catch((err) => {
        const listaLogs = document.getElementById("lista-logs");
        if (listaLogs) {
          listaLogs.innerHTML = `<p style="color: #ff444f; padding: 10px;">Erro ao carregar logs: ${err.message}</p>`;
        }
      });
  }

  function getLogColor(tipo) {
    const cores = {
      info: "#4a9eff",
      success: "#4caf50",
      warning: "#ff9800",
      error: "#f44336",
      debug: "#9e9e9e",
    };
    return cores[tipo] || "#ffffff";
  }

  function carregarHistoricoCompleto() {
    fetch("/historico")
      .then((res) => res.json())
      .then((data) => {
        const tbody = document.getElementById("historico-completo-body");
        if (!tbody) return;

        const operacoes = Array.isArray(data) ? data : (data && Array.isArray(data.historico) ? data.historico : []);

        if (!operacoes || operacoes.length === 0) {
          tbody.innerHTML = `
            <tr>
              <td colspan="6" style="text-align: center; color: #888; padding: 14px;">Nenhuma operação finalizada nesta sessão.</td>
            </tr>
          `;
          return;
        }

        let html = "";
        operacoes.forEach((op) => {
          const res = parseFloat(op.resultado_real !== undefined ? op.resultado_real : (op.lucro || 0.0));
          const resClass = res > 0 ? "positivo" : (res < 0 ? "negativo" : "");
          const resSign = res >= 0 ? "+" : "";
          const ativo = op.ativo || "1HZ75V";
          const tipo = (op.tipo || "TURBO").toUpperCase();
          const tipoClass = tipo.includes("CALL") ? "badge-call" : (tipo.includes("PUT") ? "badge-put" : "badge-turbo");
          const dataStr = op.data || "--";
          const horaStr = op.hora_fechamento || op.hora_abertura || op.hora || "--";
          const valor = parseFloat(op.valor || 0.35).toFixed(2);
          const motivo = op.motivo_saida ? `title="Motivo da saída: ${op.motivo_saida}"` : "";

          html += `
            <tr ${motivo}>
              <td>${dataStr}</td>
              <td>${horaStr}</td>
              <td><strong>${ativo}</strong></td>
              <td><span class="badge ${tipoClass}">${tipo}</span></td>
              <td>$${valor}</td>
              <td class="resultado ${resClass}"><strong>${resSign}$${res.toFixed(2)}</strong></td>
            </tr>
          `;
        });
        tbody.innerHTML = html;
      })
      .catch((err) => {
        console.error("Erro ao carregar histórico completo:", err);
      });
  }

  // Exporta funções globalmente para acesso nos eventos inline e abas
  window.carregarHistoricoCompleto = carregarHistoricoCompleto;
  window.carregarGrafico = carregarGrafico;
  window.carregarLogsTempoReal = carregarLogsTempoReal;

  // Função descontinuada - bolinhas seguem estritamente o funil de execução da Deriv
  function demonstrarProgresso() {
    // No-op: progresso do ciclo e bolinhas seguem estritamente o motor da Deriv
  }

  // Função para atualizar a meta
  function atualizarMeta(novaMeta) {
    if (novaMeta !== metaDiaria) {
      metaDiaria = novaMeta;
      if (metaValor) {
        metaValor.textContent = "/" + Math.round(metaDiaria);
      }
      if (metaInput) {
        metaInput.value = Math.round(metaDiaria);
      }
    }
  }

  // Adiciona listener para mudanças na meta
  if (metaInput) {
    metaInput.addEventListener("change", function () {
      const novaMeta = parseFloat(this.value);
      if (!isNaN(novaMeta) && novaMeta > 0) {
        atualizarMeta(novaMeta);
      }
    });
  }

  // Inicialização
  function inicializar() {
    // Obtém o modo atual selecionado
    const modoAtual = modoSelect.value;
    const config = modosConfig[modoAtual];

    if (config) {
      // Primeiro tenta carregar meta salva do localStorage
      const metaSalva = localStorage.getItem("meta_diaria");
      let metaParaUsar = config.meta; // Meta padrão do modo

      if (metaSalva && !isNaN(metaSalva)) {
        const metaValorSalvo = parseInt(metaSalva);

        // Verifica se a meta salva é válida para o modo atual
        if (config.maxMeta === null || metaValorSalvo <= config.maxMeta) {
          metaParaUsar = metaValorSalvo;
        } else {
          // Meta salva excede limite do modo, usa meta padrão
          atualizarLog(
            `Meta salva (${metaValorSalvo}) excede limite do modo ${modoAtual.toUpperCase()}, usando meta padrão (${
              config.meta
            })`,
            "aviso"
          );
        }
      }

      // Aplica a meta escolhida
      metaInput.value = metaParaUsar;
      metaDiaria = metaParaUsar;
      metaValor.textContent = "/" + metaParaUsar;

      // Salva no localStorage
      localStorage.setItem("meta_diaria", metaParaUsar);
    }

    // Configura o dropdown de conta
    const dropdownToggle = document.getElementById("dropdown-toggle");
    const dropdownMenu = document.getElementById("dropdown-conta");

    if (dropdownToggle && dropdownMenu) {
      dropdownToggle.addEventListener("click", function () {
        dropdownMenu.classList.toggle("visible");
      });

      // Fecha o dropdown quando clicar fora dele
      document.addEventListener("click", function (event) {
        if (
          !dropdownToggle.contains(event.target) &&
          !dropdownMenu.contains(event.target)
        ) {
          dropdownMenu.classList.remove("visible");
        }
      });
    }

    // Inicia o timer de verificação de conexão com a Deriv
    verificarConexaoDeriv();
    verificacaoDerivTimer = setInterval(verificarConexaoDeriv, 10000);

    // O status do robô, saldo, lucro, steppers e operações ativas são gerenciados
    // de forma unificada e estável por atualizarStatusGeral() no painel.html.
  }

  // Função para atualizar logs da estratégia turbo
  function atualizarLogsTempoReal() {
    fetch("/logs_tempo_real")
      .then((response) => response.json())
      .then((data) => {
        const listaLogs = document.getElementById("lista-logs");
        if (data.logs && data.logs.length > 0) {
          listaLogs.innerHTML = "";
          data.logs.slice(-20).forEach((log) => {
            const logElement = document.createElement("div");
            logElement.style.cssText = `
              margin: 5px 0;
              padding: 8px;
              border-radius: 4px;
              font-size: 12px;
              line-height: 1.4;
              border-left: 3px solid ${getLogColor(log.tipo)};
              background: ${getLogBackground(log.tipo)};
              color: ${getLogTextColor(log.tipo)};
            `;

            const timestamp = new Date(log.timestamp).toLocaleTimeString(
              "pt-BR"
            );
            logElement.innerHTML = `
              <span style="color: #888; font-size: 10px;">[${timestamp}]</span>
              <span style="font-weight: bold;">${log.tipo.toUpperCase()}:</span>
              ${log.mensagem}
            `;
            listaLogs.appendChild(logElement);
          });

          // Auto-scroll para o final
          const containerLogs = document.getElementById("container-logs");
          containerLogs.scrollTop = containerLogs.scrollHeight;
        }
      })
      .catch((error) => {
        console.error("Erro ao buscar logs:", error);
      });
  }

  function getLogColor(tipo) {
    switch (tipo) {
      case "success":
        return "#4CAF50";
      case "error":
        return "#f44336";
      case "warning":
        return "#ff9800";
      case "info":
        return "#2196F3";
      default:
        return "#888";
    }
  }

  function getLogBackground(tipo) {
    switch (tipo) {
      case "success":
        return "rgba(76, 175, 80, 0.1)";
      case "error":
        return "rgba(244, 67, 54, 0.1)";
      case "warning":
        return "rgba(255, 152, 0, 0.1)";
      case "info":
        return "rgba(33, 150, 243, 0.1)";
      default:
        return "rgba(136, 136, 136, 0.1)";
    }
  }

  function getLogTextColor(tipo) {
    switch (tipo) {
      case "success":
        return "#4CAF50";
      case "error":
        return "#f44336";
      case "warning":
        return "#ff9800";
      case "info":
        return "#2196F3";
      default:
        return "#ccc";
    }
  }

  // Inicia tudo
  inicializar();

  // Atualiza logs da estratégia turbo a cada 2 segundos
  setInterval(atualizarLogsTempoReal, 2000);
  atualizarLogsTempoReal(); // Primeira execução imediata
});

function atualizarLogs(log) {
  const listaLogs = document.getElementById("lista-logs");
  const logEntry = document.createElement("div");
  logEntry.className = `log-entry ${log.tipo}`;

  logEntry.innerHTML = `
      <span class="timestamp">${log.timestamp}</span>
      <span class="message">${log.emoji} ${log.mensagem}</span>
  `;

  listaLogs.appendChild(logEntry);
  listaLogs.scrollTop = listaLogs.scrollHeight;

  // Atualiza a barra de progresso se houver etapa
  if (log.etapa) {
    atualizarProgresso(log.etapa);
  }
}

function atualizarProgresso(etapa) {
  const steps = document.querySelectorAll(".progress-step");
  let etapaAtual = 0;

  const etapas = ["analise", "modo", "operacao"];
  const index = etapas.indexOf(etapa);

  steps.forEach((step, i) => {
    step.classList.remove("active");
    if (i <= index) {
      step.classList.add("active");
    }
  });
}
