/**
 * SouthTech Session Guard - Sistema Controllo Sessione Centralizzato
 * Versione: 1.1.1 - CORREZIONE LOOP TIMEOUT
 * 
 * FIXES:
 * - Correzione loop infinito modal timeout
 * - Pulizia forzata su timeout scaduto
 * - Timestamp reset su logout
 * - Disabilitazione controlli durante redirect
 */

// ====================================================================
// CONFIGURAZIONE SESSION GUARD
// ====================================================================

const SOUTHTECH_SESSION_GUARD = {
  // 🕐 CONFIGURAZIONE TIMEOUT (sincronizzata con southtech_timeout.js v4.1)
  INACTIVITY_TIMEOUT: 30 * 60 * 1000,    // 30 minuti
  WARNING_TIME: 5 * 60 * 1000,           // 5 minuti warning
  TOLERANCE: 30 * 1000,                  // ±30 secondi tolleranza
  MAX_DISPLAY_TIME: 60 * 60 * 1000,     // 1 ora - sopra mostra "più di 30 minuti"
  
  // 🔧 STATO
  state: {
      currentPage: '',
      modalShown: false,
      initialized: false,
      redirecting: false,        // ← NUOVO: Flag redirect in corso
      forceCleanup: false        // ← NUOVO: Flag pulizia forzata
  }
};

// ====================================================================
// API PRINCIPALE
// ====================================================================

/**
* 🚀 Inizializzazione Session Guard CORRETTA
* Funzione principale da chiamare all'inizio di ogni pagina autenticata
* 
* @returns {Promise<boolean>} true se sessione valida, false se scaduta
*/
async function initSouthTechSessionGuard() {
  console.log('🛡️ [Session Guard v1.1.1] Inizializzazione controllo sessione');
  
  // ✅ CORREZIONE: Se siamo in redirect, non fare controlli
  if (SOUTHTECH_SESSION_GUARD.state.redirecting) {
      console.log('🛡️ [Session Guard] Redirect in corso - skip controlli');
      return false;
  }
  
  // Identifica pagina corrente
  SOUTHTECH_SESSION_GUARD.state.currentPage = getCurrentPageName();
  console.log(`🛡️ [Session Guard] Pagina corrente: ${SOUTHTECH_SESSION_GUARD.state.currentPage}`);
  
  // ✅ CORREZIONE: Controlla flag di pulizia recente
  const recentCleanup = sessionStorage.getItem('southtech_cleanup_timestamp');
  if (recentCleanup) {
      const cleanupTime = parseInt(recentCleanup);
      const timeSinceCleanup = Date.now() - cleanupTime;
      
      if (timeSinceCleanup < 10000) { // Ultimi 10 secondi
          console.log('🛡️ [Session Guard] Pulizia recente rilevata - skip controllo timeout');
          sessionStorage.removeItem('southtech_cleanup_timestamp');
          SOUTHTECH_SESSION_GUARD.state.initialized = true;
          return true; // Non fare controllo timeout se c'è stata pulizia recente
      }
  }
  
  // Controllo completo sessione (timeout + warning)
  const sessionCheck = performCompleteSessionCheck();
  
  if (sessionCheck.expired) {
      console.log('🛡️ [Session Guard] Sessione scaduta rilevata');
      showSessionExpiredModal(sessionCheck.timeoutInfo);
      return false; // Sessione scaduta
  }
  
  // ✅ NUOVO: Gestione area warning
  if (sessionCheck.showWarning) {
      console.log('🛡️ [Session Guard] Area warning rilevata - delega al sistema timeout');
      
      // Registra attività attuale SENZA resettare timer
      recordCurrentActivity();
      
      // Inizializza sistema timeout che gestirà il warning
      SOUTHTECH_SESSION_GUARD.state.initialized = true;
      
      // Delega al sistema timeout per mostrare il warning
      setTimeout(() => {
          if (typeof checkPageState === 'function') {
              checkPageState(); // Questo mostrerà il warning
          } else if (typeof SOUTHTECH_TIMEOUT_V4 !== 'undefined') {
              // Fallback se checkPageState non disponibile
              console.log('🛡️ [Session Guard] Triggering timeout system check');
          }
      }, 500);
      
      return true; // Sessione valida ma in warning
  }
  
  // Sessione completamente valida - registra attività attuale
  recordCurrentActivity();
  
  SOUTHTECH_SESSION_GUARD.state.initialized = true;
  console.log('✅ [Session Guard] Sessione valida - inizializzazione completata');
  
  return true; // Sessione OK
}

