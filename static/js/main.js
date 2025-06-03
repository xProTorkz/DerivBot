// Configurações globais
const CONFIG = {
  API_URL: "/api",
  CHART_UPDATE_INTERVAL: 5000,
  NOTIFICATION_DURATION: 3000,
};

// Gerenciador de Estado
const StateManager = {
  state: {
    isRunning: false,
    currentMode: "beginner",
    balance: 0,
    lastOperation: null,
    chartData: [],
  },

  updateState(newState) {
    this.state = { ...this.state, ...newState };
    this.notifyListeners();
  },

  listeners: [],

  subscribe(listener) {
    this.listeners.push(listener);
  },

  notifyListeners() {
    this.listeners.forEach((listener) => listener(this.state));
  },
};

// Gerenciador de API
const API = {
  async request(endpoint, method = "GET", data = null) {
    try {
      const options = {
        method,
        headers: {
          "Content-Type": "application/json",
        },
      };

      if (data) {
        options.body = JSON.stringify(data);
      }

      const response = await fetch(`${CONFIG.API_URL}${endpoint}`, options);
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.message || "Erro na requisição");
      }

      return result;
    } catch (error) {
      console.error("Erro na API:", error);
      throw error;
    }
  },

  async startBot() {
    return this.request("/bot/start", "POST");
  },

  async stopBot() {
    return this.request("/bot/stop", "POST");
  },

  async getStatus() {
    return this.request("/bot/status");
  },

  async getOperations() {
    return this.request("/bot/operations");
  },

  async getAnalysis() {
    return this.request("/bot/analysis");
  },
};

// Gerenciador de Gráficos
const ChartManager = {
  chart: null,

  init(containerId) {
    const ctx = document.getElementById(containerId).getContext("2d");
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Preço",
            data: [],
            borderColor: "#3498db",
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: false,
          },
        },
      },
    });
  },

  updateData(data) {
    if (!this.chart) return;

    this.chart.data.labels = data.map((d) => d.timestamp);
    this.chart.data.datasets[0].data = data.map((d) => d.price);
    this.chart.update();
  },
};

// Gerenciador de Notificações
const NotificationManager = {
  show(message, type = "success") {
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    notification.style.display = "block";
    setTimeout(() => {
      notification.style.display = "none";
      notification.remove();
    }, CONFIG.NOTIFICATION_DURATION);
  },
};

// Gerenciador de Interface
const UIManager = {
  init() {
    this.bindEvents();
    this.startStatusUpdates();
  },

  bindEvents() {
    document
      .getElementById("startBot")
      ?.addEventListener("click", this.handleStartBot);
    document
      .getElementById("stopBot")
      ?.addEventListener("click", this.handleStopBot);
    document
      .getElementById("modeSelect")
      ?.addEventListener("change", this.handleModeChange);
  },

  async handleStartBot() {
    try {
      await API.startBot();
      StateManager.updateState({ isRunning: true });
      NotificationManager.show("Bot iniciado com sucesso");
    } catch (error) {
      NotificationManager.show(error.message, "error");
    }
  },

  async handleStopBot() {
    try {
      await API.stopBot();
      StateManager.updateState({ isRunning: false });
      NotificationManager.show("Bot parado com sucesso");
    } catch (error) {
      NotificationManager.show(error.message, "error");
    }
  },

  handleModeChange(event) {
    StateManager.updateState({ currentMode: event.target.value });
  },

  updateStatusDisplay(status) {
    document.getElementById("botStatus").textContent = status.isRunning
      ? "Em execução"
      : "Parado";
    document.getElementById(
      "currentBalance"
    ).textContent = `R$ ${status.balance.toFixed(2)}`;
    document.getElementById("lastOperation").textContent =
      status.lastOperation || "Nenhuma";
  },

  startStatusUpdates() {
    setInterval(async () => {
      try {
        const status = await API.getStatus();
        StateManager.updateState(status);
      } catch (error) {
        console.error("Erro ao atualizar status:", error);
      }
    }, CONFIG.CHART_UPDATE_INTERVAL);
  },
};

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
  UIManager.init();
  ChartManager.init("priceChart");

  StateManager.subscribe((state) => {
    UIManager.updateStatusDisplay(state);
    if (state.chartData.length > 0) {
      ChartManager.updateData(state.chartData);
    }
  });
});
