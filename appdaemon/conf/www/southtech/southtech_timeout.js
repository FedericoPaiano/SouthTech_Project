/**
 * SouthTech Timeout Module - Sistema Timeout Inattività Avanzato
 * Versione: 4.1.0 - CORRETTA
 * 
 * Sistema robusto con:
 * - Controllo timestamp persistente (sopravvive al riavvio PC)
 * - Heartbeat ogni minuto
 * - Gestione multi-tab indipendente
 * - Disconnessione immediata dopo inattività
 * - Modal manual-close con countdown
 * - Warning persistente che NON scompare al cambio tab
 * - Fallback safety (RIMOSSO debug mode)
 */

// ====================================================================
// CONFIGURAZIONE AVANZATA (RIMOSSO DEBUG MODE)
// ====================================================================

const SOUTHTECH_TIMEOUT_V4 = {
  // 🕐 TIMING CONFIGURATION (SOLO PRODUZIONE)
  INACTIVITY_TIMEOUT: 30 * 60 * 1000,    // 30 minuti in millisecondi
  WARNING_TIME: 5 * 60 * 1000,           // 5 minuti warning
  TOLERANCE: 30 * 1000,                  // ±30 secondi tolleranza
  HEARTBEAT_INTERVAL: 60 * 1000,         // Controllo ogni 1 minuto
  CLEANUP_INTERVAL: 24 * 60 * 60 * 1000, // Pulizia ogni 24h
  CLEANUP_AGE: 7 * 24 * 60 * 60 * 1000,  // Rimuovi dati >7 giorni
  
  // 📱 EVENTI MONITORATI
  MONITORED_EVENTS: ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click', 'keydown'],
  
  // 🔧 STATO SISTEMA
  state: {
      tabId: null,                    // ID unico per questo tab
      heartbeatTimer: null,           // Timer heartbeat
      fallbackTimer: null,           // Timer JS fallback
      lastActivity: null,             // Timestamp ultima attività
      warningShown: false,            // Flag warning mostrato
      isAuthenticated: false,         // Stato autenticazione
      cleanupTimer: null,             // Timer pulizia automatica
      eventListenersAdded: false,     // Flag event listeners
      countdownInterval: null,        // Interval countdown
      warningStartTime: null,         // Tempo inizio warning
      pageVisible: true               // Visibilità pagina
  }
};

// ====================================================================
// FUNZIONI PRINCIPALI
// ====================================================================

/**
* 🚀 Inizializzazione sistema timeout avanzato (CORRETTA)
* NOTA: Il controllo iniziale di timeout è ora gestito da SouthTechSessionGuard
* @returns {boolean} Success/failure
*/
function initializeSouthTechTimeout() {
  console.log('🔒 [SouthTech Timeout v4.1] Inizializzazione sistema timer (PRODUZIONE)');
  
  // Controllo autenticazione
  const authToken = sessionStorage.getItem('southtech_session_token');
  if (!authToken) {
      console.log('🔒 [Timeout v4.1] Nessun token - timeout non attivato');
      return false;
  }
  
  // Genera ID tab univoco
  SOUTHTECH_TIMEOUT_V4.state.tabId = generateTabId();
  console.log(`🔒 [Timeout v4.1] Tab ID: ${SOUTHTECH_TIMEOUT_V4.state.tabId}`);
  
  // Imposta stato autenticato
  SOUTHTECH_TIMEOUT_V4.state.isAuthenticated = true;
  SOUTHTECH_TIMEOUT_V4.state.pageVisible = !document.hidden;
  
  // Aggiungi event listeners
  addSystemEventListeners();
  
  // Registra attività iniziale
  recordUserActivity();
  
  // Avvia heartbeat system
  startHeartbeatSystem();
  
  // Avvia timer fallback JavaScript
  startFallbackTimer();
  
  // Avvia pulizia automatica
  startAutomaticCleanup();
  
  // Aggiungi CSS per modal
  addTimeoutModalCSS();
  
  // Gestione visibilità pagina
  handlePageVisibilityChange();
  
  console.log('✅ [Timeout v4.1] Sistema timer PRODUZIONE attivato (30 minuti)');
  console.log('ℹ️ [Timeout v4.1] Controllo iniziale sessione gestito da SouthTechSessionGuard');
  
  return true;
}

/**
* 🆔 Genera ID tab univoco
* @returns {string} Tab ID
*/
function generateTabId() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substr(2, 9);
  return `tab_${timestamp}_${random}`;
}

