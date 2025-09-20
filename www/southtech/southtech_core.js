/**
 * SouthTech Core Functions - Sistema Completo Aggiornato
 * Versione: 3.1.0 - WebSocket Fix + Tutte le Funzioni Originali
 * 
 * RESPONSABILITÀ:
 * - Validazione accesso e sicurezza
 * - Gestione sessione e token  
 * - Navigazione tra pagine
 * - WebSocket utilities e manager con rilevamento rete intelligente
 * - Utility base di sistema
 */

// ====================================================================
// 🌐 SISTEMA DI RILEVAMENTO RETE AVANZATO (NUOVO)
// ====================================================================

class NetworkDetector {
  static detect() {
      const hostname = window.location.hostname;
      const protocol = window.location.protocol;
      const port = window.location.port;
      
      console.log(`🔍 Analisi rete - Host: ${hostname}, Protocol: ${protocol}, Port: ${port}`);
      
      // Rileva tipo di rete
      const isLocalNetwork = NetworkDetector.isLocalNetwork(hostname);
      
      // Genera URL WebSocket intelligente
      const wsUrl = NetworkDetector.generateWebSocketURL(hostname, protocol, port, isLocalNetwork);
      
      const networkInfo = {
          hostname,
          protocol,
          port,
          isLocalNetwork,
          wsUrl,
          networkType: isLocalNetwork ? 'locale' : 'esterna'
      };
      
      console.log(`🌐 Rete rilevata: ${networkInfo.networkType.toUpperCase()}`);
      console.log(`🔌 URL WebSocket: ${wsUrl}`);
      
      return networkInfo;
  }
  
  static isLocalNetwork(hostname) {
      // Indirizzi locali
      const localPatterns = [
          /^localhost$/,
          /^127\.0\.0\.1$/,
          /\.local$/,
          /^192\.168\./,
          /^10\./,
          /^172\.(1[6-9]|2[0-9]|3[01])\./,
          /^::1$/,
          /^fe80:/
      ];
      
      return localPatterns.some(pattern => pattern.test(hostname));
  }
  
  static generateWebSocketURL(hostname, protocol, port, isLocal) {
      const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
      
      if (isLocal) {
          // 🏠 RETE LOCALE: Usa sempre porta 8123
          return `${wsProtocol}//${hostname}:8123/api/websocket`;
      } else {
          // 🌐 RETE ESTERNA: NON usare porta 8123
          // Se siamo su una porta custom non standard, usala
          if (port && port !== '80' && port !== '443' && port !== '8123') {
              return `${wsProtocol}//${hostname}:${port}/api/websocket`;
          } else {
              // Usa porta standard del protocollo (443 per wss, 80 per ws)
              return `${wsProtocol}//${hostname}/api/websocket`;
          }
      }
  }
}

// ====================================================================
// 🔌 WEBSOCKET MANAGER AGGIORNATO CON RILEVAMENTO RETE
// ====================================================================
class WebSocketManager {
  constructor(haToken) {
      this.haToken = haToken;
      this.socket = null;
      this.messageId = 1;
      this.pendingRequests = new Map();
      this.isConnected = false;
      this.reconnectAttempts = 0;
      this.maxReconnectAttempts = 3;
      
      // 🆕 RILEVAMENTO RETE INTELLIGENTE
      this.networkInfo = NetworkDetector.detect();
      this.wsUrl = this.networkInfo.wsUrl;
      
      console.log(`🔌 [WSManager] Inizializzato per rete ${this.networkInfo.networkType}`);
      console.log(`🔌 [WSManager] URL: ${this.wsUrl}`);
  }

