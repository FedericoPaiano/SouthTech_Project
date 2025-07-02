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
        self.log("🚀 SouthTech Configurator inizializzato - Versione con WebSocket FIXED")
        
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
        
        # 🔧 Inizializza last_processed
        self.last_processed = {}
        
        # Inizializza la struttura completa delle directory e file
        self.initialize_directory_structure()
        
        # Carica i dati di sicurezza esistenti
        self.load_security_data()
        
        # 🚨 SPOSTA QUI: Registra gli endpoint API AppDaemon DOPO la definizione dei metodi
        # (viene fatto in setup_endpoints)
        
        # Sistema principale: Direct File Write con WebSocket interno
        self.setup_internal_websocket_handler()
        
        # Sistema fallback: Sensori ottimizzati
        self.setup_sensor_fallback()
        
        # Crea file di stato iniziale
        self.update_auth_status_file()
        
        # Setup entità di comunicazione per fallback
        self.setup_communication_entities()
        
        # ✅ REGISTRA ENDPOINT ALLA FINE (dopo che tutti i metodi sono definiti)
        self.setup_endpoints()
        
        # Monitora richieste via sensori ogni 2 secondi (sistema fallback)
        self.run_every(self.monitor_sensor_requests, "now+5", 5)
        
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
        self.log("🚫 Template sensors RIMOSSI - filtro gestito via WebSocket frontend")
        
        # Log informazioni di sistema
        self.log_system_info()

    # 🔧 CORREZIONE 4: Log di sistema aggiornato
    def log_system_info(self):
        """Log informazioni del sistema - VERSIONE SEMPLIFICATA"""
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
                    "version": "3.0.0",  # ← Mantieni versione stabile
                    "mode": "rest_endpoints_only"  # ← Indica modalità semplificata
                }
            }
            
            self.log(f"📊 INFO SISTEMA: {json.dumps(info, indent=2)}")
            
        except Exception as e:
            self.error(f"Errore log system info: {e}")

    # 🔧 Estrazione sezione YAML
    def _extract_yaml_section(self, content):
        """Estrae la sezione controllo luci dal contenuto YAML"""
        try:
            # Prova nuovo formato prima
            start_line_idx = content.find(self.new_start_line)
            if start_line_idx != -1:
                self.log("✅ Trovata sezione formato NUOVO")
                start_block_idx = content.rfind(self.new_start_marker, 0, start_line_idx)
                end_line_idx = content.find(self.new_end_line, start_line_idx)
                
                if end_line_idx != -1:
                    end_block_idx = content.find(self.new_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.new_end_marker)
                        return content[start_block_idx:end_block_idx]
            
            # Prova formato vecchio
            old_start_idx = content.find(self.start_marker)
            old_end_idx = content.find(self.end_marker)
            
            if old_start_idx != -1 and old_end_idx != -1:
                self.log("✅ Trovata sezione formato VECCHIO")
                old_end_idx += len(self.end_marker)
                return content[old_start_idx:old_end_idx]
            
            # Nessuna sezione trovata
            return None
            
        except Exception as e:
            self.error(f"Errore estrazione sezione YAML: {e}")
            return None

    # === INIZIALIZZAZIONE STRUTTURA DIRECTORY ===
    
    # 🔧 CORREZIONE 2: Gestione sicura delle directory
    def initialize_directory_structure(self):
        """Inizializza la struttura completa di directory e file necessari"""
        try:
            self.log("🏗️ Inizializzazione struttura directory...")
            self.log(f"🎯 Percorso target: {self.www_path}")
            
            # Crea le directory necessarie con gestione errori
            directories = [
                self.www_path,
                self.backup_path, 
                self.api_path
            ]
            
            for directory in directories:
                try:
                    if not os.path.exists(directory):
                        os.makedirs(directory, mode=0o755, exist_ok=True)
                        self.log(f"📁 Creata directory: {directory}")
                    else:
                        self.log(f"✓ Directory già esistente: {directory}")
                        
                    # 🔧 FIX: Verifica permessi dopo creazione
                    if not os.access(directory, os.W_OK):
                        raise PermissionError(f"Permessi di scrittura mancanti: {directory}")
                        
                except PermissionError as e:
                    self.error(f"❌ Errore permessi directory {directory}: {e}")
                    raise
                except Exception as e:
                    self.error(f"❌ Errore creazione directory {directory}: {e}")
                    raise
            
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

    def create_atomic_backup(self):
        """Crea backup atomico se file esiste"""
        if not os.path.exists(self.apps_yaml_path):
            return None
            
        timestamp = int(time.time())
        backup_file = f"{self.apps_yaml_path}.backup_{timestamp}"
        
        try:
            shutil.copy2(self.apps_yaml_path, backup_file)
            return backup_file
        except Exception as e:
            self.error(f"Errore creazione backup: {e}")
            return None
    
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

    # ================================================================
    # 1. WEBSOCKET (PRIMARIO) - Mantiene l'implementazione esistente
    # ================================================================

    def websocket_save_service(self, namespace, domain, service, kwargs, **kwds):
        """Handler WebSocket con metodi avanzati"""
        try:
            self.log("🔌 WEBSOCKET: Ricevuta richiesta (metodo avanzato)")
            
            if kwargs.get("test_mode"):
                return {"test_mode": True, "advanced_processing": True}
            
            configurations = kwargs.get("configurations", [])
            if not configurations:
                return {"success": False, "error": "Configurazioni richieste"}
            
            # 🆕 USA METODO AVANZATO
            result = self.execute_save_advanced("websocket", configurations, kwargs)
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === SISTEMA ANTI-BRUTEFORCE ===

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
            self.error(f"Errore get_user_id_unified: {e}")
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

    def is_new_request(self, request_type, attributes):
        """Verifica se è una nuova richiesta basandosi su timestamp"""
        request_timestamp = attributes.get('timestamp')
        if not request_timestamp:
            return True
            
        last_processed = self.last_processed.get(request_type)
        if last_processed != request_timestamp:
            self.last_processed[request_type] = request_timestamp
            return True
            
        return False
    
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
    
    def read_existing_configs(self):
        """Legge le configurazioni esistenti da apps.yaml - Supporto doppio formato"""
        configurations = []
        
        try:
            if not os.path.exists(self.apps_yaml_path):
                self.log("⚠️ File apps.yaml non trovato")
                return configurations
            
            with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # ✅ CORREZIONE: Estrai la sezione YAML dal contenuto
            yaml_content = self._extract_yaml_section(content)
            
            if yaml_content:
                configurations = self._parse_yaml_configurations(yaml_content)
            else:
                self.log("ℹ️ Sezione controllo luci non trovata in apps.yaml")
            
            self.log(f"📋 Caricate {len(configurations)} configurazioni dal file apps.yaml")
            return configurations
            
        except Exception as e:
            self.error(f"Errore lettura apps.yaml: {e}")
            return configurations
    
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
        """Salva la configurazione YAML con spazi di separazione corretti"""
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
                # ✅ CORREZIONE: Mantieni spazio di separazione
                if existing_content and not existing_content.endswith('\n'):
                    existing_content += '\n'
                
                # Aggiungi con spazio di separazione dalla sezione precedente
                new_content = existing_content + '\n' + yaml_content.rstrip('\n') + '\n'
            
            # Scrivi il nuovo contenuto
            with open(self.apps_yaml_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log("💾 Configurazione YAML salvata in apps.yaml")
            return True
            
        except Exception as e:
            self.error(f"Errore salvataggio YAML: {e}")
            raise

    # 4. NUOVA FUNZIONE: Salva contenuto YAML in modo sicuro
    def save_yaml_content_safe(self, yaml_content):
        """Salva contenuto YAML con massima sicurezza"""
        try:
            # Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.apps_yaml_path):
                with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.log(f"📖 Letto file esistente: {len(existing_content)} caratteri")
            
            # Unisci con nuovo contenuto
            new_content = self.merge_yaml_content_smart(existing_content, yaml_content)
            self.log(f"🔗 Contenuto unito: {len(new_content)} caratteri")
            
            # Verifica YAML valido PRIMA di scrivere
            try:
                import yaml
                parsed = yaml.safe_load(new_content)
                if parsed is None:
                    raise Exception("YAML risulta vuoto dopo parsing")
                self.log("✅ YAML validato correttamente")
            except yaml.YAMLError as e:
                raise Exception(f"YAML non valido: {e}")
            
            # Scrivi in file temporaneo
            temp_file = self.apps_yaml_path + ".tmp_save"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            self.log(f"💾 Scritto file temporaneo: {temp_file}")
            
            # Verifica file temporaneo
            with open(temp_file, 'r', encoding='utf-8') as f:
                temp_content = f.read()
            
            if temp_content != new_content:
                raise Exception("Contenuto file temporaneo non corrisponde")
            
            # Crea backup di sicurezza
            if os.path.exists(self.apps_yaml_path):
                safety_backup = self.apps_yaml_path + ".safety_backup"
                shutil.copy2(self.apps_yaml_path, safety_backup)
                self.log(f"🛡️ Backup sicurezza: {safety_backup}")
            
            # Sostituisci file originale
            shutil.move(temp_file, self.apps_yaml_path)
            self.log("🔄 File originale sostituito")
            
        except Exception as e:
            # Pulizia in caso di errore
            temp_file = self.apps_yaml_path + ".tmp_save"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    self.log("🗑️ File temporaneo rimosso")
                except:
                    pass
            raise e

    # Unisce contenuto YAML intelligentemente
    def merge_yaml_content_smart(self, existing_content, new_yaml_content):
        """Unisce contenuto YAML con spazi di separazione corretti"""
        
        # Marcatori nuovo formato (priorità)
        new_start_marker = "################################################################################"
        new_start_line = "#                      START CONTROLLO LUCI AUTOMATICHE                        #"
        new_end_line = "#                      END CONTROLLO LUCI AUTOMATICHE                          #"
        new_end_marker = "################################################################################"
        
        # Marcatori vecchio formato (compatibilità)
        old_start_marker = "# START CONTROLLO LUCI AUTOMATICHE"
        old_end_marker = "# END CONTROLLO LUCI AUTOMATICHE"
        
        self.log("🔍 Ricerca sezione esistente...")
        
        # Prova formato nuovo
        start_line_idx = existing_content.find(new_start_line)
        if start_line_idx != -1:
            self.log("✅ Trovata sezione formato NUOVO")
            start_block_idx = existing_content.rfind(new_start_marker, 0, start_line_idx)
            end_line_idx = existing_content.find(new_end_line, start_line_idx)
            
            if end_line_idx != -1:
                end_block_idx = existing_content.find(new_end_marker, end_line_idx)
                if end_block_idx != -1:
                    end_block_idx += len(new_end_marker)
                    
                    # ✅ CORREZIONE BILANCIATA: Mantiene 1 riga vuota prima e dopo
                    before = existing_content[:start_block_idx].rstrip('\n')
                    after = existing_content[end_block_idx:].lstrip('\n')
                    
                    # Assicura 1 riga vuota prima della sezione
                    if before and not before.endswith('\n'):
                        before += '\n'
                    
                    # Costruisci risultato con spazi corretti
                    result = before + '\n' + new_yaml_content.rstrip('\n')
                    
                    # Assicura 1 riga vuota dopo la sezione (se c'è contenuto dopo)
                    if after:
                        result += '\n\n' + after
                    else:
                        result += '\n'
                    
                    self.log(f"🔄 Sostituita sezione esistente (nuovo formato)")
                    return result
        
        # Prova formato vecchio
        old_start_idx = existing_content.find(old_start_marker)
        old_end_idx = existing_content.find(old_end_marker)
        
        if old_start_idx != -1 and old_end_idx != -1:
            self.log("✅ Trovata sezione formato VECCHIO")
            old_end_idx += len(old_end_marker)
            
            # ✅ CORREZIONE BILANCIATA: Mantiene 1 riga vuota prima e dopo
            before = existing_content[:old_start_idx].rstrip('\n')
            after = existing_content[old_end_idx:].lstrip('\n')
            
            # Assicura 1 riga vuota prima della sezione
            if before and not before.endswith('\n'):
                before += '\n'
            
            # Costruisci risultato con spazi corretti
            result = before + '\n' + new_yaml_content.rstrip('\n')
            
            # Assicura 1 riga vuota dopo la sezione (se c'è contenuto dopo)
            if after:
                result += '\n\n' + after
            else:
                result += '\n'
            
            self.log(f"🔄 Sostituita sezione esistente (vecchio formato)")
            return result
        
        # Nessuna sezione esistente
        self.log("ℹ️ Nessuna sezione esistente, aggiunta alla fine")
        
        # ✅ CORREZIONE: Mantiene spazio di separazione dalla sezione precedente
        if existing_content and not existing_content.endswith('\n'):
            existing_content += '\n'
        
        # Aggiungi con spazio di separazione
        return existing_content + '\n' + new_yaml_content.rstrip('\n') + '\n'

    def rebuild_apps_yaml_content(self, existing_content, new_section, start_idx, end_idx):
        """Ricostruisce il contenuto completo con spazi di separazione corretti"""
        try:
            if start_idx == -1 or end_idx == -1:
                # Nessuna sezione esistente, aggiungi alla fine
                if existing_content and not existing_content.endswith('\n'):
                    existing_content += '\n'
                
                # ✅ CORREZIONE: Mantieni spazio di separazione
                return existing_content + '\n' + new_section.rstrip('\n') + '\n'
            else:
                # Sostituisci sezione esistente con spazi corretti
                before = existing_content[:start_idx].rstrip('\n')
                after = existing_content[end_idx:].lstrip('\n')
                
                result = before
                if before:
                    result += '\n\n'  # 1 riga vuota prima
                
                result += new_section.rstrip('\n')
                
                if after:
                    result += '\n\n' + after  # 1 riga vuota dopo
                else:
                    result += '\n'
                
                return result
                
        except Exception as e:
            self.error(f"Errore ricostruzione contenuto apps.yaml: {e}")
            raise

    # 6. NUOVA FUNZIONE: Verifica file salvato
    def verify_saved_file(self, expected_yaml_content):
        """Verifica che il file sia stato salvato correttamente"""
        try:
            # Controlla che il file esista
            if not os.path.exists(self.apps_yaml_path):
                raise Exception("File apps.yaml non trovato dopo salvataggio")
            
            # Leggi contenuto salvato
            with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            if not saved_content:
                raise Exception("File apps.yaml è vuoto")
            
            # Verifica che contenga la nostra sezione
            if "START CONTROLLO LUCI AUTOMATICHE" not in saved_content:
                raise Exception("Sezione light_presence non trovata nel file salvato")
            
            # Verifica YAML valido
            import yaml
            try:
                parsed = yaml.safe_load(saved_content)
                if parsed is None:
                    raise Exception("File YAML risulta vuoto")
            except yaml.YAMLError as e:
                raise Exception(f"File YAML non valido: {e}")
            
            file_size = os.path.getsize(self.apps_yaml_path)
            self.log(f"✅ File verificato: {len(saved_content)} caratteri, {file_size} bytes")
            
        except Exception as e:
            self.error(f"❌ Verifica file fallita: {e}")
            raise

    # 7. Monitor salvataggio via sensori
    def monitor_save_requests(self, kwargs):
        """Monitora richieste di salvataggio via sensori (fallback) - VERSIONE MIGLIORATA"""
        try:
            save_sensor = self.get_state("sensor.southtech_save_request")
            
            if save_sensor == "pending":
                self.log("📡 SENSOR SAVE: Rilevata richiesta fallback")
                
                # Aggiorna debug
                self.set_state("sensor.southtech_websocket_debug",
                              state="fallback_active",
                              attributes={
                                  "fallback_method": "sensor",
                                  "fallback_trigger_time": datetime.now().isoformat(),
                                  "websocket_failed": True
                              })
                
                self.process_sensor_save_request()
                
        except Exception as e:
            self.error(f"Errore monitor save requests: {e}")

    # ================================================================
    # 2. SENSORI HA (FALLBACK 1) - Aggiornato con metodi avanzati
    # ================================================================

    # ================================================================
    # 5. METODI CORE AVANZATI (Indipendenti dal sistema di comunicazione)
    # ================================================================

    def process_apps_yaml_advanced(self, new_configurations):
        """
        🎯 METODO CORE: Processamento avanzato apps.yaml
        Funziona identicamente per WebSocket, Sensori e File System
        """
        try:
            self.log("🔧 CORE: Inizio processamento intelligente apps.yaml")
            
            # 1. Validazione configurazioni
            if not new_configurations:
                return {"success": False, "error": "Nessuna configurazione fornita"}
            
            valid_configs = self.validate_configurations(new_configurations)
            if not valid_configs:
                return {"success": False, "error": "Nessuna configurazione valida"}
            
            # 2. Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.apps_yaml_path):
                with open(self.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.log(f"📖 File esistente: {len(existing_content)} caratteri")
            else:
                existing_content = self.create_empty_apps_yaml_structure()
                self.log("📄 Creato template file vuoto")
            
            # 3. Analisi sezione esistente
            start_idx, end_idx = self.find_light_control_section(existing_content)
            existing_configs = set()
            
            if start_idx != -1 and end_idx != -1:
                section_content = existing_content[start_idx:end_idx]
                existing_configs = self.extract_light_configs_from_section(section_content)
                self.log(f"🔍 Configurazioni esistenti: {len(existing_configs)}")
            
            # 4. Calcola differenze
            new_config_ids = {self.generate_config_id(cfg) for cfg in valid_configs}
            configs_to_add = new_config_ids - existing_configs
            configs_to_remove = existing_configs - new_config_ids
            
            self.log(f"📊 Operazioni: +{len(configs_to_add)} -{len(configs_to_remove)}")
            
            # 5. Ottimizzazione: se identiche, non fare nulla
            if not configs_to_add and not configs_to_remove and start_idx != -1:
                return {
                    "success": True,
                    "message": "Configurazioni identiche, nessuna modifica necessaria",
                    "configurations_unchanged": len(existing_configs),
                    "optimized_skip": True
                }
            
            # 6. Genera nuova sezione
            new_section = self.generate_light_control_section(valid_configs)
            
            # 7. Ricostruisci file completo
            new_content = self.rebuild_apps_yaml_content(
                existing_content, new_section, start_idx, end_idx
            )
            
            # 8. Backup di sicurezza
            backup_file = None
            if os.path.exists(self.apps_yaml_path):
                backup_file = self.create_backup()
            
            # 9. Salvataggio atomico e sicuro
            self.atomic_file_write(self.apps_yaml_path, new_content)
            
            # 10. Verifica post-salvataggio
            self.verify_yaml_integrity(self.apps_yaml_path)
            
            # 11. Risultato dettagliato
            return {
                "success": True,
                "message": "apps.yaml aggiornato con processamento avanzato",
                "processing_method": "advanced_inspired_by_template_generator",
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "configurations_total": len(valid_configs),
                "configurations_added": len(configs_to_add),
                "configurations_removed": len(configs_to_remove),
                "configurations_unchanged": len(existing_configs & new_config_ids),
                "file_size": os.path.getsize(self.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "validation_passed": True,
                "integrity_verified": True
            }
            
        except Exception as e:
            self.error(f"❌ CORE: Errore processamento avanzato: {e}")
            
            # Tentativo di ripristino da backup se disponibile
            if 'backup_file' in locals() and backup_file:
                self.attempt_restore_from_backup(backup_file)
            
            raise

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
                # Scrittura atomica
                self.atomic_yaml_write(yaml_content)
                
                # Verifica integrità
                self.verify_yaml_integrity(self.apps_yaml_path)
                
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
            self.error(f"Errore salvataggio diretto: {e}")
            return {"success": False, "error": str(e)}

    # ================================================================
    # 4. METODO UNIFICATO AVANZATO (Usato da tutti i sistemi)
    # ================================================================

    # 🔧 Metodo execute_save_advanced
    def execute_save_advanced(self, method_type, configurations, request_data):
        """
        Metodo unificato per salvataggio avanzato
        Usato da WebSocket, Sensori e File System
        """
        try:
            self.log(f"💾 ADVANCED SAVE ({method_type.upper()}): Inizio processamento")
            
            # ✅ CORREZIONE:
            user_id = self.get_user_id_unified(request_data, method_type)
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            
            if is_blocked:
                return {
                    "success": False,
                    "error": "Utente temporaneamente bloccato",
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time()),
                    "method": f"{method_type}_blocked"
                }
            
            # 2. 🆕 PROCESSAMENTO AVANZATO (core logic)
            result = self.process_apps_yaml_advanced(configurations)
            
            # 3. Aggiungi metadati specifici del metodo
            result.update({
                "communication_method": method_type,
                "user_id": user_id[:20],
                "advanced_processing": True,
                "fallback_level": self.get_fallback_level(method_type)
            })
            
            # 4. Registra tentativo
            success = result.get("success", False)
            self.record_attempt(user_id, f"{method_type}_save_advanced", success)
            
            if success:
                self.log(f"✅ ADVANCED SAVE ({method_type.upper()}): Completato con successo")
                
                # Notifica successo
                self.create_ha_notification(
                    "✅ SouthTech: Configurazione Salvata",
                    f"Apps.yaml aggiornato con {len(configurations)} configurazioni via {method_type}"
                )
            else:
                self.log(f"❌ ADVANCED SAVE ({method_type.upper()}): Fallito")
            
            return result
            
        except Exception as e:
            self.error(f"❌ ADVANCED SAVE ({method_type.upper()}): Errore critico: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": f"{method_type}_error",
                "timestamp": datetime.now().isoformat()
            }

    def execute_yaml_save_websocket(self, yaml_content, configurations, user_id):
        """
        Esegue il salvataggio YAML per richiesta WebSocket
        """
        try:
            self.log("💾 WEBSOCKET: Inizio salvataggio apps.yaml...")
            
            # 1. Backup se file esiste
            backup_file = None
            if os.path.exists(self.apps_yaml_path):
                backup_file = self.create_backup()
                self.log(f"📦 Backup creato: {backup_file}")
            
            # 2. Salva contenuto usando metodo esistente
            self.save_yaml_content_safe(yaml_content)
            
            # 3. Verifica file salvato
            self.verify_saved_file(yaml_content)
            
            # 4. Genera helper opzionali
            helpers_created = 0
            try:
                helpers_created = self.generate_helpers_sync(configurations)
            except Exception as e:
                self.log(f"⚠️ Warning generazione helper: {e}")
            
            # 5. Risultato successo
            result = {
                "success": True,
                "message": "Configurazione salvata con successo via WebSocket",
                "method": "websocket_direct",
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "helpers_created": helpers_created,
                "configurations_count": len(configurations),
                "file_path": self.apps_yaml_path,
                "file_size": os.path.getsize(self.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id[:20]
            }
            
            self.log("✅ WEBSOCKET: Salvataggio completato con successo")
            
            # Notifica successo
            self.create_ha_notification(
                "✅ SouthTech: Configurazione Salvata",
                f"Apps.yaml aggiornato con {len(configurations)} configurazioni via WebSocket"
            )
            
            return result
            
        except Exception as e:
            self.error(f"❌ WEBSOCKET: Errore durante salvataggio: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": "websocket_error",
                "timestamp": datetime.now().isoformat()
            }

    def execute_yaml_save_sensor(self, yaml_content, configurations, user_id):
        """Esegue il salvataggio YAML per comando sensore (versione corretta)"""
        try:
            self.log("💾 SENSOR: Inizio salvataggio apps.yaml...")
            
            # 1. Backup se file esiste
            backup_file = None
            if os.path.exists(self.apps_yaml_path):
                backup_file = self.create_backup()
                self.log(f"📦 Backup creato: {backup_file}")
            else:
                self.log("📄 File apps.yaml non esiste, sarà creato")
            
            # 2. Verifica/crea directory
            yaml_dir = os.path.dirname(self.apps_yaml_path)
            if not os.path.exists(yaml_dir):
                os.makedirs(yaml_dir, exist_ok=True)
                self.log(f"📁 Creata directory: {yaml_dir}")
            
            # 3. Salva il contenuto usando il metodo esistente
            self.save_yaml_configuration(yaml_content)
            
            # 4. Genera helper opzionali
            helpers_created = 0
            try:
                helpers_created = self.generate_helpers_sync(configurations)
                if helpers_created > 0:
                    self.log(f"🔧 Generati {helpers_created} helper")
            except Exception as e:
                self.log(f"⚠️ Warning generazione helper: {e}")
            
            # 5. Risultato successo
            result = {
                "success": True,
                "message": "Configurazione salvata con successo via sensore",
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "helpers_created": helpers_created,
                "configurations_count": len(configurations),
                "file_path": self.apps_yaml_path,
                "file_size": os.path.getsize(self.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "method": "sensor_success"
            }
            
            self.log("✅ SENSOR: Salvataggio completato con successo")
            
            # Notifica successo in HA
            self.create_ha_notification(
                "✅ SouthTech: Configurazione Salvata",
                f"Apps.yaml aggiornato con {len(configurations)} configurazioni via sensore fallback"
            )
            
            return result
            
        except Exception as e:
            self.error(f"❌ SENSOR: Errore durante salvataggio: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "method": "sensor_error"
            }

    def validate_configurations(self, configurations):
        """Valida e filtra configurazioni valide"""
        valid_configs = []
        
        for i, config in enumerate(configurations):
            light_entity = config.get('light_entity', '').strip()
            presence_sensor_on = config.get('presence_sensor_on', '').strip()
            
            if not light_entity:
                self.log(f"⚠️ Config {i+1}: light_entity mancante, saltata")
                continue
                
            if not light_entity.startswith('light.'):
                self.log(f"⚠️ Config {i+1}: light_entity non valida ({light_entity}), saltata")
                continue
                
            if not presence_sensor_on:
                self.log(f"⚠️ Config {i+1}: presence_sensor_on mancante, saltata")
                continue
            
            valid_configs.append(config)
        
        self.log(f"✅ Validazione: {len(valid_configs)}/{len(configurations)} configurazioni valide")
        return valid_configs

    def atomic_file_write(self, file_path, content):
        """Scrittura atomica del file per evitare corruzioni"""
        temp_path = file_path + ".tmp_atomic"
        
        try:
            # Scrivi in file temporaneo
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Verifica file temporaneo
            with open(temp_path, 'r', encoding='utf-8') as f:
                verify_content = f.read()
            
            if verify_content != content:
                raise Exception("Contenuto file temporaneo non corrisponde")
            
            # Sostituisci atomicamente
            os.replace(temp_path, file_path)
            self.log("💾 Scrittura atomica completata")
            
        except Exception as e:
            # Pulizia in caso di errore
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise

    
    def atomic_yaml_write(self, content):
        """Scrittura atomica del file YAML"""
        temp_file = self.apps_yaml_path + ".tmp_write"
        
        try:
            # Scrivi in file temporaneo
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Verifica contenuto
            with open(temp_file, 'r', encoding='utf-8') as f:
                verify_content = f.read()
            
            if verify_content != content:
                raise Exception("Verifica contenuto fallita")
            
            # Sostituisci atomicamente
            os.replace(temp_file, self.apps_yaml_path)
            
        except Exception as e:
            # Cleanup in caso di errore
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise

    def attempt_restore_from_backup(self, backup_file):
        """Tentativo di ripristino da backup in caso di errore"""
        try:
            backup_path = os.path.join(self.backup_path, backup_file)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.apps_yaml_path)
                self.log(f"🛡️ Ripristinato da backup: {backup_file}")
                return True
        except Exception as e:
            self.error(f"❌ Errore ripristino backup: {e}")
        return False

    # 9. NUOVA FUNZIONE: Crea risposta sensore
    def create_sensor_save_response(self, result_data):
        """Crea risposta per salvataggio via sensore"""
        try:
            result_data["timestamp"] = datetime.now().isoformat()
            
            self.set_state("sensor.southtech_save_response",
                          state="completed",
                          attributes=result_data)
            
            if result_data.get("success"):
                self.log("✅ Risposta successo inviata via sensore")
            else:
                self.log(f"❌ Risposta errore inviata via sensore: {result_data.get('error')}")
                
        except Exception as e:
            self.error(f"Errore creazione risposta sensore: {e}")
    
    def _replace_yaml_new_format(self, content, yaml_content):
        """Sostituisce YAML nel nuovo formato con spazi corretti"""
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
                    
                    # ✅ CORREZIONE BILANCIATA: Mantiene spazi di separazione
                    before = content[:start_block_idx].rstrip('\n')
                    after = content[end_block_idx:].lstrip('\n')
                    
                    # Costruisci con spazi corretti
                    result = before
                    if before:
                        result += '\n\n'  # 1 riga vuota prima
                    
                    result += yaml_content.rstrip('\n')
                    
                    if after:
                        result += '\n\n' + after  # 1 riga vuota dopo
                    else:
                        result += '\n'
                    
                    return result
            
            return None
            
        except Exception as e:
            self.error(f"Errore sostituzione nuovo formato: {e}")
            return None
    
    def _replace_yaml_old_format(self, content, yaml_content):
        """Sostituisce YAML nel formato vecchio con spazi corretti"""
        try:
            start_idx = content.find(self.start_marker)
            end_idx = content.find(self.end_marker)
            
            if start_idx != -1 and end_idx != -1:
                end_idx += len(self.end_marker)
                
                # ✅ CORREZIONE BILANCIATA: Mantieni spazi di separazione
                before = content[:start_idx].rstrip('\n')
                after = content[end_idx:].lstrip('\n')
                
                # Costruisci con spazi corretti
                result = before
                if before:
                    result += '\n\n'  # 1 riga vuota prima
                
                result += yaml_content.rstrip('\n')
                
                if after:
                    result += '\n\n' + after  # 1 riga vuota dopo
                else:
                    result += '\n'
                
                return result
            
            return None
            
        except Exception as e:
            self.error(f"Errore sostituzione formato vecchio: {e}")
            return None
    
    # === API ENDPOINTS CON SICUREZZA ===
    
    def api_check_blocked(self, data):
        """Controlla se un utente è bloccato - CORRETTO"""
        try:
            # ✅ CORRETTO: Usa metodo unificato
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
    
    def create_response_sensor(self, sensor_name, result):
        """Crea un sensore di risposta per il sistema file-based - VERSIONE CORRETTA"""
        try:
            # Non verificare se il sensore esiste, crealo direttamente
            self.set_state(sensor_name, 
                          state="completed",
                          attributes=result)
            
            self.log(f"✅ Risposta salvata in {sensor_name}")
            
        except Exception as e:
            self.error(f"Errore creazione sensore risposta {sensor_name}: {e}")
            
            # Fallback: prova a crearlo forzatamente
            try:
                import time
                time.sleep(0.1)  # Piccolo delay
                self.set_state(sensor_name, 
                              state="completed",
                              attributes=result)
                self.log(f"✅ Risposta salvata in {sensor_name} (fallback)")
            except Exception as e2:
                self.error(f"Errore anche nel fallback per {sensor_name}: {e2}")
    
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
    
    # ================================================================
    # 3. FILE SYSTEM (FALLBACK 2) - Aggiornato con metodi avanzati
    # ================================================================

    def process_file_request(self, filename, filepath):
        """Processa richiesta da file con metodi avanzati"""
        try:
            if filename != "save_request.json":
                return  # Solo per richieste di salvataggio
                
            self.log("📁 FILE: Processamento con metodo avanzato")
            
            # Leggi richiesta
            with open(filepath, 'r') as f:
                request_data = json.load(f)
            os.remove(filepath)  # Rimuovi file richiesta
            
            configurations = request_data.get("configurations", [])
            if not configurations:
                response_data = {"success": False, "error": "Configurazioni mancanti"}
            else:
                # 🆕 USA METODO AVANZATO
                response_data = self.execute_save_advanced("file", configurations, request_data)
            
            # Salva risposta
            response_path = os.path.join(self.api_path, "save_response.json")
            response_data['timestamp'] = datetime.now().isoformat()
            
            with open(response_path, 'w') as f:
                json.dump(response_data, f, indent=2)
                
            self.log("📁 FILE: Risposta salvata")
            
        except Exception as e:
            self.error(f"❌ FILE: Errore: {e}")
    
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
    
    # 🔧 Heartbeat sistema aggiornato
    def system_heartbeat(self, kwargs):
        """Heartbeat del sistema per monitoraggio con protezione errori"""
        try:
            # Verifica handler WebSocket
            websocket_handler_ok = hasattr(self, 'handle_websocket_save') and callable(getattr(self, 'handle_websocket_save'))
            
            # Aggiorna sensore di sistema
            self.set_state("sensor.southtech_system_status",
                          state="online",
                          attributes={
                              "last_heartbeat": datetime.now().isoformat(),
                              "active_tokens": len(self.active_tokens) if hasattr(self, 'active_tokens') else 0,
                              "api_endpoints": 9,
                              "fallback_modes": ["sensor", "file"],
                              "version": "3.2.0",
                              "websocket_fixed": True,
                              "yaml_format_support": "dual",
                              "websocket_service": {
                                  "handler_available": websocket_handler_ok,
                                  "service_name": "appdaemon.southtech_save_yaml",
                                  "test_mode_supported": True
                              },
                              "security_features": {
                                  "anti_bruteforce": True,
                                  "blocked_users": len(self.blocked_users) if hasattr(self, 'blocked_users') else 0,
                                  "attempt_counters": len(self.attempt_counters) if hasattr(self, 'attempt_counters') else 0,
                                  "notifications": True
                              }
                          })
        except Exception as e:
            self.error(f"Errore heartbeat: {e}")
            # Fallback heartbeat minimale
            try:
                self.set_state("sensor.southtech_system_status",
                              state="error",
                              attributes={
                                  "error": str(e),
                                  "last_heartbeat": datetime.now().isoformat()
                              })
            except:
                pass

    def handle_websocket_save(self, namespace, domain, service, kwargs, **kwds):
        """Handler per servizio WebSocket save"""
        try:
            self.log("🔌 WEBSOCKET SAVE: Ricevuta richiesta")
            
            # Gestisci test mode
            if kwargs.get("test_mode"):
                return {
                    "test_mode": True,
                    "service_available": True,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Gestisci salvataggio normale
            yaml_content = kwargs.get("yaml_content")
            configurations = kwargs.get("configurations", [])
            
            if yaml_content:
                result = self.execute_yaml_save_sensor(yaml_content, configurations, "websocket_user")
                return result
            else:
                return {"success": False, "error": "Contenuto YAML mancante"}
                
        except Exception as e:
            self.error(f"Errore WebSocket save: {e}")
            return {"success": False, "error": str(e)}
    
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

    def setup_endpoints(self):
        """🔧 Registra tutti gli endpoint API AppDaemon - ALLA FINE dell'inizializzazione"""
        try:
            self.log("🔗 Registrazione endpoint API...")
            
            # Endpoint principali
            self.register_endpoint(self.api_auth_status, "southtech_auth_status")
            self.register_endpoint(self.api_auth_setup, "southtech_auth_setup")
            self.register_endpoint(self.api_auth_login, "southtech_auth_login")
            self.register_endpoint(self.api_auth_change, "southtech_auth_change")
            self.register_endpoint(self.api_get_entities, "southtech_entities")
            self.register_endpoint(self.api_sync_configs, "southtech_sync")
            self.register_endpoint(self.api_save_config, "southtech_save")
            
            # 🎯 ENDPOINT WEBSOCKET PRINCIPALE - registrato correttamente
            self.register_endpoint(self.handle_websocket_save, "southtech_save_yaml")
            
            # Endpoint sicurezza
            self.register_endpoint(self.api_validate_token, "southtech_validate_token")
            self.register_endpoint(self.api_reset_system, "southtech_reset_system")
            self.register_endpoint(self.api_check_blocked, "southtech_check_blocked")
            
            # Endpoint diagnostici
            self.register_endpoint(self.api_diagnostics, "southtech_diagnostics")
            self.register_endpoint(self.api_emergency_reset, "southtech_emergency_reset")
            
            self.log("✅ Tutti gli endpoint registrati con successo!")
            self.log("🔌 Servizio WebSocket: appdaemon.southtech_save_yaml")
            
        except Exception as e:
            self.error(f"❌ Errore registrazione endpoint: {e}")
            raise

    def setup_internal_websocket_handler(self):
        """WebSocket handler interno - non esposto come servizio HA"""
        # Crea endpoint interno per comunicazione WebSocket
        self.internal_ws_queue = []
        self.is_processing_ws = False
        
        # Monitor queue ogni secondo
        self.run_every(self.process_internal_ws_queue, "now+1", 1)
    
    def setup_sensor_fallback(self):
        """Sistema sensori ottimizzato con anti-race-condition"""
        self.sensor_locks = {
            'save': False,
            'sync': False,
            'setup': False,
            'login': False
        }
    
    # 🔧 Gestione più robusta dei sensori
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
            ]
            
            for entity in communication_entities:
                try:
                    current_state = self.get_state(entity)
                    
                    if current_state is None:
                        if "websocket_debug" in entity:
                            # ✅ SENSORE DEBUG WEBSOCKET ENHANCED
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
                                "version": "3.2.0",
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
                        
                        self.set_state(entity, state=initial_state, attributes=attributes)
                        self.log(f"🔍 Inizializzato sensore: {entity}")
                    else:
                        self.log(f"✓ Sensore già esistente: {entity}")
                        
                except Exception as e:
                    self.error(f"❌ Errore inizializzazione {entity}: {e}")
                    continue
                    
            self.log("✅ Setup sensori comunicazione completato (incluso WebSocket debug)")
            
        except Exception as e:
            self.error(f"❌ Errore setup comunicazione: {e}")

    def setup_websocket_handler(self):
        """Setup handler WebSocket principale"""
        self.register_endpoint(self.api_websocket_save, "southtech_websocket_save")
        
    def api_websocket_save(self, data):
        """Handler WebSocket unificato"""
        try:
            # Verifica token
            token = data.get("token")
            if not self.verify_token(token):
                return {"success": False, "error": "Non autorizzato"}, 401
            
            # Processa salvataggio
            configurations = data.get("configurations", [])
            result = self.execute_save_advanced("websocket", configurations, data)
            
            return result, 200
            
        except Exception as e:
            return {"success": False, "error": str(e)}, 500
    
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
        """Valida token Home Assistant - CORRETTO"""
        try:
            # ✅ CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            
            # Resto del metodo rimane invariato...
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
            has_password = os.path.exists(self.auth_file)
            
            return {
                "valid": True,
                "has_password": has_password,
                "user_id": user_id[:20]
            }, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def api_reset_system(self, data):
        """Reset completo del sistema - CORRETTO"""
        try:
            # ✅ CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            
            # Resto del metodo rimane invariato...
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            self.log(f"🔄 RESET SISTEMA richiesto da {user_id[:20]}")
            
            if os.path.exists(self.auth_file):
                os.remove(self.auth_file)
                self.log("🗑️ File auth cancellato")
            
            self.active_tokens.clear()
            
            if user_id in self.attempt_counters:
                del self.attempt_counters[user_id]
            if user_id in self.blocked_users:
                del self.blocked_users[user_id]
            
            self.update_auth_status_file()
            self.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema completato")
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
        """Setup iniziale della password con sicurezza - CORRETTO"""
        try:
            # ✅ CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(data, "api")
            self.log(f"🔍 API SETUP: Richiesta da {user_id[:20]}")
            
            # Resto del metodo rimane invariato...
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
            
            self.log("✅ Password configurata con successo")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.error(f"❌ API SETUP: Errore: {e}")
            return {"error": str(e)}, 500
    
    # 🔧 MODIFICA ANCHE GLI ENDPOINT API PER SUPPORTARE HASH
    def api_auth_login(self, data):
        """Login con password con sicurezza - VERSIONE SICURA"""
        try:
            user_id = self.get_user_id_unified(data, "api")
            self.log(f"🔍 API LOGIN: Richiesta da {user_id[:20]}")
            
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                return {
                    "blocked": True, 
                    "remaining_seconds": int(block_until - time.time())
                }, 423
            
            if not os.path.exists(self.auth_file):
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password non configurata"}, 400
            
            # 🔐 SUPPORTO HASH SICURO
            password = data.get("password")  # Legacy
            password_hash = data.get("password_hash")  # Sicuro
            security_method = data.get("security_method", "legacy")
            browser_id = data.get("browser_id", "")
            timestamp = data.get("timestamp", "")
            
            if not password and not password_hash:
                self.record_attempt(user_id, "password_login", False)
                return {"error": "Password richiesta"}, 400
            
            with open(self.auth_file, 'r') as f:
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
            
            self.log("✅ Login effettuato con successo (API sicura)")
            return {"success": True, "token": token}, 200
            
        except Exception as e:
            self.error(f"❌ API LOGIN: Errore: {e}")
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
        """Recupera le entità di Home Assistant - Versione semplificata senza template"""
        self.log("🔍 ENTITIES: Endpoint chiamato via API diretta (no template)")
        
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401
            
            # Recupera tutte le entità (il filtro ora è gestito lato frontend)
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
            
            self.log(f"📋 Recuperate: {len(entities['lights'])} luci, {len(entities['binary_sensors'])} sensori binari, {len(entities['sensors'])} sensori lux")
            
            result = {
                "entities": entities,
                "mode": "direct_no_template",
                "total_entities": len(entities['lights']) + len(entities['binary_sensors']) + len(entities['sensors']),
                "timestamp": datetime.now().isoformat()
            }
            
            return result, 200
            
        except Exception as e:
            self.error(f"❌ ENTITIES: Errore: {e}")
            return {"error": str(e)}, 500

    def api_get_areas(self, data):
        """Restituisce una lista di aree disponibili."""
        self.log("🔍 AREE: Richiesta lista aree via API")
        try:
            # Verifica token
            auth_header = data.get("__headers", {}).get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
            if not self.verify_token(token):
                return {"error": "Non autorizzato"}, 401

            # Usa la cache per restituire le aree
            areas = [{"id": area, "name": area} for area in self.area_cache.keys()]
            
            # Ordina per nome
            areas.sort(key=lambda x: x["name"].lower())
            
            self.log(f"📋 Restituite {len(areas)} aree.")
            return areas, 200

        except Exception as e:
            self.error(f"❌ AREE: Errore: {e}")
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

    # 🔧 Monitor sync sensori CORRETTA (era mancante!)
    def monitor_sensor_requests(self, kwargs):
        """Monitor sensori con protezione errori"""
        try:
            current_time = time.time()
            
            # Save Request
            if not getattr(self, 'sensor_locks', None):
                self.sensor_locks = {'save': False, 'sync': False, 'setup': False, 'login': False}
            
            if not self.sensor_locks['save']:
                save_sensor = self.get_state("sensor.southtech_save_request")
                save_attrs = self.get_state("sensor.southtech_save_request", attribute="all")
                
                if (save_sensor == "pending" and save_attrs and 
                    self.is_new_request('save', save_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['save'] = True
                    try:
                        self.process_sensor_save_request()
                    finally:
                        self.sensor_locks['save'] = False
            
            # Sync Request  
            if not self.sensor_locks['sync']:
                sync_sensor = self.get_state("sensor.southtech_sync_request")
                sync_attrs = self.get_state("sensor.southtech_sync_request", attribute="all")
                
                if (sync_sensor == "pending" and sync_attrs and
                    self.is_new_request('sync', sync_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['sync'] = True
                    try:
                        self.process_sensor_sync_request()
                    finally:
                        self.sensor_locks['sync'] = False
                        
            # Login Request
            if not self.sensor_locks['login']:
                login_sensor = self.get_state("sensor.southtech_login_request")
                login_attrs = self.get_state("sensor.southtech_login_request", attribute="all")
                
                if (login_sensor == "pending" and login_attrs and
                    self.is_new_request('login', login_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['login'] = True
                    try:
                        self.process_sensor_login_request()
                    finally:
                        self.sensor_locks['login'] = False
                        
            # Setup Request
            if not self.sensor_locks['setup']:
                setup_sensor = self.get_state("sensor.southtech_setup_request")
                setup_attrs = self.get_state("sensor.southtech_setup_request", attribute="all")
                
                if (setup_sensor == "pending" and setup_attrs and
                    self.is_new_request('setup', setup_attrs.get('attributes', {}))):
                    
                    self.sensor_locks['setup'] = True
                    try:
                        self.process_sensor_setup_request()
                    finally:
                        self.sensor_locks['setup'] = False
                        
            # Reset Request
            reset_sensor = self.get_state("sensor.southtech_reset_request")
            reset_attrs = self.get_state("sensor.southtech_reset_request", attribute="all")
            
            if (reset_sensor == "pending" and reset_attrs and
                self.is_new_request('reset', reset_attrs.get('attributes', {}))):
                
                try:
                    self.process_sensor_reset_request()
                except Exception as e:
                    self.error(f"Errore process_sensor_reset_request: {e}")
                        
        except Exception as e:
            self.error(f"Errore monitor_sensor_requests: {e}")

    # ✅ Processa richiesta sincronizzazione via sensore
    def process_sensor_sync_request(self):
        """Processa richiesta sincronizzazione via sensore - VERSIONE CORRETTA"""
        try:
            attrs = self.get_state("sensor.southtech_sync_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                self.log("⚠️ Attributi sensore sync mancanti")
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "sync_configurations":
                return
                
            user_id = f"browser_{request_data.get('browser_id', 'unknown')}"
            
            self.log(f"🔍 SENSOR SYNC: Processando sync da {user_id[:20]}")
            
            # Aggiorna debug
            self.set_state("sensor.southtech_websocket_debug",
                          state="sync_fallback",
                          attributes={
                              "fallback_method": "sensor_sync",
                              "user_id": user_id[:20],
                              "request_time": datetime.now().isoformat()
                          })
            
            # Controlla se bloccato
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            else:
                # Esegui sincronizzazione
                try:
                    configurations = self.read_existing_configs()
                    
                    result = {
                        "success": True,
                        "configurations": configurations,
                        "last_sync": datetime.now().isoformat(),
                        "file_exists": os.path.exists(self.apps_yaml_path),
                        "yaml_format_support": "dual",
                        "method": "sensor_fallback"
                    }
                    
                    self.record_attempt(user_id, "sync_configs", True)
                    self.log(f"✅ SENSOR SYNC: Caricate {len(configurations)} configurazioni")
                    
                except Exception as e:
                    self.error(f"❌ SENSOR SYNC: Errore lettura configurazioni: {e}")
                    self.record_attempt(user_id, "sync_configs", False)
                    result = {
                        "success": False,
                        "error": str(e),
                        "method": "sensor_fallback"
                    }
            
            # Crea il sensore di risposta
            self.create_response_sensor("sensor.southtech_sync_response", result)
            
            # Reset sensore richiesta
            self.set_state("sensor.southtech_sync_request", state="completed")
            
            self.log("✅ SENSOR SYNC: Completato")
            
        except Exception as e:
            self.error(f"❌ SENSOR SYNC: Errore: {e}")
            self.create_response_sensor("sensor.southtech_sync_response", 
                                      {"success": False, "error": str(e), "method": "sensor_fallback_error"})

    def process_sensor_login_request(self):
        """Processa richiesta login via sensore - VERSIONE UNIFICATA CORRETTA"""
        try:
            attrs = self.get_state("sensor.southtech_login_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "login":
                return
                
            user_id = self.get_user_id_unified(request_data, "sensor")
            
            # ✅ CORREZIONE: Gestisci sia hash che password legacy
            password = request_data.get("password")
            password_hash = request_data.get("password_hash")
            security_method = request_data.get("security_method", "legacy")
            browser_id = request_data.get("browser_id", "")
            timestamp = request_data.get("timestamp", "")
            
            self.log(f"🔍 SENSOR LOGIN: Da {user_id[:20]} - Metodo: {security_method}")
            self.log(f"🔍 LOGIN DEBUG: password={bool(password)}, hash={bool(password_hash)}")
            
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
            else:
                # Carica dati autenticazione
                with open(self.auth_file, 'r') as f:
                    auth_data = json.load(f)
                
                saved_security_method = auth_data.get("security_method", "legacy")
                self.log(f"🔐 AUTH FILE: Metodo salvato: {saved_security_method}")
                
                # ✅ VERIFICA COMPATIBILITÀ METODI
                login_success = False
                
                if security_method in ["client_hash_sha256", "client_hash_fallback"] and password_hash:
                    # Frontend invia hash
                    if saved_security_method in ["client_hash_sha256", "client_hash_fallback"]:
                        # Confronta hash con hash salvato
                        stored_hash = auth_data.get("password_hash", "")
                        login_success = (password_hash == stored_hash)
                        self.log(f"🔐 HASH vs HASH: {password_hash[:10]}... vs {stored_hash[:10]}...")
                    else:
                        # Hash vs password: calcola hash della password salvata
                        stored_password = auth_data.get("stored_password", "")
                        if stored_password:
                            expected_hash = self.calculate_client_hash(stored_password, browser_id, timestamp)
                            login_success = (password_hash == expected_hash)
                            self.log(f"🔐 HASH vs PASSWORD: calcolato {expected_hash[:10]}...")
                        else:
                            login_success = False
                            self.log("🔐 Nessuna password salvata per calcolo hash")
                            
                elif password:
                    # Frontend invia password in chiaro
                    if saved_security_method in ["client_hash_sha256", "client_hash_fallback"]:
                        # Password vs hash: impossibile, errore
                        login_success = False
                        self.log("🔐 Incompatibilità: password chiara vs hash salvato")
                    else:
                        # Password vs password: metodo legacy
                        salt = auth_data.get("salt", "")
                        stored_hash = auth_data.get("password_hash", "")
                        if salt and stored_hash:
                            provided_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                            login_success = (provided_hash == stored_hash)
                            self.log(f"🔐 PASSWORD LEGACY: {provided_hash[:10]}... vs {stored_hash[:10]}...")
                        else:
                            # Prova confronto diretto con stored_password
                            stored_password = auth_data.get("stored_password", "")
                            login_success = (password == stored_password)
                            self.log(f"🔐 PASSWORD DIRETTO: confronto diretto")
                else:
                    # Nessuna password fornita
                    self.record_attempt(user_id, "password_login", False)
                    result = {"success": False, "error": "Password richiesta"}
                    self.create_response_sensor("sensor.southtech_login_response", result)
                    self.set_state("sensor.southtech_login_request", state="unavailable")
                    return
                
                # ✅ RISULTATO FINALE
                if login_success:
                    token = self.generate_token()
                    self.record_attempt(user_id, "password_login", True)
                    result = {"success": True, "token": token}
                    self.log("✅ Login completato con successo")
                else:
                    self.record_attempt(user_id, "password_login", False)
                    result = {"success": False, "error": "Password non corretta"}
                    self.log("❌ Login fallito - password errata")
            
            self.create_response_sensor("sensor.southtech_login_response", result)
            self.set_state("sensor.southtech_login_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor login: {e}")
            self.create_response_sensor("sensor.southtech_login_response", 
                                      {"success": False, "error": str(e)})

    def process_sensor_setup_request(self):
        """Processa richiesta setup via sensore - VERSIONE CORRETTA FINALE"""
        try:
            attrs = self.get_state("sensor.southtech_setup_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "setup":
                return
                
            user_id = self.get_user_id_unified(request_data, "sensor")
            
            # ✅ CORREZIONE: Gestisci sia hash che password legacy
            password = request_data.get("password")
            password_confirm = request_data.get("password_confirm")
            password_hash = request_data.get("password_hash")
            password_confirm_hash = request_data.get("password_confirm_hash")
            security_method = request_data.get("security_method", "legacy")
            
            self.log(f"🔍 SENSOR SETUP: Metodo {security_method}, password: {bool(password)}, hash: {bool(password_hash)}")
            
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
            else:
                # ✅ CORREZIONE: Controlla entrambi i metodi
                if security_method in ["client_hash_sha256", "client_hash_fallback"] and password_hash and password_confirm_hash:
                    # Metodo hash - usa hash direttamente
                    if password_hash != password_confirm_hash:
                        self.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Le password non coincidono"}
                    else:
                        # ✅ CORREZIONE: Salva l'hash PULITO direttamente
                        self.save_auth_data_unified(password_hash, user_id, security_method)
                        result = {"success": True, "token": self.generate_token()}
                        self.record_attempt(user_id, "password_setup", True)
                        self.log(f"✅ Setup hash completato: {password_hash[:10]}...")
                elif password and password_confirm:
                    # Metodo legacy - usa password in chiaro
                    if password != password_confirm:
                        self.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Le password non coincidono"}
                    elif len(password) < 6:
                        self.record_attempt(user_id, "password_setup", False)
                        result = {"success": False, "error": "Password troppo corta"}
                    else:
                        # ✅ CORREZIONE: Salva la password PULITA direttamente
                        self.save_auth_data_unified(password, user_id, "legacy")
                        result = {"success": True, "token": self.generate_token()}
                        self.record_attempt(user_id, "password_setup", True)
                        self.log(f"✅ Setup legacy completato")
                else:
                    self.record_attempt(user_id, "password_setup", False)
                    result = {"success": False, "error": "Password e conferma richieste"}
            
            self.create_response_sensor("sensor.southtech_setup_response", result)
            self.set_state("sensor.southtech_setup_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor setup: {e}")
            self.create_response_sensor("sensor.southtech_setup_response", 
                                      {"success": False, "error": str(e)})

    def save_auth_data_unified(self, password_data, user_id, method):
        """Salva dati auth con metodo unificato - VERSIONE CORRETTA"""
        try:
            if method.startswith("client_hash"):
                # ✅ CORREZIONE: Salva hash direttamente senza manipolazioni
                auth_data = {
                    "password_hash": password_data,  # ← Hash già corretto dal frontend
                    "stored_password": None,
                    "salt": None,
                    "security_method": method,
                    "created_at": datetime.now().isoformat(),
                    "created_by": user_id[:20]
                }
                self.log(f"🔐 Salvando hash diretto: {password_data[:10]}...")
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
                self.log(f"🔐 Salvando con salt: password={password_data[:3]}..., salt={salt[:10]}...")
            
            # Scrivi file auth
            with open(self.auth_file, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            self.update_auth_status_file()
            self.log(f"✅ Setup completato con metodo {method}")
            
            # ✅ DEBUG: Verifica cosa è stato salvato
            self.log(f"🔍 AUTH FILE SALVATO: {auth_data}")
            
        except Exception as e:
            self.error(f"❌ Errore salvataggio auth data: {e}")
            raise

    def process_sensor_reset_request(self):
        """Processa richiesta reset via sensore - CORRETTO"""
        try:
            attrs = self.get_state("sensor.southtech_reset_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            if request_data.get("action") != "reset_system":
                return
                
            # ✅ CORRETTO: Usa metodo unificato
            user_id = self.get_user_id_unified(request_data, "sensor")
            
            self.log(f"🔍 SENSOR RESET: Processando reset da {user_id[:20]}")
            
            # Resto del metodo rimane invariato...
            is_blocked, block_until = self.is_user_blocked(user_id)
            if is_blocked:
                result = {
                    "success": False, 
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time())
                }
            else:
                if os.path.exists(self.auth_file):
                    os.remove(self.auth_file)
                    self.log("🗑️ File auth cancellato via sensore")
                
                self.active_tokens.clear()
                
                if user_id in self.attempt_counters:
                    del self.attempt_counters[user_id]
                if user_id in self.blocked_users:
                    del self.blocked_users[user_id]
                
                self.update_auth_status_file()
                self.log_security_event(user_id, "RESET_SYSTEM", "INFO", "Reset sistema via sensore")
                self.save_security_data()
                
                result = {"success": True, "message": "Sistema resettato via sensore"}
            
            self.create_response_sensor("sensor.southtech_reset_response", result)
            self.set_state("sensor.southtech_reset_request", state="unavailable")
            
        except Exception as e:
            self.error(f"Errore processing sensor reset: {e}")
            self.create_response_sensor("sensor.southtech_reset_response", 
                                      {"success": False, "error": str(e)})

    def process_sensor_save_request(self):
        """Processa salvataggio via sensore con metodi avanzati"""
        try:
            attrs = self.get_state("sensor.southtech_save_request", attribute="all")
            if not attrs or "attributes" not in attrs:
                return
                
            request_data = attrs["attributes"]
            configurations = request_data.get("configurations", [])
            
            if not configurations:
                self.create_sensor_save_response({
                    "success": False, 
                    "error": "Configurazioni mancanti"
                })
                return
            
            self.log("📡 SENSOR: Processamento con metodo avanzato")
            
            # 🆕 USA METODO AVANZATO
            result = self.execute_save_advanced("sensor", configurations, request_data)
            
            # Invia risposta
            self.create_sensor_save_response(result)
            self.set_state("sensor.southtech_save_request", state="completed")
            
        except Exception as e:
            self.error(f"❌ SENSOR: Errore: {e}")
            self.create_sensor_save_response({"success": False, "error": str(e)})

    def find_light_control_section(self, content):
        """
        Trova la sezione controllo luci nel contenuto YAML
        Supporta sia formato nuovo che vecchio
        
        Returns:
            tuple: (start_idx, end_idx) oppure (-1, -1) se non trovata
        """
        try:
            # Prova formato nuovo prima
            start_line_idx = content.find(self.new_start_line)
            if start_line_idx != -1:
                self.log("✅ Trovata sezione formato NUOVO")
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
                        return (start_block_idx, end_block_idx)
            
            # Prova formato vecchio
            old_start_idx = content.find(self.start_marker)
            old_end_idx = content.find(self.end_marker)
            
            if old_start_idx != -1 and old_end_idx != -1:
                self.log("✅ Trovata sezione formato VECCHIO")
                old_end_idx += len(self.end_marker)
                return (old_start_idx, old_end_idx)
            
            # Nessuna sezione trovata
            self.log("ℹ️ Nessuna sezione controllo luci trovata")
            return (-1, -1)
            
        except Exception as e:
            self.error(f"Errore ricerca sezione controllo luci: {e}")
            return (-1, -1)

    def extract_light_configs_from_section(self, section_content):
        """
        Estrae le configurazioni luci dalla sezione YAML
        
        Returns:
            set: Set di ID configurazioni esistenti
        """
        try:
            configs = set()
            
            # Parsing del contenuto YAML
            import yaml
            parsed = yaml.safe_load(section_content)
            
            if parsed and 'light_presence' in parsed:
                light_configs = parsed['light_presence'].get('light_presence', [])
                
                for cfg in light_configs:
                    if 'light_entity' in cfg:
                        # Genera ID configurazione basato su light_entity
                        config_id = self.generate_config_id(cfg)
                        configs.add(config_id)
            
            self.log(f"🔍 Estratte {len(configs)} configurazioni esistenti")
            return configs
            
        except Exception as e:
            self.error(f"Errore estrazione configurazioni: {e}")
            return set()

    def generate_config_id(self, config):
        """
        Genera ID univoco per una configurazione
        
        Returns:
            str: ID della configurazione
        """
        try:
            # Usa light_entity come chiave principale
            light_entity = config.get('light_entity', '')
            if light_entity:
                return light_entity
            
            # Fallback: usa combinazione di sensori
            sensors = [
                config.get('presence_sensor_on', ''),
                config.get('presence_sensor_off', ''),
                config.get('illuminance_sensor', '')
            ]
            
            # Filtra sensori vuoti e crea hash
            valid_sensors = [s for s in sensors if s]
            if valid_sensors:
                import hashlib
                combined = '|'.join(sorted(valid_sensors))
                return hashlib.md5(combined.encode()).hexdigest()[:8]
            
            return f"config_{id(config)}"
            
        except Exception as e:
            self.error(f"Errore generazione ID configurazione: {e}")
            return f"config_error_{id(config)}"

    def create_empty_apps_yaml_structure(self):
        """
        Crea struttura vuota apps.yaml se necessario
        
        Returns:
            str: Contenuto YAML base
        """
        return """# Apps.yaml - Configurazione AppDaemon
    # File generato automaticamente da SouthTech

    """

    def verify_yaml_integrity(self, file_path):
        """
        Verifica l'integrità del file YAML
        
        Returns:
            bool: True se valido
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verifica parsing YAML
            import yaml
            parsed = yaml.safe_load(content)
            
            if parsed is None and content.strip():
                raise Exception("YAML parsing risulta vuoto con contenuto presente")
            
            self.log(f"✅ Integrità YAML verificata: {file_path}")
            return True
            
        except Exception as e:
            self.error(f"❌ Errore integrità YAML {file_path}: {e}")
            raise

    def generate_light_control_section(self, configurations):
        """
        Genera la sezione di controllo luci completa - VERSIONE MIGLIORATA
        
        Returns:
            str: Sezione YAML formattata
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Inizio sezione con indentazione corretta
            yaml_content = "################################################################################\n"
            yaml_content += "#                      START CONTROLLO LUCI AUTOMATICHE                        #\n"
            yaml_content += "################################################################################\n"
            # ✅ MODIFICA 1: Cambiato "SouthTech" in "SouthTech Configurator"
            yaml_content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
            yaml_content += "light_presence:\n"
            # ✅ MODIFICA 2: Aggiunta linea decorativa dopo light_presence:
            yaml_content += "  ##############################################################################\n"
            yaml_content += "  module: light_presence_control\n"
            yaml_content += "  class: LightPresenceControl\n"
            yaml_content += "  log_level: DEBUG\n"
            yaml_content += "  light_presence:\n"
            
            # Aggiungi ogni configurazione con indentazione precisa
            for i, config in enumerate(configurations):
                light_entity = config.get('light_entity', '')
                if not light_entity:
                    continue
                    
                base_id = light_entity.replace('light.', '')
                
                # Commento configurazione
                yaml_content += f"    # Configurazione {i + 1} - {base_id}\n"
                
                # Elementi della lista con 4 spazi di base + 2 per le proprietà
                yaml_content += f"    - light_entity: {light_entity}\n"
                yaml_content += f"      presence_sensor_on: {config.get('presence_sensor_on', '')}\n"
                yaml_content += f"      presence_sensor_off: {config.get('presence_sensor_off', '')}\n"
                yaml_content += f"      illuminance_sensor: {config.get('illuminance_sensor', '')}\n"
                yaml_content += f"      enable_sensor: input_boolean.{base_id}_enable_sensor\n"
                yaml_content += f"      enable_manual_activation_sensor: input_boolean.{base_id}_enable_manual_activation_sensor\n"
                yaml_content += f"      enable_manual_activation_light_sensor: input_boolean.{base_id}_enable_manual_activation_light_sensor\n"
                yaml_content += f"      enable_automation: input_boolean.{base_id}_enable_automation\n"
                yaml_content += f"      enable_illuminance_filter: input_boolean.{base_id}_enable_illuminance_filter\n"
                yaml_content += f"      enable_illuminance_automation: input_boolean.{base_id}_enable_illuminance_automation\n"
                yaml_content += f"      automatic_enable_automation: input_select.{base_id}_automatic_enable_automation\n"
                yaml_content += f"      light_sensor_config: input_select.{base_id}_light_sensor_config\n"
                yaml_content += f"      timer_minutes_on_push: input_number.{base_id}_timer_minutes_on_push\n"
                yaml_content += f"      timer_filter_on_push: input_number.{base_id}_timer_filter_on_push\n"
                yaml_content += f"      timer_minutes_on_time: input_number.{base_id}_timer_minutes_on_time\n"
                yaml_content += f"      timer_filter_on_time: input_number.{base_id}_timer_filter_on_time\n"
                yaml_content += f"      timer_seconds_max_lux: input_number.{base_id}_timer_seconds_max_lux\n"
                yaml_content += f"      min_lux_activation: input_number.{base_id}_min_lux_activation\n"
                yaml_content += f"      max_lux_activation: input_number.{base_id}_max_lux_activation\n"
                yaml_content += f"      turn_on_light_offset: input_number.{base_id}_turn_on_light_offset\n"
                yaml_content += f"      turn_off_light_offset: input_number.{base_id}_turn_off_light_offset\n"
            yaml_content += "################################################################################\n"
            yaml_content += "#                      END CONTROLLO LUCI AUTOMATICHE                          #\n"
            yaml_content += "################################################################################\n"
            
            return yaml_content
            
        except Exception as e:
            self.error(f"Errore generazione sezione controllo luci: {e}")
            raise

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

    # 🔒 SOUTHTECH CONFIGURATOR - MODIFICHE SERVER PER HASH SICURO
    # Aggiungi questi metodi alla classe SouthTechConfigurator

    def calculate_client_hash(self, password, browser_id, timestamp):
        """
        🔐 Calcola hash client-side per confronto - VERSIONE CORRETTA
        Deve produrre lo stesso hash del JavaScript
        """
        try:
            # ✅ FIX: Usa salt fisso senza timestamp (come nel frontend)
            salt = f"southtech_{browser_id}_fixed_security_salt"
            
            # 2. Combina password + salt (stesso ordine del client)
            password_with_salt = f"{password}{salt}"
            
            # 3. Genera hash SHA-256
            hash_bytes = hashlib.sha256(password_with_salt.encode('utf-8')).digest()
            
            # 4. Converti in hex (stesso formato del client)
            hash_hex = hash_bytes.hex()
            
            return hash_hex
            
        except Exception as e:
            self.error(f"Errore calcolo hash client: {e}")
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
            self.error(f"Errore verifica hash password: {e}")
            return False

    # 🚨 IMPORTANTE: Gestione Migrazione Sicurezza
    def migrate_to_secure_system(self):
        """
        🔄 Migra sistema esistente al nuovo metodo sicuro
        Aggiunge stored_password ai file auth esistenti
        """
        try:
            if not os.path.exists(self.auth_file):
                return
                
            with open(self.auth_file, 'r') as f:
                auth_data = json.load(f)
            
            # Se non ha stored_password, non può usare hash sicuro
            if "stored_password" not in auth_data:
                self.log("⚠️ Sistema auth legacy rilevato - hash sicuro limitato")
                auth_data["security_method"] = "legacy_only"
                auth_data["migration_note"] = "Reset password per abilitare sicurezza completa"
                
                with open(self.auth_file, 'w') as f:
                    json.dump(auth_data, f, indent=2)
            
        except Exception as e:
            self.error(f"Errore migrazione sicurezza: {e}")