/**
* 📡 Aggiungi event listeners di sistema (CORRETTI)
*/
function addSystemEventListeners() {
  if (SOUTHTECH_TIMEOUT_V4.state.eventListenersAdded) {
      return; // Evita duplicati
  }
  
  // Event listeners per attività utente REALE
  SOUTHTECH_TIMEOUT_V4.MONITORED_EVENTS.forEach(event => {
      document.addEventListener(event, recordUserActivity, true);
  });
  
  // ✅ CORREZIONE: Event listeners per controlli stato (NON attività)
  document.addEventListener('visibilitychange', handlePageVisibilityChange);
  window.addEventListener('focus', handleWindowFocus);
  window.addEventListener('blur', handleWindowBlur);
  
  // Cleanup su unload
  window.addEventListener('beforeunload', cleanupSouthTechTimeout);
  
  SOUTHTECH_TIMEOUT_V4.state.eventListenersAdded = true;
  console.log('📡 [Timeout v4.1] Event listeners corretti aggiunti');
}

/**
* 📝 Registra attività utente REALE (CORRETTA)
*/
function recordUserActivity() {
  const now = Date.now();
  SOUTHTECH_TIMEOUT_V4.state.lastActivity = now;
  
  // Salva timestamp locale per questo tab
  const tabKey = `southtech_last_activity_${SOUTHTECH_TIMEOUT_V4.state.tabId}`;
  localStorage.setItem(tabKey, now.toString());
  
  // Salva anche timestamp globale per controlli cross-tab
  localStorage.setItem('southtech_global_last_activity', now.toString());
  
  // ✅ CORREZIONE: Reset warning SOLO per attività REALE dell'utente
  if (SOUTHTECH_TIMEOUT_V4.state.warningShown) {
      console.log('📝 [Timeout v4.1] Attività utente REALE rilevata - reset warning valido');
      hideTimeoutWarning();
  }
  
  // Reset timer fallback
  resetFallbackTimer();
  
  console.log(`📝 [Timeout v4.1] Attività REALE registrata: ${new Date(now).toLocaleTimeString()}`);
}

/**
 * ✅ NUOVA FUNZIONE: Controllo stato pagina SENZA registrare attività
 * Questa è la chiave per risolvere il problema del warning che scompare
 */
function checkPageState() {
    console.log('👁️ [Timeout v4.1] Controllo stato pagina (SENZA reset timer)');
    
    if (!SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
        return;
    }
    
    const timeoutCheck = performCompleteTimeoutCheck();
    
    if (timeoutCheck.shouldLogout) {
        console.log('👁️ [Timeout v4.1] TIMEOUT SCADUTO rilevato al controllo pagina');
        performSouthTechLogout('page_check_timeout');
        return;
    }
    
    if (timeoutCheck.shouldShowWarning) {
        console.log('👁️ [Timeout v4.1] Area WARNING rilevata al controllo pagina - mostra/mantieni warning');
        showTimeoutWarning();
        return;
    }
    
    console.log('👁️ [Timeout v4.1] Controllo pagina OK - sessione valida');
}

/**
* 💓 Sistema heartbeat - controllo ogni minuto
*/
function startHeartbeatSystem() {
  // Cancella heartbeat precedente se esiste
  if (SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer);
  }
  
  // Heartbeat ogni minuto
  SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer = setInterval(() => {
      performHeartbeatCheck();
  }, SOUTHTECH_TIMEOUT_V4.HEARTBEAT_INTERVAL);
  
  console.log('💓 [Timeout v4.1] Heartbeat avviato (ogni 1 minuto)');
  
  // Primo controllo immediato
  setTimeout(() => performHeartbeatCheck(), 5000); // Dopo 5 secondi
}

/**
 * 🔄 Heartbeat check (CORRETTO - rimosso debug mode)
 */
function performHeartbeatCheck() {
  if (!SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
      return; // Non autenticato, skip
  }
  
  try {
      const now = Date.now();
      const lastActivity = SOUTHTECH_TIMEOUT_V4.state.lastActivity || now;
      const timeDiff = now - lastActivity;
      
      // ✅ CORREZIONE: Usa sempre valori di produzione (rimosso debug mode)
      const timeoutLimit = SOUTHTECH_TIMEOUT_V4.INACTIVITY_TIMEOUT;
      const warningLimit = timeoutLimit - SOUTHTECH_TIMEOUT_V4.WARNING_TIME;
      
      console.log(`💓 [Timeout v4.1] Heartbeat - Inattivo da: ${Math.round(timeDiff / 1000)} secondi`);
      
      // Controllo logout immediato
      if (timeDiff > timeoutLimit + SOUTHTECH_TIMEOUT_V4.TOLERANCE) {
          console.log('🚨 [Timeout v4.1] Heartbeat - TIMEOUT SCADUTO');
          performSouthTechLogout('heartbeat_timeout');
          return;
      }
      
      // ✅ CORREZIONE: Controllo warning SENZA condizione warningShown
      if (timeDiff > warningLimit) {
          console.log('⚠️ [Timeout v4.1] Heartbeat - Area warning, mostra avviso');
          showTimeoutWarning();
      }
      
  } catch (error) {
      console.error('❌ [Timeout v4.1] Errore heartbeat:', error);
  }
}

/**
 * 🔍 Controllo timeout completo CORRETTO (rimossa condizione warningShown)
 */
