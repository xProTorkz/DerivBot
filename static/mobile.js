// DerivBot - Funções específicas para Mobile
// Arquivo separado para lidar com funcionalidades exclusivas de dispositivos móveis

// Adicionar estilo direto para o símbolo USD e espaçamento entre lucro e meta
const estiloUSD = document.createElement("style");
estiloUSD.textContent = `
  /* Garantir que o valor-saldo tenha o símbolo USD visível após o valor */
  #saldo-valor::after {
    content: " USD";
    display: inline-block;
    visibility: visible;
    opacity: 0.7;
    font-weight: normal;
    color: #aaaaaa;
    margin-left: 15px;
    font-size: 1rem;
  }
  
  /* Ajustar espaço entre o lucro e a meta */
  #meta-valor {
    margin-left: 3px !important;
    letter-spacing: 1px !important;
  }
  
  /* Aumentar o tamanho dos valores de saldo e lucro */
  #saldo-valor, #lucro-valor {
    font-size: 1.7rem !important;
    font-weight: bold !important;
  }
  
  /* Ajustes responsivos para telas menores */
  @media (max-width: 480px) {
    #saldo-valor, #lucro-valor {
      font-size: 1.5rem !important;
    }
  }
  
  @media (max-width: 320px) {
    #saldo-valor, #lucro-valor {
      font-size: 1.3rem !important;
    }
  }
`;
document.head.appendChild(estiloUSD);

