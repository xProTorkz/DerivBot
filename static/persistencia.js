// persistencia.js - Funcionalidade de persistência de estado para o DerivBot
document.addEventListener("DOMContentLoaded", function () {
  // Referências aos elementos do DOM
  const botaoControle = document.getElementById("bot-control-btn");
  const modoSelect = document.getElementById("modo");
  const metaInput = document.getElementById("meta");
  const saldoValor = document.getElementById("saldo-valor");
  const lucroValor = document.getElementById("lucro-valor");
  const metaValor = document.getElementById("meta-valor");
  const operacoesDiarias = document.getElementById("operacoes-diarias");
  const historicoTabela = document.getElementById("historico-tabela-body");
  const logTemp = document.getElementById("log-temporario");

  // Variável para controlar se precisamos restaurar o estado
  let precisaRestaurarEstado = false;

  // Função para emitir logs com formatação apropriada
  function atualizarLogPersistencia(mensagem, tipo = "info") {
    if (!logTemp) return;

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
    logTemp.className = "log-temp";

    // Adiciona classe correspondente ao tipo
    logTemp.classList.add(tipo);

    // Atualiza o conteúdo com emoji e mensagem
    logTemp.innerHTML = `
            <span class="log-emoji">${emoji}</span>
            <span class="log-texto">${mensagem}</span>
        `;
  }

  // Função para salvar o estado atual do robô no localStorage
  function salvarEstadoRobo() {
    // Verifica se o robô está ativo (se o botão tem a classe "ativo")
    if (!botaoControle || !botaoControle.classList.contains("ativo")) return;

    const modoOperacao = modoSelect ? modoSelect.value : "iniciante";
    const metaDiaria = metaInput ? parseFloat(metaInput.value) : 50.0;
    const saldoAtual = saldoValor ? parseFloat(saldoValor.textContent) : 0;
    const lucroAtual = lucroValor ? parseFloat(lucroValor.textContent) : 0;
    const contadorOperacoes = operacoesDiarias
      ? parseInt(operacoesDiarias.textContent)
      : 0;

    const estadoRobo = {
      roboAtivo: true,
      metaDiaria,
      modoOperacao,
      saldoAtual,
      lucroAtual,
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

  // Função para restaurar o histórico de operações
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

      // Restaurar os valores na interface, se possível
      if (metaInput) metaInput.value = estado.metaDiaria.toString();
      if (modoSelect) modoSelect.value = estado.modoOperacao;
      if (saldoValor) saldoValor.textContent = estado.saldoAtual.toFixed(2);
      if (lucroValor) lucroValor.textContent = estado.lucroAtual.toFixed(2);
      if (metaValor) metaValor.textContent = "/" + estado.metaDiaria.toFixed(2);
      if (operacoesDiarias)
        operacoesDiarias.textContent = estado.contadorOperacoes.toString();

      // Restaurar o histórico de operações se disponível
      if (estado.historicoOperacoes && estado.historicoOperacoes.length > 0) {
        restaurarHistoricoOperacoes(estado.historicoOperacoes);
      }

      // Se o robô estava ativo, precisamos reiniciá-lo
      if (estado.roboAtivo) {
        precisaRestaurarEstado = true;
        console.log("Robô estava ativo, marcando para reiniciar");
        atualizarLogPersistencia(
          "📋 Recuperando sessão anterior do robô...",
          "info"
        );
      }

      console.log("Estado do robô restaurado com sucesso");
      return true;
    } catch (erro) {
      console.error("Erro ao restaurar estado:", erro);
      localStorage.removeItem("derivbot_estado");
      return false;
    }
  }

  // Função para iniciar o robô automaticamente após restauração de estado
  function iniciarRoboAutomaticamente() {
    if (!precisaRestaurarEstado) return;

    console.log("Iniciando robô automaticamente após restauração de estado");

    // Obtém os valores recuperados
    const modoOperacao = modoSelect ? modoSelect.value : "iniciante";
    const metaDiaria = metaInput ? parseFloat(metaInput.value) : 50.0;

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
          // Atualiza a interface para refletir o estado ativo
          if (botaoControle) {
            botaoControle.textContent = "Parar Robô";
            botaoControle.classList.add("ativo");
          }

          atualizarLogPersistencia(
            "✅ Robô restaurado com sucesso!",
            "sucesso"
          );

          // Atualiza exibição do modo
          const modoSelecionadoBox =
            document.getElementById("modo-selecionado");
          const modoTextoSpan = document.getElementById("modo-texto");

          if (modoSelecionadoBox) modoSelecionadoBox.style.display = "block";
          if (modoTextoSpan)
            modoTextoSpan.textContent = modoOperacao.toUpperCase();

          // Reset da flag
          precisaRestaurarEstado = false;
        } else {
          atualizarLogPersistencia(
            "⚠️ Erro ao restaurar robô: " +
              (data.mensagem || "Falha na conexão"),
            "erro"
          );
          precisaRestaurarEstado = false;
        }
      })
      .catch((error) => {
        atualizarLogPersistencia(
          "⚠️ Erro de conexão ao restaurar robô",
          "erro"
        );
        console.error("Erro:", error);
        precisaRestaurarEstado = false;
      });
  }

  // Observar modificações no botão de controle para salvar estado quando ativado
  function observarBotaoControle() {
    // Verificar se o MutationObserver existe e se temos acesso ao botão
    if (!("MutationObserver" in window) || !botaoControle) return;

    // Criar um observador para detectar mudanças nas classes do botão
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === "class") {
          // Se o botão agora estiver ativo, salvar estado
          if (botaoControle.classList.contains("ativo")) {
            // Esperamos um pouco para garantir que todos os dados estejam atualizados
            setTimeout(salvarEstadoRobo, 500);
          } else {
            // Se o botão não estiver mais ativo, remover o estado salvo
            localStorage.removeItem("derivbot_estado");
          }
        }
      });
    });

    // Configurar o observador para monitorar mudanças no atributo 'class'
    observer.observe(botaoControle, { attributes: true });
  }

  // Inicialização do sistema de persistência
  function inicializarPersistencia() {
    // Tentar restaurar o estado salvo
    const estadoRestaurado = restaurarEstadoRobo();

    // Configurar evento para salvar estado quando a página for fechada/atualizada
    window.addEventListener("beforeunload", salvarEstadoRobo);

    // Verificar a cada 30 segundos para salvar o estado (backup)
    setInterval(salvarEstadoRobo, 30000);

    // Iniciar observação do botão de controle
    observarBotaoControle();

    // Se o robô estava ativo, reiniciá-lo após alguns segundos
    if (precisaRestaurarEstado) {
      setTimeout(() => {
        iniciarRoboAutomaticamente();
      }, 3000);
    }
  }

  // Inicializar a persistência quando o documento estiver pronto
  inicializarPersistencia();
});