function performCompleteTimeoutCheck() {
  try {
      // Cerca timestamp più recente tra locale e globale
      const globalTimestamp = localStorage.getItem('southtech_global_last_activity');
      const allTabKeys = Object.keys(localStorage).filter(key => 
          key.startsWith('southtech_last_activity_')
      );
      
      let mostRecentActivity = null;
      
      // Trova attività più recente
      if (globalTimestamp) {
          mostRecentActivity = parseInt(globalTimestamp);
      }
      
      allTabKeys.forEach(key => {
          const timestamp = parseInt(localStorage.getItem(key));
          if (!mostRecentActivity || timestamp > mostRecentActivity) {
              mostRecentActivity = timestamp;
          }
      });
      
      if (!mostRecentActivity) {
          console.log('🔍 [Timeout Check] Nessuna attività precedente trovata');
          return { shouldLogout: false, shouldShowWarning: false };
      }
      
      const now = Date.now();
      const timeDiff = now - mostRecentActivity;
      
      // ✅ CORREZIONE: Usa sempre valori di produzione (rimosso debug mode)
      const timeoutLimit = SOUTHTECH_TIMEOUT_V4.INACTIVITY_TIMEOUT;
      const warningLimit = timeoutLimit - SOUTHTECH_TIMEOUT_V4.WARNING_TIME;
      
      console.log(`🔍 [Complete Check] Ultima attività: ${new Date(mostRecentActivity).toLocaleString()}`);
      console.log(`🔍 [Complete Check] Tempo inattività: ${Math.round(timeDiff / 1000 / 60)} minuti`);
      console.log(`🔍 [Complete Check] Limite timeout: ${Math.round(timeoutLimit / 1000 / 60)} minuti`);
      console.log(`🔍 [Complete Check] Limite warning: ${Math.round(warningLimit / 1000 / 60)} minuti`);
      
      // Gestisci edge cases
      if (mostRecentActivity > now) {
          console.warn('⚠️ [Complete Check] Timestamp futuro - possibile cambio orario sistema');
          return { shouldLogout: false, shouldShowWarning: false };
      }
      
      // ✅ CONTROLLO LOGOUT (priorità massima)
      if (timeDiff > timeoutLimit + SOUTHTECH_TIMEOUT_V4.TOLERANCE) {
          console.log('🚨 [Complete Check] TIMEOUT SCADUTO - logout necessario');
          return {
              shouldLogout: true,
              shouldShowWarning: false,
              inactiveTime: timeDiff,
              lastActivity: mostRecentActivity
          };
      }
      
      // ✅ CORREZIONE CRITICA: Controllo warning SENZA condizione warningShown
      // Ora può rimostrare il warning anche se era già mostrato
      if (timeDiff > warningLimit) {
          console.log('⚠️ [Complete Check] AREA WARNING - mostra/rimostra avviso');
          return {
              shouldLogout: false,
              shouldShowWarning: true,
              inactiveTime: timeDiff,
              lastActivity: mostRecentActivity,
              timeUntilTimeout: timeoutLimit - timeDiff
          };
      }
      
      // Tutto OK
      console.log('✅ [Complete Check] Sessione valida, nessuna azione necessaria');
      return { shouldLogout: false, shouldShowWarning: false };
      
  } catch (error) {
      console.error('❌ [Complete Check] Errore controllo timeout:', error);
      return { shouldLogout: false, shouldShowWarning: false };
  }
}

/**
* 🛡️ Timer fallback JavaScript (CORRETTO - rimosso debug mode)
*/
function startFallbackTimer() {
  resetFallbackTimer();
}

function resetFallbackTimer() {
  // Cancella timer precedente
  if (SOUTHTECH_TIMEOUT_V4.state.fallbackTimer) {
      clearTimeout(SOUTHTECH_TIMEOUT_V4.state.fallbackTimer);
  }
  
  // Solo se autenticato
  if (!SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
      return;
  }
  
  // ✅ CORREZIONE: Usa sempre timeout di produzione (rimosso debug mode)
  const timeoutDuration = SOUTHTECH_TIMEOUT_V4.INACTIVITY_TIMEOUT;
  
  // Timer fallback
  SOUTHTECH_TIMEOUT_V4.state.fallbackTimer = setTimeout(() => {
      if (SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
          console.log('🛡️ [Timeout v4.1] Fallback timer scaduto');
          performSouthTechLogout('fallback_timeout');
      }
  }, timeoutDuration + SOUTHTECH_TIMEOUT_V4.TOLERANCE);
}

/**
 * ⚠️ CORRETTO: Mostra warning timeout (permette ri-mostrazione)
 */