document.addEventListener("DOMContentLoaded", function () {
  let isMobile = false;

  // Detecção de dispositivo móvel
  function detectarDispositivoMovel() {
    const eraMobile = isMobile;
    isMobile =
      window.innerWidth <= 768 || "ontouchstart" in document.documentElement;

    if (isMobile) {
      document.body.classList.add("mobile-device");
      ajustarInterfaceMobile();
      adicionarSuporteGestos();
      corrigirBarraProgresso(); // Aplica correções específicas na barra de progresso
      corrigirCamposValores(); // Correção dos campos de saldo e lucro

      // Nova função: verifica o estado atual da barra e força atualização
      setTimeout(forcarAtualizacaoBarraProgresso, 500);
    } else {
      document.body.classList.remove("mobile-device");
      removerSuporteGestos();
      // Restaura texto original de elementos com data-mobile-text
      if (eraMobile) {
        restaurarTextoOriginal();
      }
    }
  }

  // Restaura o texto original dos elementos com data-mobile-text
  function restaurarTextoOriginal() {
    document.querySelectorAll(".esconde-texto-mobile").forEach((elemento) => {
      if (elemento.hasAttribute("data-original-text")) {
        elemento.textContent = elemento.getAttribute("data-original-text");
        elemento.style.display = ""; // Remove o display:none que possa ter sido aplicado
      } else {
        elemento.style.display = ""; // Apenas remove o display:none
      }
    });
  }

  // Adiciona suporte a gestos de toque para facilitar a interação
  function adicionarSuporteGestos() {
    // Verifica se já existe um listener para evitar duplicações
    if (!window.temListenersGestos) {
      // Suporte para swipe na tabela de histórico (para navegação)
      const historicoEl = document.querySelector(".tabela-wrapper");
      if (historicoEl) {
        let touchStartX = 0;
        let touchEndX = 0;

        historicoEl.addEventListener(
          "touchstart",
          (e) => {
            touchStartX = e.changedTouches[0].screenX;
          },
          { passive: true }
        );

        historicoEl.addEventListener(
          "touchend",
          (e) => {
            touchEndX = e.changedTouches[0].screenX;
            processarGestoSwipe(touchStartX, touchEndX);
          },
          { passive: true }
        );
      }

      // Toque duplo no saldo para atualizar o saldo
      const saldoEl = document.getElementById("saldo-valor");
      if (saldoEl) {
        saldoEl.addEventListener("dblclick", () => {
          if (typeof atualizarSaldoEmTempoReal === "function") {
            atualizarSaldoEmTempoReal(true);
          }
          saldoEl.classList.add("destaque-mobile");
          setTimeout(() => saldoEl.classList.remove("destaque-mobile"), 1500);
        });
      }

      window.temListenersGestos = true;
    }
  }

  // Remove os listeners de gestos quando não estiver em dispositivo móvel
  function removerSuporteGestos() {
    // Apenas marca a flag, pois remover listeners específicos é complexo
    window.temListenersGestos = false;
  }

  // Processa os gestos de swipe horizontal
  function processarGestoSwipe(inicioX, fimX) {
    const swipeThreshold = 50; // Mínimo de pixels para considerar um swipe

    if (inicioX - fimX > swipeThreshold) {
      // Swipe para esquerda - avançar página na tabela
      const botaoAvancar = document.querySelector(
        '.icone-historico[data-acao="avancar"]'
      );
      if (botaoAvancar) {
        botaoAvancar.click();
      }
    } else if (fimX - inicioX > swipeThreshold) {
      // Swipe para direita - retornar página na tabela
      const botaoVoltar = document.querySelector(
        '.icone-historico[data-acao="voltar"]'
      );
      if (botaoVoltar) {
        botaoVoltar.click();
      }
    }
  }

  // Ajustes específicos para interface mobile
  function ajustarInterfaceMobile() {
    const saldoValor = document.getElementById("saldo-valor");
    const lucroValor = document.getElementById("lucro-valor");

    if (isMobile) {
      // Processa elementos com a classe esconde-texto-mobile
      document.querySelectorAll(".esconde-texto-mobile").forEach((elemento) => {
        // Verifica se tem atributo data-mobile-text
        if (elemento.hasAttribute("data-mobile-text")) {
          // Salva o texto original como atributo se ainda não existir
          if (!elemento.hasAttribute("data-original-text")) {
            elemento.setAttribute("data-original-text", elemento.textContent);
          }
          // Substitui pelo texto mobile
          elemento.textContent = elemento.getAttribute("data-mobile-text");
        } else {
          // Apenas esconde o elemento sem texto alternativo
          elemento.style.display = "none";
        }
      });

      // Reduz informações na tabela de histórico para visualização mobile
      const tabela = document.getElementById("historico-tabela");
      if (tabela) {
        const cabecalhos = tabela.querySelectorAll("th");
        const linhas = tabela.querySelectorAll("tr:not(:first-child)");

        // Ajusta células importantes para melhor visualização
        if (cabecalhos.length > 0) {
          if (window.innerWidth <= 480) {
            // Em telas muito pequenas, oculta colunas menos importantes
            Array.from(cabecalhos).forEach((th, index) => {
              if (index !== 0 && index !== 2 && index !== 3) {
                th.classList.add("hide-on-mobile");

                // Oculta as colunas correspondentes em todas as linhas
                linhas.forEach((linha) => {
                  const celulas = linha.querySelectorAll("td");
                  if (celulas[index]) {
                    celulas[index].classList.add("hide-on-mobile");
                  }
                });
              }
            });
          }
        }
      }

      // Ajusta o comportamento do botão de iniciar/parar para dispositivos móveis
      const botaoControle = document.getElementById("bot-control-btn");
      if (botaoControle) {
        // Adiciona feedback tátil para dispositivos que suportam
        botaoControle.addEventListener("click", () => {
          if ("vibrate" in navigator) {
            navigator.vibrate(50);
          }
        });
      }
    }
  }

  // Função para corrigir a apresentação dos valores de saldo e lucro em dispositivos móveis
  function corrigirCamposValores() {
    const saldoValor = document.getElementById("saldo-valor");
    const lucroValor = document.getElementById("lucro-valor");
    const metaValor = document.getElementById("meta-valor");
    const infoBar = document.querySelector(".info-bar");

    if (!saldoValor || !lucroValor) return;

    // Garantir que a info-bar esteja em layout horizontal
    if (infoBar) {
      infoBar.style.flexDirection = "row";
      infoBar.style.justifyContent = "space-between";

      // Corrigir alinhamento dos elementos filhos
      const saldoContainer = infoBar.querySelector(".saldo");
      const lucroContainer = infoBar.querySelector(".lucro");

      if (saldoContainer) {
        saldoContainer.style.alignItems = "flex-start";
        saldoContainer.style.textAlign = "left";
        saldoContainer.style.width = "auto";

        // Garantir que o valor do saldo seja visível
        const valorSaldo = saldoContainer.querySelector("#valor-saldo");
        if (valorSaldo) {
          valorSaldo.style.display = "flex";
          valorSaldo.style.alignItems = "center";
          valorSaldo.style.flexWrap = "nowrap";
          valorSaldo.style.overflow = "visible";
        }
      }

      if (lucroContainer) {
        lucroContainer.style.alignItems = "flex-end";
        lucroContainer.style.textAlign = "right";
        lucroContainer.style.width = "auto";

        // Garantir que o valor do lucro seja visível
        const lucroMeta = lucroContainer.querySelector("#lucro-meta");
        if (lucroMeta) {
          lucroMeta.style.display = "flex";
          lucroMeta.style.alignItems = "center";
          lucroMeta.style.justifyContent = "flex-end";
          lucroMeta.style.flexWrap = "nowrap";
          lucroMeta.style.overflow = "visible";
        }
      }
    }

    // Corrigir estilo direto dos elementos de valor
    if (saldoValor) {
      saldoValor.style.maxWidth = "100%";
      saldoValor.style.overflow = "visible";
      saldoValor.style.textOverflow = "initial";
      saldoValor.style.whiteSpace = "nowrap";
    }

    if (lucroValor) {
      lucroValor.style.maxWidth = "100%";
      lucroValor.style.overflow = "visible";
      lucroValor.style.textOverflow = "initial";
      lucroValor.style.whiteSpace = "nowrap";
    }

    // Função para formatação de valores numéricos
    function formatarValor(valor) {
      if (!valor || isNaN(parseFloat(valor))) return valor;

      // Sempre mostrar 2 casas decimais para valores numéricos
      let numeroFormatado = parseFloat(valor).toFixed(2);

      // Se o valor for muito grande, simplificar a apresentação
      if (numeroFormatado > 9999) {
        return Math.floor(numeroFormatado / 1000) + "k";
      }

      return numeroFormatado;
    }

    // Configurar o MutationObserver para monitorar alterações nos valores
    const observarValor = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        if (
          mutation.type === "childList" ||
          mutation.type === "characterData"
        ) {
          const elemento = mutation.target;

          // Se o elemento for o saldo ou lucro, aplicar formatação
          if (elemento === saldoValor || elemento.parentNode === saldoValor) {
            const valorAtual = saldoValor.textContent.trim();
            if (!isNaN(parseFloat(valorAtual))) {
              if (valorAtual.length > 8) {
                saldoValor.classList.add("valor-longo");
              } else {
                saldoValor.classList.remove("valor-longo");
              }
            }
          }

          // Se o elemento for o lucro, verificar se é positivo ou negativo
          if (elemento === lucroValor || elemento.parentNode === lucroValor) {
            const valorAtual = lucroValor.textContent.trim();
            if (!isNaN(parseFloat(valorAtual))) {
              const valor = parseFloat(valorAtual);
              if (valor > 0) {
                lucroValor.classList.add("positivo");
                lucroValor.classList.remove("negativo", "neutro");
              } else if (valor < 0) {
                lucroValor.classList.add("negativo");
                lucroValor.classList.remove("positivo", "neutro");
              } else {
                lucroValor.classList.add("neutro");
                lucroValor.classList.remove("positivo", "negativo");
              }

              if (valorAtual.length > 8) {
                lucroValor.classList.add("valor-longo");
              } else {
                lucroValor.classList.remove("valor-longo");
              }
            }
          }

          // Se o elemento for a meta, garantir formato correto
          if (elemento === metaValor || elemento.parentNode === metaValor) {
            const valorAtual = metaValor.textContent.trim();
            if (valorAtual && !valorAtual.startsWith("/")) {
              metaValor.textContent = "/" + valorAtual.replace("/", "");
            }
          }
        }
      });
    });

    // Observar mudanças nos elementos
    observarValor.observe(saldoValor, {
      childList: true,
      characterData: true,
      subtree: true,
    });

    observarValor.observe(lucroValor, {
      childList: true,
      characterData: true,
      subtree: true,
    });

    if (metaValor) {
      observarValor.observe(metaValor, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }

    // Aplicar imediatamente para valores iniciais
    setTimeout(() => {
      saldoValor.textContent = formatarValor(saldoValor.textContent);
      lucroValor.textContent = formatarValor(lucroValor.textContent);

      if (metaValor && !metaValor.textContent.startsWith("/")) {
        metaValor.textContent = "/" + metaValor.textContent.replace("/", "");
      }
    }, 100);
  }

  // Inicialização - detecta se é dispositivo móvel
  detectarDispositivoMovel();

  // Adiciona listener para redimensionamento
  window.addEventListener("resize", function () {
    detectarDispositivoMovel();
    if (isMobile) {
      // Ajustar as barras quando redimensionar
      ajustarBarrasEmResize();
      corrigirCamposValores(); // Reaplica a correção após redimensionar
    }
  });

  // Adicionar a nova função ao objeto window.mobileUtils
  window.mobileUtils = {
    detectarDispositivoMovel,
    ajustarInterfaceMobile,
    restaurarTextoOriginal,
    calcularWidthProgressoBarra,
    adaptarMensagensDemo,
    corrigirBarraProgresso,
    forcarAtualizacaoBarraProgresso,
    atualizarBarraProgressoMobile,
    ajustarBarrasEmResize,
    corrigirCamposValores,
  };

  // Inicialização adicional após carregamento completo da página
  window.addEventListener("load", function () {
    if (isMobile) {
      // Garante que as barras estejam criadas e visíveis
      corrigirBarraProgresso();
      corrigirCamposValores(); // Aplica a correção nos valores iniciais

      // Aplica atualização inicial
      setTimeout(forcarAtualizacaoBarraProgresso, 200);

      // Atualização secundária com atraso maior para garantir
      setTimeout(forcarAtualizacaoBarraProgresso, 1000);

      // Atualização dos campos de valores após a renderização completa
      setTimeout(corrigirCamposValores, 500);
    }
  });

  // Função para calcular a largura da barra de progresso com base no tamanho da tela
  function calcularWidthProgressoBarra(progresso) {
    // Calcula o valor correto com base no tamanho da tela
    if (window.innerWidth <= 320) {
      // Telas muito pequenas
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 18px)"
        : `calc(${progresso}% * (100% - 18px) / 100)`;
    } else if (window.innerWidth <= 480) {
      // Telas pequenas (mobile)
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 30px)"
        : `calc(${progresso}% * (100% - 30px) / 100)`;
    } else {
      // Telas médias e grandes - valor padrão
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 32px)"
        : `calc(${progresso}% * (100% - 32px) / 100)`;
    }
  }

  // Função para adaptar mensagens de demonstração para dispositivos móveis
  function adaptarMensagensDemo(etapasDemo) {
    // Só modifica se estivermos em um dispositivo móvel
    if (!isMobile) return etapasDemo;

    // Cria uma cópia para não modificar o original
    const etapasAdaptadas = JSON.parse(JSON.stringify(etapasDemo));

    // Obtém o valor da entrada da etapa original
    const msgOriginal = etapasAdaptadas[2].mensagem;
    // Extrai o valor usando expressão regular (procura por $X.XX)
    const valorMatch = msgOriginal.match(/\$(\d+\.\d+)/);
    const valorEntrada = valorMatch ? valorMatch[1] : "0.35";

    // Reduz o tamanho das mensagens para dispositivos móveis
    if (window.innerWidth <= 320) {
      // Versões curtas para telas muito pequenas
      etapasAdaptadas[0].mensagem = "Analisando mercado...";
      etapasAdaptadas[1].mensagem = "Sinal detectado em R_10";
      etapasAdaptadas[2].mensagem = `MULTUP $${valorEntrada} (1s)`;
      etapasAdaptadas[3].mensagem = "Aguardando resultado...";
      etapasAdaptadas[4].mensagem = `✅ GANHO! +$${(
        parseFloat(valorEntrada) * 0.9
      ).toFixed(2)}`;
      etapasAdaptadas[5].mensagem = "Próxima análise...";
    } else if (window.innerWidth <= 480) {
      // Versões médias para telas pequenas
      etapasAdaptadas[0].mensagem = "Analisando mercado...";
      etapasAdaptadas[1].mensagem = "Sinal identificado! Alta em R_10";
      etapasAdaptadas[2].mensagem = `MULTUP $${valorEntrada} (micro 1s)`;
      etapasAdaptadas[3].mensagem = "Aguardando fechamento...";
      etapasAdaptadas[4].mensagem = `✅ GANHO! +$${(
        parseFloat(valorEntrada) * 0.9
      ).toFixed(2)}`;
      etapasAdaptadas[5].mensagem = "Analisando nova oportunidade...";
    }

    return etapasAdaptadas;
  }

  // Função para corrigir a barra de progresso em dispositivos móveis
  function corrigirBarraProgresso() {
    if (!isMobile) return;

    // Busca o contêiner de status
    const statusEtapas = document.querySelector(".status-etapas");
    if (!statusEtapas) return;

    // Cria barras DOM reais em vez de depender de pseudo-elementos
    const barraBackgroundId = "barra-background-mobile";
    const barraProgressoId = "barra-progresso-mobile";

    // Verifica se já existem as barras
    if (!document.getElementById(barraBackgroundId)) {
      // Primeiro adiciona a barra de fundo (cinza)
      const barraBackground = document.createElement("div");
      barraBackground.id = barraBackgroundId;
      barraBackground.style.cssText = `
        position: absolute;
        top: 6px;
        left: 18px;
        right: 18px;
        height: 3px;
        background-color: var(--transparente-claro);
        z-index: 1;
      `;

      // Adiciona ao DOM
      statusEtapas.appendChild(barraBackground);

      // Agora adiciona a barra de progresso (amarela)
      const barraProgresso = document.createElement("div");
      barraProgresso.id = barraProgressoId;
      barraProgresso.style.cssText = `
        position: absolute;
        top: 6px;
        left: 18px;
        height: 3px;
        width: 0;
        background-color: var(--amarelo-escuro);
        box-shadow: 0 0 5px var(--amarelo-claro);
        z-index: 2;
        transition: width 0.3s ease-in-out;
      `;

      // Adiciona ao DOM
      statusEtapas.appendChild(barraProgresso);

      // Ajusta para telas muito pequenas
      if (window.innerWidth <= 320) {
        barraBackground.style.top = "4px";
        barraBackground.style.left = "10px";
        barraBackground.style.right = "10px";
        barraBackground.style.height = "2px";

        barraProgresso.style.top = "4px";
        barraProgresso.style.left = "10px";
        barraProgresso.style.height = "2px";
      }
    }

    // Esconde os pseudo-elementos que causam problemas
    const style = document.createElement("style");
    style.id = "disable-pseudo-bars";
    style.textContent = `
      .status-etapas::before, .status-etapas::after {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        content: none !important;
      }
    `;
    document.head.appendChild(style);

    // Função para atualizar o progresso da barra
    window.atualizarBarraProgressoMobile = function (etapa) {
      if (!isMobile) return;

      // Converte etapa em valor de progresso
      let progresso = 0;
      switch (etapa) {
        case "analisando":
          progresso = 0;
          break;
        case "medio":
          progresso = 33;
          break;
        case "abrindo":
          progresso = 50;
          break;
        case "aguardando":
          progresso = 75;
          break;
        case "finalizado":
        case "finalizado-win":
        case "finalizado-loss":
          progresso = 100;
          break;
        default:
          progresso = 0;
      }

      // Atualiza a largura da barra de progresso real
      const barraProgresso = document.getElementById(barraProgressoId);
      if (barraProgresso) {
        // Calcula a largura baseada na tela
        const larguraTotal =
          statusEtapas.clientWidth - (window.innerWidth <= 320 ? 20 : 36);
        const larguraBarra =
          progresso === 0 ? 0 : (progresso / 100) * larguraTotal;

        // Aplica a largura diretamente
        barraProgresso.style.width = larguraBarra + "px";
      }
    };
  }

  // Nova função dedicada para forçar a atualização em etapas críticas
  function forcarAtualizacaoBarraProgresso() {
    // Obtém o estado das bolinhas
    const bolinhaAnalisando = document.getElementById("bolinha-analisando");
    const bolinhaAbrindo = document.getElementById("bolinha-abrindo");
    const bolinhaFinalizado = document.getElementById("bolinha-finalizado");

    // Determina a etapa atual baseada nas bolinhas ativas
    let etapaAtual = "parado";

    if (bolinhaFinalizado && bolinhaFinalizado.classList.contains("ativa")) {
      etapaAtual = "finalizado";
    } else if (bolinhaAbrindo && bolinhaAbrindo.classList.contains("ativa")) {
      etapaAtual = bolinhaAbrindo.classList.contains("pisca")
        ? "abrindo"
        : "aguardando";
    } else if (
      bolinhaAnalisando &&
      bolinhaAnalisando.classList.contains("ativa")
    ) {
      etapaAtual = bolinhaAnalisando.classList.contains("pisca")
        ? "analisando"
        : "medio";
    }

    // Aplica a atualização se a função existir
    if (typeof window.atualizarBarraProgressoMobile === "function") {
      window.atualizarBarraProgressoMobile(etapaAtual);

      // Segunda atualização após um pequeno atraso para garantir
      setTimeout(() => {
        window.atualizarBarraProgressoMobile(etapaAtual);
      }, 100);
    }
  }

  // Função auxiliar para ajustar dinamicamente as barras ao redimensionar
  function ajustarBarrasEmResize() {
    // Primeiro restaura os valores padrão
    const barraFundo = document.getElementById("barra-background-mobile");
    const barraProgresso = document.getElementById("barra-progresso-mobile");

    if (!barraFundo || !barraProgresso) return;

    if (window.innerWidth <= 320) {
      barraFundo.style.top = "4px";
      barraFundo.style.left = "10px";
      barraFundo.style.right = "10px";
      barraFundo.style.height = "2px";

      barraProgresso.style.top = "4px";
      barraProgresso.style.left = "10px";
      barraProgresso.style.height = "2px";
    } else {
      barraFundo.style.top = "6px";
      barraFundo.style.left = "18px";
      barraFundo.style.right = "18px";
      barraFundo.style.height = "3px";

      barraProgresso.style.top = "6px";
      barraProgresso.style.left = "18px";
      barraProgresso.style.height = "3px";
    }

    // Força uma atualização da largura da barra de progresso
    forcarAtualizacaoBarraProgresso();
  }
});
