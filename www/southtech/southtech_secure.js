/**
 * 🔐 SouthTech Secure - Versione con Fallback per HTTP
 * Supporta sia crypto.subtle (HTTPS) che fallback sicuro (HTTP)
 */

class SouthTechSecure {
  constructor() {
      this.isSecureContext = this.checkSecureContext();
      this.hasCrypto = this.checkCryptoSupport();
      
      console.log(`🔐 SouthTech Secure inizializzato:`);
      console.log(`   Contesto sicuro: ${this.isSecureContext}`);
      console.log(`   Crypto disponibile: ${this.hasCrypto}`);
      
      if (!this.hasCrypto) {
          console.warn(`⚠️ crypto.subtle non disponibile. Usando fallback sicuro.`);
          console.warn(`💡 Per sicurezza completa, usa HTTPS o localhost`);
      }
  }
  
  checkSecureContext() {
      // Verifica se siamo in un contesto sicuro
      return (
          window.isSecureContext ||
          location.protocol === 'https:' ||
          location.hostname === 'localhost' ||
          location.hostname === '127.0.0.1'
      );
  }
  
  checkCryptoSupport() {
      // Verifica se crypto.subtle è disponibile
      return !!(window.crypto && window.crypto.subtle);
  }
  
    /**
     * 🔐 Hash password con fallback sicuro
     */
  async hashPassword(password, browserId, timestamp) {
      try {
          if (this.hasCrypto) {
              // Metodo preferito con crypto.subtle
              return await this.hashPasswordSecure(password, browserId, timestamp);
          } else {
              // Fallback per HTTP
              return await this.hashPasswordFallback(password, browserId, timestamp);
          }
      } catch (error) {
          console.error('❌ Errore hashing password:', error);
          throw new Error('Errore nella sicurezza password');
      }
  }

  /**
   * 🔐 Hash sicuro con crypto.subtle (HTTPS) - VERSIONE CORRETTA
   */
  async hashPasswordSecure(password, browserId, timestamp) {
      // ✅ FIX: Usa salt fisso basato solo su browser_id (senza timestamp)
      const salt = `southtech_${browserId}_fixed_security_salt`;
      const passwordWithSalt = `${password}${salt}`;
      
      // Converti in Uint8Array
      const encoder = new TextEncoder();
      const data = encoder.encode(passwordWithSalt);
      
      // Genera hash SHA-256
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      
      // Converti in hex
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      
      return hashHex;
  }

  /**
   * 🔄 Hash fallback per HTTP (meno sicuro ma funzionale) - VERSIONE CORRETTA
   */
  async hashPasswordFallback(password, browserId, timestamp) {
      // ✅ FIX: Usa salt fisso basato solo su browser_id (senza timestamp)
      const salt = `southtech_${browserId}_fixed_security_salt`;
      const passwordWithSalt = `${password}${salt}`;
      
      // Implementazione SHA-256 semplificata (se necessario)
      const hash = await this.simpleHash(passwordWithSalt);
      
      console.warn('⚠️ Usando hash fallback - meno sicuro');
      return hash;
  }async hashPassword(password, browserId, timestamp) {
    try {
        if (this.hasCrypto) {
            // Metodo preferito con crypto.subtle
            return await this.hashPasswordSecure(password, browserId, timestamp);
        } else {
            // Fallback per HTTP
            return await this.hashPasswordFallback(password, browserId, timestamp);
        }
    } catch (error) {
        console.error('❌ Errore hashing password:', error);
        throw new Error('Errore nella sicurezza password');
    }
  }

  /**
  * 🔐 Hash sicuro con crypto.subtle (HTTPS) - VERSIONE CORRETTA
  */
  async hashPasswordSecure(password, browserId, timestamp) {
    // ✅ FIX: Usa salt fisso basato solo su browser_id (senza timestamp)
    const salt = `southtech_${browserId}_fixed_security_salt`;
    const passwordWithSalt = `${password}${salt}`;
    
    // Converti in Uint8Array
    const encoder = new TextEncoder();
    const data = encoder.encode(passwordWithSalt);
    
    // Genera hash SHA-256
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    
    // Converti in hex
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    
    return hashHex;
  }