function showTimeoutWarning() {
  console.log('⚠️ [Timeout v4.1] Mostrando warning timeout (permettendo ri-mostrazione)');
  
  // ✅ CORREZIONE: Se warning già presente, NON rimuoverlo - lascialo visibile
  const existingModal = document.getElementById('southtechTimeoutWarningModal');
  if (existingModal) {
      console.log('ℹ️ [Warning] Warning già visibile - mantieni esistente');
      return; // Mantieni il warning esistente
  }
  
  SOUTHTECH_TIMEOUT_V4.state.warningShown = true;
  SOUTHTECH_TIMEOUT_V4.state.warningStartTime = Date.now();
  
  console.log(`🕒 [Warning] Warning start time: ${new Date(SOUTHTECH_TIMEOUT_V4.state.warningStartTime).toLocaleTimeString()}`);
  
  // ✅ CORREZIONE: Usa sempre valori di produzione (rimosso debug mode)
  const warningTime = SOUTHTECH_TIMEOUT_V4.WARNING_TIME;
  
  console.log(`⏱️ [Warning] Durata warning: ${Math.round(warningTime / 1000)} secondi`);
  
  const warningModal = document.createElement('div');
  warningModal.id = 'southtechTimeoutWarningModal';
  warningModal.className = 'modal fade show';
  warningModal.style.display = 'block';
  warningModal.style.backgroundColor = 'rgba(0,0,0,0.8)';
  warningModal.style.zIndex = '2500';
  
  // ✅ MODAL BLOCCANTE - rimuovi possibilità di dismissione
  warningModal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
              <div class="modal-header bg-warning text-dark">
                  <h5 class="modal-title">
                      <i class="fas fa-clock me-2"></i>Sessione in Scadenza
                  </h5>
                  <!-- RIMOSSO pulsante X per rendere modal non dismissibile -->
              </div>
              <div class="modal-body text-center">
                  <div class="mb-3">
                      <i class="fas fa-hourglass-half text-warning" style="font-size: 2.5rem;"></i>
                  </div>
                  <p class="mb-3">
                      La tua sessione scadrà tra <strong id="southtechCountdownDisplay">--:--</strong> per inattività.
                  </p>
                  <p class="text-muted">
                      Clicca "Rimani Connesso" per continuare o "Logout" per uscire subito.
                  </p>
                  <div class="mt-3">
                      <small class="text-muted">
                          Limite inattività: <strong>30 minuti</strong>
                      </small>
                  </div>
              </div>
              <div class="modal-footer">
                  <button type="button" class="btn btn-success" onclick="stayConnectedSouthTech()">
                      <i class="fas fa-check me-2"></i>Rimani Connesso
                  </button>
                  <button type="button" class="btn btn-outline-danger" onclick="logoutNowSouthTech()">
                      <i class="fas fa-sign-out-alt me-2"></i>Logout Ora
                  </button>
              </div>
          </div>
      </div>
  `;
  
  document.body.appendChild(warningModal);
  console.log('✅ [Warning] Modal bloccante aggiunto al DOM');
  
  // Avvia countdown robusto
  startRobustCountdown(warningTime);
  
  // Aggiungi funzioni globali (se non esistono già)
  if (!window.stayConnectedSouthTech) {
      window.stayConnectedSouthTech = function() {
          console.log('✅ [Timeout v4.1] Utente sceglie di rimanere connesso');
          hideTimeoutWarning();
          recordUserActivity(); // Registra nuova attività REALE
          
          // Mostra conferma
          if (typeof SouthTechUI !== 'undefined' && SouthTechUI.showAlert) {
              SouthTechUI.showAlert('✅ Sessione rinnovata! Timer resettato.', 'success');
          }
      };
  }
  
  if (!window.logoutNowSouthTech) {
      window.logoutNowSouthTech = function() {
          console.log('🚪 [Timeout v4.1] Utente sceglie logout immediato');
          hideTimeoutWarning();
          performSouthTechLogout('user_choice');
      };
  }
}

/**
 * 🚨 Modal timeout scaduto standalone (se SessionGuard non disponibile)
 * @param {object} timeoutInfo Informazioni timeout
 */
function showTimeoutExpiredModal(timeoutInfo) {
  console.log('🚨 [Timeout] Mostrando modal timeout scaduto standalone');
  
  // Rimuovi modal esistenti
  removeExistingTimeoutModals();
  
  const modal = document.createElement('div');
  modal.id = 'southtechTimeoutExpiredModal';
  modal.className = 'modal fade show';
  modal.style.display = 'block';
  modal.style.backgroundColor = 'rgba(0,0,0,0.9)';
  modal.style.zIndex = '3000';
  
  const limitText = "30 minuti"; // ✅ CORREZIONE: Sempre 30 minuti (rimosso debug)
  const timeText = timeoutInfo.formattedTime || "più di 30 minuti";
  
  modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
              <div class="modal-header bg-danger text-white">
                  <h5 class="modal-title">
                      <i class="fas fa-exclamation-triangle me-2"></i>Sessione Scaduta per Timeout
                  </h5>
              </div>
              <div class="modal-body text-center">
                  <div class="mb-4">
                      <i class="fas fa-clock text-danger" style="font-size: 4rem;"></i>
                  </div>
                  <h5 class="text-danger mb-3">Sessione scaduta per inattività</h5>
                  <p class="mb-3">
                      La tua sessione è rimasta inattiva per <strong>${timeText}</strong>.<br>
                      Il limite di sicurezza è di <strong>${limitText}</strong>.
                  </p>
                  <div class="alert alert-info mb-3">
                      <i class="fas fa-info-circle me-2"></i>
                      <strong>Motivo:</strong> ${getReasonDescription(timeoutInfo.reason)}
                  </div>
                  <p class="text-muted small">
                      Per motivi di sicurezza, devi effettuare nuovamente il login.
                  </p>
              </div>
              <div class="modal-footer justify-content-center">
                  <button type="button" class="btn btn-primary btn-lg" onclick="handleTimeoutExpiredOK()">
                      <i class="fas fa-sign-in-alt me-2"></i>Torna al Login
                  </button>
              </div>
          </div>
      </div>
  `;
  
  document.body.appendChild(modal);
  
  // Handler globale
  window.handleTimeoutExpiredOK = function() {
      console.log('🚪 [Timeout] Utente conferma logout - redirect');
      removeTimeoutExpiredModal();
      performTimeoutRedirect();
  };
  
  console.log('✅ [Timeout] Modal timeout scaduto mostrato');
}

