// DerivBot - Funções específicas para Mobile
// Arquivo separado para lidar com funcionalidades exclusivas de dispositivos móveis

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

  // Função para corrigir a barra de progresso em dispositivos móveis
  function corrigirBarraProgresso() {
    const statusEtapas = document.querySelector(".status-etapas");
    if (!statusEtapas) return;

    // Adiciona estilo específico para dispositivos móveis conectando exatamente nos centros das bolinhas
    const styleEl = document.createElement("style");
    styleEl.id = "mobile-progress-bar-fix";
    styleEl.textContent = `
      @media (max-width: 768px) {
        .status-etapas > div {
          width: 60px !important;
        }
        .status-etapas::before,
        .status-etapas::after {
          left: 30px !important;
          right: 30px !important;
          top: 7px !important;
        }
        .status-etapas::after {
          right: auto !important;
          max-width: calc(100% - 60px) !important;
        }
      }
      @media (max-width: 480px) {
        .status-etapas > div {
          width: 50px !important;
        }
        .status-etapas::before,
        .status-etapas::after {
          left: 25px !important;
          right: 25px !important;
          top: 6px !important;
        }
        .status-etapas::after {
          right: auto !important;
          max-width: calc(100% - 50px) !important;
        }
      }
    `;
    document.head.appendChild(styleEl);
  }

  // Função para forçar atualização da barra de progresso
  function forcarAtualizacaoBarraProgresso() {
    // Verifica se há alguma bolinha ativa
    const bolinhasAtivas = document.querySelectorAll(".bolinha.ativa");
    if (bolinhasAtivas.length === 0) return; // Não há progresso para atualizar

    // Determina o progresso atual com base nas bolinhas ativas
    let progresso = 0;
    if (document.getElementById("bolinha-finalizado").classList.contains("ativa")) {
      progresso = 100;
    } else if (document.getElementById("bolinha-abrindo").classList.contains("ativa")) {
      progresso = 50;
    } else if (document.getElementById("bolinha-analisando").classList.contains("ativa")) {
      progresso = 25;
    }

    // Atualiza a barra de progresso
    atualizarBarraProgressoMobile(progresso);
  }

  // Função para atualizar a barra de progresso em dispositivos móveis
  function atualizarBarraProgressoMobile(progresso) {
    const statusEtapas = document.querySelector(".status-etapas");
    if (!statusEtapas) return;

    // Calcula o valor para dispositivos móveis
    let widthValue = calcularWidthProgressoBarra(progresso);

    // Atualiza o CSS diretamente
    const styleElement = document.getElementById("barra-progresso-style");
    if (!styleElement) {
      // Criar elemento de estilo se não existir
      const style = document.createElement("style");
      style.id = "barra-progresso-style";
      document.head.appendChild(style);
    }

    // Atualizar o CSS diretamente
    const styleSheet = document.getElementById("barra-progresso-style").sheet;
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

  // Função para ajustar as barras quando a janela é redimensionada
  function ajustarBarrasEmResize() {
    // Força atualização da barra de progresso
    forcarAtualizacaoBarraProgresso();
  }

  // Função para calcular a largura da barra de progresso com base no tamanho da tela
  function calcularWidthProgressoBarra(progresso) {
    if (window.innerWidth <= 480) {
      // Mobile pequeno (etapa = 50px, margem = 25px em cada ponta)
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 50px)"
        : `calc(${progresso}% * (100% - 50px) / 100)`;
    } else if (window.innerWidth <= 768) {
      // Tablet / Mobile largo (etapa = 60px, margem = 30px em cada ponta)
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 60px)"
        : `calc(${progresso}% * (100% - 60px) / 100)`;
    } else {
      // Desktop padrão (etapa = 70px, margem = 35px em cada ponta)
      return progresso === 0
        ? "0"
        : progresso === 100
        ? "calc(100% - 70px)"
        : `calc(${progresso}% * (100% - 70px) / 100)`;
    }
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
});
