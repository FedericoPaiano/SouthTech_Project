/**
 * SouthTech UI Functions - Versione Pulita
 * Versione: 1.1.0 - Solo funzioni utilizzate
 * 
 * RESPONSABILITÀ:
 * - Sistema notifiche e alert
 * - Modal di conferma personalizzati
 * - Componenti status e badge
 * - Formattazione dati essenziali
 */

// ====================================================================
// SISTEMA NOTIFICHE E ALERT
// ====================================================================

/**
 * Mostra alert/notifica all'utente
 * Utilizzata da: tutti i file per feedback utente
 * @param {string} message - Messaggio da mostrare
 * @param {string} type - Tipo: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Durata in millisecondi
 */
function showAlert(message, type = 'info', duration = 4000) {
  const indicator = document.getElementById('statusIndicator');
  
  if (!indicator) {
      console.warn('⚠️ Elemento statusIndicator non trovato - mostro alert di fallback');
      alert(message);
      return;
  }
  
  // Gestisci stack di alert (max 3)
  const existingAlerts = indicator.querySelectorAll('.alert');
  if (existingAlerts.length >= 3) {
      existingAlerts[0].remove();
  }
  
  let alertClass, icon;
  switch (type) {
      case 'success':
          alertClass = 'alert-success';
          icon = 'fas fa-check-circle';
          break;
      case 'error':
          alertClass = 'alert-danger';
          icon = 'fas fa-exclamation-triangle';
          duration = Math.max(duration, 6000);
          break;
      case 'warning':
          alertClass = 'alert-warning';
          icon = 'fas fa-exclamation-circle';
          duration = Math.max(duration, 5000);
          break;
      default:
          alertClass = 'alert-info';
          icon = 'fas fa-info-circle';
  }
  
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert ${alertClass} alert-dismissible fade show`;
  alertDiv.style.zIndex = '1060'; // Sopra i modal
  alertDiv.innerHTML = `
      <i class="${icon} me-2"></i>
      ${message.replace(/\n/g, '<br>')}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  
  indicator.appendChild(alertDiv);
  
  // Logging per debug
  console.log(`📢 Alert ${type}: ${message}`);
  
  // Auto-rimozione con fade out
  setTimeout(() => {
      if (alertDiv.parentNode) {
          alertDiv.classList.remove('show');
          setTimeout(() => {
              if (alertDiv.parentNode) {
                  alertDiv.remove();
              }
          }, 150);
      }
  }, duration);
}

/**
* Mostra dialog di conferma personalizzato
* Alternativa moderna a confirm() nativo
* @param {string} title - Titolo del dialog
* @param {string} message - Messaggio del dialog
* @param {Object} options - Opzioni di configurazione
*/
function showConfirmDialog(title, message, options = {}) {
  const defaults = {
      confirmText: 'Conferma',
      cancelText: 'Annulla',
      confirmClass: 'btn-primary',
      cancelClass: 'btn-secondary',
      onConfirm: () => {},
      onCancel: () => {}
  };
  
  const config = { ...defaults, ...options };
  
  // Crea modal
  const modal = document.createElement('div');
  modal.className = 'modal fade';
  modal.id = 'southtechConfirmDialog';
  modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
              <div class="modal-header">
                  <h5 class="modal-title">${title}</h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                  <p>${message}</p>
              </div>
              <div class="modal-footer">
                  <button type="button" class="btn ${config.cancelClass}" data-bs-dismiss="modal">
                      ${config.cancelText}
                  </button>
                  <button type="button" class="btn ${config.confirmClass}" id="confirmDialogButton">
                      ${config.confirmText}
                  </button>
              </div>
          </div>
      </div>
  `;
  
  document.body.appendChild(modal);
  
  const bootstrapModal = new bootstrap.Modal(modal);
  bootstrapModal.show();
  
  // Event handlers
  document.getElementById('confirmDialogButton').addEventListener('click', () => {
      config.onConfirm();
      bootstrapModal.hide();
  });
  
  modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
      config.onCancel();
  });
}

/**
* Mostra dialog informativo personalizzato
* Alternativa moderna ad alert() nativo  
* @param {string} title - Titolo del dialog
* @param {string} message - Messaggio del dialog
* @param {Object} options - Opzioni di configurazione
*/
function showInfoDialog(title, message, options = {}) {
  const defaults = {
      okText: 'OK',
      okClass: 'btn-primary',
      type: 'info', // 'info', 'success', 'warning', 'error'
      onOK: () => {},
      autoClose: false,
      autoCloseDelay: 3000
  };
  
  const config = { ...defaults, ...options };
  
  // Determina icona e colore header in base al tipo
  let headerClass, icon;
  switch (config.type) {
      case 'success':
          headerClass = 'bg-success text-white';
          icon = 'fas fa-check-circle';
          break;
      case 'warning':
          headerClass = 'bg-warning text-dark';
          icon = 'fas fa-exclamation-triangle';
          break;
      case 'error':
          headerClass = 'bg-danger text-white';
          icon = 'fas fa-exclamation-circle';
          break;
      default:
          headerClass = 'bg-primary text-white';
          icon = 'fas fa-info-circle';
  }
  
  // Crea modal
  const modal = document.createElement('div');
  modal.className = 'modal fade';
  modal.id = 'southtechInfoDialog';
  modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
              <div class="modal-header ${headerClass}">
                  <h5 class="modal-title">
                      <i class="${icon} me-2"></i>${title}
                  </h5>
                  <button type="button" class="btn-close ${config.type === 'warning' ? '' : 'btn-close-white'}" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                  <p class="mb-0">${message}</p>
              </div>
              <div class="modal-footer">
                  <button type="button" class="btn ${config.okClass}" id="infoDialogButton">
                      ${config.okText}
                  </button>
              </div>
          </div>
      </div>
  `;
  
  document.body.appendChild(modal);
  
  const bootstrapModal = new bootstrap.Modal(modal);
  bootstrapModal.show();
  
  // Event handlers
  document.getElementById('infoDialogButton').addEventListener('click', () => {
      config.onOK();
      bootstrapModal.hide();
  });
  
  modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
  });
  
  // Auto-close se configurato
  if (config.autoClose) {
      setTimeout(() => {
          if (document.getElementById('southtechInfoDialog')) {
              bootstrapModal.hide();
          }
      }, config.autoCloseDelay);
  }
}

