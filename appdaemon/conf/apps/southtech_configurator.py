import appdaemon.plugins.hass.hassapi as hass
import yaml
import os
import re
import json
import hashlib
import secrets
import time
from datetime import datetime, timedelta
import shutil

class SouthTechConfigurator(hass.Hass):
    def initialize(self):
        self.log("🚀 SouthTech Configurator inizializzato - Versione con Sicurezza Avanzata")
        
        # Path dei file - CORRETTI per Home Assistant OS con AppDaemon addon
        self.apps_yaml_path = "/homeassistant/appdaemon/apps/apps.yaml"
        self.www_path = "/homeassistant/www/southtech"
        self.auth_file = os.path.join(self.www_path, "auth.json")
        self.backup_path = os.path.join(self.www_path, "backup")
        self.security_file = os.path.join(self.www_path, "security.json")
        
        # File per comunicazione con il frontend
        self.api_path = os.path.join(self.www_path, "api")
        
        # Markers per il file YAML - Supporto doppio formato
        self.start_marker = "# START CONTROLLO LUCI AUTOMATICHE"
        self.end_marker = "# END CONTROLLO LUCI AUTOMATICHE"
        # Nuovo formato con bordi
        self.new_start_marker = "################################################################################"
        self.new_start_line = "#                      START CONTROLLO LUCI AUTOMATICHE                        #"
        self.new_end_line = "#                      END CONTROLLO LUCI AUTOMATICHE                          #"
        self.new_end_marker = "################################################################################"
        
        # Token attivi (in memoria)
        self.active_tokens = {}
        
        # Sistema anti-bruteforce
        self.blocked_users = {}  # {user_id: block_until_timestamp}
        self.attempt_counters = {}  # {user_id: {type: count}}
        
        # Inizializza la struttura completa delle directory e file
        self.initialize_directory_structure()
        
        # Carica i dati di sicurezza esistenti
        self.load_security_data()
        
        # Registra gli endpoint API AppDaemon
        self.register_endpoint(self.api_auth_status, "southtech_auth_status")
        self.register_endpoint(self.api_auth_setup, "southtech_auth_setup")
        self.register_endpoint(self.api_auth_login, "southtech_auth_login")
        self.register_endpoint(self.api_auth_change, "southtech_auth_change")
        self.register_endpoint(self.api_get_entities, "southtech_entities")
        self.register_endpoint(self.api_sync_configs, "southtech_sync")
        self.register_endpoint(self.api_save_config, "southtech_save")
        self.register_endpoint(self.api_validate_token, "southtech_validate_token")
        self.register_endpoint(self.api_reset_system, "southtech_reset_system")
        self.register_endpoint(self.api_check_blocked, "southtech_check_blocked")
        
        # Registra endpoint diagnostici aggiuntivi
        self.register_additional_endpoints()
        
        # Crea file di stato iniziale
        self.update_auth_status_file()
        
        # Setup entità di comunicazione per fallback
        self.setup_communication_entities()
        
        # Monitora richieste via sensori ogni 2 secondi (sistema fallback)
        self.run_every(self.monitor_sensor_requests, "now+2", 2)
        
        # Monitora richieste via file ogni 3 secondi (sistema fallback)
        self.run_every(self.monitor_file_requests, "now+3", 3)
        
        # Pulizia periodica
        self.run_every(self.cleanup_expired_tokens, "now+3600", 3600)
        self.run_every(self.cleanup_expired_blocks, "now+60", 60)
        
        # Pulizia backup vecchi ogni giorno
        self.run_every(self.cleanup_old_backups, "now+86400", 86400)
        
        # Controllo integrità file ogni 6 ore
        self.run_every(self.periodic_integrity_check, "now+21600", 21600)
        
        # Heartbeat per monitoraggio sistema
        self.run_every(self.system_heartbeat, "now+60", 60)
        
        # Salva dati sicurezza ogni 5 minuti
        self.run_every(self.save_security_data, "now+300", 300)
        
        self.log("✅ SouthTech Configurator pronto con sistema di sicurezza avanzato!")
        self.log("🔍 API Endpoints registrati via AppDaemon")
        self.log("🔍 Sistema file-based attivo come fallback")
        self.log("🛡️ Sistema anti-bruteforce attivo")
        self.log("📁 Struttura directory inizializzata")
        self.log(f"📂 Percorso www: {self.www_path}")
        self.log(f"📂 Percorso api: {self.api_path}")
        self.log(f"📂 Percorso backup: {self.backup_path}")
        
        # Log informazioni di sistema
        self.log_system_info()

    def log_system_info(self):
        """Log informazioni del sistema"""
        try:
            info = {
                "paths": {
                    "apps_yaml": self.apps_yaml_path,
                    "www_path": self.www_path,
                    "api_path": self.api_path,
                    "backup_path": self.backup_path
                },
                "files": {
                    "apps_yaml": os.path.exists(self.apps_yaml_path),
                    "index_html": os.path.exists(os.path.join(self.www_path, "index.html")),
                    "light_presence_html": os.path.exists(os.path.join(self.www_path, "light_presence.html")),
                    "auth_file": os.path.exists(self.auth_file)
                },
                "system": {
                    "active_tokens": len(self.active_tokens),
                    "blocked_users": len(self.blocked_users),
                    "version": "3.0.0"
                }
            }
            
            self.log(f"📊 INFO SISTEMA: {json.dumps(info, indent=2)}")
            
        except Exception as e:
            self.error(f"Errore log system info: {e}")

    # === INIZIALIZZAZIONE STRUTTURA DIRECTORY ===
    
    def initialize_directory_structure(self):
        """Inizializza la struttura completa di directory e file necessari"""
        try:
            self.log("🏗️ Inizializzazione struttura directory...")
            self.log(f"🎯 Percorso target: {self.www_path}")
            
            # Crea le directory necessarie
            directories = [
                self.www_path,
                self.backup_path, 
                self.api_path
            ]
            
            for directory in directories:
                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    self.log(f"📁 Creata directory: {directory}")
                else:
                    self.log(f"✓ Directory già esistente: {directory}")
            
            # Verifica che i file HTML esistano nella directory corretta
            self.verify_html_files()
            
            # Crea il file auth_status.json iniziale se non esiste
            self.create_initial_auth_status()
            
            # Crea file .gitkeep nelle directory per preservarle
            self.create_gitkeep_files()
            
            # Verifica permessi di scrittura
            self.verify_write_permissions()
            
            self.log("✅ Struttura directory inizializzata con successo")
            
        except Exception as e:
            self.error(f"❌ Errore inizializzazione struttura: {e}")
            raise
    
    def verify_html_files(self):
        """Verifica che i file HTML necessari esistano"""
        try:
            html_files = ["index.html", "light_presence.html"]
            
            for html_file in html_files:
                file_path = os.path.join(self.www_path, html_file)
                if os.path.exists(file_path):
                    self.log(f"✓ File {html_file} trovato: {file_path}")
                else:
                    self.log(f"⚠️ File {html_file} NON trovato in: {file_path}")
                    self.log(f"💡 Assicurati che {html_file} sia presente nella directory corretta")
                
        except Exception as e:
            self.error(f"Errore verifica file HTML: {e}")
    
    def create_initial_auth_status(self):
        """Crea il file auth_status.json iniziale"""
        try:
            auth_status_file = os.path.join(self.www_path, "auth_status.json")
            
            if not os.path.exists(auth_status_file):
                initial_status = {
                    "has_password": False,
                    "last_update": datetime.now().isoformat(),
                    "system_mode": "secure_dual_fallback",
                    "api_available": True,
                    "security_active": True,
                    "initialized": True,
                    "version": "3.0.0",
                    "yaml_format_support": "dual"
                }
                
                with open(auth_status_file, 'w') as f:
                    json.dump(initial_status, f, indent=2)
                
                self.log(f"📄 Creato file auth_status.json iniziale")
            else:
                self.log(f"✓ File auth_status.json già esistente")
                
        except Exception as e:
            self.error(f"Errore creazione auth_status.json: {e}")
    
    def create_gitkeep_files(self):
        """Crea file .gitkeep per preservare le directory vuote"""
        try:
            gitkeep_dirs = [self.backup_path, self.api_path]
            
            for directory in gitkeep_dirs:
                gitkeep_file = os.path.join(directory, ".gitkeep")
                if not os.path.exists(gitkeep_file):
                    with open(gitkeep_file, 'w') as f:
                        f.write("# Questo file mantiene la directory nel repository\n")
                    self.log(f"📝 Creato .gitkeep in {directory}")
                    
        except Exception as e:
            self.error(f"Errore creazione .gitkeep: {e}")
    
    def verify_write_permissions(self):
        """Verifica i permessi di scrittura nelle directory"""
        try:
            test_dirs = [self.www_path, self.backup_path, self.api_path]
            
            for directory in test_dirs:
                test_file = os.path.join(directory, "test_write.tmp")
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                    self.log(f"✓ Permessi scrittura OK: {directory}")
                except Exception as e:
                    self.error(f"❌ Permessi scrittura mancanti: {directory} - {e}")
                    raise
                    
        except Exception as e:
            self.error(f"Errore verifica permessi: {e}")
            raise

    # === SISTEMA ANTI-BRUTEFORCE ===
    
    def get_user_id(self, data):
        """Genera ID utente per tracking sicurezza"""
        # Prova a usare token HA se disponibile
        ha_token = data.get("ha_token") or data.get("__headers", {}).get("Authorization", "").replace("Bearer ", "")
        if ha_token and len(ha_token) > 10:
            return f"token_{hashlib.md5(ha_token.encode()).hexdigest()[:16]}"
        
        # Fallback a browser fingerprint
        browser_id = data.get("browser_id")
        if browser_id:
            return f"browser_{browser_id}"
        
        # Ultimo fallback a IP (se disponibile)
        ip = data.get("__request_ip", "unknown")
        return f"ip_{ip}"
    
    def is_user_blocked(self, user_id):
        """Controlla se un utente è bloccato"""
        if user_id in self.blocked_users:
            block_until = self.blocked_users[user_id]
            if time.time() < block_until:
                return True, block_until
            else:
                # Blocco scaduto, rimuovi
                del self.blocked_users[user_id]
                if user_id in self.attempt_counters:
                    del self.attempt_counters[user_id]
                self.save_security_data()
        return False, None
    
    def record_attempt(self, user_id, attempt_type, success=False):
        """Registra un tentativo di accesso"""
        current_time = time.time()
        
        if success:
            # Reset contatori per successo
            if user_id in self.attempt_counters:
                del self.attempt_counters[user_id]
            if user_id in self.blocked_users:
                del self.blocked_users[user_id]
            self.log_security_event(user_id, attempt_type, "SUCCESS", "Accesso riuscito")
            self.save_security_data()
            return
        
        # Registra fallimento
        if user_id not in self.attempt_counters:
            self.attempt_counters[user_id] = {}
        
        if attempt_type not in self.attempt_counters[user_id]:
            self.attempt_counters[user_id][attempt_type] = 0
        
        self.attempt_counters[user_id][attempt_type] += 1
        total_attempts = sum(self.attempt_counters[user_id].values())
        
        self.log_security_event(user_id, attempt_type, "FAILED", 
                               f"Tentativo {total_attempts}/3 fallito")
        
        # Blocca se raggiunge 3 tentativi totali
        if total_attempts >= 3:
            block_until = current_time + (5 * 60)  # 5 minuti
            self.blocked_users[user_id] = block_until
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
            self.error(log_msg)
        elif level == "WARNING":
            self.warning(log_msg)
        else:
            self.log(log_msg)
        
        # Aggiorna sensore HA
        try:
            self.set_state("sensor.southtech_security_log",
                          state=level.lower(),
                          attributes={
                              "last_event": timestamp,
                              "user_id": user_id[:20],
                              "event_type": event_type,
                              "message": message,
                              "blocked_users": len(self.blocked_users),
                              "total_attempts": sum(len(attempts) for attempts in self.attempt_counters.values())
                          })
        except Exception as e:
            self.error(f"Errore aggiornamento sensore sicurezza: {e}")
    
    def create_ha_notification(self, title, message):
        """Crea notifica persistente in Home Assistant"""
        try:
            self.call_service("persistent_notification/create",
                            title=title,
                            message=message,
                            notification_id=f"southtech_security_{int(time.time())}")
        except Exception as e:
            self.error(f"Errore creazione notifica HA: {e}")
    
    def load_security_data(self):
        """Carica dati di sicurezza da file"""
        try:
            if os.path.exists(self.security_file):
                with open(self.security_file, 'r') as f:
                    data = json.load(f)
                    self.blocked_users = data.get("blocked_users", {})
                    self.attempt_counters = data.get("attempt_counters", {})
                    
                    # Rimuovi blocchi scaduti
                    current_time = time.time()
                    expired_blocks = [uid for uid, until in self.blocked_users.items() 
                                    if current_time >= until]
                    for uid in expired_blocks:
                        del self.blocked_users[uid]
                        if uid in self.attempt_counters:
                            del self.attempt_counters[uid]
                    
                    if expired_blocks:
                        self.save_security_data()
                    
                    self.log(f"🛡️ Caricati dati sicurezza: {len(self.blocked_users)} utenti bloccati")
            else:
                # Crea file security vuoto iniziale
                self.blocked_users = {}
                self.attempt_counters = {}
                self.save_security_data()
                self.log("🛡️ Creato file security.json iniziale")
                
        except Exception as e:
            self.error(f"Errore caricamento dati sicurezza: {e}")
            self.blocked_users = {}
            self.attempt_counters = {}
            # Prova a creare file iniziale
            try:
                self.save_security_data()
            except:
                pass
    
    def save_security_data(self, kwargs=None):
        """Salva dati di sicurezza su file"""
        try:
            data = {
                "blocked_users": self.blocked_users,
                "attempt_counters": self.attempt_counters,
                "last_save": datetime.now().isoformat()
            }
            with open(self.security_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.error(f"Errore salvataggio dati sicurezza: {e}")
    
    def cleanup_expired_blocks(self, kwargs):
        """Pulisce blocchi scaduti"""
        current_time = time.time()
        expired = []
        
        for user_id, block_until in self.blocked_users.items():
            if current_time >= block_until:
                expired.append(user_id)
        
        for user_id in expired:
            del self.blocked_users[user_id]
            if user_id in self.attempt_counters:
                del self.attempt_counters[user_id]
            self.log_security_event(user_id, "UNBLOCK", "INFO", "Blocco scaduto")
        
        if expired:
            self.save_security_data()
    
    # === LETTURA E SALVATAGGIO CONFIGURAZIONI YAML (AGGIORNATO) ===
    
    def read_existing_configs(self):
        """Legge le configurazioni esistenti da apps.yaml - Supporto doppio formato"""
        configurations = []
        
        try:
            if not os.path.exists(self.apps_yaml_path):
                self.log("⚠️ File apps.yaml non trovato")
                return configurations
            
            with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Prova prima il nuovo formato
            yaml_content = self._extract_yaml_new_format(content)
            if not yaml_content:
                # Fallback al formato vecchio
                yaml_content = self._extract_yaml_old_format(content)
            
            if yaml_content:
                configurations = self._parse_yaml_configurations(yaml_content)
            else:
                self.log("ℹ️ Sezione controllo luci non trovata in apps.yaml")
            
            self.log(f"📋 Caricate {len(configurations)} configurazioni dal file apps.yaml")
            return configurations
            
        except Exception as e:
            self.error(f"Errore lettura apps.yaml: {e}")
            return configurations
    
    def _extract_yaml_new_format(self, content):
        """Estrae YAML dal nuovo formato con bordi"""
        try:
            start_line_idx = content.find(self.new_start_line)
            if start_line_idx == -1:
                return None
            
            end_line_idx = content.find(self.new_end_line, start_line_idx)
            if end_line_idx == -1:
                return None
            
            # Estrai la sezione tra le linee
            yaml_section = content[start_line_idx:end_line_idx]
            
            # Trova l'inizio della configurazione light_presence
            light_presence_start = yaml_section.find('light_presence:')
            if light_presence_start == -1:
                return None
            
            return yaml_section[light_presence_start:]
            
        except Exception as e:
            self.error(f"Errore estrazione nuovo formato: {e}")
            return None
    
    def _extract_yaml_old_format(self, content):
        """Estrae YAML dal formato vecchio"""
        try:
            start_idx = content.find(self.start_marker)
            end_idx = content.find(self.end_marker)
            
            if start_idx != -1 and end_idx != -1:
                return content[start_idx + len(self.start_marker):end_idx].strip()
            
            return None
            
        except Exception as e:
            self.error(f"Errore estrazione formato vecchio: {e}")
            return None
    
    def _parse_yaml_configurations(self, yaml_content):
        """Parse delle configurazioni YAML"""
        configurations = []
        
        try:
            config_data = yaml.safe_load(yaml_content)
            
            if config_data and 'light_presence' in config_data:
                light_configs = config_data['light_presence'].get('light_presence', [])
                
                for cfg in light_configs:
                    # Estrai solo i parametri base per l'interfaccia
                    configurations.append({
                        'light_entity': cfg.get('light_entity', ''),
                        'presence_sensor_on': cfg.get('presence_sensor_on', ''),
                        'presence_sensor_off': cfg.get('presence_sensor_off', ''),
                        'illuminance_sensor': cfg.get('illuminance_sensor', '')
                    })
                    
        except yaml.YAMLError as e:
            self.error(f"Errore parsing YAML: {e}")
        
        return configurations
    
    def save_yaml_configuration(self, yaml_content):
        """Salva la configurazione YAML nel file apps.yaml - Supporto nuovo formato"""
        try:
            # Leggi il contenuto esistente
            existing_content = ""
            if os.path.exists(self.apps_yaml_path):
                with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Prova a sostituire nel nuovo formato prima
            new_content = self._replace_yaml_new_format(existing_content, yaml_content)
            if new_content is None:
                # Fallback al formato vecchio
                new_content = self._replace_yaml_old_format(existing_content, yaml_content)
            
            # Se nessuna sezione esistente trovata, aggiungi alla fine
            if new_content is None:
                if existing_content and not existing_content.endswith('\n'):
                    existing_content += '\n'
                new_content = existing_content + '\n' + yaml_content + '\n'
            
            # Scrivi il nuovo contenuto
            with open(self.apps_yaml_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log("💾 Configurazione YAML salvata in apps.yaml")
            return True
            
        except Exception as e:
            self.error(f"Errore salvataggio YAML: {e}")
            raise
    
    def _replace_yaml_new_format(self, content, yaml_content):
        """Sostituisce YAML nel nuovo formato"""
        try:
            start_line_idx = content.find(self.new_start_line)
            if start_line_idx == -1:
                return None
            
            # Trova l'inizio del blocco (linea di #'s prima)
            start_block_idx = content.rfind(self.new_start_marker, 0, start_line_idx)
            if start_block_idx == -1:
                start_block_idx = start_line_idx
            
            # Trova la fine del blocco
            end_line_idx = content.find(self.new_end_line, start_line_idx)
            if end_line_idx != -1:
                # Trova la fine del blocco (linea di #'s dopo)
                end_block_idx = content.find(self.new_end_marker, end_line_idx)
                if end_block_idx != -1:
                    end_block_idx += len(self.new_end_marker)
                    
                    # Sostituisci la sezione esistente
                    before = content[:start_block_idx]
                    after = content[end_block_idx:]
                    return before + yaml_content + after
            
            return None
            
        except Exception as e:
            self.error(f"Errore sostituzione nuovo formato: {e}")
            return None
    
    def _replace_yaml_old_format(self, content, yaml_content):
        """Sostituisce YAML nel formato vecchio"""
        try:
            start_idx = content.find(self.start_marker)
            end_idx = content.find(self.end_marker)
            
            if start_idx != -1 and end_idx != -1:
                # Sostituisci la sezione esistente mantenendo il marker di fine
                before = content[:start_idx]
                after = content[end_idx:]
                return before + yaml_content + after
            
            return None
            
        except Exception as e:
            self.error(f"Errore sostituzione formato vecchio: {e}")
            return None
    
    # === API ENDPOINTS CON SICUREZZA ===
    
    def api_check_blocked(self, data):
        """Controlla se un utente è bloccato"""
        try:
            user_id = self.get_user_id(data)
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
    
    def process_sensor_login_request(self):
        """Processa richiesta login via sensore"""
        try:
            attrs = self.get_state("sensor.southtech_login_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "login":
                return
                
            user_id = f"browser_{request_data.get('browser_id', 'unknown')}"
            password = request_data.get("password")
            
            self.log(f"🔍 SENSOR LOGIN: Processando login da {user_id[:20]}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            elif not os.path.exists(self.auth_file):
                self.record_attempt(user_id, "password_login", False)
                result = {"success": False, "error": "Password non configurata"}
            elif not password:
                self.record_attempt(user_id, "password_login", False)
                result = {"success": False, "error": "Password richiesta"}
            else:
                with open(self.auth_file, 'r') as f:
                    auth_data = json.load(f)
                
                salt = auth_data["salt"]
                stored_hash = auth_data["password_hash"]
                provided_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                
                if provided_hash != stored_hash:
                    self.record_attempt(user_id, "password_login", False)
                    result = {"success": False, "error": "Password non corretta"}
                else:
                    token = self.generate_token()
                    self.record_attempt(user_id, "password_login", True)
                    result = {"success": True, "token": token}
                    self.log("✅ Login completato via sensore")
            
            # Crea il sensore di risposta
            self.create_response_sensor("sensor.southtech_login_response", result)
            
            # Rimuovi richiesta
            self.set_state("sensor.southtech_login_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor login: {e}")
            self.create_response_sensor("sensor.southtech_login_response", 
                                       {"success": False, "error": str(e)})
    
    def process_sensor_reset_request(self):
        """Processa richiesta reset via sensore"""
        try:
            attrs = self.get_state("sensor.southtech_reset_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "reset_system":
                return
                
            user_id = f"browser_{request_data.get('browser_id', 'unknown')}"
            
            self.log(f"🔍 SENSOR RESET: Processando reset da {user_id[:20]}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            else:
                # Esegui reset
                if os.path.exists(self.auth_file):
                    os.remove(self.auth_file)
                    self.log("🗑️ File auth cancellato via sensore")
                
                self.active_tokens.clear()
                
                # Reset contatori per questo utente
                if user_id in self.attempt_counters:
                    del self.attempt_counters[user_id]
                if user_id in self.blocked_users:
                    del self.blocked_users[user_id]
                
                self.update_auth_status_file()
                self.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema via sensore")
                self.save_security_data()
                
                result = {"success": True, "message": "Sistema resettato via sensore"}
            
            # Crea il sensore di risposta
            self.create_response_sensor("sensor.southtech_reset_response", result)
            
            # Rimuovi richiesta
            self.set_state("sensor.southtech_reset_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor reset: {e}")
            self.create_response_sensor("sensor.southtech_reset_response", 
                                       {"success": False, "error": str(e)})
    
    def create_response_sensor(self, sensor_name, result):
        """Crea un sensore di risposta per il sistema file-based"""
        try:
            # Verifica se il sensore esiste
            current_state = self.get_state(sensor_name)
            if current_state is None:
                # Crea il sensore
                self.set_state(sensor_name, 
                              state="created",
                              attributes={"created_at": datetime.now().isoformat()})
                self.log(f"🔍 Creato sensore {sensor_name}")
            
            # Imposta la risposta
            self.set_state(sensor_name, 
                          state="completed",
                          attributes=result)
            
            self.log(f"✅ Risposta salvata in {sensor_name}: {result}")
            
        except Exception as e:
            self.error(f"Errore creazione sensore risposta {sensor_name}: {e}")
    
    def monitor_file_requests(self, kwargs):
        """Monitora richieste tramite file system (fallback secondario)"""
        try:
            if not os.path.exists(self.api_path):
                return
                
            for filename in os.listdir(self.api_path):
                if filename.endswith('_request.json'):
                    filepath = os.path.join(self.api_path, filename)
                    self.process_file_request(filename, filepath)
                    
        except Exception as e:
            self.error(f"Errore monitoraggio file requests: {e}")
    
    def process_file_request(self, filename, filepath):
        """Processa una richiesta da file"""
        try:
            self.log(f"🔍 FILE REQUEST: Processando {filename}")
            
            # Leggi la richiesta
            with open(filepath, 'r') as f:
                request_data = json.load(f)
            
            # Rimuovi il file di richiesta
            os.remove(filepath)
            
            # Processa in base al tipo di richiesta
            response_data = None
            response_file = None
            
            if filename == "auth_setup_request.json":
                response_data, _ = self.api_auth_setup(request_data)
                response_file = "auth_setup_response.json"
                
            elif filename == "auth_login_request.json":
                response_data, _ = self.api_auth_login(request_data)
                response_file = "auth_login_response.json"
                
            elif filename == "entities_request.json":
                request_data["__headers"] = {"Authorization": f"Bearer {request_data.get('token', '')}"}
                response_data, _ = self.api_get_entities(request_data)
                response_file = "entities_response.json"
                
            elif filename == "sync_request.json":
                request_data["__headers"] = {"Authorization": f"Bearer {request_data.get('token', '')}"}
                response_data, _ = self.api_sync_configs(request_data)
                response_file = "sync_response.json"
                
            elif filename == "save_request.json":
                request_data["__headers"] = {"Authorization": f"Bearer {request_data.get('token', '')}"}
                response_data, _ = self.api_save_config(request_data)
                response_file = "save_response.json"
            
            # Salva la risposta
            if response_data and response_file:
                response_path = os.path.join(self.api_path, response_file)
                response_data['timestamp'] = datetime.now().isoformat()
                
                with open(response_path, 'w') as f:
                    json.dump(response_data, f, indent=2)
                    
                self.log(f"🔍 FILE REQUEST: Risposta salvata in {response_file}")
                
        except Exception as e:
            self.error(f"Errore processamento file request {filename}: {e}")
    
    def update_auth_status_file(self):
        """Aggiorna il file di stato autenticazione e crea sensore HA"""
        try:
            has_password = os.path.exists(self.auth_file)
            
            # Aggiorna file JSON
            status = {
                "has_password": has_password,
                "last_update": datetime.now().isoformat(),
                "system_mode": "secure_dual_fallback",
                "api_available": True,
                "security_active": True,
                "version": "3.0.0",
                "directories_initialized": True,
                "yaml_format_support": "dual"
            }
            
            status_file = os.path.join(self.www_path, "auth_status.json")
            
            # Assicurati che la directory esista
            os.makedirs(self.www_path, exist_ok=True)
            
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            # Crea anche un sensore in HA per facile accesso
            self.set_state("sensor.southtech_auth_status", 
                          state="configured" if has_password else "not_configured",
                          attributes={
                              "has_password": has_password,
                              "last_update": datetime.now().isoformat(),
                              "system_mode": "secure_dual_fallback",
                              "api_endpoints_active": True,
                              "file_fallback_active": True,
                              "security_system_active": True,
                              "blocked_users": len(self.blocked_users),
                              "total_attempt_counters": len(self.attempt_counters),
                              "directories_initialized": True,
                              "yaml_format_support": "dual"
                          })
                
            self.log(f"🔍 AUTH STATUS: Aggiornato - has_password: {has_password}")
            
        except Exception as e:
            self.error(f"Errore aggiornamento status auth: {e}")
            # In caso di errore, almeno crea il sensore HA
            try:
                self.set_state("sensor.southtech_auth_status", 
                              state="error",
                              attributes={
                                  "error": str(e),
                                  "last_update": datetime.now().isoformat()
                              })
            except:
                pass
    
    def system_heartbeat(self, kwargs):
        """Heartbeat del sistema per monitoraggio avanzato"""
        try:
            # Aggiorna sensore di sistema
            self.set_state("sensor.southtech_system_status",
                          state="online",
                          attributes={
                              "last_heartbeat": datetime.now().isoformat(),
                              "active_tokens": len(self.active_tokens),
                              "api_endpoints": 9,  # Aggiornato numero endpoint
                              "fallback_modes": ["sensor", "file"],
                              "version": "3.0.0",
                              "yaml_format_support": "dual",
                              "security_features": {
                                  "anti_bruteforce": True,
                                  "blocked_users": len(self.blocked_users),
                                  "attempt_counters": len(self.attempt_counters),
                                  "notifications": True
                              }
                          })
        except Exception as e:
            self.error(f"Errore heartbeat: {e}")
    
    # === METODI UTILITY ===
    
    def generate_token(self):
        """Genera un token di sessione"""
        token = secrets.token_urlsafe(32)
        token_data = {
            "created_at": time.time(),
            "expires_at": time.time() + (8 * 3600)  # 8 ore
        }
        self.active_tokens[token] = token_data
        return token
    
    def verify_token(self, token):
        """Verifica validità del token"""
        if not token or token not in self.active_tokens:
            return False
        
        token_data = self.active_tokens[token]
        if time.time() > token_data["expires_at"]:
            del self.active_tokens[token]
            return False
        
        return True
    
    def cleanup_expired_tokens(self, kwargs):
        """Rimuove i token scaduti"""
        current_time = time.time()
        expired_tokens = [
            token for token, data in self.active_tokens.items()
            if current_time > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self.active_tokens[token]
        
        if expired_tokens:
            self.log(f"🧹 Rimossi {len(expired_tokens)} token scaduti")
    
    def create_backup(self):
        """Crea un backup del file apps.yaml"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"apps_yaml_backup_{timestamp}.yaml"
            backup_path = os.path.join(self.backup_path, backup_filename)
            
            shutil.copy2(self.apps_yaml_path, backup_path)
            
            self.log(f"📦 Backup creato: {backup_filename}")
            return backup_filename
            
        except Exception as e:
            self.error(f"Errore creazione backup: {e}")
            return None
    
    def generate_helpers_sync(self, configurations):
        """Genera automaticamente gli helper per ogni configurazione"""
        helpers_created = 0
        
        for config in configurations:
            light_entity = config.get('light_entity', '')
            if not light_entity:
                continue
                
            base_id = light_entity.replace('light.', '')
            
            try:
                # Nota: Home Assistant non supporta la creazione dinamica di helper via API
                # Questa funzione può solo suggerire quali helper creare
                self.log(f"ℹ️ Helper da creare manualmente per {base_id}:")
                self.log(f"  - input_boolean.{base_id}_enable_sensor")
                self.log(f"  - input_boolean.{base_id}_enable_automation")
                self.log(f"  - input_number.{base_id}_timer_minutes_on_push")
                self.log(f"  - etc...")
                
            except Exception as e:
                self.error(f"Errore suggerimento helper per {base_id}: {e}")
        
        return helpers_created
    
    def setup_communication_entities(self):
        """Setup entità di comunicazione per fallback"""
        try:
            # Crea sensori di comunicazione se non esistono
            communication_entities = [
                "sensor.southtech_system_status",
                "sensor.southtech_auth_status",
                "sensor.southtech_security_log",
                "sensor.southtech_setup_request",
                "sensor.southtech_setup_response", 
                "sensor.southtech_login_request",
                "sensor.southtech_login_response",
                "sensor.southtech_reset_request",
                "sensor.southtech_reset_response"
            ]
            
            for entity in communication_entities:
                try:
                    current_state = self.get_state(entity)
                    if current_state is None:
                        # Inizializza l'entità se non esiste
                        if "system_status" in entity:
                            self.set_state(entity, state="initializing", 
                                         attributes={"initialized": datetime.now().isoformat()})
                        elif "auth_status" in entity:
                            self.set_state(entity, state="unknown",
                                         attributes={"initialized": datetime.now().isoformat()})
                        elif "security_log" in entity:
                            self.set_state(entity, state="info",
                                         attributes={
                                             "initialized": datetime.now().isoformat(),
                                             "blocked_users": 0,
                                             "total_attempts": 0
                                         })
                        else:
                            self.set_state(entity, state="unavailable",
                                         attributes={"initialized": datetime.now().isoformat()})
                        
                        self.log(f"🔍 Inizializzato sensore: {entity}")
                except Exception as e:
                    self.error(f"Errore inizializzazione {entity}: {e}")
                    
        except Exception as e:
            self.error(f"Errore setup comunicazione: {e}")
    
    def cleanup_old_backups(self, kwargs):
        """Pulisce i backup vecchi mantenendo solo gli ultimi"""
        keep_count = 10
        
        try:
            if not os.path.exists(self.backup_path):
                return
            
            # Lista tutti i file di backup
            backup_files = []
            for filename in os.listdir(self.backup_path):
                if filename.startswith("apps_yaml_backup_") and filename.endswith(".yaml"):
                    filepath = os.path.join(self.backup_path, filename)
                    backup_files.append((filepath, os.path.getmtime(filepath)))
            
            # Ordina per data di modifica (più recenti prima)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Rimuovi i backup più vecchi
            for filepath, _ in backup_files[keep_count:]:
                try:
                    os.remove(filepath)
                    self.log(f"🗑️ Rimosso backup vecchio: {os.path.basename(filepath)}")
                except Exception as e:
                    self.error(f"Errore rimozione backup {filepath}: {e}")
        
        except Exception as e:
            self.error(f"Errore pulizia backup: {e}")
    
    def check_file_integrity(self):
        """Controlla la integrità del file apps.yaml"""
        try:
            if not os.path.exists(self.apps_yaml_path):
                return True, "File non esiste"
            
            with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Controlla se il file è parsabile come YAML
            try:
                yaml.safe_load(content)
                return True, "File integro"
            except yaml.YAMLError as e:
                return False, f"Errore YAML: {e}"
                
        except Exception as e:
            return False, f"Errore lettura file: {e}"
    
    def periodic_integrity_check(self, kwargs):
        """Controllo periodico dell'integrità del file"""
        is_valid, message = self.check_file_integrity()
        if not is_valid:
            self.error(f"⚠️ Problema integrità file apps.yaml: {message}")
            
            # Aggiorna sensore di sistema con warning
            try:
                self.set_state("sensor.southtech_system_status",
                              state="warning", 
                              attributes={
                                  "last_check": datetime.now().isoformat(),
                                  "integrity_issue": message,
                                  "action_required": "Controlla file apps.yaml"
                              })
            except:
                pass
    
    def get_system_info(self):
        """Restituisce informazioni di sistema avanzate"""
        return {
            "apps_yaml_exists": os.path.exists(self.apps_yaml_path),
            "auth_configured": os.path.exists(self.auth_file),
            "backup_count": len([f for f in os.listdir(self.backup_path) 
                               if f.startswith("apps_yaml_backup_")]) if os.path.exists(self.backup_path) else 0,
            "active_sessions": len(self.active_tokens),
            "version": "3.0.0",
            "yaml_format_support": "dual",
            "communication_modes": ["api_direct", "sensor_fallback", "file_fallback"],
            "endpoints_available": 9,
            "fallback_status": "active",
            "security": {
                "anti_bruteforce": True,
                "blocked_users": len(self.blocked_users),
                "attempt_counters": len(self.attempt_counters),
                "notifications_enabled": True
            }
        }
    
    def register_additional_endpoints(self):
        """Registra endpoint diagnostici aggiuntivi"""
        try:
            self.register_endpoint(self.api_diagnostics, "southtech_diagnostics")
            self.register_endpoint(self.api_emergency_reset, "southtech_emergency_reset")
            self.log("🔍 Endpoint diagnostici registrati")
        except Exception as e:
            self.error(f"Errore registrazione endpoint diagnostici: {e}")
    
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
                "system": self.get_system_info(),
                "files": {
                    "auth_file_exists": os.path.exists(self.auth_file),
                    "apps_yaml_exists": os.path.exists(self.apps_yaml_path),
                    "www_path_exists": os.path.exists(self.www_path),
                    "api_path_exists": os.path.exists(self.api_path),
                    "backup_path_exists": os.path.exists(self.backup_path),
                    "security_file_exists": os.path.exists(self.security_file),
                    "index_html_exists": os.path.exists(os.path.join(self.www_path, "index.html")),
                    "light_presence_html_exists": os.path.exists(os.path.join(self.www_path, "light_presence.html"))
                },
                "tokens": {
                    "active_count": len(self.active_tokens),
                    "tokens_list": [
                        {
                            "token": token[:8] + "...",
                            "created": datetime.fromtimestamp(data["created_at"]).isoformat(),
                            "expires": datetime.fromtimestamp(data["expires_at"]).isoformat(),
                            "expired": time.time() > data["expires_at"]
                        }
                        for token, data in self.active_tokens.items()
                    ]
                },
                "security": {
                    "blocked_users": len(self.blocked_users),
                    "attempt_counters": len(self.attempt_counters),
                    "blocked_details": [
                        {
                            "user_id": uid[:20],
                            "blocked_until": datetime.fromtimestamp(until).isoformat(),
                            "remaining_seconds": max(0, int(until - time.time()))
                        }
                        for uid, until in self.blocked_users.items()
                    ]
                },
                "configurations": {
                    "count": len(self.read_existing_configs()),
                    "valid": True
                },
                "last_check": datetime.now().isoformat()
            }
            
            return diagnostics
            
        except Exception as e:
            self.error(f"Errore generazione diagnostiche: {e}")
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
            self.log("🚨 EMERGENCY RESET: Avviato reset di emergenza")
            
            # Invalida tutti i token
            self.active_tokens.clear()
            
            # Reset completo sistema sicurezza
            self.blocked_users.clear()
            self.attempt_counters.clear()
            
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
                    self.set_state(sensor, state="unavailable")
                except:
                    pass
            
            # Pulisci directory API
            if os.path.exists(self.api_path):
                for filename in os.listdir(self.api_path):
                    if filename.endswith('.json'):
                        try:
                            os.remove(os.path.join(self.api_path, filename))
                        except:
                            pass
            
            # Salva dati aggiornati
            self.save_security_data()
            
            # Aggiorna stato sistema
            self.set_state("sensor.southtech_system_status",
                          state="reset", 
                          attributes={
                              "reset_time": datetime.now().isoformat(),
                              "reason": "emergency_reset",
                              "tokens_cleared": True,
                              "temp_files_cleared": True,
                              "security_counters_reset": True
                          })
            
            self.log("✅ EMERGENCY RESET: Completato con successo")
            return True
            
        except Exception as e:
            self.error(f"❌ EMERGENCY RESET: Errore: {e}")
            return False
    
    def api_validate_token(self, data):
        """Valida token Home Assistant"""
        try:
            user_id = self.get_user_id(data)
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423  # 423 Locked
            
            ha_token = data.get("ha_token")
            if not ha_token:
                self.record_attempt(user_id, "token_validation", False)
                return {"error": "Token richiesto"}, 400
            
            # Simula validazione token (in realtà dovrebbe testare con HA API)
            # Per ora assumiamo che sia valido se ha lunghezza corretta
            if len(ha_token) < 50:
                self.record_attempt(user_id, "token_validation", False)
                return {"error": "Token non valido"}, 401
            
            # Token valido
            self.record_attempt(user_id, "token_validation", True)
            
            # Controlla se password esiste
            has_password = os.path.exists(self.auth_file)
            
            return {
                "valid": True,
                "has_password": has_password,
                "user_id": user_id[:20]
            }, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def api_reset_system(self, data):
        """Reset completo del sistema"""
        try:
            user_id = self.get_user_id(data)
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            self.log(f"🔄 RESET SISTEMA richiesto da {user_id[:20]}")
            
            # Cancella file auth
            if os.path.exists(self.auth_file):
                os.remove(self.auth_file)
                self.log("🗑️ File auth cancellato")
            
            # Cancella token attivi
            self.active_tokens.clear()
            
            # Reset contatori per questo utente (permette reset anche se bloccato)
            if user_id in self.attempt_counters:
                del self.attempt_counters[user_id]
            if user_id in self.blocked_users:
                del self.blocked_users[user_id]
            
            # Aggiorna file status
            self.update_auth_status_file()
            
            # Log evento
            self.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema completato")
            
            # Salva dati
            self.save_security_data()
            
            return {"success": True, "message": "Sistema resettato"}, 200
            
        except Exception as e:
            self.error(f"Errore reset sistema: {e}")
            return {"error": str(e)}, 500
    
    # === API ENDPOINTS MIGLIORATI ===
    
    def api_auth_status(self, data):
        """Controlla se esiste una password configurata"""
        self.log("🔍 AUTH STATUS: Endpoint chiamato via API diretta")
        try:
            result = {"has_password": os.path.exists(self.auth_file)}
            self.log(f"🔍 AUTH STATUS: Ritornando {result}")
            return result, 200
        except Exception as e:
            self.error(f"❌ AUTH STATUS: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_setup(self, data):
        """Setup iniziale della password con sicurezza"""
        try:
            user_id = self.get_user_id(data)
            self.log(f"🔍 AUTH SETUP: Richiesta da {user_id[:20]}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            if os.path.exists(self.auth_file):
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
            
            # Genera salt e hash
            salt = secrets.token_hex(32)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            # Salva i dati di autenticazione
            auth_data = {
                "password_hash": password_hash,
                "salt": salt,
                "created_at": datetime.now().isoformat(),
                "last_changed": datetime.now().isoformat(),
                "created_by": user_id[:20]
            }
            
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            # Genera token
            token = self.generate_token()
            
            # Aggiorna file di stato
            self.update_auth_status_file()
            
            # Registra successo
            self.record_attempt(user_id, "password_setup", True)
            
            self.log("✅ Password configurata con successo")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.error(f"❌ AUTH SETUP: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_login(self, data):
        """Login con password con sicurezza"""
        try:
            user_id = self.get_user_id(data)
            self.log(f"🔍 AUTH LOGIN: Richiesta da {user_id[:20]}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            if not os.path.exists(self.auth_file):
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password non configurata"}, 400
            
            password = data.get("password")
            if not password:
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password richiesta"}, 400
            
            # Carica i dati di autenticazione
            with open(self.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            # Verifica password
            salt = auth_data["salt"]
            stored_hash = auth_data["password_hash"]
            provided_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            if provided_hash != stored_hash:
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password non corretta"}, 401
            
            # Genera token
            token = self.generate_token()
            
            # Registra successo
            self.record_attempt(user_id, "password_login", True)
            
            self.log("✅ Login effettuato con successo")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.error(f"❌ AUTH LOGIN: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_auth_change(self, data):
        """Cambio password"""
        self.log("🔍 AUTH CHANGE: Endpoint chiamato via API diretta")
        
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
            with open(self.auth_file, 'r') as f:
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
            
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            # Invalida tutti i token esistenti
            self.active_tokens.clear()
            
            self.log("✅ Password cambiata con successo via API")
            return {"success": True}, 200
            
        except Exception as e:
            self.error(f"❌ AUTH CHANGE: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_get_entities(self, data):
        """Recupera le entità di Home Assistant"""
        self.log("🔍 ENTITIES: Endpoint chiamato via API diretta")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            # Recupera tutte le entità
            all_states = self.get_state()
            
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
                elif entity_id.startswith('sensor.') and ('illuminance' in entity_id.lower() or 'lux' in entity_id.lower()):
                    entities["sensors"].append({
                        "entity_id": entity_id,
                        "friendly_name": state_obj.get("attributes", {}).get("friendly_name", entity_id)
                    })
            
            # Ordina per nome friendly
            for category in entities.values():
                category.sort(key=lambda x: x["friendly_name"].lower())
            
            self.log(f"📋 Recuperate {len(entities['lights'])} luci, {len(entities['binary_sensors'])} sensori binari, {len(entities['sensors'])} sensori")
            
            return entities, 200
            
        except Exception as e:
            self.error(f"❌ ENTITIES: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_sync_configs(self, data):
        """Sincronizza le configurazioni dal file apps.yaml"""
        self.log("🔍 SYNC: Endpoint chiamato via API diretta")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            configurations = self.read_existing_configs()
            
            result = {
                "configurations": configurations,
                "last_sync": datetime.now().isoformat(),
                "file_exists": os.path.exists(self.apps_yaml_path),
                "yaml_format_support": "dual"
            }
            
            self.log(f"🔄 Sincronizzate {len(configurations)} configurazioni via API")
            return result, 200
            
        except Exception as e:
            self.error(f"❌ SYNC: Errore: {e}")
            return {"error": str(e)}, 500
    
    def api_save_config(self, data):
        """Salva la configurazione nel file apps.yaml"""
        self.log("🔍 SAVE: Endpoint chiamato via API diretta")
        
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
            
            # Crea backup del file esistente
            backup_file = None
            if os.path.exists(self.apps_yaml_path):
                backup_file = self.create_backup()
            
            # Salva la configurazione
            self.save_yaml_configuration(yaml_content)
            
            # Genera gli helper se richiesto
            helpers_created = 0
            try:
                helpers_created = self.generate_helpers_sync(configurations)
            except Exception as e:
                self.error(f"Errore generazione helper: {e}")
            
            response = {
                "success": True,
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "helpers_created": helpers_created,
                "timestamp": datetime.now().isoformat(),
                "yaml_format": "new_extended"
            }
            
            self.log("✅ Configurazione salvata con successo via API")
            return response, 200
            
        except Exception as e:
            self.error(f"❌ SAVE: Errore: {e}")
            return {"error": str(e)}, 500
    
    # === SISTEMA FALLBACK MIGLIORATO ===
    
    def monitor_sensor_requests(self, kwargs):
        """Monitora richieste tramite sensori Home Assistant (fallback principale)"""
        try:
            # Setup Request
            setup_sensor = self.get_state("sensor.southtech_setup_request")
            if setup_sensor and setup_sensor == "pending":
                self.process_sensor_setup_request()
            
            # Login Request  
            login_sensor = self.get_state("sensor.southtech_login_request")
            if login_sensor and login_sensor == "pending":
                self.process_sensor_login_request()
                
            # Reset Request
            reset_sensor = self.get_state("sensor.southtech_reset_request")
            if reset_sensor and reset_sensor == "pending":
                self.process_sensor_reset_request()
                
        except Exception as e:
            self.error(f"Errore monitoraggio sensor requests: {e}")
    
    def process_sensor_setup_request(self):
        """Processa richiesta setup via sensore"""
        try:
            attrs = self.get_state("sensor.southtech_setup_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "setup":
                return
                
            user_id = f"browser_{request_data.get('browser_id', 'unknown')}"
            password = request_data.get("password")
            password_confirm = request_data.get("password_confirm")
            
            self.log(f"🔍 SENSOR SETUP: Processando setup da {user_id[:20]}")
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            elif os.path.exists(self.auth_file):
                self.record_attempt(user_id, "password_setup", False)
                result = {"success": False, "error": "Password già configurata"}
            elif not password or not password_confirm:
                self.record_attempt(user_id, "password_setup", False)
                result = {"success": False, "error": "Password e conferma richieste"}
            elif password != password_confirm:
                self.record_attempt(user_id, "password_setup", False)
                result = {"success": False, "error": "Le password non coincidono"}
            elif len(password) < 6:
                self.record_attempt(user_id, "password_setup", False)
                result = {"success": False, "error": "Password troppo corta"}
            else:
                # Genera salt e hash
                salt = secrets.token_hex(32)
                password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                
                auth_data = {
                    "password_hash": password_hash,
                    "salt": salt,
                    "created_at": datetime.now().isoformat(),
                    "last_changed": datetime.now().isoformat(),
                    "created_by": user_id[:20]
                }
                
                with open(self.auth_file, 'w') as f:
                    json.dump(auth_data, f, indent=2)
                
                token = self.generate_token()
                self.update_auth_status_file()
                
                self.record_attempt(user_id, "password_setup", True)
                result = {"success": True, "token": token}
                self.log("✅ Setup completato via sensore")
            
            # Crea il sensore di risposta
            self.create_response_sensor("sensor.southtech_setup_response", result)
            
            # Rimuovi richiesta
            self.set_state("sensor.southtech_setup_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor setup: {e}")
            self.create_response_sensor("sensor.southtech_setup_response", 
                                       {"success": False, "error": str(e)})
    
    def terminate(self):
        """Cleanup alla terminazione"""
        try:
            self.log("🛑 SouthTech Configurator terminazione in corso...")
            
            # Salva dati di sicurezza
            self.save_security_data()
            
            # Salva stato finale
            self.set_state("sensor.southtech_system_status",
                          state="offline", 
                          attributes={
                              "shutdown_time": datetime.now().isoformat(),
                              "final_token_count": len(self.active_tokens) if hasattr(self, 'active_tokens') else 0,
                              "final_blocked_users": len(self.blocked_users) if hasattr(self, 'blocked_users') else 0,
                              "clean_shutdown": True,
                              "yaml_format_support": "dual"
                          })
            
            # Pulisci token e contatori
            if hasattr(self, 'active_tokens'):
                self.active_tokens.clear()
            if hasattr(self, 'blocked_users'):
                self.blocked_users.clear()
            if hasattr(self, 'attempt_counters'):
                self.attempt_counters.clear()
            
            self.log("✅ SouthTech Configurator terminato correttamente con pulizia sicurezza")
            
        except Exception as e:
            self.error(f"Errore durante terminazione: {e}")