/**
 * 📝 Descrizione motivo timeout user-friendly
 * @param {string} reason Motivo tecnico
 * @returns {string} Descrizione leggibile
 */
function getReasonDescription(reason) {
  const reasons = {
      'heartbeat_timeout': 'Controllo automatico sistema',
      'fallback_timeout': 'Timer di sicurezza JavaScript',
      'page_visibility_timeout': 'Rilevato al ritorno sulla pagina',
      'window_focus_timeout': 'Rilevato al focus della finestra',
      'page_check_timeout': 'Rilevato al controllo pagina',
      'countdown_expired': 'Countdown di avviso terminato'
  };
  
  return reasons[reason] || 'Timeout automatico del sistema';
}

/**
 * 🗑️ Rimuovi modal timeout esistenti
 */
function removeExistingTimeoutModals() {
  const modalIds = [
      'southtechTimeoutExpiredModal',
      'southtechTimeoutWarningModal',
      'southtechSessionExpiredModal' // Dal SessionGuard
  ];
  
  modalIds.forEach(id => {
      const modal = document.getElementById(id);
      if (modal) {
          console.log(`🗑️ [Timeout] Rimuovo modal esistente: ${id}`);
          modal.remove();
      }
  });
}

/**
 * 🚫 Rimuovi modal timeout scaduto
 */
function removeTimeoutExpiredModal() {
  const modal = document.getElementById('southtechTimeoutExpiredModal');
  if (modal) {
      modal.remove();
  }
}

/**
 * 🔄 Redirect dopo timeout con pulizia completa
 */
function performTimeoutRedirect() {
  console.log('🔄 [Timeout] Eseguo redirect dopo timeout');
  
  // Pulizia sessione completa
  cleanupSessionAfterTimeout();
  
  // Determina pagina corrente
  const currentPage = getCurrentPageName();
  
  if (currentPage === 'index') {
      console.log('🔄 [Timeout] Già su index.html - ricarico per reset');
      window.location.reload();
  } else {
      console.log('🔄 [Timeout] Redirect a index.html');
      window.location.href = 'index.html';
  }
}

/**
 * 🧹 Pulizia sessione dopo timeout
 */
function cleanupSessionAfterTimeout() {
  console.log('🧹 [Timeout] Pulizia sessione dopo timeout');
  
  // Pulisci sessionStorage
  const sessionKeys = [
      'southtech_session_token',
      'southtech_ha_token', 
      'southtech_browser_id',
      'southtech_return_to_menu',
      'southtech_page_source'
  ];
  
  sessionKeys.forEach(key => {
      sessionStorage.removeItem(key);
  });
  
  // Aggiorna timestamp per evitare loop
  localStorage.setItem('southtech_global_last_activity', Date.now().toString());
  
  console.log('✅ [Timeout] Pulizia sessione completata');
}

/**
 * 📄 Ottieni nome pagina corrente
 * @returns {string} Nome pagina
 */
function getCurrentPageName() {
  const path = window.location.pathname;
  const filename = path.split('/').pop() || 'unknown';
  return filename.replace('.html', '') || 'index';
}

/**
 * ⏱️ Countdown robusto (CORRETTO - rimosso debug mode)
 * @param {number} duration Durata in millisecondi
 */