  /**
   * Connette al WebSocket HA con rilevamento rete automatico
   */
  async connect() {
      if (this.isConnected) return true;

      try {
          console.log(`🔌 [WSManager] Connessione a: ${this.wsUrl}`);
          this.socket = new WebSocket(this.wsUrl);
          
          return new Promise((resolve, reject) => {
              // Timeout connessione (più lungo per rete esterna)
              const timeoutDuration = this.networkInfo.isLocalNetwork ? 10000 : 15000;
              const timeout = setTimeout(() => {
                  reject(new Error(`WebSocket timeout (${timeoutDuration/1000}s) - ${this.wsUrl}`));
              }, timeoutDuration);

              this.socket.onopen = () => {
                  console.log(`🔌 [WSManager] Connesso a rete ${this.networkInfo.networkType}`);
                  this.reconnectAttempts = 0;
              };

              this.socket.onmessage = (event) => {
                  this.handleMessage(event);
              };

              this.socket.onerror = (error) => {
                  clearTimeout(timeout);
                  console.error(`❌ [WSManager] Errore rete ${this.networkInfo.networkType}:`, error);
                  reject(error);
              };

              this.socket.onclose = (event) => {
                  console.log(`🔌 [WSManager] Chiuso - Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`);
                  this.isConnected = false;
              };

              // Auto-gestione autenticazione
              this.setupAuthentication(resolve, reject, timeout);
          });
      } catch (error) {
          console.error('❌ [WSManager] Errore connessione:', error);
          throw error;
      }
  }

  /**
   * Gestisce autenticazione automatica
   */
  setupAuthentication(resolve, reject, timeout) {
      const authHandler = (event) => {
          try {
              const message = JSON.parse(event.data);
              
              if (message.type === 'auth_required') {
                  console.log('🔐 [WSManager] Autenticazione richiesta');
                  this.socket.send(JSON.stringify({
                      type: 'auth',
                      access_token: this.haToken
                  }));
              } else if (message.type === 'auth_ok') {
                  console.log('✅ [WSManager] Autenticazione completata');
                  clearTimeout(timeout);
                  this.isConnected = true;
                  this.socket.onmessage = (e) => this.handleMessage(e);
                  resolve(true);
              } else if (message.type === 'auth_invalid') {
                  clearTimeout(timeout);
                  reject(new Error('Token HA non valido per WebSocket'));
              }
          } catch (error) {
              console.error('❌ [WSManager] Errore parsing auth:', error);
          }
      };

      this.socket.onmessage = authHandler;
  }