/**
* 📄 Identifica nome pagina corrente
* @returns {string} Nome pagina
*/
function getCurrentPageName() {
  const path = window.location.pathname;
  const filename = path.split('/').pop() || 'unknown';
  
  // Rimuovi estensione
  return filename.replace('.html', '') || 'index';
}

/**
* 🔍 NUOVO: Controllo completo sessione (timeout + warning)
* @returns {object} Risultato controllo completo
*/
function performCompleteSessionCheck() {
  try {
      const timeoutCheck = checkSessionTimeout();
      
      if (timeoutCheck.isExpired) {
          console.log('🛡️ [Session Guard] Sessione SCADUTA');
          return { 
              expired: true, 
              showWarning: false, 
              timeoutInfo: timeoutCheck 
          };
      }
      
      // ✅ NUOVO: Controllo anche area WARNING
      if (timeoutCheck.inWarningZone) {
          console.log('🛡️ [Session Guard] Sessione in AREA WARNING');
          return { 
              expired: false, 
              showWarning: true, 
              timeoutInfo: timeoutCheck 
          };
      }
      
      return { expired: false, showWarning: false };
      
  } catch (error) {
      console.error('❌ [Session Guard] Errore controllo completo:', error);
      return { expired: false, showWarning: false };
  }
}

/**
* ⏰ CORRETTO: Controllo timeout sessione (con area warning)
* @returns {object} Risultato controllo
*/
function checkSessionTimeout() {
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
          console.log('🛡️ [Session Guard] Nessuna attività precedente trovata');
          return { isExpired: false, inWarningZone: false };
      }
      
      const now = Date.now();
      const inactiveTime = now - mostRecentActivity;
      
      // ✅ CORREZIONE: Usa sempre timeout di produzione (rimosso debug mode)
      const timeoutLimit = SOUTHTECH_SESSION_GUARD.INACTIVITY_TIMEOUT;
      const warningLimit = timeoutLimit - SOUTHTECH_SESSION_GUARD.WARNING_TIME;
      
      console.log(`🛡️ [Session Guard] Ultima attività: ${new Date(mostRecentActivity).toLocaleString()}`);
      console.log(`🛡️ [Session Guard] Tempo inattività: ${Math.round(inactiveTime / 1000 / 60)} minuti`);
      console.log(`🛡️ [Session Guard] Limite timeout: ${Math.round(timeoutLimit / 1000 / 60)} minuti`);
      console.log(`🛡️ [Session Guard] Limite warning: ${Math.round(warningLimit / 1000 / 60)} minuti`);
      
      // Gestisci edge cases
      if (mostRecentActivity > now) {
          console.warn('⚠️ [Session Guard] Timestamp futuro - possibile cambio orario sistema');
          return { isExpired: false, inWarningZone: false };
      }
      
      // Controllo timeout con tolleranza
      if (inactiveTime > timeoutLimit + SOUTHTECH_SESSION_GUARD.TOLERANCE) {
          return {
              isExpired: true,
              inWarningZone: false,
              inactiveTime: inactiveTime,
              lastActivity: mostRecentActivity,
              formattedTime: formatInactiveTime(inactiveTime)
          };
      }
      
      // ✅ NUOVO: Controllo area warning
      if (inactiveTime > warningLimit) {
          return {
              isExpired: false,
              inWarningZone: true,
              inactiveTime: inactiveTime,
              lastActivity: mostRecentActivity,
              timeUntilTimeout: timeoutLimit - inactiveTime
          };
      }
      
      return { isExpired: false, inWarningZone: false };
      
  } catch (error) {
      console.error('❌ [Session Guard] Errore controllo timeout:', error);
      return { isExpired: false, inWarningZone: false }; // In caso di errore, non bloccare
  }
}

