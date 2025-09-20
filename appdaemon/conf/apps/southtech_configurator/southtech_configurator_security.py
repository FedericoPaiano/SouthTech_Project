import os
import json
import hashlib
import secrets
import time
from datetime import datetime, timedelta

class SouthTechConfiguratorSecurity:
    """
    🛡️ SOUTHTECH CONFIGURATOR SECURITY
    Gestisce autenticazione, sicurezza, anti-bruteforce e tutti gli endpoint API
    """
    
    def __init__(self, configurator):
        """Inizializza il modulo security"""
        self.configurator = configurator
        # Rimosse le assegnazioni dirette dei metodi di logging,
        # si userà self.configurator.log/error/warning direttamente.
        
        self.configurator.log("🛡️ Inizializzazione modulo Security...")
        
        # Carica dati di sicurezza esistenti
        self.load_security_data()
        
        # Migrazione sistema sicurezza se necessario
        self.migrate_to_secure_system()
        
        self.configurator.log("✅ Modulo Security inizializzato")

    # ===============================================================
    # GESTIONE UTENTI E ANTI-BRUTEFORCE
    # ===============================================================

    def get_user_id_unified(self, data, method_type="api"):
        """
        🎯 METODO UNIFICATO per estrarre User ID
        Sostituisce get_user_id() e get_user_id_from_request()
        """
        try:
            # 1. Prova browser_id (metodo principale)
            browser_id = data.get("browser_id", "")
            if browser_id:
                # Usa sempre prefisso "user" per consistenza
                return f"user_{browser_id}"
            
            # 2. Fallback: headers per API dirette
            if method_type == "api":
                headers = data.get("__headers", {})
                user_agent = headers.get("User-Agent", "")
                if user_agent:
                    user_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
                    return f"user_agent_{user_hash}"
            
            # 3. Fallback finale con timestamp
            timestamp = int(time.time())
            return f"user_unknown_{timestamp}"
            
        except Exception as e:
            self.configurator.error(f"Errore get_user_id_unified: {e}")
            return f"user_error_{int(time.time())}"

    def get_fallback_level(self, method_type):
        """Restituisce il livello di fallback del metodo"""
        levels = {
            "websocket": 0,  # Primario
            "sensor": 1,     # Fallback 1
            "file": 2        # Fallback 2
        }
        return levels.get(method_type, 99)
    
    def is_user_blocked(self, user_id):
        """Controlla se un utente è bloccato"""
        if user_id in self.configurator.blocked_users:
            block_until = self.configurator.blocked_users[user_id]
            if time.time() < block_until:
                return True, block_until
            else:
                # Blocco scaduto, rimuovi
                del self.configurator.blocked_users[user_id]
                if user_id in self.configurator.attempt_counters:
                    del self.configurator.attempt_counters[user_id]
                self.save_security_data()
        return False, None

    def is_new_request(self, request_type, attributes):
        """Verifica se è una nuova richiesta basandosi su timestamp"""
        request_timestamp = attributes.get('timestamp')
        if not request_timestamp:
            return True
            
        last_processed = self.configurator.last_processed.get(request_type)
        if last_processed != request_timestamp:
            self.configurator.last_processed[request_type] = request_timestamp
            return True
            
        return False
    
    def record_attempt(self, user_id, attempt_type, success=False):
        """Registra un tentativo di accesso"""
        current_time = time.time()
        
        if success:
            # Reset contatori per successo
            if user_id in self.configurator.attempt_counters:
                del self.configurator.attempt_counters[user_id]
            if user_id in self.configurator.blocked_users:
                del self.configurator.blocked_users[user_id]
            self.log_security_event(user_id, attempt_type, "SUCCESS", "Accesso riuscito")
            self.save_security_data()
            return
        
        # Registra fallimento
        if user_id not in self.configurator.attempt_counters:
            self.configurator.attempt_counters[user_id] = {}
        
        if attempt_type not in self.configurator.attempt_counters[user_id]:
            self.configurator.attempt_counters[user_id][attempt_type] = 0
        
        self.configurator.attempt_counters[user_id][attempt_type] += 1
        total_attempts = sum(self.configurator.attempt_counters[user_id].values())
        
        self.log_security_event(user_id, attempt_type, "FAILED", 
                               f"Tentativo {total_attempts}/3 fallito")
        
        # Blocca se raggiunge 3 tentativi totali
        if total_attempts >= 3:
            block_until = current_time + (5 * 60)  # 5 minuti
            self.configurator.blocked_users[user_id] = block_until
            self.log_security_event(user_id, "BLOCK", "CRITICAL", 
                                   f"Utente bloccato per 5 minuti (fino alle {datetime.fromtimestamp(block_until).strftime('%H:%M:%S')})")
            
            # Notifica Home Assistant
            self.create_ha_notification(
                f"⚠️ SouthTech: Utente bloccato",
                f"Troppi tentativi falliti. Utente {user_id[:20]} bloccato fino alle {datetime.fromtimestamp(block_until).strftime('%H:%M:%S')}"
            )
        
        self.save_security_data()
    
    def log_security_event(self, user_id, event_type, level, message):
        """Registra eventi di sicurezza"""
        timestamp = datetime.now().isoformat()
        
        # Log in AppDaemon
        log_msg = f"🛡️ SECURITY [{level}] {user_id[:20]}: {event_type} - {message}"
        if level == "CRITICAL":
            self.configurator.error(log_msg)
        elif level == "WARNING":
            self.configurator.warning(log_msg)
        else:
            self.configurator.log(log_msg)
        
        # Aggiorna sensore HA
        try:
            self.configurator.set_state("sensor.southtech_security_log",
                          state=level.lower(),
                          attributes={
                              "last_event": timestamp,
                              "user_id": user_id[:20],
                              "event_type": event_type,
                              "message": message,
                              "blocked_users": len(self.configurator.blocked_users),
                              "total_attempts": sum(len(attempts) for attempts in self.configurator.attempt_counters.values())
                          })
        except Exception as e:
            self.configurator.error(f"Errore aggiornamento sensore sicurezza: {e}")
    
    def create_ha_notification(self, title, message):
        """Crea notifica persistente in Home Assistant"""
        try:
            self.configurator.call_service("persistent_notification/create",
                            title=title,
                            message=message,
                            notification_id=f"southtech_security_{int(time.time())}")
        except Exception as e:
            self.configurator.error(f"Errore creazione notifica HA: {e}")

    # ===============================================================
    # GESTIONE DATI DI SICUREZZA
    # ===============================================================
    
    def load_security_data(self):
        """Carica dati di sicurezza da file"""
        try:
            if os.path.exists(self.configurator.security_file):
                with open(self.configurator.security_file, 'r') as f:
                    data = json.load(f)
                    self.configurator.blocked_users = data.get("blocked_users", {})
                    self.configurator.attempt_counters = data.get("attempt_counters", {})
                    
                    # Rimuovi blocchi scaduti
                    current_time = time.time()
                    expired_blocks = [uid for uid, until in self.configurator.blocked_users.items() 
                                    if current_time >= until]
                    for uid in expired_blocks:
                        del self.configurator.blocked_users[uid]
                        if uid in self.configurator.attempt_counters:
                            del self.configurator.attempt_counters[uid]
                    
                    if expired_blocks:
                        self.save_security_data()
                    
                    self.configurator.log(f"🛡️ Caricati dati sicurezza: {len(self.configurator.blocked_users)} utenti bloccati")
            else:
                # Crea file security vuoto iniziale
                self.configurator.blocked_users = {}
                self.configurator.attempt_counters = {}
                self.save_security_data()
                self.configurator.log("🛡️ Creato file security.json iniziale")
                
        except Exception as e:
            self.configurator.error(f"Errore caricamento dati sicurezza: {e}")
            self.configurator.blocked_users = {}
            self.configurator.attempt_counters = {}
            # Prova a creare file iniziale
            try:
                self.save_security_data()
            except:
                pass
    
    def save_security_data(self, kwargs=None):
        """Salva dati di sicurezza su file"""
        try:
            # Assicurati che la directory json esista
            os.makedirs(os.path.dirname(self.configurator.security_file), exist_ok=True)
            
            data = {
                "blocked_users": self.configurator.blocked_users,
                "attempt_counters": self.configurator.attempt_counters,
                "last_save": datetime.now().isoformat()
            }
            with open(self.configurator.security_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.configurator.error(f"Errore salvataggio dati sicurezza: {e}")
    
    def cleanup_expired_blocks(self, kwargs):
        """Pulisce blocchi scaduti"""
        current_time = time.time()
        expired = []
        
        for user_id, block_until in self.configurator.blocked_users.items():
            if current_time >= block_until:
                expired.append(user_id)
        
        for user_id in expired:
            del self.configurator.blocked_users[user_id]
            if user_id in self.configurator.attempt_counters:
                del self.configurator.attempt_counters[user_id]
            self.log_security_event(user_id, "UNBLOCK", "INFO", "Blocco scaduto")
        
        if expired:
            self.save_security_data()

    # ===============================================================
    # GESTIONE TOKEN
    # ===============================================================
    
    def generate_token(self):
        """Genera un token di sessione"""
        token = secrets.token_urlsafe(32)
        token_data = {
            "created_at": time.time(),
            "expires_at": time.time() + (8 * 3600)  # 8 ore
        }
        self.configurator.active_tokens[token] = token_data
        return token
    
    def verify_token(self, token):
        """Verifica validità del token"""
        if not token or token not in self.configurator.active_tokens:
            return False
        
        token_data = self.configurator.active_tokens[token]
        if time.time() > token_data["expires_at"]:
            del self.configurator.active_tokens[token]
            return False
        
        return True
    
    def cleanup_expired_tokens(self, kwargs):
        """Rimuove i token scaduti"""
        current_time = time.time()
        expired_tokens = [
            token for token, data in self.configurator.active_tokens.items()
            if current_time > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self.configurator.active_tokens[token]
        
        if expired_tokens:
            self.configurator.log(f"🧹 Rimossi {len(expired_tokens)} token scaduti")

    # ===============================================================
    # SISTEMA HASH SICURO
    # ===============================================================
    
    def calculate_client_hash(self, password, browser_id, timestamp):
        """
        🔐 Calcola hash client-side per confronto - VERSIONE CORRETTA
        Deve produrre lo stesso hash del JavaScript
        """
        try:
            # FIX: Usa salt fisso senza timestamp (come nel frontend)
            salt = f"southtech_{browser_id}_fixed_security_salt"
            
            # 2. Combina password + salt (stesso ordine del client)
            password_with_salt = f"{password}{salt}"
            
            # 3. Genera hash SHA-256
            hash_bytes = hashlib.sha256(password_with_salt.encode('utf-8')).digest()
            
            # 4. Converti in hex (stesso formato del client)
            hash_hex = hash_bytes.hex()
            
            return hash_hex
            
        except Exception as e:
            self.configurator.error(f"Errore calcolo hash client: {e}")
            return None

    def verify_password_hash(self, provided_hash, stored_password, browser_id, timestamp):
        """
        🔍 Verifica hash password confrontando con password salvata
        """
        try:
            # Calcola hash della password salvata con stesso salt
            expected_hash = self.calculate_client_hash(stored_password, browser_id, timestamp)
            
            if not expected_hash:
                return False
                
            # Confronto sicuro degli hash
            return provided_hash == expected_hash
            
        except Exception as e:
            self.configurator.error(f"Errore verifica hash password: {e}")
            return False

    def migrate_to_secure_system(self):
        """
        🔄 Migra sistema esistente al nuovo metodo sicuro
        Aggiunge stored_password ai file auth esistenti
        """
        try:
            if not os.path.exists(self.configurator.auth_file):
                return
                
            with open(self.configurator.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            # Se non ha stored_password, non può usare hash sicuro
            if "stored_password" not in auth_data:
                self.configurator.log("⚠️ Sistema auth legacy rilevato - hash sicuro limitato")
                auth_data["security_method"] = "legacy_only"
                auth_data["migration_note"] = "Reset password per abilitare sicurezza completa"
                
                # Assicurati che la directory json esista
                os.makedirs(os.path.dirname(self.configurator.auth_file), exist_ok=True)
                
                with open(self.configurator.auth_file, 'w') as f:
                    json.dump(auth_data, f, indent=2)
            
        except Exception as e:
            self.configurator.error(f"Errore migrazione sicurezza: {e}")

    def save_auth_data_unified(self, password_data, user_id, method):
        """Salva dati auth con metodo unificato - VERSIONE CORRETTA"""
        try:
            if method.startswith("client_hash"):
                # CORREZIONE: Salva hash direttamente senza manipolazioni
                auth_data = {
                    "password_hash": password_data,  # ← Hash già corretto dal frontend
                    "stored_password": None,
                    "salt": None,
                    "security_method": method,
                    "created_at": datetime.now().isoformat(),
                    "created_by": user_id[:20]
                }
                self.configurator.log(f"🔐 Salvando hash diretto: {password_data[:10]}...")
            else:
                # Metodo legacy con salt
                salt = secrets.token_hex(32)
                password_hash = hashlib.sha256((password_data + salt).encode()).hexdigest()
                auth_data = {
                    "password_hash": password_hash,
                    "stored_password": password_data,  # ← Salva anche password per compatibilità
                    "salt": salt,
                    "security_method": "server_unified",
                    "created_at": datetime.now().isoformat(),
                    "created_by": user_id[:20]
                }
                self.configurator.log(f"🔐 Salvando con salt: password={password_data[:3]}..., salt={salt[:10]}...")
            
            # Assicurati che la directory json esista
            os.makedirs(os.path.dirname(self.configurator.auth_file), exist_ok=True)
            
            # Scrivi file auth
            with open(self.configurator.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            self.configurator.communication.update_auth_status_file()
            self.configurator.log(f"✅ Setup completato con metodo {method}")
            
            # DEBUG: Verifica cosa è stato salvato
            self.configurator.log(f"🔍 AUTH FILE SALVATO: {auth_data}")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore salvataggio auth data: {e}")
            raise

    # ===============================================================
    # API ENDPOINTS - CONTROLLI DI SICUREZZA
    # ===============================================================
    
    def api_check_blocked(self, data):
        """Controlla se un utente è bloccato - CORRETTO"""
        try:
            # CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            is_blocked, block_until = self.is_user_blocked(user_id)
            
            result = {
                "blocked": is_blocked,
                "user_id": user_id[:20]
            }
            
            if is_blocked:
                result["block_until"] = block_until
                result["remaining_seconds"] = int(block_until - time.time())
            
            return result, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def api_validate_token(self, data):
        """Valida token Home Assistant - CORRETTO"""
        try:
            # CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            ha_token = data.get("ha_token")
            if not ha_token:
                self.record_attempt(user_id, "token_validation", False)
                return {"error": "Token richiesto"}, 400
            
            if len(ha_token) < 50:
                self.record_attempt(user_id, "token_validation", False)
                return {"error": "Token non valido"}, 401
            
            self.record_attempt(user_id, "token_validation", True)
            has_password = os.path.exists(self.configurator.auth_file)
            
            return {
                "valid": True,
                "has_password": has_password,
                "user_id": user_id[:20]
            }, 200
            
        except Exception as e:
            return {"error": str(e)}, 500

    # ===============================================================
    # API ENDPOINTS - AUTENTICAZIONE
    # ===============================================================
    
    def api_auth_status(self, data):
        """Controlla se esiste una password configurata"""
        self.configurator.log("🔍 AUTH STATUS: Endpoint chiamato via API diretta")
        try:
            result = {"has_password": os.path.exists(self.configurator.auth_file)}
            self.configurator.log(f"🔍 AUTH STATUS: Ritornando {result}")
            return result, 200
        except Exception as e:
            self.configurator.error(f"❌ AUTH STATUS: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_setup(self, data):
        """Setup iniziale della password con sicurezza - CORRETTO"""
        try:
            # CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            self.configurator.log(f"🔍 API SETUP: Richiesta da {user_id[:20]}")
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            if os.path.exists(self.configurator.auth_file):
                self.record_attempt(user_id, "password_setup", False)
                return {"error": "Password già configurata"}, 400
            
            password = data.get("password")
            password_confirm = data.get("password_confirm")
            
            if not password or not password_confirm:
                self.record_attempt(user_id, "password_setup", False)
                return {"error": "Password e conferma richieste"}, 400
            
            if password != password_confirm:
                self.record_attempt(user_id, "password_setup", False)
                return {"error": "Le password non coincidono"}, 400
            
            if len(password) < 6:
                self.record_attempt(user_id, "password_setup", False)
                return {"error": "Password troppo corta (minimo 6 caratteri)"}, 400
            
            salt = secrets.token_hex(32)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            auth_data = {
                "password_hash": password_hash,
                "salt": salt,
                "created_at": datetime.now().isoformat(),
                "last_changed": datetime.now().isoformat(),
                "created_by": user_id[:20]
            }
            
            # Assicurati che la directory json esista
            os.makedirs(os.path.dirname(self.configurator.auth_file), exist_ok=True)
            
            with open(self.configurator.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            token = self.generate_token()
            self.configurator.communication.update_auth_status_file()
            self.record_attempt(user_id, "password_setup", True)
            
            self.configurator.log("✅ Password configurata con successo")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.configurator.error(f"❌ API SETUP: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_login(self, data):
        """Login con password con sicurezza - VERSIONE SICURA"""
        try:
            user_id = self.get_user_id_unified(data, "api")
            self.configurator.log(f"🔍 API LOGIN: Richiesta da {user_id[:20]}")
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            if not os.path.exists(self.configurator.auth_file):
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password non configurata"}, 400
            
            # SUPPORTO HASH SICURO
            password = data.get("password")  # Legacy
            password_hash = data.get("password_hash")  # Sicuro
            security_method = data.get("security_method", "legacy")
            browser_id = data.get("browser_id", "")
            timestamp = data.get("timestamp", "")
            
            if not password and not password_hash:
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password richiesta"}, 400
            
            with open(self.configurator.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            login_success = False
            
            if security_method == "client_hash_sha256" and password_hash:
                # Hash sicuro
                stored_password = auth_data.get("stored_password")
                if stored_password:
                    login_success = self.verify_password_hash(password_hash, stored_password, browser_id, timestamp)
                else:
                    self.record_attempt(user_id, "password_login", False)
                    return {"error": "Sistema di sicurezza aggiornato. Resetta la password."}, 400
            else:
                # Legacy
                salt = auth_data["salt"]
                stored_hash = auth_data["password_hash"]
                provided_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                login_success = (provided_hash == stored_hash)
            
            if not login_success:
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password non corretta"}, 401
            
            token = self.generate_token()
            self.record_attempt(user_id, "password_login", True)
            
            self.configurator.log("✅ Login effettuato con successo (API sicura)")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.configurator.error(f"❌ API LOGIN: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_change(self, data):
        """Cambio password"""
        self.configurator.log("🔍 AUTH CHANGE: Endpoint chiamato via API diretta")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Token non valido"}, 401
            
            old_password = data.get("old_password")
            new_password = data.get("new_password")
            
            if not old_password or not new_password:
                return {"error": "Password richieste"}, 400
            
            if len(new_password) < 6:
                return {"error": "Nuova password troppo corta"}, 400
            
            # Carica i dati di autenticazione
            with open(self.configurator.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            # Verifica password attuale
            salt = auth_data["salt"]
            stored_hash = auth_data["password_hash"]
            old_hash = hashlib.sha256((old_password + salt).encode()).hexdigest()
            
            if old_hash != stored_hash:
                return {"error": "Password attuale non corretta"}, 401
            
            # Genera nuovo salt e hash
            new_salt = secrets.token_hex(32)
            new_hash = hashlib.sha256((new_password + new_salt).encode()).hexdigest()
            
            # Aggiorna i dati
            auth_data.update({
                "password_hash": new_hash,
                "salt": new_salt,
                "last_changed": datetime.now().isoformat()
            })
            
            # Assicurati che la directory json esista
            os.makedirs(os.path.dirname(self.configurator.auth_file), exist_ok=True)
            
            with open(self.configurator.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            # Invalida tutti i token esistenti
            self.configurator.active_tokens.clear()
            
            self.configurator.log("✅ Password cambiata con successo via API")
            return {"success": True}, 200
            
        except Exception as e:
            self.configurator.error(f"❌ AUTH CHANGE: Errore: {e}")
            return {"error": str(e)}, 500

    # ===============================================================
    # API ENDPOINTS - SISTEMA
    # ===============================================================
    
    def api_reset_system(self, data):
        """Reset completo del sistema - CORRETTO"""
        try:
            # CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            self.configurator.log(f"🔄 RESET SISTEMA richiesto da {user_id[:20]}")
            
            if os.path.exists(self.configurator.auth_file):
                os.remove(self.configurator.auth_file)
                self.configurator.log("🗑️ File auth cancellato")
            
            self.configurator.active_tokens.clear()
            
            if user_id in self.configurator.attempt_counters:
                del self.configurator.attempt_counters[user_id]
            if user_id in self.configurator.blocked_users:
                del self.configurator.blocked_users[user_id]
            
            self.configurator.communication.update_auth_status_file()
            self.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema completato")
            self.save_security_data()
            
            return {"success": True, "message": "Sistema resettato"}, 200
            
        except Exception as e:
            self.configurator.error(f"Errore reset sistema: {e}")
            return {"error": str(e)}, 500

    # ===============================================================
    # API ENDPOINTS - DATI E ENTITÀ
    # ===============================================================
    
    def api_get_entities(self, data):
        """Recupera le entità di Home Assistant - Versione semplificata senza template"""
        self.configurator.log("🔍 ENTITIES: Endpoint chiamato via API diretta (no template)")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            # Recupera tutte le entità (il filtro ora è gestito lato frontend)
            all_states = self.configurator.get_state()
            
            entities = {
                "lights": [],
                "binary_sensors": [],
                "sensors": []
            }
            
            for entity_id, state_obj in all_states.items():
                if entity_id.startswith('light.'):
                    entities["lights"].append({
                        "entity_id": entity_id,
                        "friendly_name": state_obj.get("attributes", {}).get("friendly_name", entity_id)
                    })
                elif entity_id.startswith('binary_sensor.'):
                    entities["binary_sensors"].append({
                        "entity_id": entity_id,
                        "friendly_name": state_obj.get("attributes", {}).get("friendly_name", entity_id)
                    })
                elif entity_id.startswith('sensor.'):
                    # Filtro solo sensori di illuminamento
                    attributes = state_obj.get("attributes", {})
                    device_class = attributes.get("device_class")
                    unit = attributes.get("unit_of_measurement", "").lower()
                    
                    is_illuminance = (
                        device_class == 'illuminance' or
                        'lux' in unit or
                        'illuminance' in entity_id.lower() or
                        'lux' in entity_id.lower()
                    )
                    
                    if is_illuminance:
                        entities["sensors"].append({
                            "entity_id": entity_id,
                            "friendly_name": attributes.get("friendly_name", entity_id)
                        })
            
            # Ordina per nome friendly
            for category in entities.values():
                category.sort(key=lambda x: x["friendly_name"].lower())
            
            self.configurator.log(f"📋 Recuperate: {len(entities['lights'])} luci, {len(entities['binary_sensors'])} sensori binari, {len(entities['sensors'])} sensori lux")
            
            result = {
                "entities": entities,
                "mode": "direct_no_template",
                "total_entities": len(entities['lights']) + len(entities['binary_sensors']) + len(entities['sensors']),
                "timestamp": datetime.now().isoformat()
            }
            
            return result, 200
            
        except Exception as e:
            self.configurator.error(f"❌ ENTITIES: Errore: {e}")
            return {"error": str(e)}, 500

    def api_get_areas(self, data):
        """Restituisce una lista di aree disponibili."""
        self.configurator.log("🔍 AREE: Richiesta lista aree via API")
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401

            # Usa la cache per restituire le aree (se disponibile)
            # Per ora restituiamo un placeholder
            areas = [{"id": "living_room", "name": "Soggiorno"}, {"id": "kitchen", "name": "Cucina"}]
            
            # Ordina per nome
            areas.sort(key=lambda x: x["name"].lower())
            
            self.configurator.log(f"📋 Restituite {len(areas)} aree.")
            return areas, 200

        except Exception as e:
            self.configurator.error(f"❌ AREE: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_sync_configs(self, data):
        """Sincronizza le configurazioni dal file apps.yaml"""
        self.configurator.log("🔍 SYNC: Endpoint chiamato via API diretta")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            configurations = self.configurator.yaml.read_existing_configs()
            
            result = {
                "configurations": configurations,
                "last_sync": datetime.now().isoformat(),
                "file_exists": os.path.exists(self.configurator.apps_yaml_path),
                "yaml_format_support": "dual"
            }
            
            self.configurator.log(f"🔄 Sincronizzate {len(configurations)} configurazioni via API")
            return result, 200
            
        except Exception as e:
            self.configurator.error(f"❌ SYNC: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_save_config(self, data):
        """Salva la configurazione nel file apps.yaml"""
        self.configurator.log("🔍 SAVE: Endpoint chiamato via API diretta")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            yaml_content = data.get("yaml_content")
            configurations = data.get("configurations", [])
            
            if not yaml_content:
                return {"error": "Contenuto YAML richiesto"}, 400
            
            # Usa il modulo YAML per il salvataggio
            result = self.configurator.yaml.execute_save_advanced("api", configurations, data)
            
            response = {
                "success": result.get("success", False),
                "timestamp": datetime.now().isoformat(),
                "yaml_format": "new_extended"
            }
            
            if result.get("success"):
                response.update({
                    "backup_created": result.get("backup_created", False),
                    "configurations_count": len(configurations)
                })
                self.configurator.log("✅ Configurazione salvata con successo via API")
            else:
                response["error"] = result.get("error", "Errore sconosciuto")
                self.configurator.error(f"❌ Errore salvataggio API: {response['error']}")
            
            return response, 200 if result.get("success") else 500
            
        except Exception as e:
            self.configurator.error(f"❌ SAVE: Errore: {e}")
            return {"error": str(e)}, 500

    def api_websocket_save(self, data):
        """Handler WebSocket unificato"""
        try:
            # Verifica token
            token = data.get("token")
            if not self.verify_token(token):
                return {"success": False, "error": "Non autorizzato"}, 401
            
            # Processa salvataggio tramite modulo Communication
            configurations = data.get("configurations", [])
            result = self.configurator.communication.handle_websocket_save(
                namespace=None, 
                domain=None, 
                service=None, 
                kwargs=data
            )
            
            return result, 200
            
        except Exception as e:
            return {"success": False, "error": str(e)}, 500

    # ===============================================================
    # API ENDPOINTS - DIAGNOSTICHE E EMERGENZA
    # ===============================================================
    
    def api_diagnostics(self, data):
        """Endpoint per informazioni diagnostiche"""
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            diagnostics = self.get_diagnostics_info()
            return diagnostics, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def get_diagnostics_info(self):
        """Informazioni diagnostiche complete del sistema"""
        try:
            diagnostics = {
                "system": self.configurator.get_system_info(),
                "files": {
                    "auth_file_exists": os.path.exists(self.configurator.auth_file),
                    "apps_yaml_exists": os.path.exists(self.configurator.apps_yaml_path),
                    "www_path_exists": os.path.exists(self.configurator.www_path),
                    "api_path_exists": os.path.exists(self.configurator.api_path),
                    "backup_path_exists": os.path.exists(self.configurator.backup_path),
                    "security_file_exists": os.path.exists(self.configurator.security_file),
                    "index_html_exists": os.path.exists(os.path.join(self.configurator.www_path, "index.html")),
                    "light_presence_html_exists": os.path.exists(os.path.join(self.configurator.www_path, "light_presence.html"))
                },
                "tokens": {
                    "active_count": len(self.configurator.active_tokens),
                    "tokens_list": [
                        {
                            "token": token[:8] + "...",
                            "created": datetime.fromtimestamp(data["created_at"]).isoformat(),
                            "expires": datetime.fromtimestamp(data["expires_at"]).isoformat(),
                            "expired": time.time() > data["expires_at"]
                        }
                        for token, data in self.configurator.active_tokens.items()
                    ]
                },
                "security": {
                    "blocked_users": len(self.configurator.blocked_users),
                    "attempt_counters": len(self.configurator.attempt_counters),
                    "blocked_details": [
                        {
                            "user_id": uid[:20],
                            "blocked_until": datetime.fromtimestamp(until).isoformat(),
                            "remaining_seconds": max(0, int(until - time.time()))
                        }
                        for uid, until in self.configurator.blocked_users.items()
                    ]
                },
                "configurations": {
                    "count": len(self.configurator.yaml.read_existing_configs()),
                    "valid": True
                },
                "last_check": datetime.now().isoformat()
            }
            
            return diagnostics
            
        except Exception as e:
            self.configurator.error(f"Errore generazione diagnostiche: {e}")
            return {"error": str(e)}
    
    def api_emergency_reset(self, data):
        """Endpoint per reset di emergenza"""
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            success = self.emergency_reset()
            
            if success:
                return {"success": True, "message": "Reset di emergenza completato"}, 200
            else:
                return {"error": "Reset fallito"}, 500
                
        except Exception as e:
            return {"error": str(e)}, 500
    
    def emergency_reset(self):
        """Reset di emergenza del sistema"""
        try:
            self.configurator.log("🚨 EMERGENCY RESET: Avviato reset di emergenza")
            
            # Invalida tutti i token
            self.configurator.active_tokens.clear()
            
            # Reset completo sistema sicurezza
            self.configurator.blocked_users.clear()
            self.configurator.attempt_counters.clear()
            
            # Rimuovi file temporanei
            temp_sensors = [
                "sensor.southtech_setup_request",
                "sensor.southtech_setup_response", 
                "sensor.southtech_login_request",
                "sensor.southtech_login_response",
                "sensor.southtech_reset_request",
                "sensor.southtech_reset_response"
            ]
            
            for sensor in temp_sensors:
                try:
                    self.configurator.set_state(sensor, state="unavailable")
                except:
                    pass
            
            # Pulisci directory API
            if os.path.exists(self.configurator.api_path):
                for filename in os.listdir(self.configurator.api_path):
                    if filename.endswith('.json'):
                        try:
                            os.remove(os.path.join(self.configurator.api_path, filename))
                        except:
                            pass
            
            # Salva dati aggiornati
            self.save_security_data()
            
            # Aggiorna stato sistema
            self.configurator.set_state("sensor.southtech_system_status",
                          state="reset", 
                          attributes={
                              "reset_time": datetime.now().isoformat(),
                              "reason": "emergency_reset",
                              "tokens_cleared": True,
                              "temp_files_cleared": True,
                              "security_counters_reset": True
                          })
            
            self.configurator.log("✅ EMERGENCY RESET: Completato con successo")
            return True
            
        except Exception as e:
            self.configurator.error(f"❌ EMERGENCY RESET: Errore: {e}")
            return False

    # ===============================================================
    # SETUP ENDPOINTS
    # ===============================================================
    
    def setup_endpoints(self):
        """🔧 Registra tutti gli endpoint API AppDaemon"""
        try:
            self.configurator.log("🔗 Registrazione endpoint API...")
            
            # [MODIFICATO] Vengono registrati solo gli endpoint essenziali.
            # Le operazioni di anteprima, salvataggio e sincronizzazione sono ora gestite
            # principalmente dal sistema di comunicazione a sensori.

            # Endpoint per autenticazione e status (usati da index.html)
            self.configurator.register_endpoint(self.api_auth_status, "southtech_auth_status")
            self.configurator.register_endpoint(self.api_auth_setup, "southtech_auth_setup")
            self.configurator.register_endpoint(self.api_auth_login, "southtech_auth_login")
            self.configurator.register_endpoint(self.api_auth_change, "southtech_auth_change")

            # Endpoint di sicurezza e sistema
            self.configurator.register_endpoint(self.api_validate_token, "southtech_validate_token")
            self.configurator.register_endpoint(self.api_reset_system, "southtech_reset_system")
            self.configurator.register_endpoint(self.api_check_blocked, "southtech_check_blocked")

            # Endpoint WebSocket (se ancora utilizzato da altre parti del sistema, es. entity loading)
            self.configurator.register_endpoint(self.configurator.communication.handle_websocket_save, "southtech_save_yaml")

            # Endpoint diagnostici
            self.configurator.register_endpoint(self.api_diagnostics, "southtech_diagnostics")
            self.configurator.register_endpoint(self.api_emergency_reset, "southtech_emergency_reset")
            
            self.configurator.log("✅ Endpoint API essenziali registrati.")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore registrazione endpoint: {e}")
            raise

    # ===============================================================
    # CLEANUP E GESTIONE CONFIGURAZIONE
    # ===============================================================
    
    def on_configuration_change(self, change_type, data):
        """Gestisce notifiche di cambio configurazione per il modulo security"""
        self.configurator.log(f"🛡️ Security: Ricevuta notifica cambio configurazione: {change_type}")
        
        # Per ora non serve gestire cambi di configurazione specifici
        # ma il metodo è disponibile per future estensioni
        pass
    
    def cleanup(self):
        """Cleanup del modulo security alla terminazione"""
        try:
            self.configurator.log("🧹 Security: Inizio cleanup...")
            
            # Salva dati di sicurezza finali
            self.save_security_data()
            
            # Pulisci token attivi
            self.configurator.active_tokens.clear()
            
            # Salva stato finale nel log di sicurezza
            self.log_security_event("system", "CLEANUP", "INFO", "Modulo security terminato")
            
            self.configurator.log("✅ Security: Cleanup completato")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore cleanup security: {e}")
