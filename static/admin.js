// Funções do Painel Admin

// Variáveis globais
let currentLicenseCode = "";

// Função para mostrar abas
function showTab(tabName) {
  console.log("showTab chamado para:", tabName);

  // Esconder todas as abas
  const tabs = document.querySelectorAll(".tab-content");
  console.log("Abas encontradas:", tabs.length);
  tabs.forEach((tab) => {
    tab.classList.remove("active");
  });

  // Remover classe active de todos os botões
  const buttons = document.querySelectorAll(".tab-button");
  console.log("Botões encontrados:", buttons.length);
  buttons.forEach((btn) => {
    btn.classList.remove("active");
  });

  // Mostrar aba selecionada
  const selectedTab = document.getElementById(tabName);
  console.log("Aba selecionada:", selectedTab);
  if (selectedTab) {
    selectedTab.classList.add("active");
  }

  // Adicionar classe active ao botão clicado
  const selectedButton = document.querySelector(
    `button[onclick="showTab('${tabName}')"]`
  );
  console.log("Botão selecionado:", selectedButton);
  if (selectedButton) {
    selectedButton.classList.add("active");
  }

  // Carregar dados específicos da aba
  if (tabName === "dashboard") {
    loadDashboard();
  } else if (tabName === "manage") {
    loadLicenses();
  } else if (tabName === "email") {
    loadEmailConfig();
  } else if (tabName === "api") {
    loadApiKey();
  }
}

// Função para mostrar alertas
function showAlert(message, type = "info") {
  console.log("showAlert chamado:", message, type);
  const alertsContainer = document.getElementById("alerts");
  if (!alertsContainer) {
    console.error("Container de alertas não encontrado");
    // Criar container se não existir
    const container = document.createElement("div");
    container.id = "alerts";
    container.style.cssText =
      "position: fixed; top: 20px; right: 20px; z-index: 10000;";
    document.body.appendChild(container);
    return showAlert(message, type); // Tentar novamente
  }

  const alert = document.createElement("div");
  alert.className = `alert alert-${type}`;
  alert.innerHTML = message;

  alertsContainer.appendChild(alert);

  // Remover alerta após 5 segundos
  setTimeout(() => {
    if (alert.parentNode) {
      alert.remove();
    }
  }, 5000);
}

// Carregar dashboard
function loadDashboard() {
  console.log("Iniciando loadDashboard...");
  fetch("/api/admin/stats")
    .then((response) => {
      console.log("Resposta recebida:", response);
      return response.json();
    })
    .then((data) => {
      console.log("Dados recebidos:", data);
      if (data.success) {
        document.getElementById("total-licenses").textContent =
          data.stats.total;
        document.getElementById("active-licenses").textContent =
          data.stats.ativas;
        document.getElementById("expired-licenses").textContent =
          data.stats.expiradas;
        document.getElementById("today-generated").textContent =
          data.stats.hoje;

        // Carregar licenças recentes
        const recentContainer = document.getElementById("recent-licenses");
        recentContainer.innerHTML = "";

        if (data.recentes && data.recentes.length > 0) {
          const table = createLicensesTable(data.recentes.slice(0, 5));
          recentContainer.appendChild(table);
        } else {
          recentContainer.innerHTML =
            '<p style="color: #aaa;">Nenhuma licença encontrada.</p>';
        }
      }
    })
    .catch((error) => {
      console.error("Erro ao carregar dashboard:", error);
      showAlert("Erro ao carregar estatísticas", "error");
    });
}