/**
 * CORREZIONE FORMATTAZIONE TEMPO TIMEOUT
 * 
 * Aggiorna le funzioni di formattazione per mostrare:
 * - "più di 30 minuti" (30-59 min)
 * - "più di 1 ora" (1-1.59 ore)  
 * - "più di 2 ore" (2-2.59 ore)
 * - fino a "più di 24 ore" (24+ ore)
 */

// ====================================================================
// CORREZIONE 1: Session Guard - formatInactiveTime()
// ====================================================================

/**
* 🕐 Formatta tempo inattività per display (CORRETTO - progressivo)
* @param {number} inactiveTime Tempo in millisecondi
* @returns {string} Tempo formattato progressivo
*/
function formatInactiveTime(inactiveTime) {
  const minutes = Math.round(inactiveTime / 1000 / 60);
  const hours = Math.floor(minutes / 60);
  
  console.log(`🕐 [Format] Input: ${inactiveTime}ms = ${minutes} minuti = ${hours} ore`);
  
  // ✅ NUOVA LOGICA PROGRESSIVA
  if (minutes < 30) {
      // Meno di 30 minuti - non dovrebbe mai accadere per timeout scaduto
      return `${minutes} minuti`;
  } else if (minutes < 60) {
      // 30-59 minuti
      return "più di 30 minuti";
  } else if (hours < 2) {
      // 1-1.59 ore
      return "più di 1 ora";
  } else if (hours < 24) {
      // 2-23.59 ore - mostra ore specifiche
      return `più di ${hours} ore`;
  } else {
      // 24+ ore - limite massimo
      return "più di 24 ore";
  }
}

// ====================================================================
// CORREZIONE 2: Timeout Module - formatTimeoutDuration()
// ====================================================================

/**
 * 🕐 Formatta durata timeout per display (CORRETTO - progressivo)
 * @param {number} inactiveTime Tempo in millisecondi
 * @returns {string} Tempo formattato user-friendly
 */
function formatTimeoutDuration(inactiveTime) {
  const minutes = Math.round(inactiveTime / 1000 / 60);
  const hours = Math.floor(minutes / 60);
  
  console.log(`🕐 [Format] Input: ${inactiveTime}ms = ${minutes} minuti = ${hours} ore`);
  
  // ✅ NUOVA LOGICA PROGRESSIVA (identica a formatInactiveTime)
  if (minutes < 30) {
      // Meno di 30 minuti - non dovrebbe mai accadere per timeout scaduto
      return `${minutes} minuti`;
  } else if (minutes < 60) {
      // 30-59 minuti
      return "più di 30 minuti";
  } else if (hours < 2) {
      // 1-1.59 ore
      return "più di 1 ora";
  } else if (hours < 24) {
      // 2-23.59 ore - mostra ore specifiche
      return `più di ${hours} ore`;
  } else {
      // 24+ ore - limite massimo
      return "più di 24 ore";
  }
}

/**
* 📝 Registra attività corrente
*/
function recordCurrentActivity() {
  const now = Date.now();
  
  // Aggiorna timestamp globale
  localStorage.setItem('southtech_global_last_activity', now.toString());
  
  console.log(`📝 [Session Guard] Attività registrata: ${new Date(now).toLocaleString()}`);
}

// ====================================================================
// MODAL SESSIONE SCADUTA - CORREZIONE LOOP
// ====================================================================