function startRobustCountdown(duration) {
  // Cancella countdown precedente
  if (SOUTHTECH_TIMEOUT_V4.state.countdownInterval) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
  }
  
  const startTime = SOUTHTECH_TIMEOUT_V4.state.warningStartTime;
  
  SOUTHTECH_TIMEOUT_V4.state.countdownInterval = setInterval(() => {
      try {
          const now = Date.now();
          const elapsed = now - startTime;
          const remaining = duration - elapsed;
          
          const countdownElement = document.getElementById('southtechCountdownDisplay');
          if (!countdownElement) {
              console.warn('⚠️ [Timeout v4.1] Elemento countdown non trovato - interrompo');
              clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
              return;
          }
          
          if (remaining <= 0) {
              countdownElement.textContent = '0:00';
              clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
              
              console.log('⏰ [Timeout v4.1] Countdown terminato - logout automatico');
              performSouthTechLogout('countdown_expired');
              return;
          }
          
          // Aggiorna display
          const minutes = Math.floor(remaining / 60000);
          const seconds = Math.floor((remaining % 60000) / 1000);
          const timeString = `${minutes}:${seconds.toString().padStart(2, '0')}`;
          
          countdownElement.textContent = timeString;
          
          // Cambia colore negli ultimi 30 secondi
          if (remaining <= 30000) {
              countdownElement.style.color = '#dc3545'; // Rosso
              countdownElement.style.fontWeight = 'bold';
          }
          
      } catch (error) {
          console.error('❌ [Timeout v4.1] Errore countdown:', error);
          clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
      }
  }, 1000);
  
  console.log(`⏱️ [Timeout v4.1] Countdown avviato: ${Math.round(duration / 1000)} secondi`);
}

/**
* 🚫 CORRETTO: Nasconde warning timeout
*/
function hideTimeoutWarning() {
  const modal = document.getElementById('southtechTimeoutWarningModal');
  if (modal) {
      modal.remove();
  }
  
  // Cancella countdown
  if (SOUTHTECH_TIMEOUT_V4.state.countdownInterval) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
      SOUTHTECH_TIMEOUT_V4.state.countdownInterval = null;
  }
  
  SOUTHTECH_TIMEOUT_V4.state.warningShown = false;
  SOUTHTECH_TIMEOUT_V4.state.warningStartTime = null;
  
  console.log('🚫 [Timeout v4.1] Warning nascosto e stato resettato');
}

/**
 * 🚪 Esegue logout per timeout INTEGRATO con SessionGuard
 * @param {string} reason Motivo logout
 */
function performSouthTechLogout(reason) {
  console.log(`🚪 [Timeout v4.1] Logout per: ${reason}`);
  
  // Nascondi warning se presente
  hideTimeoutWarning();
  
  // Calcola info timeout per modal
  const timeoutInfo = calculateTimeoutInfoForModal(reason);
  
  // Pulizia sistema timeout
  cleanupSouthTechTimeout();
  
  // ✅ INTEGRAZIONE CON SESSION GUARD
  if (typeof window.SouthTechSessionGuard !== 'undefined' && 
      typeof window.SouthTechSessionGuard.redirectToLogin === 'function') {
      
      console.log('🚪 [Timeout] Usando SessionGuard per logout con modal');
      
      // Se SouthTechSessionGuard esiste, mostra il modal sessione scaduta
      if (typeof window.showSessionExpiredModal === 'function') {
          console.log('🚪 [Timeout] Mostrando modal sessione scaduta');
          window.showSessionExpiredModal(timeoutInfo);
      } else {
          // Fallback diretto al redirect
          console.log('🚪 [Timeout] Modal non disponibile, redirect diretto');
          window.SouthTechSessionGuard.redirectToLogin();
      }
      
  } else {
      console.log('🚪 [Timeout] SessionGuard non disponibile, usando logout fallback');
      
      // MOSTRA MODAL TIMEOUT SCADUTO STANDALONE
      showTimeoutExpiredModal(timeoutInfo);
  }
}

/**
 * 🧮 Calcola informazioni timeout per il modal (CORRETTO)
 * @param {string} reason Motivo del timeout
 * @returns {object} Informazioni per il modal
 */
function calculateTimeoutInfoForModal(reason) {
  const now = Date.now();
  let lastActivity = SOUTHTECH_TIMEOUT_V4.state.lastActivity;
  
  // Se non abbiamo lastActivity, prova dal localStorage
  if (!lastActivity) {
      const globalTimestamp = localStorage.getItem('southtech_global_last_activity');
      if (globalTimestamp) {
          lastActivity = parseInt(globalTimestamp);
      } else {
          lastActivity = now - (35 * 60 * 1000); // Default: 35 minuti fa
      }
  }
  
  const inactiveTime = now - lastActivity;
  // ✅ CORREZIONE: Usa sempre timeout di produzione (rimosso debug mode)
  const timeoutLimit = SOUTHTECH_TIMEOUT_V4.INACTIVITY_TIMEOUT;
  
  return {
      isExpired: true,
      reason: reason,
      inactiveTime: inactiveTime,
      lastActivity: lastActivity,
      formattedTime: formatTimeoutDuration(inactiveTime),
      timeoutLimit: timeoutLimit
  };
}