// Gerar nova licença
function generateLicense() {
  const form = document.getElementById("generate-form");
  const formData = new FormData(form);

  const data = {
    tipo: formData.get("tipo"),
    email: formData.get("email"),
    nome: formData.get("nome"),
    observacoes: formData.get("observacoes"),
    enviar_email: formData.get("enviar_email") === "on",
  };

  fetch("/api/admin/generate-license", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        currentLicenseCode = data.codigo_licenca;
        document.getElementById("license-code").textContent =
          data.codigo_licenca;
        document.getElementById("generated-license").style.display = "block";

        showAlert("✅ Licença gerada com sucesso!", "success");

        if (data.email_enviado) {
          showAlert("📧 Email enviado automaticamente!", "success");
        }

        // Limpar formulário
        form.reset();

        // Atualizar dashboard se estiver visível
        if (document.getElementById("dashboard").classList.contains("active")) {
          loadDashboard();
        }
      } else {
        showAlert("❌ Erro ao gerar licença: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Copiar código da licença
function copyLicenseCode() {
  navigator.clipboard.writeText(currentLicenseCode).then(() => {
    showAlert("📋 Código copiado para a área de transferência!", "success");
  });
}

// Enviar email manual
function sendEmailManual() {
  const email = document.getElementById("client-email").value;
  const nome = document.getElementById("client-name").value;

  if (!email) {
    showAlert("❌ Email do cliente é obrigatório", "error");
    return;
  }

  fetch("/api/admin/send-email", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      codigo_licenca: currentLicenseCode,
      email: email,
      nome: nome,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showAlert("📧 Email enviado com sucesso!", "success");
      } else {
        showAlert("❌ Erro ao enviar email: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Carregar licenças
function loadLicenses() {
  fetch("/api/admin/licenses")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const tbody = document.getElementById("licenses-tbody");
        tbody.innerHTML = "";

        data.licenses.forEach((license) => {
          const row = createLicenseRow(license);
          tbody.appendChild(row);
        });
      } else {
        showAlert("❌ Erro ao carregar licenças", "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Criar linha da tabela de licenças
function createLicenseRow(license) {
  const row = document.createElement("tr");

  const statusClass =
    license.status === "ativa"
      ? "status-ativa"
      : license.status === "expirada"
      ? "status-expirada"
      : "status-inativa";

  row.innerHTML = `
        <td>${license.codigo_licenca}</td>
        <td>${license.plano}</td>
        <td><span class="status-badge ${statusClass}">${
    license.status
  }</span></td>
        <td>${license.cliente || "N/A"}</td>
        <td>${formatDate(license.data_criacao)}</td>
        <td>${license.validade}</td>
        <td>
            <button onclick="editLicense('${
              license.codigo_licenca
            }')" class="btn-admin" style="padding: 5px 10px; font-size: 12px;">✏️ Editar</button>
            <button onclick="deleteLicense('${
              license.codigo_licenca
            }')" class="btn-admin btn-danger" style="padding: 5px 10px; font-size: 12px;">🗑️ Excluir</button>
            <button onclick="resendEmail('${
              license.codigo_licenca
            }')" class="btn-admin btn-success" style="padding: 5px 10px; font-size: 12px;">📧 Reenviar</button>
        </td>
    `;

  return row;
}

// Criar tabela de licenças
function createLicensesTable(licenses) {
  const table = document.createElement("table");
  table.className = "licenses-table";

  table.innerHTML = `
        <thead>
            <tr>
                <th>Código</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Cliente</th>
                <th>Criação</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

  const tbody = table.querySelector("tbody");
  licenses.forEach((license) => {
    const row = document.createElement("tr");
    const statusClass =
      license.status === "ativa"
        ? "status-ativa"
        : license.status === "expirada"
        ? "status-expirada"
        : "status-inativa";

    row.innerHTML = `
            <td>${license.codigo_licenca}</td>
            <td>${license.plano}</td>
            <td><span class="status-badge ${statusClass}">${
      license.status
    }</span></td>
            <td>${license.cliente || "N/A"}</td>
            <td>${formatDate(license.data_criacao)}</td>
        `;

    tbody.appendChild(row);
  });

  return table;
}

// Editar licença
function editLicense(codigo) {
  // Implementar modal de edição
  showAlert("🔧 Funcionalidade de edição em desenvolvimento", "info");
}

// Excluir licença
function deleteLicense(codigo) {
  if (confirm("⚠️ Tem certeza que deseja excluir esta licença?")) {
    fetch("/api/admin/delete-license", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ codigo_licenca: codigo }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showAlert("✅ Licença excluída com sucesso!", "success");
          loadLicenses();
          loadDashboard();
        } else {
          showAlert("❌ Erro ao excluir licença: " + data.message, "error");
        }
      })
      .catch((error) => {
        console.error("Erro:", error);
        showAlert("❌ Erro de conexão", "error");
      });
  }
}

// Reenviar email
function resendEmail(codigo) {
  fetch("/api/admin/resend-email", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ codigo_licenca: codigo }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showAlert("📧 Email reenviado com sucesso!", "success");
      } else {
        showAlert("❌ Erro ao reenviar email: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Exportar licenças para CSV
function exportLicenses() {
  fetch("/api/admin/export-licenses")
    .then((response) => response.blob())
    .then((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `licencas_derivbot_${
        new Date().toISOString().split("T")[0]
      }.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      showAlert("📥 Arquivo CSV baixado com sucesso!", "success");
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro ao exportar licenças", "error");
    });
}

// Carregar configuração de email
function loadEmailConfig() {
  fetch("/api/admin/email-config")
    .then((response) => response.json())
    .then((data) => {
      if (data.success && data.config) {
        document.getElementById("smtp-server").value =
          data.config.smtp_server || "";
        document.getElementById("smtp-port").value =
          data.config.smtp_port || "";
        document.getElementById("email-user").value =
          data.config.email_user || "";
        // Não carregar senha por segurança
      }

      // Carregar preview do email
      loadEmailPreview();
    })
    .catch((error) => {
      console.error("Erro:", error);
    });
}

// Salvar configuração de email
function saveEmailConfig() {
  const form = document.getElementById("email-config-form");
  const formData = new FormData(form);

  const data = {
    smtp_server: formData.get("smtp_server"),
    smtp_port: parseInt(formData.get("smtp_port")),
    email_user: formData.get("email_user"),
    email_pass: formData.get("email_pass"),
  };

  fetch("/api/admin/save-email-config", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showAlert("✅ Configuração de email salva com sucesso!", "success");
      } else {
        showAlert("❌ Erro ao salvar configuração: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Testar email
function testEmail() {
  const email = document.getElementById("email-user").value;

  if (!email) {
    showAlert("❌ Configure o email primeiro", "error");
    return;
  }

  fetch("/api/admin/test-email", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email_destino: email }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showAlert("✅ Email de teste enviado com sucesso!", "success");
      } else {
        showAlert("❌ Erro ao enviar email de teste: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
      showAlert("❌ Erro de conexão", "error");
    });
}

// Carregar preview do email
function loadEmailPreview() {
  fetch("/api/admin/email-preview")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        document.getElementById("email-preview").innerHTML = data.preview;
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
    });
}

// Carregar chave API
function loadApiKey() {
  fetch("/api/admin/api-key")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        document.getElementById("api-key").value = data.api_key;
      }
    })
    .catch((error) => {
      console.error("Erro:", error);
    });
}

// Gerar nova chave API
function generateApiKey() {
  if (confirm("⚠️ Tem certeza? A chave atual será invalidada.")) {
    fetch("/api/admin/generate-api-key", {
      method: "POST",
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          document.getElementById("api-key").value = data.api_key;
          showAlert("✅ Nova chave API gerada!", "success");
        } else {
          showAlert("❌ Erro ao gerar chave API", "error");
        }
      })
      .catch((error) => {
        console.error("Erro:", error);
        showAlert("❌ Erro de conexão", "error");
      });
  }
}

// Função utilitária para formatar data
function formatDate(dateString) {
  if (!dateString) return "N/A";
  const date = new Date(dateString);
  return date.toLocaleDateString("pt-BR");
}

// Inicializar página
document.addEventListener("DOMContentLoaded", function () {
  console.log("Admin.js carregado com sucesso!");

  // Carregar dashboard por padrão
  console.log("Carregando dashboard...");
  loadDashboard();

  // Event listener para formulário de geração
  const generateForm = document.getElementById("generate-form");
  if (generateForm) {
    generateForm.addEventListener("submit", function (e) {
      e.preventDefault();
      generateLicense();
    });
  }

  // Event listener para configuração de email
  const emailConfigForm = document.getElementById("email-config-form");
  if (emailConfigForm) {
    emailConfigForm.addEventListener("submit", function (e) {
      e.preventDefault();
      saveEmailConfig();
    });
  }
});