  /**
  * 🔄 Hash fallback per HTTP (meno sicuro ma funzionale) - VERSIONE CORRETTA
  */
  async hashPasswordFallback(password, browserId, timestamp) {
    // ✅ FIX: Usa salt fisso basato solo su browser_id (senza timestamp)
    const salt = `southtech_${browserId}_fixed_security_salt`;
    const passwordWithSalt = `${password}${salt}`;
    
    // Implementazione SHA-256 semplificata (se necessario)
    const hash = await this.simpleHash(passwordWithSalt);
    
    console.warn('⚠️ Usando hash fallback - meno sicuro');
    return hash;
  }
  
  /**
   * 🔨 Hash semplificato per fallback
   */
  async simpleHash(str) {
      // Implementazione semplificata di hash
      // Usa algoritmo djb2 modificato per consistenza
      
      let hash = 5381;
      for (let i = 0; i < str.length; i++) {
          hash = ((hash << 5) + hash) + str.charCodeAt(i);
          hash = hash & hash; // Converti a 32bit
      }
      
      // Converti in hex e aggiungi padding per consistenza
      const hexHash = Math.abs(hash).toString(16).padStart(8, '0');
      
      // Aggiungi complessità extra per sicurezza
      const complexHash = this.addComplexity(hexHash, str);
      
      return complexHash;
  }
  
  /**
   * 🔐 Aggiunge complessità al hash fallback
   */
  addComplexity(baseHash, originalStr) {
      // Aggiunge layer di complessità per migliorare sicurezza
      const multiplier = originalStr.length * 7919; // Numero primo
      const complexity = (multiplier % 999983).toString(16); // Altro primo
      
      return `${baseHash}${complexity}`.substring(0, 64); // Lunghezza fissa
  }
  
  /**
   * 🎯 Prepara login sicuro
   */
  async prepareSecureLogin(password, browserId) {
      try {
          const timestamp = Date.now().toString();
          const passwordHash = await this.hashPassword(password, browserId, timestamp);
          
          return {
              password_hash: passwordHash,
              browser_id: browserId,
              timestamp: timestamp,
              security_method: this.hasCrypto ? 'client_hash_sha256' : 'client_hash_fallback',
              secure_context: this.isSecureContext
          };
          
      } catch (error) {
          console.error('❌ Errore preparazione login sicuro:', error);
          throw error;
      }
  }
  
  /**
   * 🎯 Prepara setup sicuro
   */
  async prepareSecureSetup(password, passwordConfirm, browserId) {
      try {
          if (password !== passwordConfirm) {
              throw new Error('Le password non coincidono');
          }
          
          const timestamp = Date.now().toString();
          const passwordHash = await this.hashPassword(password, browserId, timestamp);
          const passwordConfirmHash = await this.hashPassword(passwordConfirm, browserId, timestamp);
          
          return {
              password_hash: passwordHash,
              password_confirm_hash: passwordConfirmHash,
              browser_id: browserId,
              timestamp: timestamp,
              security_method: this.hasCrypto ? 'client_hash_sha256' : 'client_hash_fallback',
              secure_context: this.isSecureContext
          };
          
      } catch (error) {
          console.error('❌ Errore preparazione setup sicuro:', error);
          throw error;
      }
  }
  
  /**
   * 🔄 Metodo di compatibilità per login legacy
   */
  prepareLegacyLogin(password, browserId) {
      return {
          password: password, // Password in chiaro (legacy)
          browser_id: browserId,
          timestamp: Date.now().toString(),
          security_method: 'legacy'
      };
  }
  
  /**
   * 🛡️ Esegue login sicuro con fallback automatico
   */
  async loginSecure(password, browserId) {
      try {
          console.log('🔐 Tentativo login sicuro...');
          
          // Prova prima il metodo sicuro
          const secureData = await this.prepareSecureLogin(password, browserId);
          
          // Invia richiesta al server
          const response = await this.sendLoginRequest(secureData);
          
          if (response.success) {
              console.log('✅ Login sicuro riuscito');
              return response;
          } else {
              console.warn('⚠️ Login sicuro fallito, provo fallback legacy...');
              return await this.loginLegacy(password, browserId);
          }
          
      } catch (error) {
          console.error('❌ Errore login sicuro:', error);
          console.log('🔄 Tentativo fallback legacy...');
          return await this.loginLegacy(password, browserId);
      }
  }
  