/**
 * 🕐 Formatta durata timeout per display
 * @param {number} inactiveTime Tempo in millisecondi
 * @returns {string} Tempo formattato user-friendly
 */
function formatTimeoutDuration(inactiveTime) {
  const minutes = Math.round(inactiveTime / 1000 / 60);
  
  // Se più di 1 ora, mostra testo generico
  if (minutes > 60) {
      return "più di 30 minuti";
  }
  
  // Altrimenti mostra tempo più preciso
  if (minutes < 60) {
      return `${minutes} minuti`;
  } else {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      return `${hours}h ${remainingMinutes}m`;
  }
}

/**
 * 👁️ CORREZIONE: Gestione visibilità pagina (usa checkPageState)
 */
function handlePageVisibilityChange() {
  const wasVisible = SOUTHTECH_TIMEOUT_V4.state.pageVisible;
  SOUTHTECH_TIMEOUT_V4.state.pageVisible = !document.hidden;
  
  if (!wasVisible && SOUTHTECH_TIMEOUT_V4.state.pageVisible) {
      // ✅ CORREZIONE CRITICA: Non registrare attività, solo controllare stato
      console.log('👁️ [Timeout v4.1] Pagina tornata visibile - controllo stato SENZA reset timer');
      
      if (SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
          checkPageState(); // ← Questo NON registra attività
      }
  }
}

/**
 * 👁️ CORREZIONE: Window focus (usa checkPageState)
 */
function handleWindowFocus() {
  console.log('👁️ [Timeout v4.1] Window focus - controllo stato SENZA reset timer');
  
  if (SOUTHTECH_TIMEOUT_V4.state.isAuthenticated) {
      checkPageState(); // ← Questo NON registra attività
  }
}

function handleWindowBlur() {
  console.log('👁️ [Timeout v4.1] Window blur');
  // Nessuna azione specifica al blur
}

/**
* 🧹 Pulizia automatica storage
*/
function startAutomaticCleanup() {
  // Pulizia immediata
  performStorageCleanup();
  
  // Pulizia periodica ogni 24h
  SOUTHTECH_TIMEOUT_V4.state.cleanupTimer = setInterval(() => {
      performStorageCleanup();
  }, SOUTHTECH_TIMEOUT_V4.CLEANUP_INTERVAL);
  
  console.log('🧹 [Timeout v4.1] Auto-pulizia avviata (ogni 24h)');
}

function performStorageCleanup() {
  try {
      const now = Date.now();
      const keys = Object.keys(localStorage);
      let cleanedCount = 0;
      
      keys.forEach(key => {
          if (key.startsWith('southtech_last_activity_')) {
              const timestamp = localStorage.getItem(key);
              if (timestamp) {
                  const age = now - parseInt(timestamp);
                  if (age > SOUTHTECH_TIMEOUT_V4.CLEANUP_AGE) {
                      localStorage.removeItem(key);
                      cleanedCount++;
                  }
              }
          }
      });
      
      if (cleanedCount > 0) {
          console.log(`🧹 [Timeout v4.1] Pulizia completata: ${cleanedCount} entry rimosse`);
      }
      
  } catch (error) {
      console.error('❌ [Timeout v4.1] Errore pulizia storage:', error);
  }
}

/**
* 🧼 Pulizia completa sistema
*/
function cleanupSouthTechTimeout() {
  console.log('🧼 [Timeout v4.1] Pulizia completa sistema');
  
  // Cancella tutti i timer
  if (SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer);
      SOUTHTECH_TIMEOUT_V4.state.heartbeatTimer = null;
  }
  
  if (SOUTHTECH_TIMEOUT_V4.state.fallbackTimer) {
      clearTimeout(SOUTHTECH_TIMEOUT_V4.state.fallbackTimer);
      SOUTHTECH_TIMEOUT_V4.state.fallbackTimer = null;
  }
  
  if (SOUTHTECH_TIMEOUT_V4.state.cleanupTimer) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.cleanupTimer);
      SOUTHTECH_TIMEOUT_V4.state.cleanupTimer = null;
  }
  
  if (SOUTHTECH_TIMEOUT_V4.state.countdownInterval) {
      clearInterval(SOUTHTECH_TIMEOUT_V4.state.countdownInterval);
      SOUTHTECH_TIMEOUT_V4.state.countdownInterval = null;
  }
  
  // Rimuovi event listeners
  if (SOUTHTECH_TIMEOUT_V4.state.eventListenersAdded) {
      SOUTHTECH_TIMEOUT_V4.MONITORED_EVENTS.forEach(event => {
          document.removeEventListener(event, recordUserActivity, true);
      });
      
      document.removeEventListener('visibilitychange', handlePageVisibilityChange);
      window.removeEventListener('focus', handleWindowFocus);
      window.removeEventListener('blur', handleWindowBlur);
      window.removeEventListener('beforeunload', cleanupSouthTechTimeout);
      
      SOUTHTECH_TIMEOUT_V4.state.eventListenersAdded = false;
  }
  
  // Rimuovi modal se presente
  hideTimeoutWarning();
  
  // Reset stato
  SOUTHTECH_TIMEOUT_V4.state.isAuthenticated = false;
  SOUTHTECH_TIMEOUT_V4.state.warningShown = false;
  SOUTHTECH_TIMEOUT_V4.state.lastActivity = null;
  SOUTHTECH_TIMEOUT_V4.state.warningStartTime = null;
  
  console.log('✅ [Timeout v4.1] Pulizia completata');
}