  /**
   * Gestisce messaggi WebSocket in arrivo
   */
  handleMessage(event) {
      try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'result' && this.pendingRequests.has(message.id)) {
              const { resolve, reject } = this.pendingRequests.get(message.id);
              this.pendingRequests.delete(message.id);
              
              if (message.success) {
                  resolve(message.result || {});
              } else {
                  reject(new Error(message.error?.message || 'WebSocket command failed'));
              }
          }
      } catch (error) {
          console.error('❌ [WSManager] Errore parsing messaggio:', error);
      }
  }

  /**
   * Invia richiesta e attende risposta
   */
  async sendRequest(type, data = {}, timeout = 30000) {
      if (!this.isConnected) {
          await this.connect();
      }

      const id = this.messageId++;
      const request = { id, type, ...data };

      return new Promise((resolve, reject) => {
          // Timeout più lungo per rete esterna
          const actualTimeout = this.networkInfo.isLocalNetwork ? timeout : timeout * 1.5;
          
          // Imposta timeout per richiesta
          const timeoutId = setTimeout(() => {
              if (this.pendingRequests.has(id)) {
                  this.pendingRequests.delete(id);
                  reject(new Error(`Request timeout (${actualTimeout}ms) - ${this.networkInfo.networkType}`));
              }
          }, actualTimeout);

          // Salva resolver con cleanup timeout
          this.pendingRequests.set(id, { 
              resolve: (result) => {
                  clearTimeout(timeoutId);
                  resolve(result);
              },
              reject: (error) => {
                  clearTimeout(timeoutId);
                  reject(error);
              }
          });

          console.log(`📤 [WSManager] Invio richiesta ${type} (ID: ${id}) - ${this.networkInfo.networkType}`);
          this.socket.send(JSON.stringify(request));
      });
  }

  /**
   * Carica aree Home Assistant
   */
  async getAreas() {
      console.log('🏠 [WSManager] Caricamento aree...');
      const result = await this.sendRequest('config/area_registry/list');
      console.log(`✅ [WSManager] Caricate ${result.length} aree`);
      return result;
  }

  /**
   * Carica entity registry
   */
  async getEntityRegistry() {
      console.log('📋 [WSManager] Caricamento entity registry...');
      const result = await this.sendRequest('config/entity_registry/list');
      console.log(`✅ [WSManager] Caricate ${result.length} entità`);
      return result;
  }

  /**
   * Carica device registry  
   */
  async getDeviceRegistry() {
      console.log('🔧 [WSManager] Caricamento device registry...');
      const result = await this.sendRequest('config/device_registry/list');
      console.log(`✅ [WSManager] Caricati ${result.length} dispositivi`);
      return result;
  }

  /**
   * Chiama servizio HA
   */
  async callService(domain, service, serviceData = {}) {
      console.log(`🔧 [WSManager] Chiamata servizio ${domain}.${service}`);
      return this.sendRequest('call_service', {
          domain,
          service,
          service_data: serviceData
      });
  }

  /**
   * Ottiene stati entità
   */
  async getStates() {
      console.log('📊 [WSManager] Caricamento stati entità...');
      return this.sendRequest('get_states');
  }

  /**
   * Riconnessione automatica
   */
  async reconnect() {
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          throw new Error('Max reconnection attempts reached');
      }

      this.reconnectAttempts++;
      console.log(`🔄 [WSManager] Tentativo riconnessione ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
      
      this.disconnect();
      await sleep(1000 * this.reconnectAttempts); // Backoff esponenziale
      return this.connect();
  }

  /**
   * Chiude connessione
   */
  disconnect() {
      console.log('🔌 [WSManager] Disconnessione...');
      
      if (this.socket) {
          this.socket.close();
          this.socket = null;
      }
      
      this.isConnected = false;
      this.pendingRequests.clear();
  }

  /**
   * Stato della connessione
   */
  getStatus() {
      return {
          connected: this.isConnected,
          reconnectAttempts: this.reconnectAttempts,
          pendingRequests: this.pendingRequests.size,
          networkType: this.networkInfo.networkType,
          wsUrl: this.wsUrl
      };
  }
}

// ====================================================================
// 🔐 VALIDAZIONE ACCESSO E SICUREZZA (MANTENUTO ORIGINALE)
// ====================================================================

/**
* Valida l'accesso diretto alle pagine protette
* Utilizzata da: light_presence.html, monitoring.html
*/
async function validateDirectPageAccess() {
  console.log('🔐 Controllo accesso diretto alla pagina...');

  try {
      // Recupera token di sessione
      const authToken = sessionStorage.getItem('southtech_session_token');
      const haToken = sessionStorage.getItem('southtech_ha_token');
      const browserId = sessionStorage.getItem('southtech_browser_id');
      
      // Controllo presenza token
      if (!authToken || !haToken || !browserId) {
          console.log('🔐 Token mancanti - reindirizzo a index');
          redirectToIndex('Token di sessione mancanti');
          return false;
      }
      
      console.log('🔐 Token di sessione presenti, validazione HA...');
      
      // Verifica SOLO il token HA (più affidabile e veloce)
      const response = await fetch('/api/states', {
          method: 'GET',
          headers: {
              'Authorization': `Bearer ${haToken}`,
              'Content-Type': 'application/json'
          }
      });
      
      if (!response.ok) {
          console.log('🔐 Token HA non valido');
          redirectToIndex('Token Home Assistant scaduto');
          return false;
      }
      
      console.log('✅ Accesso autorizzato - token HA valido');
      return true;
      
  } catch (error) {
      console.error('🔐 Errore durante validazione:', error);
      redirectToIndex('Errore di validazione');
      return false;
  }
}

/**
* Valida un token Home Assistant
* Utilizzata da: light_presence.html, monitoring.html
*/
async function validateHAToken(token) {
  try {
      const response = await fetch('/api/states', {
          method: 'GET',
          headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
          }
      });
      return response.ok;
  } catch (error) {
      console.error('🔍 Errore validazione token:', error);
      return false;
  }
}

/**
* Reindirizza alla pagina index con messaggio di errore
* Utilizzata da: tutti i file per gestire errori di accesso
*/
function redirectToIndex(reason) {
  console.log(`🔐 Reindirizzamento: ${reason}`);

  // Pulisci la sessione
  clearSessionTokens();

  // Mostra messaggio e reindirizza
  if (typeof showAlert === 'function') {
      showAlert(`Accesso non autorizzato: ${reason}. Reindirizzamento in corso...`, 'warning');
      setTimeout(() => {
          window.location.href = 'index.html';
      }, 2000);
  } else {
      alert(`Accesso non autorizzato: ${reason}`);
      window.location.href = 'index.html';
  }
}

// ====================================================================
// 💾 GESTIONE SESSIONE E TOKEN (MANTENUTO ORIGINALE)
// ====================================================================

/**
* Salva i token di sessione
* Centralizza la logica di salvataggio token
*/
function saveSessionTokens(authToken, haToken, browserId) {
  if (authToken) sessionStorage.setItem('southtech_session_token', authToken);
  if (haToken) sessionStorage.setItem('southtech_ha_token', haToken);
  if (browserId) sessionStorage.setItem('southtech_browser_id', browserId);

  console.log('💾 Token di sessione salvati');
}

/**
* Recupera i token di sessione
* Centralizza la logica di recupero token
*/
function getSessionTokens() {
  return {
      authToken: sessionStorage.getItem('southtech_session_token'),
      haToken: sessionStorage.getItem('southtech_ha_token'),
      browserId: sessionStorage.getItem('southtech_browser_id')
  };
}

/**
* Pulisce tutti i token di sessione
* Utilizzata in tutte le funzioni logout
*/
function clearSessionTokens() {
  sessionStorage.removeItem('southtech_session_token');
  sessionStorage.removeItem('southtech_ha_token');
  sessionStorage.removeItem('southtech_browser_id');
  sessionStorage.removeItem('southtech_return_to_menu');
  sessionStorage.removeItem('southtech_page_source');

  console.log('🗑️ Token di sessione puliti');
}

// ====================================================================
// 🏠 NAVIGAZIONE TRA PAGINE (MANTENUTO ORIGINALE)
// ====================================================================

/**
* Torna al menu principale (VERSIONE UNIFICATA)
* Utilizzata da: light_presence.html, monitoring.html, e altre pagine secondarie
*/
function goToMainMenu() {
  console.log('🏠 [SouthTech Core] Ritorno al menu principale...');
  
  // Salva token per il ritorno
  const tokens = getSessionTokens();
  if (tokens.authToken && tokens.haToken && tokens.browserId) {
      saveSessionTokens(tokens.authToken, tokens.haToken, tokens.browserId);
      
      // ✅ AGGIUNTA: Imposta pagina corrente per il ritorno
      const currentPage = getCurrentPageName();
      sessionStorage.setItem('southtech_page_source', currentPage);
      
      sessionStorage.setItem('southtech_return_to_menu', 'true');
      console.log(`💾 Token salvati per ritorno da ${currentPage}`);
  } else {
      console.warn('⚠️ Token mancanti durante ritorno al menu');
  }
  
  // Cleanup timeout se attivo
  if (typeof cleanupSouthTechTimeout === 'function') {
      cleanupSouthTechTimeout();
  }
  
  // Reindirizza
  window.location.href = 'index.html';
}

/**
* Esegue logout completo (VERSIONE UNIFICATA)
* Utilizzata da: tutti i file per logout utente
*/
function performLogout() {
  console.log('🚪 [SouthTech Core] Esecuzione logout completo...');
  
  // Cleanup sistema timeout se attivo
  if (typeof cleanupSouthTechTimeout === 'function') {
      console.log('🔒 Cleanup timeout sistema...');
      cleanupSouthTechTimeout();
  }
  
  // Pulisci tutti i token dalla sessione
  console.log('🗑️ Pulizia token di sessione...');
  clearSessionTokens();
  
  // Pulisci anche localStorage se necessario
  try {
      localStorage.removeItem('southtech_browser_id');
      console.log('🗑️ Pulizia localStorage completata');
  } catch (error) {
      console.warn('⚠️ Errore pulizia localStorage:', error);
  }
  
  // Mostra messaggio se possibile
  if (typeof SouthTechUI !== 'undefined' && SouthTechUI.showAlert) {
      SouthTechUI.showAlert('Logout effettuato con successo', 'info', 2000);
  } else if (typeof showAlert === 'function') {
      showAlert('Logout effettuato con successo', 'info', 2000);
  }
  
  // Reindirizza dopo breve pausa
  setTimeout(() => {
      window.location.href = 'index.html';
  }, 1000);
}

// ====================================================================
// 🛠️ UTILITY FUNCTIONS BASE (MANTENUTO ORIGINALE)
// ====================================================================

/**
* Utility per sleep/pausa
* Utilizzata in: light_presence.html per polling asincrono
*/
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
* Polling per risposta da sensore Home Assistant
* Utilizzata da: index.html per operazioni asincrone
* @param {string} sensorName - Nome del sensore da controllare
* @param {number} maxAttempts - Numero massimo di tentativi
* @param {string} haToken - Token Home Assistant (deve essere passato)
*/
async function pollForSensorResponse(sensorName, maxAttempts = 10, haToken) {
  console.log(`🔍 POLLING: Inizio polling per ${sensorName}`);

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
      console.log(`🔍 POLLING: Tentativo ${attempt + 1}/${maxAttempts} per ${sensorName}`);
      
      await sleep(1500); // Usa la funzione sleep già presente nel core
      
      try {
          const response = await fetch(`/api/states/${sensorName}`, {
              headers: { 'Authorization': `Bearer ${haToken}` }
          });
          
          if (response.ok) {
              const data = await response.json();
              console.log(`🔍 POLLING: Risposta ricevuta per ${sensorName}:`, data.state);
              console.log(`🔍 POLLING: Attributi completi per ${sensorName}:`, data.attributes);
              
              if (data.state === 'completed') {
                  const result = data.attributes;
                  
                  // Pulisci il sensore
                  try {
                      await fetch(`/api/states/${sensorName}`, { 
                          method: 'DELETE',
                          headers: { 'Authorization': `Bearer ${haToken}` }
                      });
                      console.log(`🔍 POLLING: Sensore ${sensorName} pulito`);
                  } catch (e) {
                      console.log('🔍 POLLING: Errore pulizia sensore:', e.message);
                  }
                  
                  return { success: true, data: result };
              } else if (data.state === 'error') {
                  // Gestisci errori espliciti dal backend
                  const errorMsg = data.attributes?.error || 'Errore sconosciuto dal server';
                  console.log(`🔍 POLLING: Errore esplicito ricevuto: ${errorMsg}`);
                  throw new Error(errorMsg);
              } else if (data.state === 'pending') {
                  console.log(`🔍 POLLING: ${sensorName} ancora in elaborazione...`);
                  // Continua il polling
              } else {
                  console.log(`🔍 POLLING: Stato inaspettato per ${sensorName}: ${data.state}`);
              }
          } else if (response.status === 404) {
              console.log(`🔍 POLLING: Sensore ${sensorName} non ancora disponibile (404)`);
              // Continua il polling per 404 - normale durante l'attesa
          } else {
              console.log(`🔍 POLLING: Errore HTTP ${response.status} per ${sensorName}`);
              throw new Error(`Errore HTTP ${response.status}`);
          }
      } catch (error) {
          console.log(`🔍 POLLING: Errore tentativo ${attempt + 1}:`, error.message);
          
          // Se non è un 404 o timeout, potrebbe essere un errore serio
          if (!error.message.includes('404') && attempt > 3) {
              console.log(`🔍 POLLING: Errore persistente dopo ${attempt + 1} tentativi`);
          }
      }
  }

  console.log(`🔍 POLLING: Timeout raggiunto per ${sensorName} dopo ${maxAttempts} tentativi`);
  throw new Error('Timeout - nessuna risposta dal server. Verifica che AppDaemon sia attivo.');
}

// ====================================================================
// GESTIONE BROWSER ID CENTRALIZZATA
// ====================================================================

/**
 * 🔧 Ottieni o genera browserId persistente e sicuro
 */
function initializeBrowserId() {
  console.log('🔧 [Browser ID] Inizializzazione ID browser persistente');
  
  // 1. Controlla se esiste già un ID persistente valido
  let savedBrowserId = localStorage.getItem('southtech_persistent_browser_id');
  
  if (savedBrowserId && savedBrowserId.length > 10) {
      console.log('✅ [Browser ID] ID persistente trovato:', savedBrowserId);
      // Sincronizza anche in sessionStorage per altre pagine
      sessionStorage.setItem('southtech_browser_id', savedBrowserId);
      return savedBrowserId;
  }
  
  // 2. Prova dalla sessione corrente
  savedBrowserId = sessionStorage.getItem('southtech_browser_id');
  
  if (savedBrowserId && savedBrowserId.length > 10) {
      console.log('✅ [Browser ID] ID da sessione trovato:', savedBrowserId);
      // Salvalo anche come persistente
      localStorage.setItem('southtech_persistent_browser_id', savedBrowserId);
      return savedBrowserId;
  }
  
  // 3. Genera nuovo ID solo se necessario
  console.log('🆕 [Browser ID] Generazione nuovo ID unico');
  const newBrowserId = generateSecureBrowserId();
  
  // Salva in entrambi i storage
  localStorage.setItem('southtech_persistent_browser_id', newBrowserId);
  sessionStorage.setItem('southtech_browser_id', newBrowserId);
  
  console.log('💾 [Browser ID] Nuovo ID salvato:', newBrowserId);
  return newBrowserId;
}

/**
* 🔐 Genera ID browser sicuro e unico
*/
function generateSecureBrowserId() {
  const timestamp = Date.now();
  const randomPart = Math.random().toString(36).substring(2, 15);
  const extraRandom = Math.random().toString(36).substring(2, 10);
  
  return `stb_${timestamp}_${randomPart}_${extraRandom}`;
}

// ====================================================================
// GESTIONE CREDENZIALI SESSIONE
// ====================================================================

/**
* 📋 Ottieni credenziali dalla sessione corrente
*/
function getSessionCredentials() {
  return {
      authToken: sessionStorage.getItem('southtech_session_token'),
      haToken: sessionStorage.getItem('southtech_ha_token'),
      browserId: sessionStorage.getItem('southtech_browser_id')
  };
}

/**
* 💾 Salva credenziali nella sessione
*/
function setSessionCredentials(authToken, haToken, browserId) {
  if (authToken) sessionStorage.setItem('southtech_session_token', authToken);
  if (haToken) sessionStorage.setItem('southtech_ha_token', haToken);
  if (browserId) sessionStorage.setItem('southtech_browser_id', browserId);
  
  console.log('💾 [Core] Credenziali sessione salvate');
}

/**
* 🧹 Pulisci credenziali sessione
*/
function clearSessionCredentials() {
  const sessionKeys = [
      'southtech_session_token',
      'southtech_ha_token', 
      'southtech_browser_id',
      'southtech_return_to_menu',
      'southtech_page_source'
  ];
  
  sessionKeys.forEach(key => sessionStorage.removeItem(key));
  console.log('🧹 [Core] Credenziali sessione pulite');
}

// ====================================================================
// 🧪 FUNZIONI DI TEST E DEBUG (NUOVO)
// ====================================================================

/**
* Ottieni informazioni di rete
*/
function getNetworkInfo() {
  return NetworkDetector.detect();
}

// ====================================================================
// 🌐 EXPORT GLOBALE COMPLETO
// ====================================================================

// Log di inizializzazione
console.log('🔧 [SouthTech Core] Sistema completo caricato - versione 3.1.0');
console.log('🌐 Informazioni rete:', NetworkDetector.detect());

// Export completo con tutte le funzioni
if (typeof window !== 'undefined') {
  window.SouthTechCore = {
      // 🔐 Sicurezza e Validazione
      validateDirectPageAccess,
      validateHAToken,
      redirectToIndex,
      
      // 💾 Gestione Sessione
      saveSessionTokens,
      getSessionTokens,
      clearSessionTokens,
      
      // 🏠 Navigazione
      goToMainMenu,
      performLogout,
      
      // 🔌 WebSocket (NUOVI + RETROCOMPATIBILITÀ)
      WebSocketManager,
      NetworkDetector,
      
      // 🛠️ Utility Base
      sleep,
      pollForSensorResponse,

      // Browser ID
      initializeBrowserId: initializeBrowserId,
      generateSecureBrowserId: generateSecureBrowserId,
      
      // Credenziali
      getSessionCredentials: getSessionCredentials,
      setSessionCredentials: setSessionCredentials,
      clearSessionCredentials: clearSessionCredentials,
      
      // 🧪 Test e Debug
      getNetworkInfo
  };
}