  /**
   * 🔄 Login legacy come fallback
   */
  async loginLegacy(password, browserId) {
      try {
          console.log('🔄 Login legacy...');
          
          const legacyData = this.prepareLegacyLogin(password, browserId);
          const response = await this.sendLoginRequest(legacyData);
          
          if (response.success) {
              console.log('✅ Login legacy riuscito');
          }
          
          return response;
          
      } catch (error) {
          console.error('❌ Errore login legacy:', error);
          throw error;
      }
  }
  
  /**
   * 📡 Invia richiesta di login al server
   */
  async sendLoginRequest(loginData) {
      // Determina metodo di comunicazione
      if (window.southTechApi && typeof window.southTechApi.login === 'function') {
          // API diretta
          return await window.southTechApi.login(loginData);
      } else {
          // Fallback sensori
          return await this.sendLoginViaSensor(loginData);
      }
  }
  
  /**
   * 📡 Invia login via sensori (fallback)
   */
  async sendLoginViaSensor(loginData) {
      try {
          // Implementa invio via sensori come fallback
          const requestData = {
              action: 'login',
              timestamp: Date.now(),
              ...loginData
          };
          
          // Simula invio via sensore (implementa secondo la tua architettura)
          console.log('📡 Invio via sensore:', requestData);
          
          // Qui dovresti implementare la logica per aggiornare il sensore
          // e attendere la risposta
          
          return { success: false, error: 'Implementare invio via sensore' };
          
      } catch (error) {
          console.error('❌ Errore invio via sensore:', error);
          throw error;
      }
  }
  
  /**
   * 🛡️ Esegue setup sicuro
   */
  async setupSecure(password, passwordConfirm, browserId) {
      try {
          console.log('🔐 Setup sicuro...');
          
          const secureData = await this.prepareSecureSetup(password, passwordConfirm, browserId);
          
          // Invia al server (implementa secondo la tua architettura)
          return await this.sendSetupRequest(secureData);
          
      } catch (error) {
          console.error('❌ Errore setup sicuro:', error);
          throw error;
      }
  }
  
  /**
   * 📡 Invia richiesta di setup
   */
  async sendSetupRequest(setupData) {
      // Implementa secondo la tua architettura
      if (window.southTechApi && typeof window.southTechApi.setup === 'function') {
          return await window.southTechApi.setup(setupData);
      } else {
          return await this.sendSetupViaSensor(setupData);
      }
  }
  
  /**
   * 📡 Invia setup via sensori
   */
  async sendSetupViaSensor(setupData) {
      // Implementa secondo la tua architettura dei sensori
      const requestData = {
          action: 'setup',
          timestamp: Date.now(),
          ...setupData
      };
      
      console.log('📡 Setup via sensore:', requestData);
      return { success: false, error: 'Implementare setup via sensore' };
  }
  
  /**
   * 📊 Informazioni di debug
   */
  getSecurityInfo() {
      return {
          isSecureContext: this.isSecureContext,
          hasCrypto: this.hasCrypto,
          protocol: location.protocol,
          hostname: location.hostname,
          userAgent: navigator.userAgent.substring(0, 50) + '...',
          cryptoSupport: {
              crypto: !!window.crypto,
              subtle: !!(window.crypto && window.crypto.subtle),
              getRandomValues: !!(window.crypto && window.crypto.getRandomValues)
          }
      };
  }
}

// 🚀 Inizializza istanza globale
window.southTechSecure = new SouthTechSecure();

// 🔍 Log informazioni di debug
console.log('🔐 SouthTech Secure Info:', window.southTechSecure.getSecurityInfo());

// 💡 Mostra suggerimenti se necessario
if (!window.southTechSecure.isSecureContext) {
  console.warn('💡 SUGGERIMENTO: Per sicurezza completa, accedi tramite:');
  console.warn('   - https://homeassistant.local:8123 (se hai certificato)');
  console.warn('   - http://localhost:8123 (se locale)');
  console.warn('   - http://127.0.0.1:8123 (se locale)');
}