/**
* 🚨 Mostra modal sessione scaduta
* @param {object} timeoutInfo Informazioni timeout
*/
function showSessionExpiredModal(timeoutInfo) {
  if (SOUTHTECH_SESSION_GUARD.state.modalShown) {
      return; // Modal già mostrato
  }
  
  SOUTHTECH_SESSION_GUARD.state.modalShown = true;
  
  console.log('🚨 [Session Guard] Mostrando modal sessione scaduta');
  
  // Rimuovi modal esistenti
  removeExistingModals();
  
  // Crea modal
  const modal = createSessionExpiredModal(timeoutInfo);
  document.body.appendChild(modal);
  
  // Aggiungi CSS se necessario
  addSessionGuardCSS();
  
  // ✅ CORREZIONE: Handler migliorato con anti-loop
  window.handleSessionExpiredOK = function() {
      console.log('🚪 [Session Guard v1.1.1] Utente conferma logout - CORREZIONE ANTI-LOOP');
      
      // ✅ STEP 1: Disabilita controlli futuri
      SOUTHTECH_SESSION_GUARD.state.redirecting = true;
      SOUTHTECH_SESSION_GUARD.state.forceCleanup = true;
      
      // ✅ STEP 2: Aggiorna timestamp per evitare re-check
      const now = Date.now();
      localStorage.setItem('southtech_global_last_activity', now.toString());
      sessionStorage.setItem('southtech_cleanup_timestamp', now.toString());
      
      // ✅ STEP 3: Ferma tutti i timer timeout
      if (typeof cleanupSouthTechTimeout === 'function') {
          cleanupSouthTechTimeout();
      }
      if (typeof SouthTechTimeout !== 'undefined' && SouthTechTimeout.cleanup) {
          SouthTechTimeout.cleanup();
      }
      
      // ✅ STEP 4: Rimuovi modal
      removeSessionExpiredModal();
      
      // ✅ STEP 5: Pulizia forzata e redirect
      setTimeout(() => {
          redirectToLoginFixed();
      }, 500); // Piccolo delay per assicurare cleanup
  };
  
  // Esponi anche per uso da timeout system
  window.showSessionExpiredModal = showSessionExpiredModal;
}