// ====================================================================
// COMPONENTI STATUS E BADGE
// ====================================================================

/**
* Aggiorna badge di stato
* Utilizzata da: monitoring.html per stati sistema
* @param {string} elementId - ID dell'elemento da aggiornare
* @param {string} status - Stato: 'online', 'offline', 'warning'
* @param {string} text - Testo da mostrare
*/
function updateStatusBadge(elementId, status, text) {
  const element = document.getElementById(elementId);
  if (!element) {
      console.warn(`⚠️ Elemento ${elementId} non trovato`);
      return;
  }
  
  element.className = 'status-badge';
  switch (status) {
      case 'online':
          element.classList.add('status-online');
          break;
      case 'offline':
          element.classList.add('status-offline');
          break;
      case 'warning':
          element.classList.add('status-warning');
          break;
      default:
          element.classList.add('status-info');
  }
  element.textContent = text;
}

/**
 * Aggiorna stato connessione con icona e messaggio
 * Utilizzata da: light_presence.html, monitoring.html per stato sistema
 * @param {string} message - Messaggio di stato
 * @param {string} type - Tipo: 'success', 'error', 'loading', 'warning'
 * @param {string} mode - Modalità corrente (opzionale)
 * @param {string} containerId - ID del container (default: 'connectionStatus')
 */
function updateConnectionStatus(message, type, mode = null, containerId = 'connectionStatus') {
  const statusDiv = document.getElementById(containerId);
  if (!statusDiv) {
      console.warn(`⚠️ [SouthTech UI] Elemento ${containerId} non trovato per updateConnectionStatus`);
      return;
  }
  
  let statusClass, icon;
  switch (type) {
      case 'success':
          statusClass = 'status-api';
          icon = 'fas fa-check-circle';
          break;
      case 'error':
          statusClass = 'status-error';
          icon = 'fas fa-exclamation-triangle';
          break;
      case 'warning':
          statusClass = 'status-warning';
          icon = 'fas fa-exclamation-circle';
          break;
      case 'loading':
          statusClass = 'status-file';
          icon = 'fas fa-spinner fa-spin';
          break;
      default:
          statusClass = 'status-file';
          icon = 'fas fa-info-circle';
  }
  
  const modeText = mode ? `<small class="ms-2">(${mode})</small>` : '';
  
  statusDiv.innerHTML = `
      <div class="connection-status ${statusClass}">
          <i class="${icon}"></i>
          <span>${message}</span>
          ${modeText}
      </div>
  `;
  
  // Log per debug
  console.log(`📡 [SouthTech UI] Stato connessione: ${message} (${type})`);
}

// ====================================================================
// FORMATTAZIONE DATI
// ====================================================================

/**
* Formatta uptime del sistema
* Utilizzata da: monitoring.html per visualizzare uptime
* @param {number} milliseconds - Millisecondi di uptime
*/
function formatUptime(milliseconds) {
  const days = Math.floor(milliseconds / (1000 * 60 * 60 * 24));
  const hours = Math.floor((milliseconds % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((milliseconds % (1000 * 60 * 60)) / (1000 * 60));
  
  if (days > 0) {
      return `${days}d ${hours}h`;
  } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
  } else {
      return `${minutes}m`;
  }
}

// ====================================================================
// INIZIALIZZAZIONE MODULO
// ====================================================================

// Log di inizializzazione
console.log('🎨 [SouthTech UI] Funzioni interfaccia utente caricate - versione 1.1.0 (pulita)');

// Esporta le funzioni essenziali
if (typeof window !== 'undefined') {
    window.SouthTechUI = {
        // Notifiche e Dialog
        showAlert,
        showConfirmDialog,
        showInfoDialog,
        
        // Status e Badge
        updateStatusBadge,
        updateConnectionStatus,
        
        // Formattazione
        formatUptime
    };
}
