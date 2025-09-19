import os
import json
import time
import shutil
from datetime import datetime

class SouthTechConfiguratorCommunication:
    """
    📡 SOUTHTECH CONFIGURATOR COMMUNICATION
    Gestisce comunicazione WebSocket, sensori fallback e file system
    """
    
    def __init__(self, configurator):
        """Inizializza il modulo comunicazione"""
        self.configurator = configurator
        self.version = "4.0.0"
        
        # Variabili specifiche per comunicazione
        self.internal_ws_queue = []
        self.is_processing_ws = False
        self.sensor_locks = {
            'save': False,
            'sync': False,
            'setup': False,
            'login': False,
            'reset': False
        }
        
        self.configurator.log("📡 Modulo Communication inizializzato")

    # ===============================================================
    # WEBSOCKET COMMUNICATION (PRIMARIO)
    # ===============================================================
    
    def websocket_save_service(self, namespace, domain, service, kwargs, **kwds):
        """Handler WebSocket con metodi avanzati"""
        try:
            self.configurator.log("🔌 WEBSOCKET: Ricevuta richiesta (metodo avanzato)")
            
            if kwargs.get("test_mode"):
                return {"test_mode": True, "advanced_processing": True}
            
            configurations = kwargs.get("configurations", [])
            if not configurations:
                return {"success": False, "error": "Configurazioni richieste"}
            
            # USA METODO AVANZATO tramite configurator
            result = self.configurator.yaml.execute_save_advanced("websocket", configurations, kwargs)
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_websocket_save(self, namespace, domain, service, kwargs, **kwds):
        """Handler per servizio WebSocket save"""
        try:
            self.configurator.log("🔌 WEBSOCKET SAVE: Ricevuta richiesta")
            
            # Gestisci test mode
            if kwargs.get("test_mode"):
                return {
                    "test_mode": True,
                    "service_available": True,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Determina tipo di salvataggio basandoti sui parametri dal frontend
            generate_dashboard = kwargs.get("generate_dashboard", False)
            generate_templates = kwargs.get("generate_templates", False)
            action = kwargs.get("action", "save_yaml")
            
            yaml_content = kwargs.get("yaml_content")
            configurations = kwargs.get("configurations", [])
            
            if not yaml_content:
                return {"success": False, "error": "Contenuto YAML mancante"}
            
            # ROUTING INTELLIGENTE tramite configurator
            if action == "save_complete" or generate_dashboard or generate_templates:
                self.configurator.log("✨ WEBSOCKET: Richiesta SALVATAGGIO COMPLETO")
                result = self.configurator.yaml.execute_complete_save_advanced("websocket", configurations, kwargs)
            else:
                self.configurator.log("🔌 WEBSOCKET: Richiesta salvataggio STANDARD")
                result = self.execute_yaml_save_websocket(yaml_content, configurations, "websocket_user")
            
            return result
            
        except Exception as e:
            self.configurator.error(f"Errore WebSocket save: {e}")
            return {"success": False, "error": str(e)}

    def setup_internal_websocket_handler(self):
        """WebSocket handler interno - non esposto come servizio HA"""
        # Crea endpoint interno per comunicazione WebSocket
        self.internal_ws_queue = []
        self.is_processing_ws = False
        
        # Monitor queue ogni secondo
        self.configurator.run_every(self.process_internal_ws_queue, "now+1", 1)

    def setup_websocket_handler(self):
        """Setup handler WebSocket principale"""
        self.configurator.register_endpoint(self.api_websocket_save, "southtech_websocket_save")

    def process_internal_ws_queue(self, kwargs):
        """Processa queue WebSocket interna"""
        if self.is_processing_ws or not self.internal_ws_queue:
            return
            
        self.is_processing_ws = True
        try:
            while self.internal_ws_queue:
                request = self.internal_ws_queue.pop(0)
                self.process_save_request_direct(request)
        finally:
            self.is_processing_ws = False

    def process_save_request_direct(self, request_data):
        """Processa salvataggio diretto senza servizi AppDaemon"""
        try:
            yaml_content = request_data.get('yaml_content')
            configurations = request_data.get('configurations', [])
            
            if not yaml_content:
                return {"success": False, "error": "YAML content missing"}
            
            # Salvataggio diretto con backup atomico
            backup_file = self.create_atomic_backup()
            
            try:
                # Scrittura atomica tramite configurator.yaml
                self.configurator.yaml.atomic_yaml_write(yaml_content)
                
                # Verifica integrità tramite configurator.yaml
                self.configurator.yaml.verify_yaml_integrity(self.configurator.apps_yaml_path)
                
                # Successo - rimuovi backup temporaneo se esiste
                if backup_file:
                    self.cleanup_temp_backup(backup_file)
                
                return {
                    "success": True,
                    "method": "direct_write",
                    "backup_created": backup_file is not None,
                    "configurations_count": len(configurations),
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as write_error:
                # Ripristina da backup in caso di errore
                if backup_file:
                    self.restore_from_backup(backup_file)
                raise write_error
                
        except Exception as e:
            self.configurator.error(f"Errore salvataggio diretto: {e}")
            return {"success": False, "error": str(e)}

    def execute_yaml_save_websocket(self, yaml_content, configurations, user_id):
        """
        Esegue il salvataggio YAML per richiesta WebSocket
        """
        try:
            self.configurator.log("💾 WEBSOCKET: Inizio salvataggio apps.yaml...")
            
            # 1. Backup se file esiste
            backup_file = None
            if os.path.exists(self.configurator.apps_yaml_path):
                backup_file = self.configurator.create_backup()
                self.configurator.log(f"📦 Backup creato: {backup_file}")
            
            # 2. Salva contenuto usando metodo del modulo yaml
            self.configurator.yaml.save_yaml_content_safe(yaml_content)
            
            # 3. Verifica file salvato
            self.configurator.yaml.verify_saved_file(yaml_content)
            
            # 4. Genera helper opzionali
            helpers_created = 0
            try:
                helpers_created = self.configurator.generate_helpers_sync(configurations)
            except Exception as e:
                self.configurator.log(f"⚠️ Warning generazione helper: {e}")
            
            # 5. Risultato successo
            result = {
                "success": True,
                "message": "Configurazione salvata con successo via WebSocket",
                "method": "websocket_direct",
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "helpers_created": helpers_created,
                "configurations_count": len(configurations),
                "file_path": self.configurator.apps_yaml_path,
                "file_size": os.path.getsize(self.configurator.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id[:20]
            }
            
            self.configurator.log("✅ WEBSOCKET: Salvataggio completato con successo")
            
            # Notifica successo
            self.configurator.security.create_ha_notification(
                "✅ SouthTech: Configurazione Salvata",
                f"Apps.yaml aggiornato con {len(configurations)} configurazioni via WebSocket"
            )
            
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ WEBSOCKET: Errore durante salvataggio: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": "websocket_error",
                "timestamp": datetime.now().isoformat()
            }

    def api_websocket_save(self, data):
        """Handler WebSocket unificato"""
        try:
            # Verifica token tramite security
            token = data.get("token")
            if not self.configurator.security.verify_token(token):
                return {"success": False, "error": "Non autorizzato"}, 401
            
            # Processa salvataggio tramite yaml
            configurations = data.get("configurations", [])
            result = self.configurator.yaml.execute_save_advanced("websocket", configurations, data)
            
            return result, 200
            
        except Exception as e:
            return {"success": False, "error": str(e)}, 500

    # ===============================================================
    # SENSOR FALLBACK SYSTEM (FALLBACK 1)
    # ===============================================================
    
    def setup_sensor_fallback(self):
        """Sistema sensori ottimizzato con anti-race-condition"""
        if not hasattr(self, 'sensor_locks'):
            self.sensor_locks = {
                'save': False,
                'sync': False,
                'setup': False,
                'login': False,
                'reset': False,
                'device_config': False
            }

    def monitor_sensor_requests(self, kwargs):
        """Monitor sensori con protezione errori"""
        try:
            current_time = time.time()
            
            # Save Request
            if not self.sensor_locks['save']:
                save_sensor = self.configurator.get_state("sensor.southtech_save_request")
                save_attrs = self.configurator.get_state("sensor.southtech_save_request", attribute="all")
                
                if (save_sensor == "pending" and save_attrs and 
                    self.configurator.security.is_new_request('save', save_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['save'] = True
                    try:
                        self.process_sensor_save_request()
                    finally:
                        self.sensor_locks['save'] = False
            
            # Sync Request  
            if not self.sensor_locks['sync']:
                sync_sensor = self.configurator.get_state("sensor.southtech_sync_request")
                sync_attrs = self.configurator.get_state("sensor.southtech_sync_request", attribute="all")
                
                if (sync_sensor == "pending" and sync_attrs and
                    self.configurator.security.is_new_request('sync', sync_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['sync'] = True
                    try:
                        self.process_sensor_sync_request()
                    finally:
                        self.sensor_locks['sync'] = False
                        
            # Login Request
            if not self.sensor_locks['login']:
                login_sensor = self.configurator.get_state("sensor.southtech_login_request")
                login_attrs = self.configurator.get_state("sensor.southtech_login_request", attribute="all")
                
                if (login_sensor == "pending" and login_attrs and
                    self.configurator.security.is_new_request('login', login_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['login'] = True
                    try:
                        self.process_sensor_login_request()
                    finally:
                        self.sensor_locks['login'] = False
                        
            # Setup Request
            if not self.sensor_locks['setup']:
                setup_sensor = self.configurator.get_state("sensor.southtech_setup_request")
                setup_attrs = self.configurator.get_state("sensor.southtech_setup_request", attribute="all")
                
                if (setup_sensor == "pending" and setup_attrs and
                    self.configurator.security.is_new_request('setup', setup_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['setup'] = True
                    try:
                        self.process_sensor_setup_request()
                    finally:
                        self.sensor_locks['setup'] = False
                        
            # Reset Request
            if not self.sensor_locks['reset']:
                reset_sensor = self.configurator.get_state("sensor.southtech_reset_request")
                reset_attrs = self.configurator.get_state("sensor.southtech_reset_request", attribute="all")
                
                if (reset_sensor == "pending" and reset_attrs and
                    self.configurator.security.is_new_request('reset', reset_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['reset'] = True
                    try:
                        self.process_sensor_reset_request()
                    finally:
                        self.sensor_locks['reset'] = False
            
            # Device Config Request
            if not self.sensor_locks.get('device_config', False):
                device_config_sensor = self.configurator.get_state("sensor.southtech_device_config_request")
                device_config_attrs = self.configurator.get_state("sensor.southtech_device_config_request", attribute="all")
                
                if (device_config_sensor == "pending" and device_config_attrs and 
                    self.configurator.security.is_new_request('device_config', device_config_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['device_config'] = True
                    try:
                        self.process_sensor_device_config_request()
                    finally:
                        self.sensor_locks['device_config'] = False
            
            # Device Config Request
            if not self.sensor_locks.get('device_config', False):
                device_config_sensor = self.configurator.get_state("sensor.southtech_device_config_request")
                device_config_attrs = self.configurator.get_state("sensor.southtech_device_config_request", attribute="all")
                
                if (device_config_sensor == "pending" and device_config_attrs and 
                    self.configurator.security.is_new_request('device_config', device_config_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['device_config'] = True
                    try:
                        self.process_sensor_device_config_request()
                    finally:
                        self.sensor_locks['device_config'] = False
            
            # Device Config Request
            if not self.sensor_locks.get('device_config', False):
                device_config_sensor = self.configurator.get_state("sensor.southtech_device_config_request")
                device_config_attrs = self.configurator.get_state("sensor.southtech_device_config_request", attribute="all")
                
                if (device_config_sensor == "pending" and device_config_attrs and 
                    self.configurator.security.is_new_request('device_config', device_config_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['device_config'] = True
                    try:
                        self.process_sensor_device_config_request()
                    finally:
                        self.sensor_locks['device_config'] = False
                        
        except Exception as e:
            self.configurator.error(f"Errore monitor_sensor_requests: {e}")

    def process_sensor_save_request(self):
        """Processa salvataggio via sensore con metodi avanzati - VERSIONE CORRETTA"""
        try:
            attrs = self.configurator.get_state("sensor.southtech_save_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            configurations = request_data.get("configurations", [])
            
            # [FIX] Estrai il request_id per includerlo nella risposta, garantendo che il frontend corretto riceva i dati.
            request_id = request_data.get("request_id")
            
            # RICONOSCIMENTO MODALITÀ COMPLETA
            action = request_data.get("action", "save_yaml")
            generate_dashboard = request_data.get("generate_dashboard", False)
            generate_templates = request_data.get("generate_templates", False)

            if action == "save_complete" or generate_dashboard or generate_templates:
                self.configurator.log("✨ SENSOR: Richiesta SALVATAGGIO COMPLETO/PULIZIA rilevata")
                result = self.configurator.yaml.execute_complete_save_advanced("sensor", configurations, request_data)
            
            elif action.startswith("save_") and action.endswith("_only"):
                file_type = action.replace("save_", "").replace("_only", "")
                self.configurator.log(f"📡 SENSOR: Richiesta salvataggio SPECIFICO per '{file_type}'")
                result = self.configurator.yaml.execute_single_file_save("sensor", file_type, request_data)
            
            elif action == "preview":
                self.configurator.log("🔍 SENSOR: Richiesta ANTEPRIMA rilevata")
                # Chiama il nuovo metodo centralizzato per generare le anteprime
                result = self.configurator.yaml.execute_preview_generation(configurations)

            else:
                if not configurations:
                    self.create_sensor_save_response({
                        "success": False, 
                        "error": "Configurazioni mancanti per un salvataggio standard."
                    })
                    return
                self.configurator.log("📡 SENSOR: Richiesta salvataggio STANDARD")
                result = self.configurator.yaml.execute_save_advanced("sensor", configurations, request_data)
            
            # [FIX] Aggiungi il request_id al risultato prima di inviare la risposta.
            if request_id and isinstance(result, dict):
                result["request_id"] = request_id

            # Invia risposta
            self.create_sensor_save_response(result)
            self.configurator.set_state("sensor.southtech_save_request", state="completed")
            
        except Exception as e:
            self.configurator.error(f"❌ SENSOR: Errore: {e}")
            self.create_sensor_save_response({"success": False, "error": str(e)})

    def process_sensor_sync_request(self):
        """Processa richiesta sincronizzazione via sensore - VERSIONE CORRETTA"""
        try:
            attrs = self.configurator.get_state("sensor.southtech_sync_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                self.configurator.log("⚠️ Attributi sensore sync mancanti")
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "sync_configurations":
                return
                
            user_id = f"browser_{request_data.get('browser_id', 'unknown')}"
            
            self.configurator.log(f"🔍 SENSOR SYNC: Processando sync da {user_id[:20]}")
            
            # Aggiorna debug
            self.configurator.set_state("sensor.southtech_websocket_debug",
                          state="sync_fallback",
                          attributes={
                              "fallback_method": "sensor_sync",
                              "user_id": user_id[:20],
                              "request_time": datetime.now().isoformat()
                          })
            
            # Controlla se bloccato tramite security
            is_blocked, block_until = self.configurator.security.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            else:
                # Esegui sincronizzazione tramite yaml
                try:
                    configurations = self.configurator.yaml.read_existing_configs()
                    
                    result = {
                        "success": True,
                        "configurations": configurations,
                        "last_sync": datetime.now().isoformat(),
                        "file_exists": os.path.exists(self.configurator.apps_yaml_path),
                        "yaml_format_support": "dual",
                        "method": "sensor_fallback"
                    }
                    
                    self.configurator.security.record_attempt(user_id, "sync_configs", True)
                    self.configurator.log(f"✅ SENSOR SYNC: Caricate {len(configurations)} configurazioni")
                    
                except Exception as e:
                    self.configurator.error(f"❌ SENSOR SYNC: Errore lettura configurazioni: {e}")
                    self.configurator.security.record_attempt(user_id, "sync_configs", False)
                    result = {
                        "success": False,
                        "error": str(e),
                        "method": "sensor_fallback"
                    }
            
            # Crea il sensore di risposta
            self.create_response_sensor("sensor.southtech_sync_response", result)
            
            # Reset sensore richiesta
            self.configurator.set_state("sensor.southtech_sync_request", state="completed")
            
            self.configurator.log("✅ SENSOR SYNC: Completato")
            
        except Exception as e:
            self.configurator.error(f"❌ SENSOR SYNC: Errore: {e}")
            self.create_response_sensor("sensor.southtech_sync_response", 
                                      {"success": False, "error": str(e), "method": "sensor_fallback_error"})

    def process_sensor_login_request(self):
        """Processa richiesta login via sensore - VERSIONE UNIFICATA CORRETTA"""
        try:
            attrs = self.configurator.get_state("sensor.southtech_login_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "login":
                return
                
            user_id = self.configurator.security.get_user_id_unified(request_data, "sensor")
            
            # CORREZIONE: Gestisci sia hash che password legacy
            password = request_data.get("password")
            password_hash = request_data.get("password_hash")
            security_method = request_data.get("security_method", "legacy")
            browser_id = request_data.get("browser_id", "")
            timestamp = request_data.get("timestamp", "")
            
            self.configurator.log(f"🔍 SENSOR LOGIN: Da {user_id[:20]} - Metodo: {security_method}")
            self.configurator.log(f"🔍 LOGIN DEBUG: password={bool(password)}, hash={bool(password_hash)}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.configurator.security.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            elif not os.path.exists(self.configurator.auth_file):
                self.configurator.security.record_attempt(user_id, "password_login", False)
                result = {"success": False, "error": "Password non configurata"}
            else:
                # Carica dati autenticazione
                with open(self.configurator.auth_file, 'r') as f:
                    auth_data = json.load(f)
                
                saved_security_method = auth_data.get("security_method", "legacy")
                self.configurator.log(f"🔐 AUTH FILE: Metodo salvato: {saved_security_method}")
                
                # VERIFICA COMPATIBILITÀ METODI
                login_success = False
                
                if security_method in ["client_hash_sha256", "client_hash_fallback"] and password_hash:
                    # Frontend invia hash
                    if saved_security_method in ["client_hash_sha256", "client_hash_fallback"]:
                        # Confronta hash con hash salvato
                        stored_hash = auth_data.get("password_hash", "")
                        login_success = (password_hash == stored_hash)
                        self.configurator.log(f"🔐 HASH vs HASH: {password_hash[:10]}... vs {stored_hash[:10]}...")
                    else:
                        # Hash vs password: calcola hash della password salvata
                        stored_password = auth_data.get("stored_password", "")
                        if stored_password:
                            expected_hash = self.configurator.security.calculate_client_hash(stored_password, browser_id, timestamp)
                            login_success = (password_hash == expected_hash)
                            self.configurator.log(f"🔐 HASH vs PASSWORD: calcolato {expected_hash[:10]}...")
                        else:
                            login_success = False
                            self.configurator.log("🔐 Nessuna password salvata per calcolo hash")
                            
                elif password:
                    # Frontend invia password in chiaro
                    if saved_security_method in ["client_hash_sha256", "client_hash_fallback"]:
                        # Password vs hash: impossibile, errore
                        login_success = False
                        self.configurator.log("🔐 Incompatibilità: password chiara vs hash salvato")
                    else:
                        # Password vs password: metodo legacy
                        salt = auth_data.get("salt", "")
                        stored_hash = auth_data.get("password_hash", "")
                        if salt and stored_hash:
                            import hashlib
                            provided_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                            login_success = (provided_hash == stored_hash)
                            self.configurator.log(f"🔐 PASSWORD LEGACY: {provided_hash[:10]}... vs {stored_hash[:10]}...")
                        else:
                            # Prova confronto diretto con stored_password
                            stored_password = auth_data.get("stored_password", "")
                            login_success = (password == stored_password)
                            self.configurator.log(f"🔐 PASSWORD DIRETTO: confronto diretto")
                else:
                    # Nessuna password fornita
                    self.configurator.security.record_attempt(user_id, "password_login", False)
                    result = {"success": False, "error": "Password richiesta"}
                    self.create_response_sensor("sensor.southtech_login_response", result)
                    self.configurator.set_state("sensor.southtech_login_request", state="unavailable")
                    return
                
                # RISULTATO FINALE
                if login_success:
                    token = self.configurator.security.generate_token()
                    self.configurator.security.record_attempt(user_id, "password_login", True)
                    result = {"success": True, "token": token}
                    self.configurator.log("✅ Login completato con successo")
                else:
                    self.configurator.security.record_attempt(user_id, "password_login", False)
                    result = {"success": False, "error": "Password non corretta"}
                    self.configurator.log("❌ Login fallito - password errata")
            
            self.create_response_sensor("sensor.southtech_login_response", result)
            self.configurator.set_state("sensor.southtech_login_request", state="unavailable")
            
        except Exception as e:
            self.configurator.error(f"Errore processing sensor login: {e}")
            self.create_response_sensor("sensor.southtech_login_response", 
                                      {"success": False, "error": str(e)})

    def process_sensor_setup_request(self):
        """Processa richiesta setup via sensore - VERSIONE CORRETTA FINALE"""
        try:
            attrs = self.configurator.get_state("sensor.southtech_setup_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "setup":
                return
                
            user_id = self.configurator.security.get_user_id_unified(request_data, "sensor")
            
            # CORREZIONE: Gestisci sia hash che password legacy
            password = request_data.get("password")
            password_confirm = request_data.get("password_confirm")
            password_hash = request_data.get("password_hash")
            password_confirm_hash = request_data.get("password_confirm_hash")
            security_method = request_data.get("security_method", "legacy")
            
            self.configurator.log(f"🔍 SENSOR SETUP: Metodo {security_method}, password: {bool(password)}, hash: {bool(password_hash)}")
            
            is_blocked, block_until = self.configurator.security.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            elif os.path.exists(self.configurator.auth_file):
                self.configurator.security.record_attempt(user_id, "password_setup", False)
                result = {"success": False, "error": "Password già configurata"}
            else:
                # CORREZIONE: Controlla entrambi i metodi
                if security_method in ["client_hash_sha256", "client_hash_fallback"] and password_hash and password_confirm_hash:
                    # Metodo hash - usa hash direttamente
                    if password_hash != password_confirm_hash:
                        self.configurator.security.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Le password non coincidono"}
                    else:
                        # CORREZIONE: Salva l'hash PULITO direttamente
                        self.configurator.security.save_auth_data_unified(password_hash, user_id, security_method)
                        result = {"success": True, "token": self.configurator.security.generate_token()}
                        self.configurator.security.record_attempt(user_id, "password_setup", True)
                        self.configurator.log(f"✅ Setup hash completato: {password_hash[:10]}...")
                elif password and password_confirm:
                    # Metodo legacy - usa password in chiaro
                    if password != password_confirm:
                        self.configurator.security.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Le password non coincidono"}
                    elif len(password) < 6:
                        self.configurator.security.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Password troppo corta"}
                    else:
                        # CORREZIONE: Salva la password PULITA direttamente
                        self.configurator.security.save_auth_data_unified(password, user_id, "legacy")
                        result = {"success": True, "token": self.configurator.security.generate_token()}
                        self.configurator.security.record_attempt(user_id, "password_setup", True)
                        self.configurator.log(f"✅ Setup legacy completato")
                else:
                    self.configurator.security.record_attempt(user_id, "password_setup", False)
                    result = {"success": False, "error": "Password e conferma richieste"}
            
            self.create_response_sensor("sensor.southtech_setup_response", result)
            self.configurator.set_state("sensor.southtech_setup_request", state="unavailable")
            
        except Exception as e:
            self.configurator.error(f"Errore processing sensor setup: {e}")
            self.create_response_sensor("sensor.southtech_setup_response", 
                                      {"success": False, "error": str(e)})

    def process_sensor_reset_request(self):
        """Processa richiesta reset via sensore - CORRETTO"""
        try:
            attrs = self.configurator.get_state("sensor.southtech_reset_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "reset_system":
                return
                
            # CORRETTO: Usa metodo unificato
            user_id = self.configurator.security.get_user_id_unified(request_data, "sensor")
            
            self.configurator.log(f"🔍 SENSOR RESET: Processando reset da {user_id[:20]}")
            
            # Resto del metodo rimane invariato...
            is_blocked, block_until = self.configurator.security.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            else:
                if os.path.exists(self.configurator.auth_file):
                    os.remove(self.configurator.auth_file)
                    self.configurator.log("🗑️ File auth cancellato via sensore")
                
                self.configurator.active_tokens.clear()
                
                if user_id in self.configurator.attempt_counters:
                    del self.configurator.attempt_counters[user_id]
                if user_id in self.configurator.blocked_users:
                    del self.configurator.blocked_users[user_id]
                
                self.update_auth_status_file()
                self.configurator.security.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema via sensore")
                self.configurator.security.save_security_data()
                
                result = {"success": True, "message": "Sistema resettato via sensore"}
            
            self.create_response_sensor("sensor.southtech_reset_response", result)
            self.configurator.set_state("sensor.southtech_reset_request", state="unavailable")
            
        except Exception as e:
            self.configurator.error(f"Errore processing sensor reset: {e}")
            self.create_response_sensor("sensor.southtech_reset_response", 
                                      {"success": False, "error": str(e)})

    def process_sensor_device_config_request(self):
        """Processa richiesta di configurazione dispositivo via sensore."""
        request_data = None
        try:
            attrs = self.configurator.get_state("sensor.southtech_device_config_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
            
            request_data = attrs["attributes"]
            action = request_data.get("action")
            request_id = request_data.get("request_id")

            self.configurator.log(f"🔌 SENSOR: Ricevuta richiesta configurazione dispositivo: {action} (ID: {request_id})")

            response_data = {"success": False, "error": "Azione non riconosciuta", "request_id": request_id}

            if action == "get_available_device_numbers":
                # Chiama il metodo dalla classe principale
                response_data = self.configurator._get_available_device_numbers(request_data)
            elif action == "get_available_board_models":
                # Chiama il metodo dalla classe principale per ottenere i modelli di schede
                response_data = self.configurator._get_available_board_models(request_data)
            elif action == "save_esphome_device":
                # Chiama il metodo dalla classe principale
                response_data = self.configurator._save_esphome_device(request_data)
            elif action == 'get_existing_devices':
                response_data = self.configurator._get_existing_devices(request_data)

            # Invia la risposta aggiornando il sensore di risposta
            self.create_response_sensor("sensor.southtech_device_config_response", response_data)
            self.configurator.log(f"🔌 SENSOR: Risposta inviata per {action} (ID: {request_id})")
            self.configurator.set_state("sensor.southtech_device_config_request", state="completed")

        except Exception as e:
            self.configurator.error(f"❌ SENSOR: Errore durante la gestione della richiesta dispositivo: {e}")
            error_response = {"success": False, "error": str(e)}
            if request_data and "request_id" in request_data:
                error_response["request_id"] = request_data["request_id"]
            self.create_response_sensor("sensor.southtech_device_config_response", error_response)
            self.configurator.set_state("sensor.southtech_device_config_request", state="completed")

    def monitor_save_requests(self, kwargs):
        """Monitora richieste di salvataggio via sensori (fallback) - VERSIONE MIGLIORATA"""
        try:
            save_sensor = self.configurator.get_state("sensor.southtech_save_request")
            
            if save_sensor == "pending":
                self.configurator.log("📡 SENSOR SAVE: Rilevata richiesta fallback")
                
                # Aggiorna debug
                self.configurator.set_state("sensor.southtech_websocket_debug",
                              state="fallback_active",
                              attributes={
                                  "fallback_method": "sensor",
                                  "fallback_trigger_time": datetime.now().isoformat(),
                                  "websocket_failed": True
                              })
                
                self.process_sensor_save_request()
                
        except Exception as e:
            self.configurator.error(f"Errore monitor save requests: {e}")

    # ===============================================================
    # FILE SYSTEM FALLBACK (FALLBACK 2)
    # ===============================================================
    
    def monitor_file_requests(self, kwargs):
        """Monitora richieste tramite file system (fallback secondario)"""
        try:
            if not os.path.exists(self.configurator.api_path):
                return
                
            for filename in os.listdir(self.configurator.api_path):
                if filename.endswith('_request.json'):
                    filepath = os.path.join(self.configurator.api_path, filename)
                    self.process_file_request(filename, filepath)
                    
        except Exception as e:
            self.configurator.error(f"Errore monitoraggio file requests: {e}")

    def process_file_request(self, filename, filepath):
        """Processa richiesta da file con metodi avanzati - VERSIONE CORRETTA"""
        try:
            if filename != "save_request.json":
                return  # Gestisce solo richieste di salvataggio
                
            self.configurator.log("📁 FILE: Processamento con metodo avanzato")
            
            # Leggi richiesta
            with open(filepath, 'r') as f:
                request_data = json.load(f)
            os.remove(filepath)  # Rimuovi file richiesta
            
            configurations = request_data.get("configurations", [])
            
            # RICONOSCIMENTO MODALITÀ COMPLETA
            action = request_data.get("action", "save_yaml")
            generate_dashboard = request_data.get("generate_dashboard", False)
            generate_templates = request_data.get("generate_templates", False)

            # --- INIZIO LOGICA MODIFICATA ---
            if action == "save_complete" or generate_dashboard or generate_templates:
                # Per un salvataggio/pulizia completo, una lista vuota è valida.
                self.configurator.log("✨ FILE: Richiesta SALVATAGGIO COMPLETO/PULIZIA rilevata")
                response_data = self.configurator.yaml.execute_complete_save_advanced("file", configurations, request_data)
            else:
                # Per un salvataggio standard, le configurazioni sono necessarie.
                if not configurations:
                    response_data = {"success": False, "error": "Configurazioni mancanti per un salvataggio standard."}
                else:
                    self.configurator.log("📁 FILE: Richiesta salvataggio STANDARD")
                    response_data = self.configurator.yaml.execute_save_advanced("file", configurations, request_data)
            # --- FINE LOGICA MODIFICATA ---
            
            # Salva risposta
            response_path = os.path.join(self.configurator.api_path, "save_response.json")
            response_data['timestamp'] = datetime.now().isoformat()
            
            with open(response_path, 'w') as f:
                json.dump(response_data, f, indent=2)
                
            self.configurator.log("📁 FILE: Risposta salvata")
            
        except Exception as e:
            self.configurator.error(f"❌ FILE: Errore: {e}")

    # ===============================================================
    # COMMUNICATION ENTITIES E STATUS
    # ===============================================================
    
    def setup_communication_entities(self):
        """Setup entità di comunicazione per fallback con sensore debug WebSocket"""
        try:
            communication_entities = [
                "sensor.southtech_system_status",
                "sensor.southtech_auth_status", 
                "sensor.southtech_security_log",
                "sensor.southtech_setup_request",
                "sensor.southtech_setup_response",
                "sensor.southtech_login_request",
                "sensor.southtech_login_response",
                "sensor.southtech_reset_request",
                "sensor.southtech_reset_response",
                "sensor.southtech_sync_request",
                "sensor.southtech_sync_response",
                "sensor.southtech_save_request",
                "sensor.southtech_save_response",
                "sensor.southtech_websocket_debug"
            ]
            
            for entity in communication_entities:
                try:
                    current_state = self.configurator.get_state(entity)
                    
                    if current_state is None:
                        if "websocket_debug" in entity:
                            # SENSORE DEBUG WEBSOCKET ENHANCED
                            initial_state = "initializing"
                            attributes = {
                                "initialized": datetime.now().isoformat(),
                                "description": "Debug operazioni WebSocket SouthTech",
                                "debug_active": True,
                                "service_name": "appdaemon.southtech_save_yaml",
                                "handler_method": "handle_websocket_save",
                                "test_mode_supported": True,
                                "service_registered": False,  # Sarà aggiornato dalla verifica
                                "last_test": None,
                                "fallback_methods": ["sensor", "file"],
                                "version": self.version,
                                "status": "Inizializzazione in corso...",
                                "troubleshooting": {
                                    "service_not_found": [
                                        "Verifica che AppDaemon sia avviato",
                                        "Controlla log AppDaemon per errori",
                                        "Ricarica configurazione AppDaemon",
                                        "Usa fallback sensori se necessario"
                                    ]
                                }
                            }
                        elif "save_" in entity:
                            initial_state = "ready"
                            attributes = {
                                "initialized": datetime.now().isoformat(),
                                "description": "Sensore per salvataggio YAML",
                                "fallback_priority": 2
                            }
                        elif "sync_" in entity:
                            initial_state = "ready"
                            attributes = {
                                "initialized": datetime.now().isoformat(),
                                "description": "Sensore per sincronizzazione configurazioni",
                                "fallback_priority": 2
                            }
                        else:
                            initial_state = "unavailable"
                            attributes = {
                                "initialized": datetime.now().isoformat(),
                                "description": f"Sensore comunicazione: {entity.split('.')[-1]}"
                            }
                        
                        self.configurator.set_state(entity, state=initial_state, attributes=attributes)
                        self.configurator.log(f"🔍 Inizializzato sensore: {entity}")
                    else:
                        self.configurator.log(f"✓ Sensore già esistente: {entity}")
                        
                except Exception as e:
                    self.configurator.error(f"❌ Errore inizializzazione {entity}: {e}")
                    continue
                    
            self.configurator.log("✅ Setup sensori comunicazione completato (incluso WebSocket debug)")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore setup comunicazione: {e}")

    def update_auth_status_file(self):
        """Aggiorna il file di stato autenticazione e crea sensore HA"""
        try:
            has_password = os.path.exists(self.configurator.auth_file)
            
            # Aggiorna file JSON
            status = {
                "has_password": has_password,
                "last_update": datetime.now().isoformat(),
                "system_mode": "secure_dual_fallback",
                "api_available": True,
                "security_active": True,
                "version": self.version,
                "directories_initialized": True,
                "yaml_format_support": "dual",
                "architecture": "modular"
            }
            
            json_dir = os.path.join(self.configurator.www_path, "json")
            status_file = os.path.join(json_dir, "auth_status.json")
            
            # Assicurati che la directory json esista
            os.makedirs(json_dir, exist_ok=True)
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            # Crea anche un sensore in HA per facile accesso
            self.configurator.set_state("sensor.southtech_auth_status", 
                          state="configured" if has_password else "not_configured",
                          attributes={
                              "has_password": has_password,
                              "last_update": datetime.now().isoformat(),
                              "system_mode": "secure_dual_fallback",
                              "api_endpoints_active": True,
                              "file_fallback_active": True,
                              "security_system_active": True,
                              "blocked_users": len(self.configurator.blocked_users),
                              "total_attempt_counters": len(self.configurator.attempt_counters),
                              "directories_initialized": True,
                              "yaml_format_support": "dual",
                              "architecture": "modular",
                              "version": self.version
                          })
                
            self.configurator.log(f"🔍 AUTH STATUS: Aggiornato - has_password: {has_password}")
            
        except Exception as e:
            self.configurator.error(f"Errore aggiornamento status auth: {e}")
            # In caso di errore, almeno crea il sensore HA
            try:
                self.configurator.set_state("sensor.southtech_auth_status", 
                              state="error",
                              attributes={
                                  "error": str(e),
                                  "last_update": datetime.now().isoformat()
                              })
            except:
                pass

    def create_initial_auth_status(self):
        """Crea il file auth_status.json iniziale"""
        try:
            json_dir = os.path.join(self.configurator.www_path, "json")
            auth_status_file = os.path.join(json_dir, "auth_status.json")
            
            # Assicurati che la directory json esista
            os.makedirs(json_dir, exist_ok=True)
            
            if not os.path.exists(auth_status_file):
                initial_status = {
                    "has_password": False,
                    "last_update": datetime.now().isoformat(),
                    "system_mode": "secure_dual_fallback",
                    "api_available": True,
                    "security_active": True,
                    "initialized": True,
                    "version": self.version,
                    "yaml_format_support": "dual",
                    "architecture": "modular"
                }
                
                with open(auth_status_file, 'w') as f:
                    json.dump(initial_status, f, indent=2)
                
                self.configurator.log(f"📄 Creato file auth_status.json iniziale")
            else:
                self.configurator.log(f"✓ File auth_status.json già esistente")
                
        except Exception as e:
            self.configurator.error(f"Errore creazione auth_status.json: {e}")

    def create_response_sensor(self, sensor_name, result):
        """Crea un sensore di risposta per il sistema file-based - VERSIONE CORRETTA"""
        try:
            # Non verificare se il sensore esiste, crealo direttamente
            self.configurator.set_state(sensor_name, 
                          state="completed",
                          attributes=result)
            
            self.configurator.log(f"✅ Risposta salvata in {sensor_name}")
            
        except Exception as e:
            self.configurator.error(f"Errore creazione sensore risposta {sensor_name}: {e}")
            
            # Fallback: prova a crearlo forzatamente
            try:
                import time
                time.sleep(0.1)  # Piccolo delay
                self.configurator.set_state(sensor_name, 
                              state="completed",
                              attributes=result)
                self.configurator.log(f"✅ Risposta salvata in {sensor_name} (fallback)")
            except Exception as e2:
                self.configurator.error(f"Errore anche nel fallback per {sensor_name}: {e2}")

    def create_sensor_save_response(self, result_data):
        """Crea risposta per salvataggio via sensore"""
        try:
            result_data["timestamp"] = datetime.now().isoformat()
            
            self.configurator.set_state("sensor.southtech_save_response",
                          state="completed",
                          attributes=result_data)
            
            if result_data.get("success"):
                self.configurator.log("✅ Risposta successo inviata via sensore")
            else:
                self.configurator.log(f"❌ Risposta errore inviata via sensore: {result_data.get('error')}")
                
        except Exception as e:
            self.configurator.error(f"Errore creazione risposta sensore: {e}")

    # ===============================================================
    # BACKUP E UTILITY
    # ===============================================================
    
    def create_atomic_backup(self):
        """Crea backup atomico se file esiste"""
        if not os.path.exists(self.configurator.apps_yaml_path):
            return None
            
        timestamp = int(time.time())
        backup_file = f"{self.configurator.apps_yaml_path}.backup_{timestamp}"
        
        try:
            shutil.copy2(self.configurator.apps_yaml_path, backup_file)
            return backup_file
        except Exception as e:
            self.configurator.error(f"Errore creazione backup: {e}")
            return None

    def cleanup_temp_backup(self, backup_file):
        """Pulisce backup temporaneo"""
        try:
            if backup_file and os.path.exists(backup_file):
                os.remove(backup_file)
                self.configurator.log(f"🗑️ Backup temporaneo rimosso: {backup_file}")
        except Exception as e:
            self.configurator.error(f"Errore pulizia backup temporaneo: {e}")

    def restore_from_backup(self, backup_file):
        """Ripristina da backup in caso di errore"""
        try:
            if backup_file and os.path.exists(backup_file):
                shutil.copy2(backup_file, self.configurator.apps_yaml_path)
                self.configurator.log(f"🛡️ Ripristinato da backup: {backup_file}")
                return True
            return False
        except Exception as e:
            self.configurator.error(f"Errore ripristino backup: {e}")
            return False

    # ===============================================================
    # CLEANUP E TERMINAZIONE
    # ===============================================================
    
    def cleanup(self):
        """Cleanup del modulo comunicazione"""
        self.configurator.log("🧹 Cleanup modulo Communication...")
        
        # Ferma processing WebSocket
        self.is_processing_ws = False
        
        # Pulisci queue
        self.internal_ws_queue.clear()
        
        # Reset lock sensori
        for key in self.sensor_locks:
            self.sensor_locks[key] = False
        
        # Aggiorna stato finale sensori
        try:
            self.configurator.set_state("sensor.southtech_websocket_debug",
                          state="shutdown",
                          attributes={
                              "shutdown_time": datetime.now().isoformat(),
                              "clean_shutdown": True
                          })
        except:
            pass
        
        self.configurator.log("✅ Cleanup modulo Communication completato")

    # ===============================================================
    # CALLBACK CONFIGURATION CHANGE
    # ===============================================================
    
    def on_configuration_change(self, change_type, data):
        """Gestisce notifiche di cambiamento configurazione"""
        try:
            self.configurator.log(f"📢 Communication: Ricevuto cambio configurazione {change_type}")
            
            # Aggiorna sensori di stato se necessario
            if change_type in ["auth_change", "security_change"]:
                self.update_auth_status_file()
            
            # Notifica via sensori se necessario
            if change_type == "configuration_updated":
                try:
                    self.configurator.set_state("sensor.southtech_system_status",
                                  attributes={
                                      "last_configuration_change": datetime.now().isoformat(),
                                      "change_type": change_type,
                                      "configurations_count": data.get("count", 0) if data else 0
                                  })
                except Exception as e:
                    self.configurator.log(f"⚠️ Errore aggiornamento sensore sistema: {e}")
            
        except Exception as e:
            self.configurator.error(f"Errore gestione cambio configurazione: {e}")