/**
* 🏗️ CORRETTA: Crea elemento modal sessione scaduta (sempre 30 minuti)
* @param {object} timeoutInfo Informazioni timeout
* @returns {HTMLElement} Modal element
*/
function createSessionExpiredModal(timeoutInfo) {
  const modal = document.createElement('div');
  modal.id = 'southtechSessionExpiredModal';
  modal.className = 'modal fade show';
  modal.style.display = 'block';
  modal.style.backgroundColor = 'rgba(0,0,0,0.9)';
  modal.style.zIndex = '3000';
  
  // ✅ CORREZIONE: Sempre 30 minuti (rimosso debug mode)
  const timeText = timeoutInfo.formattedTime || "più di 30 minuti";
  const limitText = "30 minuti"; // Sempre 30 minuti
  
  modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
              <div class="modal-header bg-danger text-white">
                  <h5 class="modal-title">
                      <i class="fas fa-exclamation-triangle me-2"></i>Sessione Scaduta
                  </h5>
                  <!-- Modal non dismissibile -->
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
                      <strong>Pagina corrente:</strong> ${getPageDisplayName()}
                  </div>
                  <p class="text-muted small">
                      Per motivi di sicurezza, devi effettuare nuovamente il login.
                  </p>
              </div>
              <div class="modal-footer justify-content-center">
                  <button type="button" class="btn btn-primary btn-lg" onclick="handleSessionExpiredOK()" id="sessionExpiredOkBtn">
                      <i class="fas fa-sign-in-alt me-2"></i>Torna al Login
                  </button>
              </div>
          </div>
      </div>
  `;
  
  return modal;
}

/**
* 📄 Ottieni nome display pagina corrente
* @returns {string} Nome pagina user-friendly
*/
function getPageDisplayName() {
  const pageNames = {
      'index': 'Menu Principale',
      'light_presence': 'Automatismo Luci',
      'monitoring': 'Monitoraggio Sistema'
  };
  
  return pageNames[SOUTHTECH_SESSION_GUARD.state.currentPage] || 
         SOUTHTECH_SESSION_GUARD.state.currentPage;
}

/**
* 🗑️ Rimuovi modal esistenti
*/
function removeExistingModals() {
  // Rimuovi tutti i possibili modal timeout esistenti
  const modalIds = [
      'southtechSessionExpiredModal',
      'southtechImmediateLogoutModal', 
      'southtechTimeoutWarningModal',
      'southtechTimeoutExpiredModal' // Dal timeout system
  ];
  
  modalIds.forEach(id => {
      const modal = document.getElementById(id);
      if (modal) {
          console.log(`🗑️ [Session Guard] Rimuovo modal esistente: ${id}`);
          modal.remove();
      }
  });
}

/**
* 🚫 Rimuovi modal sessione scaduta
*/
function removeSessionExpiredModal() {
  const modal = document.getElementById('southtechSessionExpiredModal');
  if (modal) {
      modal.remove();
  }
  
  SOUTHTECH_SESSION_GUARD.state.modalShown = false;
}

// ====================================================================
// GESTIONE REDIRECT - CORREZIONE LOOP
// ====================================================================

/**
* 🔄 ✅ CORRETTO: Redirect pulito al login con anti-loop
*/
function redirectToLoginFixed() {
  console.log('🔄 [Session Guard v1.1.1] Eseguo redirect CORRETTO con anti-loop');
  
  // ✅ STEP 1: Pulizia sessione FORZATA (ignora tutti i flag)
  forceCleanupSession();
  
  // ✅ STEP 2: Determina strategia redirect
  const currentPage = SOUTHTECH_SESSION_GUARD.state.currentPage;
  
  if (currentPage === 'index') {
      // Su index.html - usa replace per evitare history loop
      console.log('🔄 [Session Guard] Su index.html - replace per reset completo');
      window.location.replace(window.location.href + '?t=' + Date.now());
  } else {
      // Su altre pagine - redirect diretto
      console.log('🔄 [Session Guard] Redirect diretto a index.html');
      window.location.replace('index.html?t=' + Date.now());
  }
}

/**
* 🔄 Redirect pulito al login (versione compatibilità)
*/
function redirectToLogin() {
  console.log('🔄 [Session Guard] Redirect compatibilità - uso versione corretta');
  redirectToLoginFixed();
}

/**
* 🧹 ✅ CORRETTO: Pulizia sessione FORZATA (ignora flag di ritorno al menu)
*/
function forceCleanupSession() {
  console.log('🧹 [Session Guard v1.1.1] PULIZIA FORZATA - ignoro tutti i flag');
  
  // ✅ PULIZIA TOTALE INCONDIZIONATA
  const sessionKeys = [
      'southtech_session_token',
      'southtech_ha_token', 
      'southtech_browser_id',
      'southtech_return_to_menu',
      'southtech_page_source'
  ];
  
  sessionKeys.forEach(key => {
      sessionStorage.removeItem(key);
      console.log(`🗑️ [Force Cleanup] Rimosso: ${key}`);
  });
  
  // ✅ PULISCI ANCHE STORAGE TIMEOUT
  Object.keys(localStorage).forEach(key => {
      if (key.startsWith('southtech_last_activity_') || 
          key === 'southtech_global_last_activity') {
          localStorage.removeItem(key);
          console.log(`🗑️ [Force Cleanup] Rimosso localStorage: ${key}`);
      }
  });
  
  // ✅ RESET TIMESTAMP A VALORE FUTURO (evita re-check)
  const futureTime = Date.now() + (60 * 60 * 1000); // 1 ora nel futuro
  localStorage.setItem('southtech_global_last_activity', futureTime.toString());
  
  // ✅ CLEANUP SISTEMA TIMEOUT
  try {
      if (typeof cleanupSouthTechTimeout === 'function') {
          cleanupSouthTechTimeout();
      }
      if (typeof SouthTechTimeout !== 'undefined' && SouthTechTimeout.cleanup) {
          SouthTechTimeout.cleanup();
      }
  } catch (e) {
      console.warn('⚠️ [Force Cleanup] Errore cleanup timeout:', e);
  }
  
  console.log('✅ [Session Guard] Pulizia FORZATA completata');
}

/**
* 🧹 Pulizia sessione INTELLIGENTE (versione originale per compatibilità)
*/
function cleanupSession() {
  console.log('🧹 [Session Guard] Pulizia sessione in corso');
  
  // ✅ CORREZIONE: Se è impostato forceCleanup, fai pulizia forzata
  if (SOUTHTECH_SESSION_GUARD.state.forceCleanup) {
      console.log('🧹 [Session Guard] Flag forceCleanup attivo - pulizia forzata');
      forceCleanupSession();
      return;
  }
  
  // ✅ CORREZIONE: Controlla se si sta tornando al menu principale
  const returningToMenu = sessionStorage.getItem('southtech_return_to_menu');
  const pageSource = sessionStorage.getItem('southtech_page_source');
  
  if (returningToMenu === 'true' && pageSource) {
      console.log(`🏠 [Session Guard] Ritorno al menu da ${pageSource} - pulizia SELETTIVA`);
      
      // MANTIENI i token di sessione, pulisci solo quello che serve
      console.log('✅ [Session Guard] Pulizia selettiva completata - token preservati per ritorno');
      return; // ← IMPORTANTE: Esce subito senza fare pulizia
  }
  
  // Pulizia completa solo per logout vero o sessione scaduta
  console.log('🧹 [Session Guard] Pulizia COMPLETA (logout o scadenza)');
  forceCleanupSession();
}

// ====================================================================
// UTILITÀ E CONTROLLI
// ====================================================================

/**
* ✅ Verifica se sessione è valida (controllo rapido)
* @returns {boolean} true se valida
*/
function isSessionValid() {
  const check = checkSessionTimeout();
  return !check.isExpired;
}

/**
* 🚨 Forza mostra modal sessione scaduta (per testing)
*/
function forceShowExpiredModal() {
  console.log('🧪 [Session Guard] Forzatura modal per test');
  
  const fakeTimeoutInfo = {
      isExpired: true,
      inactiveTime: 35 * 60 * 1000, // 35 minuti
      lastActivity: Date.now() - (35 * 60 * 1000),
      formattedTime: "35 minuti"
  };
  
  showSessionExpiredModal(fakeTimeoutInfo);
}

/**
* 🧪 Test controllo timeout (per debug)
*/
function testTimeoutCheck() {
  const result = checkSessionTimeout();
  console.log('🧪 [Session Guard] Test controllo timeout:', result);
  return result;
}

// ====================================================================
// CSS STYLING
// ====================================================================

/**
* 🎨 Aggiungi CSS per modal Session Guard
*/
function addSessionGuardCSS() {
  if (document.getElementById('southtech-session-guard-css')) {
      return; // CSS già presente
  }
  
  const css = `
      <style id="southtech-session-guard-css">
      /* SouthTech Session Guard Modal Styles v1.1.1 */
      #southtechSessionExpiredModal .modal-content {
          border-radius: 20px;
          box-shadow: 0 25px 80px rgba(0,0,0,0.5);
          border: none;
          animation: modalFadeIn 0.3s ease-out;
      }
      
      @keyframes modalFadeIn {
          from { 
              opacity: 0; 
              transform: translateY(-30px) scale(0.9); 
          }
          to { 
              opacity: 1; 
              transform: translateY(0) scale(1); 
          }
      }

      #southtechSessionExpiredModal .modal-header {
          border-radius: 20px 20px 0 0;
          border-bottom: none;
          background: linear-gradient(135deg, #dc3545 0%, #b02a37 100%);
      }
      
      #southtechSessionExpiredModal .modal-body {
          padding: 40px 30px;
      }
      
      #southtechSessionExpiredModal .modal-footer {
          border-top: none;
          padding: 20px 30px 40px;
      }
      
      #southtechSessionExpiredModal .btn {
          border-radius: 12px;
          padding: 15px 35px;
          font-weight: 600;
          font-size: 1.1rem;
          transition: all 0.3s ease;
          box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      }
      
      #southtechSessionExpiredModal .btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(0,0,0,0.3);
      }
      
      #southtechSessionExpiredModal .btn-primary {
          background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
          border: none;
      }
      
      #southtechSessionExpiredModal .alert {
          border-radius: 10px;
          border: none;
      }
      
      #southtechSessionExpiredModal {
          z-index: 3000 !important;
          backdrop-filter: blur(5px);
      }
      
      #southtechSessionExpiredModal .modal-dialog {
          z-index: 3001 !important;
      }
      
      #southtechSessionExpiredModal .fas.fa-clock {
          filter: drop-shadow(0 4px 8px rgba(220, 53, 69, 0.3));
      }
      
      /* ✅ CORREZIONE: Impedisci selezione multipla del pulsante */
      #sessionExpiredOkBtn {
          pointer-events: auto;
      }
      
      #sessionExpiredOkBtn:disabled {
          pointer-events: none;
          opacity: 0.6;
      }
      </style>
  `;
  
  document.head.insertAdjacentHTML('beforeend', css);
}

// ====================================================================
// ESPORTAZIONE API
// ====================================================================

// API principale per uso esterno
if (typeof window !== 'undefined') {
  window.SouthTechSessionGuard = {
      // API principale
      init: initSouthTechSessionGuard,
      
      // Utilità controllo
      isValid: isSessionValid,
      check: testTimeoutCheck,
      
      // Gestione modal
      showExpired: forceShowExpiredModal,
      
      // Gestione redirect - ✅ CORRETTE
      redirectToLogin: redirectToLoginFixed,
      cleanup: forceCleanupSession,
      
      // Informazioni
      getCurrentPage: getCurrentPageName,
      getState: () => ({ 
          ...SOUTHTECH_SESSION_GUARD.state,
          version: '1.1.1',
          timeoutLimit: '30 minuti' // Sempre 30 minuti
      })
  };
  
  // Backward compatibility - funzioni dirette
  window.initSouthTechSessionGuard = initSouthTechSessionGuard;
  window.isSessionValid = isSessionValid;
  window.redirectToLogin = redirectToLoginFixed; // ✅ Usa versione corretta
  window.showSessionExpiredModal = showSessionExpiredModal; // Per timeout system
}

// ====================================================================
// INIZIALIZZAZIONE MODULO
// ====================================================================

// Event listeners globali
document.addEventListener('DOMContentLoaded', () => {
  console.log('📦 [Session Guard v1.1.1] Modulo caricato e pronto');
});

// Cleanup su unload
window.addEventListener('beforeunload', () => {
  if (SOUTHTECH_SESSION_GUARD.state.initialized) {
      // Solo pulizia leggera su unload normale
      SOUTHTECH_SESSION_GUARD.state.initialized = false;
  }
});

// Log inizializzazione
console.log('📦 [SouthTech Session Guard] Modulo v1.1.1 caricato con successo');
console.log('🎯 [Session Guard] CORREZIONI: Anti-loop timeout, Pulizia forzata, Redirect migliorato');
console.log('🎯 [Session Guard] API disponibile: SouthTechSessionGuard.init()');

// ====================================================================
// DEBUG HELPERS (AGGIORNATI)
// ====================================================================

// Funzioni globali per debug in console
if (typeof window !== 'undefined') {
  // Helpers per debug rapido
  window.debugSessionGuard = {
      showModal: forceShowExpiredModal,
      checkTimeout: testTimeoutCheck,
      simulateOldActivity: () => {
          const fakeTime = Date.now() - (35 * 60 * 1000); // 35 minuti fa
          localStorage.setItem('southtech_global_last_activity', fakeTime.toString());
          console.log('🧪 Debug: Simulata attività 35 minuti fa');
      },
      simulateWarningArea: () => {
          const fakeTime = Date.now() - (26 * 60 * 1000); // 26 minuti fa (area warning)
          localStorage.setItem('southtech_global_last_activity', fakeTime.toString());
          console.log('🧪 Debug: Simulata attività 26 minuti fa (area warning)');
      },
      clearActivity: () => {
          localStorage.removeItem('southtech_global_last_activity');
          Object.keys(localStorage).forEach(key => {
              if (key.startsWith('southtech_last_activity_')) {
                  localStorage.removeItem(key);
              }
          });
          console.log('🧪 Debug: Pulita tutta l\'attività salvata');
      },
      forceLogout: () => {
          console.log('🧪 Debug: Forzatura logout con pulizia completa');
          SOUTHTECH_SESSION_GUARD.state.forceCleanup = true;
          redirectToLoginFixed();
      },
      getStatus: () => {
          const check = checkSessionTimeout();
          console.log('🧪 Debug Status:', {
              page: getCurrentPageName(),
              sessionValid: !check.isExpired,
              inWarningZone: check.inWarningZone,
              modalShown: SOUTHTECH_SESSION_GUARD.state.modalShown,
              redirecting: SOUTHTECH_SESSION_GUARD.state.redirecting,
              forceCleanup: SOUTHTECH_SESSION_GUARD.state.forceCleanup,
              timeoutLimit: '30 minuti',
              lastActivity: localStorage.getItem('southtech_global_last_activity'),
              version: '1.1.1'
          });
      }
  };
}

console.log('✅ [Session Guard v1.1.1] Sistema CORRETTO anti-loop completo e pronto all\'uso');