/**
* 🎨 CSS per modal timeout
*/
function addTimeoutModalCSS() {
  if (document.getElementById('southtech-timeout-v4-css')) {
      return;
  }
  
  const css = `
      <style id="southtech-timeout-v4-css">
      /* SouthTech Timeout v4.1 Modal Styles */
      #southtechTimeoutWarningModal .modal-content {
          border-radius: 20px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.4);
          border: none;
      }

      #southtechTimeoutWarningModal .modal-header {
          border-radius: 20px 20px 0 0;
          border-bottom: none;
      }

      #southtechCountdownDisplay {
          font-size: 2rem;
          color: #f39c12;
          font-weight: bold;
          font-family: 'Courier New', monospace;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
      }
      
      #southtechTimeoutWarningModal {
          z-index: 2500 !important;
      }
      
      #southtechTimeoutWarningModal .modal-dialog {
          z-index: 2501 !important;
      }
      
      #southtechTimeoutWarningModal .btn {
          border-radius: 10px;
          padding: 12px 25px;
          font-weight: 600;
          transition: all 0.3s ease;
      }
      
      #southtechTimeoutWarningModal .btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(0,0,0,0.2);
      }
      
      /* Modal timeout scaduto */
      #southtechTimeoutExpiredModal .modal-content {
          border-radius: 20px;
          box-shadow: 0 25px 80px rgba(0,0,0,0.5);
          border: none;
      }
      
      #southtechTimeoutExpiredModal .modal-header {
          border-radius: 20px 20px 0 0;
          border-bottom: none;
      }
      
      #southtechTimeoutExpiredModal {
          z-index: 3000 !important;
      }
      </style>
  `;
  
  document.head.insertAdjacentHTML('beforeend', css);
}

// ====================================================================
// ESPORTAZIONE E COMPATIBILITÀ
// ====================================================================

// Compatibilità con sistema precedente
if (typeof window !== 'undefined') {
  // API principale
  window.SouthTechTimeout = {
      initialize: initializeSouthTechTimeout,
      cleanup: cleanupSouthTechTimeout,
      reset: recordUserActivity,
      checkState: checkPageState, // ✅ NUOVA API
      
      // Funzioni di stato
      getStatus: () => {
          const now = Date.now();
          const lastActivity = SOUTHTECH_TIMEOUT_V4.state.lastActivity || now;
          const inactiveTime = now - lastActivity;
          
          return {
              isAuthenticated: SOUTHTECH_TIMEOUT_V4.state.isAuthenticated,
              tabId: SOUTHTECH_TIMEOUT_V4.state.tabId,
              lastActivity: new Date(lastActivity).toLocaleString(),
              inactiveMinutes: Math.round(inactiveTime / 1000 / 60),
              warningShown: SOUTHTECH_TIMEOUT_V4.state.warningShown,
              pageVisible: SOUTHTECH_TIMEOUT_V4.state.pageVisible,
              timeoutLimit: '30 minuti', // ✅ SEMPRE 30 minuti
              version: '4.1.0'
          };
      }
  };
  
  // Backward compatibility
  window.initializeSouthTechTimeout = initializeSouthTechTimeout;
  window.cleanupSouthTechTimeout = cleanupSouthTechTimeout;
  window.resetSouthTechTimer = recordUserActivity;
}

// ====================================================================
// AUTO-INITIALIZATION
// ====================================================================

// Log inizializzazione modulo
console.log('📦 [SouthTech Timeout] Modulo v4.1.0 caricato con successo');
console.log('🎯 [SouthTech Timeout] CORREZIONI: Warning persistente, No debug mode, Controllo stato separato');

// Auto-cleanup su visibilità pagina
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
      // Quando la pagina si nasconde, registra timestamp per controllo futuro
      if (SOUTHTECH_TIMEOUT_V4.state.isAuthenticated && SOUTHTECH_TIMEOUT_V4.state.lastActivity) {
          localStorage.setItem('southtech_global_last_activity', SOUTHTECH_TIMEOUT_V4.state.lastActivity.toString());
      }
  }
});

console.log('✅ [SouthTech Timeout v4.1] Sistema CORRETTO pronto all\'uso');
