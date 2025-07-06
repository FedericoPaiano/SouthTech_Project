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
        self.backup_path = os.path.join(self.www_path, "backups")
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

        self.initialize_dashboard_structure()

        # 🧪 AGGIUNGI QUESTA RIGA per il test diagnostico
        self.run_diagnostic_on_startup()
        
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

        self.setup_dashboard_debug_entities()
        
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

    def merge_dashboards_section(self, existing_section):
        """
        🔀 MERGE INTELLIGENTE: Aggiunge dashboard light-presence alla sezione esistente
        Preserva resources, mode e tutte le dashboard esistenti
        """
        try:
            self.log("🔀 Inizio merge intelligente sezione dashboards...")
            
            # Analizza la struttura esistente
            lines = existing_section.split('\n')
            new_lines = []
            in_dashboards_section = False
            dashboards_indent = ""
            last_dashboard_line = -1
            
            for i, line in enumerate(lines):
                original_line = line
                
                # Trova sezione dashboards:
                if 'dashboards:' in line and not line.strip().startswith('#'):
                    in_dashboards_section = True
                    dashboards_indent = line[:line.find('dashboards:')]
                    self.log(f"🔍 Trovata sezione dashboards: alla riga {i+1}")
                    new_lines.append(line)
                    continue
                
                # Se siamo nella sezione dashboards, tieni traccia delle dashboard esistenti
                if in_dashboards_section:
                    # Controlla se è una dashboard (ha : alla fine e indentazione corretta)
                    stripped = line.strip()
                    if stripped and ':' in stripped and not stripped.startswith('#'):
                        # Calcola indentazione
                        line_indent = line[:len(line) - len(line.lstrip())]
                        expected_indent = dashboards_indent + "    "  # 4 spazi per le dashboard
                        
                        if line_indent == expected_indent and stripped.endswith(':'):
                            last_dashboard_line = len(new_lines)
                            self.log(f"🔍 Trovata dashboard esistente: {stripped} alla riga {i+1}")
                    
                    # Controlla se è uscito dalla sezione dashboards (nuova sezione al livello base)
                    elif stripped and not stripped.startswith('#') and not line.startswith(' '):
                        in_dashboards_section = False
                
                new_lines.append(line)
            
            # Se non ha trovato una sezione dashboards, la crea
            if last_dashboard_line == -1:
                self.log("⚠️ Sezione dashboards: non trovata nella sezione esistente")
                # Trova dove inserire dashboards: dopo lovelace: 
                for i, line in enumerate(new_lines):
                    if 'lovelace:' in line and not line.strip().startswith('#'):
                        lovelace_indent = line[:line.find('lovelace:')]
                        dashboards_line = lovelace_indent + "  dashboards:"
                        # Inserisci dopo le eventuali proprietà globali
                        insert_pos = i + 1
                        # Salta le proprietà globali come mode:, resources:
                        while (insert_pos < len(new_lines) and 
                              new_lines[insert_pos].strip() and 
                              not new_lines[insert_pos].strip().startswith('#') and
                              new_lines[insert_pos].startswith('  ') and
                              ':' in new_lines[insert_pos] and
                              not new_lines[insert_pos].strip().endswith(':')):
                            insert_pos += 1
                        
                        new_lines.insert(insert_pos, dashboards_line)
                        last_dashboard_line = insert_pos
                        dashboards_indent = lovelace_indent + "  "
                        self.log(f"📝 Aggiunta sezione dashboards: alla riga {insert_pos+1}")
                        break
            
            # Verifica se light-presence esiste già
            content_str = '\n'.join(new_lines)
            if 'light-presence:' in content_str:
                self.log("⚠️ Dashboard light-presence già esistente - mantengo quella esistente")
                return '\n'.join(new_lines)
            
            # Genera la dashboard light-presence
            if last_dashboard_line >= 0:
                dashboard_indent = dashboards_indent + "    "  # 4 spazi dalle dashboards:
                
                light_presence_dashboard = [
                    "",  # Riga vuota per separazione
                    dashboard_indent + "light-presence:",
                    dashboard_indent + "  mode: yaml",
                    dashboard_indent + "  filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml",
                    dashboard_indent + "  title: Configurazione Luci Automatiche",
                    dashboard_indent + "  icon: mdi:lightbulb-outline",
                    dashboard_indent + "  show_in_sidebar: true",
                    dashboard_indent + "  require_admin: true"
                ]
                
                # Inserisci dopo l'ultima dashboard trovata
                insert_position = last_dashboard_line + 1
                
                # Trova la fine dell'ultima dashboard
                while (insert_position < len(new_lines) and 
                      (new_lines[insert_position].startswith(dashboard_indent + "  ") or
                        new_lines[insert_position].strip() == "")):
                    insert_position += 1
                
                # Inserisci la nuova dashboard
                for line in light_presence_dashboard:
                    new_lines.insert(insert_position, line)
                    insert_position += 1
                
                self.log(f"✅ Dashboard light-presence aggiunta dopo riga {last_dashboard_line}")
            else:
                raise Exception("Impossibile trovare dove inserire la dashboard")
            
            result = '\n'.join(new_lines)
            self.log(f"🔀 Merge completato: {len(result)} caratteri")
            
            return result
            
        except Exception as e:
            self.error(f"Errore merge dashboards section: {e}")
            raise

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

    def process_apps_yaml_advanced(self, new_configurations, skip_backup=False):
        """
        🎯 METODO CORE: Processamento avanzato apps.yaml - CON BACKUP CONDIZIONALE
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
            
            # 🎯 BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(self.apps_yaml_path):
                self.log("📦 Backup apps.yaml...")
                try:
                    backup_files = [{
                        "source_path": self.apps_yaml_path,
                        "backup_name": "apps.bkp",
                        "type": "apps_yaml"
                    }]
                    
                    backup_result = self.create_structured_backup(
                        backup_type="single", 
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.log(f"✅ Backup apps.yaml completato: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        self.log(f"⚠️ Backup apps.yaml fallito: {backup_result.get('error')}")
                        backup_info = {
                            "backup_created": False, 
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.error(f"❌ Errore backup apps.yaml: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.log("⏭️ Backup apps.yaml saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "file_not_exists", "backup_skipped": False}
                self.log("ℹ️ File apps.yaml non esiste, nessun backup necessario")
            
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
                    "optimized_skip": True,
                    **backup_info
                }
            
            # 6. Genera nuova sezione
            new_section = self.generate_light_control_section(valid_configs)
            
            # 7. Ricostruisci file completo
            new_content = self.rebuild_apps_yaml_content(
                existing_content, new_section, start_idx, end_idx
            )
            
            # 8. Salvataggio atomico e sicuro
            self.atomic_file_write(self.apps_yaml_path, new_content)
            
            # 9. Verifica post-salvataggio
            self.verify_yaml_integrity(self.apps_yaml_path)
            
            # 10. Risultato dettagliato con info backup
            result = {
                "success": True,
                "message": f"apps.yaml aggiornato con processamento avanzato{' (backup saltato)' if skip_backup else ''}",
                "processing_method": "advanced_with_conditional_backup",
                "configurations_total": len(valid_configs),
                "configurations_added": len(configs_to_add),
                "configurations_removed": len(configs_to_remove),
                "configurations_unchanged": len(existing_configs & new_config_ids),
                "file_size": os.path.getsize(self.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "validation_passed": True,
                "integrity_verified": True,
                **backup_info
            }
            
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.log(f"✅ Apps.yaml processato con successo - {backup_msg}")
            return result
            
        except Exception as e:
            self.error(f"❌ CORE: Errore processamento avanzato: {e}")
            
            # Tentativo di ripristino da backup se disponibile
            if 'backup_info' in locals() and backup_info.get("backup_created"):
                self.log("🛡️ Tentativo ripristino da backup in corso...")
                # TODO: Implementare ripristino automatico se necessario
            
            return {
                "success": False,
                "error": str(e),
                "processing_method": "advanced_with_conditional_backup",
                "timestamp": datetime.now().isoformat(),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

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
    # METODO UNIFICATO AVANZATO (Usato da tutti i sistemi)
    # ================================================================

    def execute_save_advanced(self, method_type, configurations, request_data):
        """
        Metodo unificato per salvataggio avanzato
        Usato da WebSocket, Sensori e File System
        """
        # SOSTITUISCI tutto il contenuto con:
        return self.execute_complete_save_advanced(method_type, configurations, request_data)

    def execute_complete_save_advanced(self, method_type, configurations, request_data):
        """
        🎯 METODO CORE: Salvataggio completo Apps.yaml + Dashboard + Templates - CON BACKUP STRUTTURATO OTTIMIZZATO
        Utilizzato da tutti i sistemi di comunicazione (WebSocket, Sensori, File)
        """
        try:
            self.log(f"✨ COMPLETE SAVE ({method_type.upper()}): Inizio salvataggio completo v3.5.0 (backup ottimizzato)")
            start_time = time.time()
            
            # Inizializza struttura dashboard se necessario
            if not hasattr(self, 'dashboard_path'):
                self.initialize_dashboard_structure()
            
            # Verifica autenticazione e blocchi
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
            
            self.log(f"👤 Utente autorizzato: {user_id[:20]}")
            
            # 🎯 BACKUP STRUTTURATO COMPLETO UNICO (STEP 0)
            self.log("📦 STEP 0/4: Backup strutturato completo unico...")
            try:
                backup_result = self.create_structured_backup(backup_type="complete")
                
                if backup_result.get("success"):
                    self.log(f"✅ STEP 0/4: Backup unico completato ({backup_result.get('files_backed_up', 0)} file)")
                    backup_info = {
                        "backup_created": True,
                        "backup_folder": backup_result.get("backup_folder"),
                        "files_backed_up": backup_result.get("files_backed_up", 0),
                        "backup_path": backup_result.get("backup_path")
                    }
                else:
                    self.log(f"⚠️ STEP 0/4: Backup parziale o fallito")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": backup_result.get("error", "Unknown backup error")
                    }
                    
            except Exception as backup_error:
                self.error(f"❌ STEP 0/4: Errore critico backup: {backup_error}")
                backup_info = {
                    "backup_created": False,
                    "backup_error": str(backup_error)
                }
            
            # STEP 1: Salva apps.yaml (SENZA backup individuale)
            self.log(f"📋 STEP 1/4: Salvataggio apps.yaml (skip backup)...")
            try:
                apps_result = self.process_apps_yaml_advanced(configurations, skip_backup=True)
                
                if not apps_result.get("success"):
                    self.record_attempt(user_id, f"{method_type}_complete_save", False)
                    return {
                        "success": False,
                        "error": f"Errore apps.yaml: {apps_result.get('error')}",
                        "method": f"{method_type}_apps_failed",
                        "step_failed": "apps_yaml",
                        "partial_success": False,
                        **backup_info
                    }
                
                self.log(f"✅ STEP 1/4: Apps.yaml salvato ({apps_result.get('file_size', 0)} bytes)")
                
            except Exception as apps_error:
                error_msg = str(apps_error)
                self.error(f"❌ STEP 1/4: Eccezione apps.yaml: {error_msg}")
                self.record_attempt(user_id, f"{method_type}_complete_save", False)
                return {
                    "success": False,
                    "error": f"Eccezione apps.yaml: {error_msg}",
                    "method": f"{method_type}_apps_exception",
                    "step_failed": "apps_yaml",
                    **backup_info
                }
            
            # STEP 2: Genera dashboard e templates (SENZA backup individuali)
            self.log(f"🎨 STEP 2/4: Generazione dashboard e templates (skip backup)...")
            try:
                dashboard_result = self.generate_dashboard_and_templates(configurations, skip_backup=True)
                
                # Verifica dettagliata del risultato
                if dashboard_result.get("success"):
                    success_type = dashboard_result.get("success_type", "unknown")
                    self.log(f"✅ STEP 2/4: Dashboard completato - Tipo: {success_type}")
                    
                    # Verifica ogni componente
                    details = dashboard_result.get("details", {})
                    templates_ok = details.get("templates", {}).get("success", False)
                    dashboard_ok = details.get("dashboard", {}).get("success", False)
                    config_ok = details.get("configuration", {}).get("success", False)
                    
                    self.log(f"📊 Componenti: Templates={templates_ok}, Dashboard={dashboard_ok}, Config={config_ok}")
                    
                else:
                    self.error(f"❌ STEP 2/4: Dashboard fallita")
                    self.error(f"   Errore: {dashboard_result.get('error', 'Sconosciuto')}")
                    self.error(f"   Tipo fallimento: {dashboard_result.get('success_type', 'unknown')}")
                    
                    # Log errori specifici per ogni componente
                    details = dashboard_result.get("details", {})
                    for component, component_result in details.items():
                        if not component_result.get("success"):
                            component_error = component_result.get("error", "Errore sconosciuto")
                            self.error(f"   🔴 {component.upper()}: {component_error}")
                
            except Exception as dashboard_error:
                error_msg = str(dashboard_error)
                self.error(f"❌ STEP 2/4: Eccezione critica dashboard: {error_msg}")
                import traceback
                self.error(f"Stack trace dashboard: {traceback.format_exc()}")
                
                dashboard_result = {
                    "success": False,
                    "success_type": "critical_exception",
                    "error": error_msg,
                    "details": {
                        "templates": {"success": False, "error": f"Exception: {error_msg}"},
                        "configuration": {"success": False, "error": f"Exception: {error_msg}"},
                        "dashboard": {"success": False, "error": f"Exception: {error_msg}"},
                        "light_configs": {"success": False, "error": f"Exception: {error_msg}"}
                    }
                }
            
            # Calcola durata operazione
            operation_duration = round(time.time() - start_time, 2)
            
            # Aggiorna log operazione
            self.log_complete_save_operation(
                method_type, 
                configurations, 
                dashboard_result.get("success", False),
                dashboard_result.get("error") if not dashboard_result.get("success") else None
            )
            
            # STEP 3: Risultato finale con 4 componenti
            dashboard_success = dashboard_result.get("success", False)
            success_type = dashboard_result.get("success_type", "unknown")
            
            # ✅ NUOVO: Crea details unificati con apps.yaml incluso
            unified_details = {
                "apps": {
                    "success": apps_result.get("success", False),
                    "error": apps_result.get("error") if not apps_result.get("success") else None,
                    "configurations_total": apps_result.get("configurations_total", 0),
                    "configurations_added": apps_result.get("configurations_added", 0),
                    "configurations_removed": apps_result.get("configurations_removed", 0),
                    "file_size": apps_result.get("file_size", 0),
                    "backup_skipped": True,  # ← NUOVO: Indica backup saltato
                    "method": "advanced_processing"
                }
            }
            
            # Aggiungi i details dashboard se esistono
            dashboard_details = dashboard_result.get("details", {})
            if dashboard_details:
                # Aggiungi flag backup_skipped a tutti i componenti dashboard
                for component_key, component_details in dashboard_details.items():
                    if isinstance(component_details, dict):
                        component_details["backup_skipped"] = True
                unified_details.update(dashboard_details)
            
            # ✅ NUOVO: Calcola successo basato su 4 componenti
            apps_success = apps_result.get("success", False)
            templates_success = unified_details.get("templates", {}).get("success", False)
            config_success = unified_details.get("configuration", {}).get("success", False)
            dashboard_files_success = unified_details.get("dashboard", {}).get("success", False)
            
            # Conta componenti riusciti (su 4 totali)
            successful_components = sum([apps_success, templates_success, config_success, dashboard_files_success])
            
            # Determina successo generale basato su priorità
            if successful_components >= 3:
                # Successo completo (configuration.yaml è opzionale)
                overall_success = True
                if successful_components == 4:
                    final_success_type = "complete_success"
                    message = "Configurazione completa salvata con successo (4/4 componenti)!"
                else:
                    final_success_type = "partial_success" 
                    message = f"Configurazione parzialmente salvata ({successful_components}/4 componenti) - alcuni richiedono intervento manuale"
            elif successful_components >= 2:
                # Successo parziale - almeno templates + uno degli altri
                overall_success = True
                final_success_type = "limited_success"
                message = f"Configurazione limitata ({successful_components}/4 componenti) - diversi componenti richiedono intervento manuale"
            else:
                # Fallimento - file critici non generati
                overall_success = False
                failed_components = []
                if not templates_success:
                    failed_components.append("Templates")
                if not dashboard_files_success:
                    failed_components.append("Dashboard")
                if not apps_success:
                    failed_components.append("Apps.yaml")
                
                message = f"Generazione fallita: {', '.join(failed_components)} non creati"
                final_success_type = "failure"
            
            if overall_success:
                result = {
                    "success": True,
                    "message": message,
                    "method": f"{method_type}_complete",
                    "success_type": final_success_type,
                    
                    # ✅ AGGIORNATO: Details con 4 componenti + backup info UNICO
                    "details": unified_details,
                    "files_created": dashboard_result.get("files_created", {}),
                    "summary": dashboard_result.get("summary", {}),
                    
                    # ✅ NUOVO: Riepilogo operazione con 4 componenti
                    "operation_summary": {
                        "apps_yaml_updated": apps_success,
                        "templates_generated": templates_success,
                        "configuration_yaml_updated": config_success,
                        "dashboard_created": dashboard_files_success,
                        "total_configurations": len(configurations),
                        "total_sensors": len(configurations) * 4 + 1,  # 4 per config + placeholder
                        "dashboard_files": 1 + len(configurations),  # main + file singoli
                        "operation_duration": operation_duration,
                        "successful_components": successful_components,
                        "total_components": 4,
                        "backup_strategy": "single_complete_backup"  # ← NUOVO
                    },
                    
                    # ✅ AGGIORNATO: File modificati per 4 componenti
                    "files_modified": [
                        "apps.yaml" if apps_success else None,
                        "templates.yaml" if templates_success else None,
                        "configuration.yaml" if config_success else None,
                        "ui-lovelace-light-presence.yaml" if dashboard_files_success else None
                    ],
                    
                    # Metadati operazione
                    "communication_method": method_type,
                    "user_id": user_id[:20],
                    "advanced_processing": True,
                    "complete_save": True,
                    "timestamp": datetime.now().isoformat(),
                    "operation_duration": operation_duration,
                    "components_status": {
                        "apps_yaml": "success" if apps_success else "failed",
                        "templates_yaml": "success" if templates_success else "failed", 
                        "configuration_yaml": "success" if config_success else "failed",
                        "dashboard_yaml": "success" if dashboard_files_success else "failed"
                    },
                    
                    # ✅ BACKUP INFO UNICO
                    **backup_info
                }
                
            else:
                # Fallimento con dettagli sui 4 componenti
                result = {
                    "success": False,
                    "message": message,
                    "method": f"{method_type}_failed",
                    "success_type": final_success_type,
                    
                    # ✅ AGGIORNATO: Details con 4 componenti anche per fallimenti
                    "details": unified_details,
                    
                    "operation_duration": operation_duration,
                    "communication_method": method_type,
                    "timestamp": datetime.now().isoformat(),
                    "error_details": {
                        "step_failed": "multiple_components",
                        "successful_components": successful_components,
                        "total_components": 4,
                        "components_status": {
                            "apps_yaml": "success" if apps_success else "failed",
                            "templates_yaml": "success" if templates_success else "failed",
                            "configuration_yaml": "success" if config_success else "failed", 
                            "dashboard_yaml": "success" if dashboard_files_success else "failed"
                        }
                    },
                    
                    # ✅ BACKUP INFO UNICO anche per fallimenti
                    **backup_info
                }
            
            # Rimuovi None dai file modificati (solo per successi)
            if "files_modified" in result:
                result["files_modified"] = [f for f in result["files_modified"] if f is not None]
            
            # STEP 4: Registra tentativo e notifiche con logica 4 componenti
            success = result.get("success", False)
            self.record_attempt(user_id, f"{method_type}_complete_save", success)
            
            if success:
                self.log(f"✅ COMPLETE SAVE ({method_type.upper()}): Completato in {operation_duration}s")
                self.log(f"📊 Componenti: Apps={apps_success}, Templates={templates_success}, Config={config_success}, Dashboard={dashboard_files_success}")
                self.log(f"📦 Backup UNICO: {backup_info.get('backup_folder', 'N/A')} ({backup_info.get('files_backed_up', 0)} file)")
                
                # Notifica successo con dettaglio 4 componenti + backup UNICO
                if final_success_type == "complete_success":
                    self.create_ha_notification(
                        "✨ SouthTech: Configurazione Completa Salvata",
                        f"Tutti e 4 i componenti generati per {len(configurations)} configurazioni via {method_type}. Backup unico: {backup_info.get('backup_folder', 'N/A')}"
                    )
                else:
                    failed_components = []
                    if not apps_success: failed_components.append("Apps.yaml")
                    if not templates_success: failed_components.append("Templates")
                    if not config_success: failed_components.append("Configuration.yaml")
                    if not dashboard_files_success: failed_components.append("Dashboard")
                    
                    self.create_ha_notification(
                        "⚠️ SouthTech: Salvataggio Parziale",
                        f"{successful_components}/4 componenti generati. Backup unico: {backup_info.get('backup_folder', 'N/A')}. Richiede intervento: {', '.join(failed_components)}"
                    )
                    
                # Aggiorna entità debug complete save
                if hasattr(self, 'update_dashboard_debug_status'):
                    self.update_dashboard_debug_status("complete_save", True, {
                        "configurations_count": len(configurations),
                        "duration": operation_duration,
                        "files_modified": result.get("files_modified", []),
                        "components_successful": successful_components,
                        "components_total": 4,
                        "backup_folder": backup_info.get("backup_folder"),
                        "backup_strategy": "single_complete"
                    })
            else:
                self.log(f"❌ COMPLETE SAVE ({method_type.upper()}): Fallito ({successful_components}/4 componenti)")
                self.log(f"📦 Backup UNICO: {backup_info.get('backup_folder', 'N/A')} ({backup_info.get('files_backed_up', 0)} file)")
                
                # Aggiorna entità debug errore
                if hasattr(self, 'update_dashboard_debug_status'):
                    self.update_dashboard_debug_status("complete_save", False, {
                        "error": result.get("message", "Unknown error"),
                        "duration": operation_duration,
                        "components_successful": successful_components,
                        "components_total": 4,
                        "backup_folder": backup_info.get("backup_folder"),
                        "backup_strategy": "single_complete"
                    })
            
            return result
            
        except Exception as e:
            operation_duration = round(time.time() - start_time, 2) if 'start_time' in locals() else 0
            
            self.error(f"❌ COMPLETE SAVE ({method_type.upper()}): Errore critico: {e}")
            import traceback
            self.error(f"Stack trace completo: {traceback.format_exc()}")
            
            # Log errore
            if hasattr(self, 'log_complete_save_operation'):
                self.log_complete_save_operation(method_type, configurations, False, str(e))
            
            # Aggiorna entità debug errore
            if hasattr(self, 'update_dashboard_debug_status'):
                self.update_dashboard_debug_status("complete_save", False, {
                    "error": str(e),
                    "duration": operation_duration,
                    "backup_strategy": "single_complete"
                })
            
            return {
                "success": False,
                "error": str(e),
                "method": f"{method_type}_critical_error",
                "complete_save": True,
                "operation_duration": operation_duration,
                "timestamp": datetime.now().isoformat(),
                "details": {
                    "apps": {"success": False, "error": f"Critical error: {str(e)}"},
                    "templates": {"success": False, "error": f"Critical error: {str(e)}"},
                    "configuration": {"success": False, "error": f"Critical error: {str(e)}"},
                    "dashboard": {"success": False, "error": f"Critical error: {str(e)}"}
                },
                "backup_created": False,
                "backup_error": "Critical error prevented backup"
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
            
            # ✅ AGGIUNGI QUESTA RIGA MANCANTE:
            configurations = request_data.get("configurations", [])
            if not configurations:
                response_data = {"success": False, "error": "Configurazioni mancanti"}
            else:
                # 🆕 RICONOSCIMENTO MODALITÀ COMPLETA
                action = request_data.get("action", "save_yaml")
                generate_dashboard = request_data.get("generate_dashboard", False)
                generate_templates = request_data.get("generate_templates", False)

                if action == "save_complete" or generate_dashboard or generate_templates:
                    # ✅ AGGIUNGI QUESTO LOG MANCANTE:
                    self.log("✨ FILE: Richiesta SALVATAGGIO COMPLETO")
                    response_data = self.execute_complete_save_advanced("file", configurations, request_data)
                else:
                    # ✅ AGGIUNGI QUESTO LOG MANCANTE:
                    self.log("📁 FILE: Richiesta salvataggio STANDARD")
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
        
                # Determina tipo di salvataggio basandoti sui parametri dal frontend
                generate_dashboard = kwargs.get("generate_dashboard", False)
                generate_templates = kwargs.get("generate_templates", False)
                action = kwargs.get("action", "save_yaml")
                
                yaml_content = kwargs.get("yaml_content")
                configurations = kwargs.get("configurations", [])
                
                if not yaml_content:
                    return {"success": False, "error": "Contenuto YAML mancante"}
                
                # 🎯 ROUTING INTELLIGENTE
                if action == "save_complete" or generate_dashboard or generate_templates:
                    self.log("✨ WEBSOCKET: Richiesta SALVATAGGIO COMPLETO")
                    result = self.execute_complete_save_advanced("websocket", configurations, kwargs)
                else:
                    self.log("🔌 WEBSOCKET: Richiesta salvataggio STANDARD")
                    result = self.execute_yaml_save_websocket(yaml_content, configurations, "websocket_user")
                
                return result
            
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
            
            # 🆕 RICONOSCIMENTO MODALITÀ COMPLETA
            action = request_data.get("action", "save_yaml")
            generate_dashboard = request_data.get("generate_dashboard", False)
            generate_templates = request_data.get("generate_templates", False)

            if action == "save_complete" or generate_dashboard or generate_templates:
                self.log("✨ SENSOR: Richiesta SALVATAGGIO COMPLETO rilevata")  # ← AGGIUNGI
                result = self.execute_complete_save_advanced("sensor", configurations, request_data)
            else:
                self.log("📡 SENSOR: Richiesta salvataggio STANDARD")  # ← AGGIUNGI
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

    def find_dashboards_section_flexible(self, content):
        """
        🔍 Trova sezione DASHBOARDS con spaziatura flessibile usando regex
        
        Returns:
            tuple: (start_pos, end_pos, original_start_marker, original_end_marker) o None
        """
        try:
            import re
            
            # Pattern per START DASHBOARDS (flessibile sulla spaziatura)
            start_pattern = r'(#{10,}\s*\n\s*#\s+START\s+DASHBOARDS\s+#\s*\n\s*#{10,})'
            
            # Pattern per END DASHBOARDS (flessibile sulla spaziatura)  
            end_pattern = r'(#{10,}\s*\n\s*#\s+END\s+DASHBOARDS\s+#\s*\n\s*#{10,})'
            
            # Cerca il marcatore START
            start_match = re.search(start_pattern, content, re.IGNORECASE | re.MULTILINE)
            if not start_match:
                self.log("🔍 Marcatore START DASHBOARDS non trovato")
                return None
            
            start_pos = start_match.start()
            original_start_marker = start_match.group(1)
            
            # Cerca il marcatore END dopo il START
            end_match = re.search(end_pattern, content[start_match.end():], re.IGNORECASE | re.MULTILINE)
            if not end_match:
                self.log("🔍 Marcatore END DASHBOARDS non trovato")
                return None
            
            # Calcola posizione assoluta del END
            end_pos = start_match.end() + end_match.end()
            original_end_marker = end_match.group(1)
            
            self.log(f"🔍 Marcatori trovati:")
            self.log(f"   START: posizione {start_pos}, lunghezza {len(original_start_marker)}")
            self.log(f"   END: posizione {end_pos - len(original_end_marker)}, lunghezza {len(original_end_marker)}")
            
            return (start_pos, end_pos, original_start_marker, original_end_marker)
            
        except Exception as e:
            self.error(f"Errore ricerca flessibile marcatori: {e}")
            return None

    def add_light_presence_to_existing_section(self, existing_section, original_start_marker, original_end_marker):
        """
        ➕ Aggiunge dashboard light-presence ALLA FINE delle dashboard esistenti
        VERSIONE CORRETTA che inserisce dopo TUTTE le dashboard esistenti
        """
        try:
            self.log("➕ Aggiunta light-presence alla fine delle dashboard esistenti...")
            
            lines = existing_section.split('\n')
            
            # Indentazioni fisse
            DASHBOARD_INDENT = "    "      # 4 spazi per nomi dashboard
            PROPERTY_INDENT = "      "     # 6 spazi per proprietà dashboard
            
            # Verifica se light-presence esiste già
            content_str = existing_section
            if 'light-presence:' in content_str:
                self.log("⚠️ Dashboard light-presence già esistente - mantengo esistente")
                return existing_section
            
            # Strategia semplice: trova l'ultima riga prima dei marcatori di chiusura
            # e inserisci light-presence lì
            
            # Trova l'indice della riga di chiusura (END DASHBOARDS)
            end_marker_line_index = -1
            for i, line in enumerate(lines):
                if 'END DASHBOARDS' in line and '#' in line:
                    end_marker_line_index = i
                    break
            
            if end_marker_line_index == -1:
                # Se non trova il marcatore di fine, inserisci alla fine
                end_marker_line_index = len(lines)
            
            # Trova l'ultima riga non vuota e non commento prima del marcatore di fine
            insert_position = end_marker_line_index
            while insert_position > 0:
                prev_line = lines[insert_position - 1]
                if prev_line.strip() and not prev_line.strip().startswith('#'):
                    break
                insert_position -= 1
            
            self.log(f"📍 Inserimento light-presence alla posizione {insert_position} (prima del marcatore END)")
            
            # Genera light-presence con commento timestamp (SENZA riga vuota iniziale)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            light_presence_lines = [
                DASHBOARD_INDENT + f"# Generato automaticamente da SouthTech Configurator il {timestamp}",
                DASHBOARD_INDENT + "light-presence:",
                PROPERTY_INDENT + "mode: yaml",
                PROPERTY_INDENT + "filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml",
                PROPERTY_INDENT + "title: Configurazione Luci Automatiche",
                PROPERTY_INDENT + "icon: mdi:lightbulb-outline", 
                PROPERTY_INDENT + "show_in_sidebar: true",
                PROPERTY_INDENT + "require_admin: true"
            ]
            
            # Inserisci light-presence
            new_lines = lines[:insert_position] + light_presence_lines + lines[insert_position:]
            
            result = '\n'.join(new_lines)
            
            # Debug risultato
            self.log(f"✅ Light-presence inserita alla fine senza riga vuota")
            self.log(f"📊 Risultato: {len(result)} caratteri")
            
            # Mostra preview del risultato
            self.log("🔍 === PREVIEW RISULTATO ===")
            result_lines = result.split('\n')
            
            # Mostra le righe intorno alla sezione dashboards
            dashboards_line = -1
            for i, line in enumerate(result_lines):
                if 'dashboards:' in line and not line.strip().startswith('#'):
                    dashboards_line = i
                    break
            
            if dashboards_line != -1:
                start_preview = dashboards_line
                end_preview = min(len(result_lines), dashboards_line + 20)  # Mostra fino a 20 righe dopo dashboards:
                
                for i in range(start_preview, end_preview):
                    if i < len(result_lines):
                        line = result_lines[i]
                        indent_count = len(line) - len(line.lstrip())
                        
                        # Evidenzia righe importanti
                        if ('dashboards:' in line or 
                            line.strip().endswith(':') and not line.strip().startswith('#')):
                            marker = ">>>"
                        elif line.strip().startswith('#') and ('END DASHBOARDS' in line):
                            marker = "END"
                        else:
                            marker = "   "
                        
                        self.log(f"{marker} {i:3d}: [{indent_count:2d}] {line}")
                        
                        # Fermati al marcatore di fine
                        if 'END DASHBOARDS' in line:
                            break
            
            return result
            
        except Exception as e:
            self.error(f"Errore inserimento light-presence alla fine: {e}")
            import traceback
            self.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def debug_yaml_structure(self, content):
        """
        🔍 Debug della struttura YAML per verificare indentazioni
        """
        try:
            lines = content.split('\n')
            self.log("🔍 === DEBUG STRUTTURA YAML ===")
            
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                    
                indent_count = len(line) - len(line.lstrip())
                
                if 'dashboards:' in line:
                    self.log(f"📍 Riga {i:3d}: dashboards: (indent: {indent_count})")
                elif line.strip().endswith(':') and 'dashboards' not in line:
                    self.log(f"📍 Riga {i:3d}: {line.strip()} (indent: {indent_count})")
                elif ':' in line and not line.strip().startswith('#'):
                    self.log(f"📋 Riga {i:3d}: {line.strip()} (indent: {indent_count})")
            
            self.log("🔍 === FINE DEBUG STRUTTURA ===")
            
        except Exception as e:
            self.log(f"Errore debug struttura: {e}")

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

    ############################################################################
    #                            DASHBOAR SECTION                              #
    ############################################################################

    #                               INITIALIZE                                 #
    def initialize_dashboard_structure(self):
        """Inizializza la struttura completa di directory e file per dashboard e templates"""
        try:
            self.log("🏗️ Inizializzazione struttura dashboard...")
            
            # Path aggiuntivi per dashboard e templates
            self.dashboard_path = os.path.join(self.www_path, "dashboards")
            self.light_configs_path = os.path.join(self.dashboard_path, "light_configs")
            self.templates_file = "/homeassistant/www/configurations/templates.yaml"
            self.configuration_yaml_path = "/homeassistant/configuration.yaml"
            
            # Marcatori per templates.yaml
            self.templates_start_marker = "################################################################################"
            self.templates_start_line = "#                    START SENSORI TEMPLATE LUCI AUTOMATICHE                   #"
            self.templates_end_line = "#                     END SENSORI TEMPLATE LUCI AUTOMATICHE                    #"
            self.templates_end_marker = "################################################################################"
            
            # ✅ CORREZIONE: Marcatori corretti per configuration.yaml (DASHBOARDS non DASHBOARD LUCI)
            self.config_start_marker = "################################################################################"
            self.config_start_line = "#                               START DASHBOARDS                                #"
            self.config_end_line = "#                                END DASHBOARDS                                 #"
            self.config_end_marker = "################################################################################"
            
            # Resto del metodo rimane invariato...
            # (creazione directory, verifica permessi, etc.)
            
            self.log("✅ Struttura dashboard inizializzata con successo")
            self.log(f"🎯 Pronto per generare dashboard con {len(self.read_existing_configs())} configurazioni esistenti")
            
            # ✅ IMPORTANTE: NON chiamare update_configuration_yaml() qui!
            
        except Exception as e:
            self.error(f"❌ Errore inizializzazione struttura dashboard: {e}")
            raise

    def run_diagnostic_on_startup(self):
        """Esegui test diagnostico all'avvio (solo una volta)"""
        try:
            if hasattr(self, '_diagnostic_run'):
                return  # Test già eseguito
            
            self._diagnostic_run = True
            self.log("🧪 Avvio test diagnostico configuration.yaml...")
            
            # Esegui test solo se la struttura dashboard è inizializzata
            if hasattr(self, 'configuration_yaml_path'):
                test_results = self.test_configuration_yaml_update_step_by_step()
                
                # Salva risultati in un sensore per debug
                try:
                    self.set_state("sensor.southtech_config_yaml_diagnostic",
                                  state="completed",
                                  attributes={
                                      "test_time": datetime.now().isoformat(),
                                      "results": test_results,
                                      "success_rate": f"{sum(1 for k,v in test_results.items() if k.startswith('step') and v)}/{len([k for k in test_results.keys() if k.startswith('step')])}"
                                  })
                except Exception as sensor_error:
                    self.log(f"⚠️ Errore creazione sensore diagnostico: {sensor_error}")
            
        except Exception as e:
            self.error(f"Errore test diagnostico startup: {e}")

    def setup_dashboard_debug_entities(self):
        """Setup entità debug specifiche per dashboard e templates"""
        try:
            self.log("🔍 Setup entità debug dashboard...")
            
            debug_entities = [
                {
                    "entity_id": "sensor.southtech_dashboard_status",
                    "description": "Stato generazione dashboard Lovelace",
                    "initial_state": "ready"
                },
                {
                    "entity_id": "sensor.southtech_templates_status", 
                    "description": "Stato generazione template sensors",
                    "initial_state": "ready"
                },
                {
                    "entity_id": "sensor.southtech_complete_save_log",
                    "description": "Log operazioni salvataggio completo",
                    "initial_state": "idle"
                },
                {
                    "entity_id": "sensor.southtech_dashboard_files_count",
                    "description": "Conteggio file dashboard generati",
                    "initial_state": "0"
                }
            ]
            
            for entity_info in debug_entities:
                entity_id = entity_info["entity_id"]
                try:
                    # Verifica se l'entità esiste già
                    current_state = self.get_state(entity_id)
                    
                    if current_state is None:
                        # Crea nuova entità
                        attributes = {
                            "initialized": datetime.now().isoformat(),
                            "description": entity_info["description"],
                            "extension_version": "3.2.0",
                            "debug_active": True,
                            "entity_type": "dashboard_debug"
                        }
                        
                        # Attributi specifici per tipo di entità
                        if "dashboard_status" in entity_id:
                            attributes.update({
                                "last_generation": None,
                                "files_created": 0,
                                "last_error": None,
                                "generation_method": None
                            })
                        elif "templates_status" in entity_id:
                            attributes.update({
                                "sensors_generated": 0,
                                "last_template_update": None,
                                "template_file_size": 0
                            })
                        elif "complete_save_log" in entity_id:
                            attributes.update({
                                "last_operation": None,
                                "operation_success": None,
                                "files_modified": [],
                                "operation_duration": None
                            })
                        elif "files_count" in entity_id:
                            attributes.update({
                                "dashboard_files": 0,
                                "light_config_files": 0,
                                "template_files": 0,
                                "last_count_update": datetime.now().isoformat()
                            })
                        
                        self.set_state(entity_id, 
                                      state=entity_info["initial_state"], 
                                      attributes=attributes)
                        
                        self.log(f"🔍 Creata entità debug: {entity_id}")
                    else:
                        # Aggiorna entità esistente
                        existing_attrs = self.get_state(entity_id, attribute="all")
                        if existing_attrs and "attributes" in existing_attrs:
                            current_attrs = existing_attrs["attributes"]
                            current_attrs.update({
                                "last_update": datetime.now().isoformat(),
                                "extension_version": "3.2.0",
                                "debug_active": True
                            })
                            
                            self.set_state(entity_id, 
                                          state=entity_info["initial_state"], 
                                          attributes=current_attrs)
                        
                        self.log(f"✓ Aggiornata entità debug esistente: {entity_id}")
                    
                except Exception as e:
                    self.error(f"❌ Errore setup entità debug {entity_id}: {e}")
                    continue
            
            # Crea entità di riepilogo dashboard
            self.create_dashboard_summary_entity()
            
            self.log("✅ Entità debug dashboard inizializzate")
            
        except Exception as e:
            self.error(f"❌ Errore setup entità debug dashboard: {e}")

    #                           INITIALIZE SUPPORT                             #
    def create_dashboard_gitkeep_files(self):
        """Crea file .gitkeep per preservare le directory dashboard vuote"""
        try:
            gitkeep_dirs = [self.dashboard_path, self.light_configs_path]
            
            for directory in gitkeep_dirs:
                gitkeep_file = os.path.join(directory, ".gitkeep")
                if not os.path.exists(gitkeep_file):
                    with open(gitkeep_file, 'w') as f:
                        f.write("# Questo file mantiene la directory dashboard nel repository\n")
                        f.write("# Directory per SouthTech Dashboard Extension\n")
                        f.write(f"# Creato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    self.log(f"📝 Creato .gitkeep in {directory}")
                    
        except Exception as e:
            self.error(f"Errore creazione .gitkeep dashboard: {e}")

    def verify_dashboard_write_permissions(self):
        """Verifica i permessi di scrittura nelle directory dashboard"""
        try:
            test_dirs = [
                self.dashboard_path, 
                self.light_configs_path,
                os.path.dirname(self.templates_file)
            ]
            
            for directory in test_dirs:
                test_file = os.path.join(directory, "test_dashboard_write.tmp")
                try:
                    # Test scrittura
                    with open(test_file, 'w') as f:
                        f.write("dashboard write test")
                    
                    # Test lettura
                    with open(test_file, 'r') as f:
                        content = f.read()
                    
                    # Rimuovi file test
                    os.remove(test_file)
                    
                    if content != "dashboard write test":
                        raise Exception("Test read/write fallito")
                    
                    self.log(f"✓ Permessi dashboard OK: {directory}")
                    
                except Exception as e:
                    self.error(f"❌ Permessi dashboard mancanti: {directory} - {e}")
                    raise
                    
        except Exception as e:
            self.error(f"Errore verifica permessi dashboard: {e}")
            raise

    def create_initial_dashboard_status(self):
        """Crea file di stato iniziale per dashboard"""
        try:
            dashboard_status_file = os.path.join(self.dashboard_path, "dashboard_status.json")
            
            if not os.path.exists(dashboard_status_file):
                initial_status = {
                    "dashboard_extension_active": True,
                    "last_update": datetime.now().isoformat(),
                    "structure_initialized": True,
                    "version": "3.2.0",
                    "paths": {
                        "dashboard_path": self.dashboard_path,
                        "light_configs_path": self.light_configs_path,
                        "templates_file": self.templates_file,
                        "configuration_yaml_path": self.configuration_yaml_path
                    },
                    "features": {
                        "dashboard_generation": True,
                        "template_sensors": True,
                        "configuration_yaml_update": True,
                        "backup_system": True
                    }
                }
                
                with open(dashboard_status_file, 'w') as f:
                    json.dump(initial_status, f, indent=2)
                
                self.log(f"📄 Creato dashboard_status.json")
            else:
                # Aggiorna status esistente
                try:
                    with open(dashboard_status_file, 'r') as f:
                        status = json.load(f)
                    
                    status.update({
                        "last_update": datetime.now().isoformat(),
                        "structure_initialized": True,
                        "version": "3.2.0"
                    })
                    
                    with open(dashboard_status_file, 'w') as f:
                        json.dump(status, f, indent=2)
                    
                    self.log(f"📄 Aggiornato dashboard_status.json esistente")
                except Exception as e:
                    self.log(f"⚠️ Errore aggiornamento status esistente: {e}")
                    
        except Exception as e:
            self.error(f"Errore creazione dashboard status: {e}")

    def create_dashboard_summary_entity(self):
        """Crea entità di riepilogo per dashboard extension"""
        try:
            summary_entity = "sensor.southtech_dashboard_extension_summary"
            
            # Conta configurazioni esistenti
            existing_configs = self.read_existing_configs()
            configs_count = len(existing_configs)
            
            # Verifica file esistenti
            dashboard_files_exist = os.path.exists(self.dashboard_path)
            templates_file_exists = os.path.exists(self.templates_file)
            
            # Conta file dashboard esistenti
            dashboard_files_count = 0
            if dashboard_files_exist:
                try:
                    dashboard_files_count = len([f for f in os.listdir(self.dashboard_path) 
                                              if f.endswith('.yaml')])
                except:
                    dashboard_files_count = 0
            
            summary_attributes = {
                "initialized": datetime.now().isoformat(),
                "extension_version": "3.2.0",
                "description": "Riepilogo SouthTech Dashboard Extension",
                
                # Stato struttura
                "structure_ready": True,
                "dashboard_path_exists": dashboard_files_exist,
                "templates_file_exists": templates_file_exists,
                
                # Conteggi
                "existing_configurations": configs_count,
                "dashboard_files_count": dashboard_files_count,
                "estimated_sensors": configs_count * 4,
                
                # Paths
                "dashboard_path": self.dashboard_path,
                "light_configs_path": self.light_configs_path,
                "templates_file": self.templates_file,
                
                # Capacità
                "can_generate_dashboard": True,
                "can_generate_templates": True,
                "can_update_configuration": True,
                
                # Status
                "last_status_check": datetime.now().isoformat(),
                "system_ready": True
            }
            
            # Stato basato su configurazioni esistenti
            if configs_count > 0:
                state = "configurations_detected"
                summary_attributes["status_message"] = f"{configs_count} configurazioni rilevate - pronto per generazione dashboard"
            else:
                state = "no_configurations"
                summary_attributes["status_message"] = "Nessuna configurazione - configura almeno una luce per generare dashboard"
            
            self.set_state(summary_entity, state=state, attributes=summary_attributes)
            
            self.log(f"📊 Creata entità riepilogo dashboard: {configs_count} config rilevate")
            
        except Exception as e:
            self.error(f"Errore creazione entità riepilogo dashboard: {e}")

    def update_dashboard_debug_status(self, operation_type, success=True, details=None):
        """Aggiorna le entità debug dopo operazioni dashboard"""
        try:
            timestamp = datetime.now().isoformat()
            
            # Aggiorna entità specifica dell'operazione
            if operation_type == "dashboard_generation":
                entity_id = "sensor.southtech_dashboard_status"
                state = "completed" if success else "error"
                
                attributes = {
                    "last_generation": timestamp,
                    "generation_success": success,
                    "last_operation": operation_type
                }
                
                if details:
                    attributes.update({
                        "files_created": details.get("files_created", 0),
                        "generation_method": details.get("method", "unknown")
                    })
                    
                if not success and details:
                    attributes["last_error"] = details.get("error", "Unknown error")
                    
            elif operation_type == "template_generation":
                entity_id = "sensor.southtech_templates_status"
                state = "completed" if success else "error"
                
                attributes = {
                    "last_template_update": timestamp,
                    "generation_success": success,
                    "last_operation": operation_type
                }
                
                if details:
                    attributes.update({
                        "sensors_generated": details.get("sensors_count", 0),
                        "template_file_size": details.get("file_size", 0)
                    })
                    
            elif operation_type == "complete_save":
                entity_id = "sensor.southtech_complete_save_log"
                state = "completed" if success else "failed"
                
                attributes = {
                    "last_operation": timestamp,
                    "operation_success": success,
                    "operation_type": "complete_save"
                }
                
                if details:
                    attributes.update({
                        "files_modified": details.get("files_modified", []),
                        "operation_duration": details.get("duration", None),
                        "configurations_processed": details.get("configurations_count", 0)
                    })
            else:
                return  # Tipo operazione non riconosciuto
            
            # Aggiorna l'entità
            try:
                # Ottieni attributi esistenti
                existing_attrs = self.get_state(entity_id, attribute="all")
                if existing_attrs and "attributes" in existing_attrs:
                    current_attrs = existing_attrs["attributes"]
                    current_attrs.update(attributes)
                    attributes = current_attrs
                
                self.set_state(entity_id, state=state, attributes=attributes)
                self.log(f"🔍 Aggiornata entità debug {entity_id}: {state}")
                
            except Exception as e:
                self.error(f"Errore aggiornamento entità debug {entity_id}: {e}")
            
            # Aggiorna anche entità riepilogo
            self.update_dashboard_summary_after_operation(operation_type, success)
            
        except Exception as e:
            self.error(f"Errore aggiornamento debug status: {e}")

    def update_dashboard_summary_after_operation(self, operation_type, success):
        """Aggiorna entità riepilogo dopo operazioni"""
        try:
            summary_entity = "sensor.southtech_dashboard_extension_summary"
            
            # Ottieni attributi esistenti
            existing_attrs = self.get_state(summary_entity, attribute="all")
            if not existing_attrs or "attributes" not in existing_attrs:
                return
            
            attributes = existing_attrs["attributes"]
            
            # Aggiorna conteggi e timestamp
            attributes.update({
                "last_operation": operation_type,
                "last_operation_time": datetime.now().isoformat(),
                "last_operation_success": success
            })
            
            # Riconteggia file se operazione di successo
            if success and operation_type in ["dashboard_generation", "complete_save"]:
                try:
                    if os.path.exists(self.dashboard_path):
                        dashboard_files_count = len([f for f in os.listdir(self.dashboard_path) 
                                                  if f.endswith('.yaml')])
                        attributes["dashboard_files_count"] = dashboard_files_count
                    
                    if os.path.exists(self.light_configs_path):
                        light_files_count = len([f for f in os.listdir(self.light_configs_path) 
                                              if f.endswith('.yaml')])
                        attributes["light_config_files_count"] = light_files_count
                        
                except Exception as e:
                    self.log(f"⚠️ Errore riconteggio file: {e}")
            
            # Determina stato
            if success:
                if operation_type == "complete_save":
                    state = "save_completed"
                elif operation_type == "dashboard_generation":
                    state = "dashboard_generated"
                else:
                    state = "operation_completed"
            else:
                state = "operation_failed"
            
            self.set_state(summary_entity, state=state, attributes=attributes)
            
        except Exception as e:
            self.error(f"Errore aggiornamento riepilogo dashboard: {e}")

#                           DASHBOARD AND TEMPLATES                            #
    def generate_dashboard_and_templates(self, configurations, skip_backup=False):
        """
        🎯 METODO PRINCIPALE: Genera dashboard Lovelace + templates - CON BACKUP CONDIZIONALE
        """
        try:
            self.log(f"🎨 === INIZIO GENERAZIONE DASHBOARD E TEMPLATES (v3.5.0) {'- BACKUP SALTATO' if skip_backup else ''} ===")
            
            if not configurations:
                self.log("⚠️ Nessuna configurazione per dashboard")
                return {"success": True, "message": "Nessuna dashboard da generare"}
            
            self.log(f"🔧 Elaborazione {len(configurations)} configurazioni...")
            
            # Risultati dettagliati per ogni step
            results = {
                "templates": {"success": False, "error": None, "details": {}},
                "configuration": {"success": False, "error": None, "details": {}}, 
                "dashboard": {"success": False, "error": None, "details": {}},
                "light_configs": {"success": False, "error": None, "details": {}}
            }
            
            # STEP 1: Genera templates sensors con backup condizionale
            self.log("🧩 STEP 1/4: Generazione template sensors...")
            try:
                templates_result = self.generate_template_sensors(configurations, skip_backup=skip_backup)
                results["templates"] = templates_result
                
                if templates_result.get("success"):
                    self.log(f"✅ STEP 1/4: Templates generati ({templates_result.get('sensors_count', 0)} sensori)")
                    self.log(f"📄 File templates: {templates_result.get('file_path', 'N/A')}")
                    self.log(f"💾 Dimensione file: {templates_result.get('file_size', 0)} bytes")
                    backup_status = "saltato" if skip_backup else templates_result.get('backup_folder', 'N/A')
                    self.log(f"📦 Backup: {backup_status}")
                else:
                    error_msg = templates_result.get('error', 'Errore sconosciuto templates')
                    self.error(f"❌ STEP 1/4: Templates falliti - {error_msg}")
                    results["templates"]["details"]["error_type"] = "generation_failed"
                    results["templates"]["details"]["step"] = "template_sensors"
                    
            except Exception as templates_error:
                error_msg = str(templates_error)
                self.error(f"❌ STEP 1/4: Eccezione templates: {error_msg}")
                import traceback
                self.error(f"Stack trace templates: {traceback.format_exc()}")
                results["templates"] = {
                    "success": False, 
                    "error": error_msg,
                    "details": {
                        "error_type": "exception",
                        "step": "template_sensors",
                        "exception_type": type(templates_error).__name__,
                        "backup_skipped": skip_backup
                    }
                }
            
            # STEP 2: Aggiorna configuration.yaml con backup condizionale
            self.log("📝 STEP 2/4: Aggiornamento configuration.yaml...")
            try:
                config_result = self.update_configuration_yaml(skip_backup=skip_backup)
                results["configuration"] = config_result
                
                if config_result.get("success"):
                    self.log(f"✅ STEP 2/4: Configuration.yaml aggiornato")
                    self.log(f"📄 File size: {config_result.get('file_size', 0)} bytes")
                    backup_status = "saltato" if skip_backup else config_result.get('backup_folder', 'N/A')
                    self.log(f"📦 Backup: {backup_status}")
                else:
                    error_msg = config_result.get('error', 'Errore sconosciuto configuration.yaml')
                    self.error(f"❌ STEP 2/4: Configuration.yaml fallito - {error_msg}")
                    results["configuration"]["details"]["error_type"] = "yaml_update_failed"
                    results["configuration"]["details"]["step"] = "configuration_yaml"
                    results["configuration"]["details"]["method"] = config_result.get("method", "unknown")
                    
                    # Crea notifica per l'utente
                    self.create_ha_notification(
                        "⚠️ SouthTech: Configuration.yaml non aggiornato",
                        f"Dashboard e templates generati ma configuration.yaml richiede intervento manuale. Errore: {error_msg[:100]}..."
                    )
                    
            except Exception as config_error:
                error_msg = str(config_error)
                self.error(f"❌ STEP 2/4: Eccezione configuration.yaml: {error_msg}")
                import traceback
                self.error(f"Stack trace config: {traceback.format_exc()}")
                results["configuration"] = {
                    "success": False,
                    "error": error_msg,
                    "details": {
                        "error_type": "exception",
                        "step": "configuration_yaml", 
                        "exception_type": type(config_error).__name__,
                        "backup_skipped": skip_backup
                    }
                }
                
                # Notifica eccezione critica
                self.create_ha_notification(
                    "❌ SouthTech: Errore critico configuration.yaml", 
                    f"Eccezione durante aggiornamento configuration.yaml: {error_msg[:80]}..."
                )
            
            # STEP 3: Genera dashboard principale con backup condizionale
            self.log("🎨 STEP 3/4: Generazione dashboard principale...")
            try:
                dashboard_result = self.generate_main_dashboard(configurations, skip_backup=skip_backup)
                results["dashboard"] = dashboard_result
                
                if dashboard_result.get("success"):
                    self.log(f"✅ STEP 3/4: Dashboard generata")
                    self.log(f"📄 File: {dashboard_result.get('file', 'N/A')}")
                    self.log(f"💾 Size: {dashboard_result.get('size', 0)} bytes")
                    backup_status = "saltato" if skip_backup else dashboard_result.get('backup_folder', 'N/A')
                    self.log(f"📦 Backup: {backup_status}")
                else:
                    error_msg = dashboard_result.get('error', 'Errore sconosciuto dashboard')
                    self.error(f"❌ STEP 3/4: Dashboard fallita - {error_msg}")
                    results["dashboard"]["details"]["error_type"] = "dashboard_generation_failed"
                    results["dashboard"]["details"]["step"] = "main_dashboard"
                    
            except Exception as dashboard_error:
                error_msg = str(dashboard_error)
                self.error(f"❌ STEP 3/4: Eccezione dashboard: {error_msg}")
                import traceback
                self.error(f"Stack trace dashboard: {traceback.format_exc()}")
                results["dashboard"] = {
                    "success": False,
                    "error": error_msg,
                    "details": {
                        "error_type": "exception",
                        "step": "main_dashboard",
                        "exception_type": type(dashboard_error).__name__,
                        "backup_skipped": skip_backup
                    }
                }
            
            # STEP 4: Genera file configurazioni singole luci con backup condizionale
            self.log("💡 STEP 4/4: Generazione file configurazioni singole luci...")
            try:
                lights_result = self.generate_light_config_files(configurations, skip_backup=skip_backup)
                results["light_configs"] = lights_result
                
                if lights_result.get("success"):
                    self.log(f"✅ STEP 4/4: File luci generati ({lights_result.get('files_created', 0)} file)")
                    backup_status = "saltato" if skip_backup else lights_result.get('backup_folder', 'N/A')
                    self.log(f"📦 Backup: {backup_status}")
                else:
                    error_msg = lights_result.get('error', 'Errore sconosciuto file luci')
                    self.error(f"❌ STEP 4/4: File luci falliti - {error_msg}")
                    results["light_configs"]["details"]["error_type"] = "light_files_failed"
                    results["light_configs"]["details"]["step"] = "light_config_files"
                    
            except Exception as lights_error:
                error_msg = str(lights_error)
                self.error(f"❌ STEP 4/4: Eccezione file luci: {error_msg}")
                import traceback
                self.error(f"Stack trace lights: {traceback.format_exc()}")
                results["light_configs"] = {
                    "success": False,
                    "error": error_msg,
                    "details": {
                        "error_type": "exception",
                        "step": "light_config_files",
                        "exception_type": type(lights_error).__name__,
                        "backup_skipped": skip_backup
                    }
                }
            
            # Aggiungi flag backup_skipped a tutti i risultati
            for component_result in results.values():
                if isinstance(component_result, dict) and "details" in component_result:
                    component_result["details"]["backup_skipped"] = skip_backup
            
            # Aggiorna entità debug
            success_count = sum(1 for r in results.values() if r.get("success"))
            total_files = 1 + len(configurations)  # dashboard principale + file singoli
            
            self.update_dashboard_debug_status("dashboard_generation", True, {
                "files_created": total_files,
                "method": f"complete_generation_{'no_backup' if skip_backup else 'with_backup'}",
                "steps_successful": f"{success_count}/4",
                "backup_strategy": "skipped" if skip_backup else "individual",
                "steps_details": {
                    "templates": results["templates"].get("success", False),
                    "configuration": results["configuration"].get("success", False),
                    "dashboard": results["dashboard"].get("success", False),
                    "light_configs": results["light_configs"].get("success", False)
                }
            })
            
            # Determina successo basato su priorità dei file
            templates_success = results["templates"].get("success", False)
            dashboard_success = results["dashboard"].get("success", False) 
            light_configs_success = results["light_configs"].get("success", False)
            configuration_success = results["configuration"].get("success", False)
            
            # Conta componenti riusciti (su 4 totali)
            successful_components = sum([templates_success, dashboard_success, light_configs_success, configuration_success])
            
            # Criteri di successo più rigorosi
            if successful_components >= 3:
                # Successo completo (configuration.yaml è opzionale)
                overall_success = True
                if successful_components == 4:
                    message = f"Configurazione completa generata con successo (4/4 componenti)!{' Backup saltato.' if skip_backup else ''}"
                    success_type = "complete_success"
                else:
                    message = f"Dashboard e templates generati con successo ({successful_components}/4 componenti) - alcuni richiedono intervento manuale{' Backup saltato.' if skip_backup else ''}"
                    success_type = "partial_success"
            elif successful_components >= 2:
                # Successo parziale - almeno templates + uno degli altri
                overall_success = True
                message = f"Configurazione limitata ({successful_components}/4 componenti) - diversi componenti richiedono intervento manuale{' Backup saltato.' if skip_backup else ''}"
                success_type = "partial_success"
            else:
                # Fallimento - file critici non generati
                overall_success = False
                failed_components = []
                if not templates_success:
                    failed_components.append("Templates")
                if not dashboard_success:
                    failed_components.append("Dashboard")
                if not light_configs_success:
                    failed_components.append("File luci")
                
                message = f"Generazione fallita: {', '.join(failed_components)} non creati{' Backup saltato.' if skip_backup else ''}"
                success_type = "failure"
            
            # Risultato con dettagli migliorati
            result = {
                "success": overall_success,
                "success_type": success_type,
                "message": message,
                "details": results,  # Contiene i dettagli per ogni file
                "files_created": {
                    "templates_yaml": self.templates_file if templates_success else None,
                    "main_dashboard": os.path.join(self.dashboard_path, "ui-lovelace-light-presence.yaml") if dashboard_success else None,
                    "light_configs_count": results["light_configs"].get("files_created", 0),
                    "configuration_yaml_updated": configuration_success
                },
                "summary": {
                    "configurations_processed": len(configurations),
                    "template_sensors_created": results["templates"].get("sensors_count", 0),
                    "dashboard_files_created": 1 if dashboard_success else 0,
                    "light_config_files_created": results["light_configs"].get("files_created", 0),
                    "total_operations": 4,
                    "successful_operations": success_count,
                    "configuration_yaml_status": "updated" if configuration_success else "manual_required",
                    "backup_strategy": "skipped" if skip_backup else "individual_per_component"
                }
            }
            
            # Logging finale dettagliato
            backup_strategy = "BACKUP SALTATO" if skip_backup else "backup individuali"
            self.log(f"🎯 === RISULTATO FINALE ({backup_strategy}) ===")
            self.log(f"Overall Success: {overall_success} ({success_type})")
            self.log(f"Success Count: {success_count}/4")
            self.log(f"Templates: {'✅' if templates_success else '❌'}")
            self.log(f"Dashboard: {'✅' if dashboard_success else '❌'}")
            self.log(f"Light Configs: {'✅' if light_configs_success else '❌'}")
            self.log(f"Configuration.yaml: {'✅' if configuration_success else '❌'}")
            
            # Log errori specifici
            for step_name, step_result in results.items():
                if not step_result.get("success"):
                    self.error(f"🔴 {step_name.upper()} ERROR: {step_result.get('error', 'Unknown')}")
            
            return result
            
        except Exception as e:
            self.error(f"❌ Errore critico generazione dashboard: {e}")
            import traceback
            self.error(f"Stack trace completo: {traceback.format_exc()}")
            
            # Aggiorna entità debug con errore
            self.update_dashboard_debug_status("dashboard_generation", False, {
                "error": str(e),
                "backup_strategy": "skipped" if skip_backup else "individual"
            })
            
            return {
                "success": False,
                "success_type": "critical_failure", 
                "error": str(e),
                "details": {
                    "templates": {"success": False, "error": "Critical failure prevented execution", "backup_skipped": skip_backup},
                    "configuration": {"success": False, "error": "Critical failure prevented execution", "backup_skipped": skip_backup},
                    "dashboard": {"success": False, "error": "Critical failure prevented execution", "backup_skipped": skip_backup},
                    "light_configs": {"success": False, "error": "Critical failure prevented execution", "backup_skipped": skip_backup}
                }
            }

    def generate_template_sensors(self, configurations, skip_backup=False):
        """Genera sensori template per tutte le configurazioni in templates.yaml - CON BACKUP CONDIZIONALE"""
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.log(f"🔧 Generazione sensori template ({backup_status})...")
            
            # ✅ DEBUG SPECIFICO
            self.log(f"📍 DEBUG TEMPLATES: File target = {self.templates_file}")
            self.log(f"📍 DEBUG TEMPLATES: Directory = {os.path.dirname(self.templates_file)}")
            self.log(f"📍 DEBUG TEMPLATES: Directory esiste = {os.path.exists(os.path.dirname(self.templates_file))}")
            self.log(f"📍 DEBUG TEMPLATES: File esiste = {os.path.exists(self.templates_file)}")
            
            # 🎯 BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(self.templates_file):
                self.log("📦 Backup templates.yaml...")
                try:
                    backup_files = [{
                        "source_path": self.templates_file,
                        "backup_name": "templates.bkp",
                        "type": "templates"
                    }]
                    
                    backup_result = self.create_structured_backup(
                        backup_type="single",
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.log(f"✅ Backup templates.yaml: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        backup_info = {
                            "backup_created": False,
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.error(f"❌ Errore backup templates.yaml: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.log("⏭️ Backup templates.yaml saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "file_not_exists", "backup_skipped": False}
                self.log("ℹ️ File templates.yaml non esiste, nessun backup necessario")
            
            # Valida configurazioni
            valid_configs = [cfg for cfg in configurations 
                            if cfg.get('light_entity') and cfg.get('presence_sensor_on')]
            
            if not valid_configs:
                self.log("⚠️ Nessuna configurazione valida per templates")
                return {
                    "success": True, 
                    "sensors_count": 0, 
                    "message": "Nessun template da generare",
                    **backup_info
                }
            
            self.log(f"📊 Generazione templates per {len(valid_configs)} configurazioni valide")
            
            # Genera contenuto templates
            self.log("📝 Creazione contenuto templates...")
            templates_content = self.create_templates_content(valid_configs)
            self.log(f"✅ Contenuto generato: {len(templates_content)} caratteri")
            
            # Salva in templates.yaml
            self.log("💾 Inizio salvataggio templates.yaml...")
            self.save_templates_yaml(templates_content)
            self.log("✅ Salvataggio templates completato")
            
            # Verifica file salvato
            if os.path.exists(self.templates_file):
                file_size = os.path.getsize(self.templates_file)
                self.log(f"📄 Templates salvati: {file_size} bytes")
            else:
                raise Exception("File templates.yaml non creato")
            
            # Aggiorna entità debug templates
            sensors_count = len(valid_configs) * 4 + 1  # 4 per config + placeholder
            self.update_dashboard_debug_status("template_generation", True, {
                "sensors_count": sensors_count,
                "file_size": file_size,
                "backup_folder": backup_info.get("backup_folder"),
                "backup_strategy": "skipped" if skip_backup else "individual"
            })
            
            result = {
                "success": True,
                "sensors_count": sensors_count,
                "configurations_processed": len(valid_configs),
                "file_size": file_size,
                "file_path": self.templates_file,
                **backup_info
            }
            
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.log(f"✅ Generati {sensors_count} sensori template per {len(valid_configs)} configurazioni - {backup_msg}")
            return result
            
        except Exception as e:
            self.error(f"❌ Errore generazione templates: {e}")
            
            # Aggiorna entità debug con errore
            self.update_dashboard_debug_status("template_generation", False, {
                "error": str(e),
                "backup_folder": backup_info.get("backup_folder") if 'backup_info' in locals() else None,
                "backup_strategy": "skipped" if skip_backup else "individual"
            })
            
            return {
                "success": False, 
                "error": str(e),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def create_templates_content(self, configurations):
        """Crea contenuto YAML per sensori template - VERSIONE CORRETTA per entity_id"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ✅ CORREZIONE: Genera solo la sezione SouthTech senza template: root
            content = f"{self.templates_start_marker}\n"
            content += f"{self.templates_start_line}\n"
            content += f"{self.templates_end_marker}\n"
            content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
            
            # ✅ CORREZIONE: NON includere "template:" - sarà aggiunto dal merge
            sensors_content = ""
            
            # Placeholder iniziale (sempre presente)
            sensors_content += f"    - unique_id: placeholder\n"
            sensors_content += f"      name: PlaceHolder\n"
            sensors_content += f"      state: \"\"\n\n"
            
            # Genera sensori per ogni configurazione
            for config in configurations:
                light_entity = config.get('light_entity', '')
                presence_sensor = config.get('presence_sensor_on', '')
                
                if not light_entity or not presence_sensor:
                    self.log(f"⚠️ Configurazione incompleta saltata: {light_entity}")
                    continue
                    
                # Estrai base_id per unique_id
                base_id = light_entity.replace('light.', '')
                friendly_base = base_id.replace('_', ' ').title()
                
                self.log(f"🧩 Creazione sensori template per: {base_id}")
                
                # ✅ CORREZIONE: 4 sensori con NOMI che corrispondono agli unique_id
                sensors = [
                    {
                        "name": f"Presenza Luce {friendly_base}",               # ✅ CORRETTO
                        "unique_id": f"presenza_luce_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'on') and is_state('{light_entity}', 'on')",
                        "description": "Presenza rilevata E luce accesa"
                    },
                    {
                        "name": f"Solo Presenza {friendly_base}",               # ✅ OK
                        "unique_id": f"solo_presenza_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'on') and is_state('{light_entity}', 'off')",
                        "description": "Presenza rilevata MA luce spenta"
                    },
                    {
                        "name": f"Solo Luce {friendly_base}",                   # ✅ OK
                        "unique_id": f"solo_luce_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'off') and is_state('{light_entity}', 'on')",
                        "description": "Nessuna presenza MA luce accesa"
                    },
                    {
                        "name": f"Vuoto {friendly_base}",                       # ✅ OK
                        "unique_id": f"vuoto_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'off') and is_state('{light_entity}', 'off')",
                        "description": "Nessuna presenza E luce spenta"
                    }
                ]
                
                # Commento per gruppo di sensori
                sensors_content += f"    # Sensori per {friendly_base} ({light_entity})\n"
                
                for sensor in sensors:
                    sensors_content += f"    - name: \"{sensor['name']}\"\n"
                    sensors_content += f"      unique_id: {sensor['unique_id']}\n"
                    sensors_content += f"      state: >\n"
                    sensors_content += f"        {{% if {sensor['condition']} %}}\n"
                    sensors_content += f"          1\n"
                    sensors_content += f"        {{% else %}}\n"
                    sensors_content += f"          0\n"
                    sensors_content += f"        {{% endif %}}\n"
                    sensors_content += f"      attributes:\n"
                    sensors_content += f"        description: \"{sensor['description']}\"\n"
                    sensors_content += f"        light_entity: \"{light_entity}\"\n"
                    sensors_content += f"        presence_sensor: \"{presence_sensor}\"\n"
                    sensors_content += f"        generated_by: \"SouthTech Configurator\"\n"
                    sensors_content += f"        category: \"light_presence_monitoring\"\n\n"
            
            # ✅ STRUTTURA FINALE: Metadati + sensori (senza template: root)
            final_content = content + sensors_content
            
            # Fine sezione
            final_content += f"{self.templates_start_marker}\n"
            final_content += f"{self.templates_end_line}\n"
            final_content += f"{self.templates_end_marker}\n"
            
            self.log(f"📝 Contenuto templates generato: {len(final_content)} caratteri")
            self.log(f"✅ NOMI CORRETTI: entity_id corrisponderanno agli unique_id")
            return final_content
            
        except Exception as e:
            self.error(f"Errore creazione contenuto templates: {e}")
            raise

    def save_templates_yaml(self, content):
        """Salva contenuto nei templates.yaml con gestione sezione esistente - SENZA BACKUP LEGACY"""
        try:
            self.log(f"💾 TEMPLATES SAVE: Inizio salvataggio...")
            self.log(f"📍 File target: {self.templates_file}")
            self.log(f"📍 Contenuto da salvare: {len(content)} caratteri")
            
            # ✅ VERIFICA DIRECTORY ESISTENTE
            templates_dir = os.path.dirname(self.templates_file)
            self.log(f"📂 Directory templates: {templates_dir}")
            self.log(f"📂 Directory esiste: {os.path.exists(templates_dir)}")
            
            if not os.path.exists(templates_dir):
                self.log(f"⚠️ Directory templates non esiste, creazione...")
                os.makedirs(templates_dir, mode=0o755, exist_ok=True)
                self.log(f"📁 Directory templates creata: {templates_dir}")
            
            # ✅ VERIFICA PERMESSI
            can_write = os.access(templates_dir, os.W_OK)
            self.log(f"📂 Permessi scrittura: {can_write}")
            if not can_write:
                raise Exception(f"Nessun permesso di scrittura in: {templates_dir}")
            
            # ✅ VERIFICA FILE ESISTENTE
            file_exists = os.path.exists(self.templates_file)
            self.log(f"📄 File templates esistente: {file_exists}")
            if file_exists:
                existing_size = os.path.getsize(self.templates_file)
                self.log(f"📄 Dimensione file esistente: {existing_size} bytes")
            
            # 🚫 RIMOSSO: Backup legacy che creava file .yaml nella cartella backup
            # Questo backup ora è gestito dal sistema strutturato in generate_template_sensors()
            
            # Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.log(f"📖 Letto file templates esistente: {len(existing_content)} caratteri")
            
            # Sostituisci o aggiungi sezione
            self.log("🔀 Merge contenuto templates...")
            new_content = self.merge_templates_content(existing_content, content)
            self.log(f"🔗 Contenuto finale: {len(new_content)} caratteri")
            
            # Verifica YAML valido prima di scrivere
            try:
                import yaml
                parsed = yaml.safe_load(new_content)
                if parsed is None and new_content.strip():
                    raise Exception("YAML parsing risulta vuoto con contenuto presente")
                self.log("✅ YAML templates validato correttamente")
            except yaml.YAMLError as e:
                raise Exception(f"YAML templates non valido: {e}")
            
            # ✅ SCRITTURA CON DEBUG ESTESO
            temp_file = f"{self.templates_file}.tmp_write"
            try:
                self.log(f"💾 Scrittura file temporaneo: {temp_file}")
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                temp_size = os.path.getsize(temp_file)
                self.log(f"✅ File temporaneo scritto: {temp_size} bytes")
                
                # Verifica file temporaneo
                with open(temp_file, 'r', encoding='utf-8') as f:
                    verify_content = f.read()
                
                if verify_content != new_content:
                    raise Exception("Verifica contenuto file temporaneo fallita")
                
                self.log(f"✅ Verifica file temporaneo OK: {len(verify_content)} caratteri")
                
                # Sostituisci atomicamente
                self.log(f"🔄 Sostituzione atomica: {temp_file} -> {self.templates_file}")
                os.replace(temp_file, self.templates_file)
                self.log(f"✅ File sostituito atomicamente")
                
            except Exception as e:
                self.error(f"❌ ERRORE SCRITTURA TEMPLATES: {e}")
                self.error(f"❌ Temp file: {temp_file}")
                self.error(f"❌ Target file: {self.templates_file}")
                
                # Pulizia in caso di errore
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        self.log(f"🗑️ File temporaneo rimosso: {temp_file}")
                    except Exception as cleanup_error:
                        self.error(f"❌ Errore pulizia file temp: {cleanup_error}")
                raise
            
            # ✅ VERIFICA FINALE ESTESA
            if os.path.exists(self.templates_file):
                final_size = os.path.getsize(self.templates_file)
                self.log(f"✅ TEMPLATES SALVATI: {self.templates_file}")
                self.log(f"📊 Dimensione finale: {final_size} bytes")
                
                # Test lettura finale
                try:
                    with open(self.templates_file, 'r', encoding='utf-8') as f:
                        test_content = f.read()
                    self.log(f"✅ Test lettura finale OK: {len(test_content)} caratteri")
                    
                    # Verifica che contenga i nostri sensori
                    if "SouthTech Configurator" in test_content:
                        self.log(f"✅ Contenuto SouthTech confermato nel file")
                    else:
                        self.log(f"⚠️ Contenuto SouthTech NON trovato nel file salvato")
                        
                except Exception as read_error:
                    self.error(f"❌ Test lettura finale fallito: {read_error}")
            else:
                raise Exception(f"❌ FILE TEMPLATES NON TROVATO DOPO SALVATAGGIO: {self.templates_file}")
            
            self.log(f"💾 Templates salvati con successo: {self.templates_file}")
            
            # Log informazioni file
            if os.path.exists(self.templates_file):
                file_size = os.path.getsize(self.templates_file)
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    lines_count = len(f.readlines())
                self.log(f"📊 File templates: {file_size} bytes, {lines_count} righe")
            
        except Exception as e:
            self.error(f"❌ Errore salvataggio templates: {e}")
            raise

    def merge_templates_content(self, existing_content, new_section):
        """Unisce contenuto templates intelligentemente"""
        try:
            self.log("🔀 Merge contenuto templates...")
            
            # Trova sezione SouthTech esistente
            start_idx = existing_content.find(self.templates_start_line)
            if start_idx != -1:
                self.log("✅ Trovata sezione templates SouthTech esistente")
                
                # Trova inizio blocco
                start_block_idx = existing_content.rfind(self.templates_start_marker, 0, start_idx)
                if start_block_idx == -1:
                    start_block_idx = start_idx
                
                # Trova fine blocco
                end_line_idx = existing_content.find(self.templates_end_line, start_idx)
                if end_line_idx != -1:
                    end_block_idx = existing_content.find(self.templates_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.templates_end_marker)
                        
                        # Sostituisci sezione esistente con spazi corretti
                        before = existing_content[:start_block_idx].rstrip('\n')
                        after = existing_content[end_block_idx:].lstrip('\n')
                        
                        result = before
                        if before:
                            result += '\n\n'
                        result += new_section.rstrip('\n')
                        if after:
                            result += '\n\n' + after
                        else:
                            result += '\n'
                        
                        self.log("🔄 Sostituita sezione SouthTech esistente")
                        return result
            
            # 🆕 LOGICA MIGLIORATA: Gestisci file con template: esistenti
            self.log("ℹ️ Nessuna sezione SouthTech trovata, analisi file esistente...")
            
            # Controlla se esiste già una sezione template:
            if 'template:' in existing_content:
                self.log("⚠️ File contiene già sezioni template:, integrazione intelligente...")
                
                # Trova l'ultima sezione template:
                template_positions = []
                lines = existing_content.split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip() == 'template:' or line.strip().startswith('template:'):
                        template_positions.append(i)
                
                if template_positions:
                    # Inserisci la sezione SouthTech dopo l'ultima sezione template esistente
                    last_template_line = template_positions[-1]
                    
                    # Trova la fine di questa sezione template
                    end_template_line = len(lines)
                    for i in range(last_template_line + 1, len(lines)):
                        line = lines[i]
                        # Se trova una riga che non è indentata e non è vuota, è l'inizio di una nuova sezione
                        if line and not line.startswith(' ') and not line.startswith('\t') and line.strip():
                            end_template_line = i
                            break
                    
                    # Inserisci la sezione SouthTech dopo questa sezione
                    before_lines = lines[:end_template_line]
                    after_lines = lines[end_template_line:]
                    
                    result_lines = before_lines + [''] + new_section.rstrip('\n').split('\n') + ['']
                    if after_lines and any(line.strip() for line in after_lines):
                        result_lines.extend(after_lines)
                    
                    result = '\n'.join(result_lines)
                    self.log("🔗 Sezione SouthTech integrata dopo template esistenti")
                    return result
            
            # File senza template: esistenti, aggiungi normalmente
            self.log("📝 File senza template: esistenti, aggiunta normale")
            
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            
            return existing_content + '\n' + new_section.rstrip('\n') + '\n'
            
        except Exception as e:
            self.error(f"Errore merge templates: {e}")
            return new_section

#                       DASHBOARD AND TEMPLATES SUPPORT                        #
    def validate_templates_structure(self, configurations):
        """Valida la struttura delle configurazioni per templates"""
        try:
            validation_result = {
                "valid_configurations": [],
                "invalid_configurations": [],
                "warnings": [],
                "total_sensors_expected": 0
            }
            
            for i, config in enumerate(configurations):
                config_id = f"config_{i+1}"
                light_entity = config.get('light_entity', '')
                presence_sensor = config.get('presence_sensor_on', '')
                
                # Validazione base
                if not light_entity:
                    validation_result["invalid_configurations"].append({
                        "config_id": config_id,
                        "error": "light_entity mancante",
                        "config": config
                    })
                    continue
                
                if not presence_sensor:
                    validation_result["invalid_configurations"].append({
                        "config_id": config_id,
                        "error": "presence_sensor_on mancante", 
                        "config": config
                    })
                    continue
                
                # Validazione formato entità
                if not light_entity.startswith('light.'):
                    validation_result["invalid_configurations"].append({
                        "config_id": config_id,
                        "error": f"light_entity formato non valido: {light_entity}",
                        "config": config
                    })
                    continue
                
                if not presence_sensor.startswith('binary_sensor.'):
                    validation_result["warnings"].append({
                        "config_id": config_id,
                        "warning": f"presence_sensor non inizia con binary_sensor.: {presence_sensor}",
                        "config": config
                    })
                
                # Configurazione valida
                validation_result["valid_configurations"].append({
                    "config_id": config_id,
                    "light_entity": light_entity,
                    "presence_sensor": presence_sensor,
                    "base_id": light_entity.replace('light.', ''),
                    "config": config
                })
                
                validation_result["total_sensors_expected"] += 4  # 4 sensori per config
            
            # Aggiungi placeholder
            validation_result["total_sensors_expected"] += 1
            
            self.log(f"✅ Validazione templates: {len(validation_result['valid_configurations'])} valide, "
                    f"{len(validation_result['invalid_configurations'])} invalide, "
                    f"{len(validation_result['warnings'])} avvisi")
            
            return validation_result
            
        except Exception as e:
            self.error(f"Errore validazione templates: {e}")
            return {
                "valid_configurations": [],
                "invalid_configurations": configurations,
                "warnings": [],
                "error": str(e)
            }

    def cleanup_old_template_sensors(self):
        """Pulisce sensori template orfani dal file"""
        try:
            if not os.path.exists(self.templates_file):
                self.log("📄 File templates non esiste, nessuna pulizia necessaria")
                return
            
            self.log("🧹 Pulizia sensori template orfani...")
            
            # Ottieni configurazioni attuali
            current_configs = self.read_existing_configs()
            current_light_entities = {cfg.get('light_entity') for cfg in current_configs if cfg.get('light_entity')}
            
            # Leggi file templates
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Trova sezione SouthTech
            start_idx = content.find(self.templates_start_line)
            if start_idx == -1:
                self.log("ℹ️ Sezione SouthTech non trovata in templates")
                return
            
            # Estrai base_id dalle configurazioni attuali
            current_base_ids = {entity.replace('light.', '') for entity in current_light_entities}
            
            self.log(f"🔍 Configurazioni attuali: {len(current_base_ids)} base_id")
            self.log(f"📝 Base ID attuali: {current_base_ids}")
            
            # Regenera templates solo per configurazioni attuali
            if current_configs:
                self.log("🔄 Rigenerazione templates per configurazioni attuali")
                templates_result = self.generate_template_sensors(current_configs)
                
                if templates_result.get("success"):
                    self.log(f"✅ Templates aggiornati: {templates_result.get('sensors_count', 0)} sensori")
                else:
                    self.log(f"❌ Errore aggiornamento templates: {templates_result.get('error')}")
            else:
                self.log("ℹ️ Nessuna configurazione attuale, templates mantenuti invariati")
            
        except Exception as e:
            self.error(f"Errore pulizia template sensors: {e}")

    def get_template_sensors_status(self):
        """Ottieni stato dei template sensors generati"""
        try:
            status = {
                "file_exists": os.path.exists(self.templates_file),
                "file_size": 0,
                "sensors_count": 0,
                "last_modified": None,
                "valid_yaml": False,
                "sensors_details": []
            }
            
            if not status["file_exists"]:
                return status
            
            # Info file
            status["file_size"] = os.path.getsize(self.templates_file)
            status["last_modified"] = datetime.fromtimestamp(
                os.path.getmtime(self.templates_file)
            ).isoformat()
            
            # Verifica contenuto
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verifica YAML valido
                import yaml
                parsed = yaml.safe_load(content)
                status["valid_yaml"] = parsed is not None
                
                # Conta sensori SouthTech
                southtech_section = self.extract_southtech_templates_section(content)
                if southtech_section:
                    sensors_count = southtech_section.count("unique_id:")
                    status["sensors_count"] = sensors_count
                    
                    # Estrai dettagli sensori
                    if parsed and "template" in parsed:
                        for template_group in parsed["template"]:
                            if "sensor" in template_group:
                                for sensor in template_group["sensor"]:
                                    if sensor.get("unique_id", "").startswith(("presenza_luce_", "solo_presenza_", "solo_luce_", "vuoto_")):
                                        status["sensors_details"].append({
                                            "unique_id": sensor.get("unique_id"),
                                            "name": sensor.get("name"),
                                            "category": sensor.get("attributes", {}).get("category", "unknown")
                                        })
                
            except Exception as e:
                self.log(f"⚠️ Errore analisi file templates: {e}")
                status["analysis_error"] = str(e)
            
            return status
            
        except Exception as e:
            self.error(f"Errore status template sensors: {e}")
            return {"error": str(e)}

    def extract_southtech_templates_section(self, content):
        """Estrae solo la sezione SouthTech dal file templates"""
        try:
            start_idx = content.find(self.templates_start_line)
            if start_idx == -1:
                return None
            
            end_idx = content.find(self.templates_end_line, start_idx)
            if end_idx == -1:
                return None
            
            return content[start_idx:end_idx + len(self.templates_end_line)]
            
        except Exception as e:
            self.error(f"Errore estrazione sezione templates: {e}")
            return None

#                             CONFIGURATION.YAML                               #
    def update_configuration_yaml(self, skip_backup=False):
        """
        📝 AGGIORNAMENTO CONFIGURATION.YAML CON BACKUP CONDIZIONALE
        Riconosce marcatori START/END DASHBOARDS indipendentemente dalla spaziatura
        """
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.log(f"📝 === AGGIORNAMENTO CONFIGURATION.YAML ({backup_status.upper()}) ===")
            
            config_path = getattr(self, 'configuration_yaml_path', '/homeassistant/configuration.yaml')
            self.log(f"🎯 File target: {config_path}")
            
            # 1. Controlli base
            if not os.path.exists(config_path):
                error_msg = f"File configuration.yaml non trovato: {config_path}"
                self.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "backup_created": False, "backup_skipped": skip_backup}
            
            if not os.access(config_path, os.W_OK):
                error_msg = f"Nessun permesso di scrittura su {config_path}"
                self.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "backup_created": False, "backup_skipped": skip_backup}
            
            # 2. Lettura contenuto
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.log(f"📖 Letto configuration.yaml: {len(existing_content)} caratteri")
            except Exception as read_error:
                error_msg = f"Errore lettura file: {read_error}"
                self.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "backup_created": False, "backup_skipped": skip_backup}
            
            # 🎯 BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup:
                self.log("📦 Backup configuration.yaml...")
                try:
                    backup_files = [{
                        "source_path": config_path,
                        "backup_name": "configuration.bkp",
                        "type": "configuration"
                    }]
                    
                    backup_result = self.create_structured_backup(
                        backup_type="single",
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.log(f"✅ Backup configuration.yaml: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        backup_info = {
                            "backup_created": False,
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.error(f"❌ Errore backup configuration.yaml: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            else:
                self.log("⏭️ Backup configuration.yaml saltato (skip_backup=True)")
            
            # 3. RICERCA FLESSIBILE MARCATORI
            try:
                self.log("🔍 Ricerca flessibile marcatori START/END DASHBOARDS...")
                
                # Usa regex per trovare marcatori con spaziatura flessibile
                section_bounds = self.find_dashboards_section_flexible(existing_content)
                
                if section_bounds:
                    start_pos, end_pos, original_start_marker, original_end_marker = section_bounds
                    
                    self.log(f"✅ Trovata sezione DASHBOARDS esistente")
                    self.log(f"📍 Posizione: caratteri {start_pos} - {end_pos}")
                    self.log(f"🔍 Marcatore START originale: '{original_start_marker.strip()}'")
                    self.log(f"🔍 Marcatore END originale: '{original_end_marker.strip()}'")
                    
                    # Estrai la sezione esistente
                    existing_section = existing_content[start_pos:end_pos]
                    self.log(f"📋 Sezione esistente estratta: {len(existing_section)} caratteri")
                    
                    # Verifica se light-presence esiste già
                    if 'light-presence:' in existing_section:
                        self.log("⚠️ Dashboard light-presence già esistente - aggiornamento")
                        updated_section = self.update_existing_light_presence_dashboard(existing_section, original_start_marker, original_end_marker)
                    else:
                        self.log("➕ Aggiunta nuova dashboard light-presence")
                        updated_section = self.add_light_presence_to_existing_section(existing_section, original_start_marker, original_end_marker)
                    
                    if not updated_section:
                        raise Exception("Aggiornamento sezione dashboards ha prodotto contenuto vuoto")
                    
                    # Ricostruisci il file
                    before = existing_content[:start_pos]
                    after = existing_content[end_pos:]
                    
                    new_content = before + updated_section + after
                    
                    self.log("🔄 Sezione DASHBOARDS aggiornata preservando marcatori originali")
                    
                else:
                    self.log("ℹ️ Nessuna sezione DASHBOARDS trovata - creazione nuova sezione")
                    
                    # Crea sezione completa con marcatori standard
                    dashboard_section = self.create_dashboards_section()
                    
                    if existing_content and not existing_content.endswith('\n'):
                        existing_content += '\n'
                    
                    new_content = existing_content + '\n' + dashboard_section.rstrip('\n') + '\n'
                
                content_added = len(new_content) - len(existing_content)
                self.log(f"✅ Aggiornamento completato: da {len(existing_content)} a {len(new_content)} caratteri")
                self.log(f"📊 Contenuto modificato: {content_added} caratteri")
                
            except Exception as merge_error:
                error_msg = f"Errore aggiornamento sezione dashboards: {merge_error}"
                self.error(f"❌ {error_msg}")
                return {
                    "success": False, 
                    "error": error_msg,
                    **backup_info
                }
            
            # 4. SCRITTURA ATOMICA
            try:
                temp_file = f"{config_path}.tmp_southtech"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Verifica presenza light-presence
                with open(temp_file, 'r', encoding='utf-8') as f:
                    temp_content = f.read()
                
                if 'light-presence:' not in temp_content:
                    raise Exception("File temporaneo non contiene la dashboard light-presence")
                
                os.replace(temp_file, config_path)
                self.log("✅ Sostituzione atomica completata")
                
            except Exception as write_error:
                error_msg = f"Errore scrittura file: {write_error}"
                self.error(f"❌ {error_msg}")
                temp_file = f"{config_path}.tmp_southtech"
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                return {
                    "success": False, 
                    "error": error_msg,
                    **backup_info
                }
            
            # 5. RISULTATO SUCCESSO con info backup
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.log(f"✅ === AGGIORNAMENTO CONFIGURATION.YAML COMPLETATO - {backup_msg} ===")
            
            result = {
                "success": True,
                "message": f"Configuration.yaml aggiornato preservando marcatori originali{' (backup saltato)' if skip_backup else ''}",
                "method": f"flexible_marker_recognition_{'no_backup' if skip_backup else 'with_backup'}",
                "file": config_path,
                "file_size": os.path.getsize(config_path),
                "content_added": len(new_content) - len(existing_content),
                "dashboard_light_presence_added": True,
                "original_markers_preserved": section_bounds is not None,
                "timestamp": datetime.now().isoformat(),
                **backup_info
            }
            
            return result
            
        except Exception as e:
            self.error(f"❌ === ERRORE CRITICO CONFIGURATION.YAML: {e} ===")
            import traceback
            self.error(f"Stack trace: {traceback.format_exc()}")
            return {
                "success": False, 
                "error": str(e), 
                "method": f"flexible_marker_recognition_{'no_backup' if skip_backup else 'with_backup'}",
                "timestamp": datetime.now().isoformat(),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def update_existing_light_presence_dashboard(self, existing_section, original_start_marker, original_end_marker):
        """
        🔄 Aggiorna dashboard light-presence esistente preservando marcatori
        """
        try:
            # Per ora, mantieni la dashboard esistente
            self.log("🔄 Dashboard light-presence già presente, mantengo configurazione esistente")
            return existing_section
            
        except Exception as e:
            self.error(f"Errore aggiornamento light-presence esistente: {e}")
            raise

    def validate_yaml_safely(self, content):
        """
        🔍 VALIDAZIONE YAML ROBUSTA: Gestisce errori in file inclusi
        
        Returns:
            dict: {
                "valid": bool,
                "sections": list,
                "sections_count": int,
                "parsed_content": dict,
                "include_error": bool,
                "error": str
            }
        """
        try:
            import yaml
            
            # Tentativo parsing normale
            try:
                parsed = yaml.safe_load(content)
                
                # Successo completo
                if parsed is None:
                    if content.strip():
                        return {"valid": False, "error": "YAML risulta vuoto con contenuto presente"}
                    else:
                        return {"valid": True, "sections": [], "sections_count": 0}
                
                sections = list(parsed.keys()) if isinstance(parsed, dict) else []
                
                return {
                    "valid": True,
                    "sections": sections,
                    "sections_count": len(sections),
                    "parsed_content": parsed,
                    "include_error": False,
                    "error": None
                }
                
            except yaml.constructor.ConstructorError as constructor_error:
                # Errore probabilmente causato da file !include
                error_str = str(constructor_error)
                
                if '!include' in error_str:
                    self.log(f"🔍 Errore constructor in file inclusi: {error_str}")
                    
                    # Prova parsing con sostituzione include per verifica sintassi base
                    try:
                        clean_content = self.replace_includes_for_validation(content)
                        clean_parsed = yaml.safe_load(clean_content)
                        
                        if clean_parsed:
                            sections = list(clean_parsed.keys()) if isinstance(clean_parsed, dict) else []
                            return {
                                "valid": True,
                                "sections": sections,
                                "sections_count": len(sections),
                                "parsed_content": None,  # Non affidabile con sostituzione
                                "include_error": True,
                                "error": f"Include error: {error_str}"
                            }
                        else:
                            return {"valid": False, "error": "YAML base non valido dopo sostituzione include"}
                            
                    except Exception as clean_error:
                        return {"valid": False, "error": f"YAML base non valido: {clean_error}"}
                else:
                    return {"valid": False, "error": f"Constructor error: {constructor_error}"}
                    
            except yaml.YAMLError as yaml_error:
                return {"valid": False, "error": f"YAML error: {yaml_error}"}
                
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {e}"}

    def replace_includes_for_validation(self, content):
        """
        🔧 SOSTITUZIONE INCLUDE: Sostituisce !include con valori dummy per validazione
        """
        try:
            lines = content.split('\n')
            clean_lines = []
            
            for line in lines:
                if '!include' in line and ':' in line:
                    # Trova indentazione e chiave
                    indent = len(line) - len(line.lstrip())
                    key_part = line.split(':')[0].strip()
                    
                    # Sostituisci con valore appropriato
                    if any(keyword in key_part.lower() for keyword in ['automation', 'script', 'scene']):
                        clean_lines.append(' ' * indent + f'{key_part}: []')
                    elif any(keyword in key_part.lower() for keyword in ['group', 'customize']):
                        clean_lines.append(' ' * indent + f'{key_part}: {{}}')
                    elif 'sensor' in key_part.lower():
                        clean_lines.append(' ' * indent + f'{key_part}: []')
                    else:
                        clean_lines.append(' ' * indent + f'{key_part}: null')
                else:
                    clean_lines.append(line)
            
            return '\n'.join(clean_lines)
            
        except Exception as e:
            self.log(f"Errore sostituzione include: {e}")
            return content

    def verify_lovelace_structure(self, parsed_content):
        """
        🔍 VERIFICA STRUTTURA LOVELACE: Controlla che la dashboard sia presente
        """
        try:
            if not isinstance(parsed_content, dict):
                self.log("⚠️ Contenuto parsed non è un dizionario")
                return False
            
            if 'lovelace' not in parsed_content:
                self.log("⚠️ Sezione lovelace non trovata nel YAML finale")
                return False
            
            lovelace_section = parsed_content['lovelace']
            if not isinstance(lovelace_section, dict):
                self.log("⚠️ Sezione lovelace non è un dizionario")
                return False
                
            if 'dashboards' not in lovelace_section:
                self.log("⚠️ Sottosezione dashboards non trovata")
                return False
            
            dashboards = lovelace_section['dashboards']
            if not isinstance(dashboards, dict):
                self.log("⚠️ Sottosezione dashboards non è un dizionario")
                return False
                
            if 'light-presence' not in dashboards:
                self.log("⚠️ Dashboard light-presence non trovata")
                return False
            
            light_presence = dashboards['light-presence']
            if isinstance(light_presence, dict):
                # Verifica proprietà dashboard
                required_props = ['mode', 'filename', 'title']
                missing_props = [prop for prop in required_props if prop not in light_presence]
                
                if missing_props:
                    self.log(f"⚠️ Proprietà mancanti in light-presence: {missing_props}")
                else:
                    self.log("✅ Dashboard light-presence completa e valida")
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Errore verifica struttura lovelace: {e}")
            return False

    def create_dashboards_section(self):
        """
        📝 Crea sezione dashboards completa con indentazioni fisse
        VERSIONE SEMPLIFICATA con indentazioni corrette
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Usa le indentazioni fisse definite dall'utente
        content = f"################################################################################\n"  # colonna 1
        content += f"#                               START DASHBOARDS                               #\n"  # colonna 1
        content += f"################################################################################\n"  # colonna 1
        content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
        content += f"lovelace:\n"  # colonna 1 (0 spazi)
        content += f"  ##############################################################################\n"  # colonna 2 (2 spazi)
        content += f"  dashboards:\n"  # colonna 2 (2 spazi)
        content += f"    light-presence:\n"  # colonna 3 (4 spazi)
        content += f"      mode: yaml\n"  # colonna 4 (6 spazi)
        content += f"      filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml\n"  # colonna 4 (6 spazi)
        content += f"      title: Configurazione Luci Automatiche\n"  # colonna 4 (6 spazi)
        content += f"      icon: mdi:lightbulb-outline\n"  # colonna 4 (6 spazi)
        content += f"      show_in_sidebar: true\n"  # colonna 4 (6 spazi)
        content += f"      require_admin: true\n"  # colonna 4 (6 spazi)
        content += f"################################################################################\n"  # colonna 1
        content += f"#                                END DASHBOARDS                                 #\n"  # colonna 1
        content += f"################################################################################\n"  # colonna 1
        
        return content

    def merge_configuration_content(self, existing_content, new_section):
        """Merge intelligente per configuration.yaml - VERSIONE AVANZATA"""
        try:
            self.log("🔀 Merge intelligente configuration.yaml (v2.0)...")
            
            # STEP 1: Cerca sezione dashboard SouthTech esistente
            start_idx = existing_content.find(self.config_start_line)
            if start_idx != -1:
                self.log("✅ Trovata sezione dashboard SouthTech esistente - sostituzione")
                
                # Sostituisci sezione SouthTech esistente
                start_block_idx = existing_content.rfind(self.config_start_marker, 0, start_idx)
                if start_block_idx == -1:
                    start_block_idx = start_idx
                
                end_line_idx = existing_content.find(self.config_end_line, start_idx)
                if end_line_idx != -1:
                    end_block_idx = existing_content.find(self.config_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.config_end_marker)
                        
                        before = existing_content[:start_block_idx].rstrip('\n')
                        after = existing_content[end_block_idx:].lstrip('\n')
                        
                        result = before
                        if before:
                            result += '\n\n'
                        result += new_section.rstrip('\n')
                        if after:
                            result += '\n\n' + after
                        else:
                            result += '\n'
                        
                        self.log("🔄 Sostituita sezione SouthTech esistente")
                        return result
            
            # STEP 2: Cerca sezione lovelace esistente
            lovelace_analysis = self.analyze_lovelace_section(existing_content)
            
            if lovelace_analysis["has_lovelace"]:
                self.log("✅ Trovata sezione lovelace esistente - inserimento dashboard")
                return self.insert_dashboard_in_existing_lovelace(existing_content, lovelace_analysis)
            
            # STEP 3: Nessuna sezione lovelace - trova posizione migliore
            self.log("ℹ️ Nessuna sezione lovelace - ricerca posizione ottimale...")
            best_position = self.find_best_position_for_dashboard(existing_content)
            
            if best_position != -1:
                before = existing_content[:best_position].rstrip('\n')
                after = existing_content[best_position:].lstrip('\n')
                
                result = before + '\n\n' + new_section.rstrip('\n')
                if after:
                    result += '\n\n' + after
                else:
                    result += '\n'
                
                self.log(f"📍 Dashboard inserita in posizione ottimale: {best_position}")
                return result
            
            # STEP 4: Fallback - aggiungi alla fine
            self.log("📍 Fallback: dashboard aggiunta alla fine del file")
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            
            return existing_content + '\n' + new_section.rstrip('\n') + '\n'
            
        except Exception as e:
            self.error(f"Errore merge configuration: {e}")
            return new_section

    def analyze_lovelace_section(self, content):
        """Analizza la sezione lovelace esistente"""
        try:
            analysis = {
                "has_lovelace": False,
                "lovelace_start": -1,
                "lovelace_end": -1,
                "has_dashboards": False,
                "dashboards_start": -1,
                "dashboards_end": -1,
                "has_light_presence": False
            }
            
            lines = content.split('\n')
            in_lovelace = False
            in_dashboards = False
            lovelace_indent = 0
            
            for i, line in enumerate(lines):
                if line.strip().startswith('lovelace:'):
                    analysis["has_lovelace"] = True
                    analysis["lovelace_start"] = i
                    in_lovelace = True
                    lovelace_indent = len(line) - len(line.lstrip())
                    self.log(f"🔍 Trovata sezione lovelace alla riga {i+1}")
                    
                elif in_lovelace:
                    current_indent = len(line) - len(line.lstrip()) if line.strip() else 999
                    
                    if line.strip().startswith('dashboards:'):
                        analysis["has_dashboards"] = True
                        analysis["dashboards_start"] = i
                        in_dashboards = True
                        self.log(f"🔍 Trovata sezione dashboards alla riga {i+1}")
                        
                    elif in_dashboards and 'light-presence:' in line:
                        analysis["has_light_presence"] = True
                        self.log(f"🔍 Trovata dashboard light-presence esistente alla riga {i+1}")
                        
                    elif line.strip() and current_indent <= lovelace_indent and not line.startswith(' '):
                        # Fine sezione lovelace
                        analysis["lovelace_end"] = i
                        break
            
            # Se non ha trovato la fine, va fino alla fine del file
            if analysis["lovelace_end"] == -1 and analysis["has_lovelace"]:
                analysis["lovelace_end"] = len(lines)
            
            self.log(f"📊 Analisi lovelace: {analysis}")
            return analysis
            
        except Exception as e:
            self.error(f"Errore analisi sezione lovelace: {e}")
            return {"has_lovelace": False}

    def insert_dashboard_in_existing_lovelace(self, content, analysis):
        """Inserisce dashboard in sezione lovelace esistente"""
        try:
            lines = content.split('\n')
            
            if analysis["has_light_presence"]:
                self.log("⚠️ Dashboard light-presence già esistente - sostituzione")
                # TODO: Implementa sostituzione dashboard esistente se necessario
                return content
            
            # Genera solo l'entry della dashboard
            dashboard_entry = self.create_dashboards_section(mode="dashboard_only")
            dashboard_lines = dashboard_entry.split('\n')
            
            if analysis["has_dashboards"]:
                # Inserisci nella sezione dashboards esistente
                insert_position = analysis["dashboards_start"] + 1
                
                # Trova l'ultima dashboard esistente
                for i in range(insert_position, analysis["lovelace_end"]):
                    if lines[i].strip() and not lines[i].startswith('  ') and not lines[i].startswith('\t'):
                        # Fine sezione dashboards
                        insert_position = i
                        break
                    elif lines[i].strip().endswith(':') and lines[i].startswith('    '):
                        # Trovata dashboard, continua a cercare
                        insert_position = i + 1
                        
                        # Salta le proprietà di questa dashboard
                        for j in range(i + 1, analysis["lovelace_end"]):
                            if lines[j].strip() and lines[j].startswith('      '):
                                continue  # Proprietà della dashboard
                            else:
                                insert_position = j
                                break
                
                self.log(f"📍 Inserimento dashboard alla riga {insert_position + 1}")
                
            else:
                # Aggiungi sezione dashboards
                insert_position = analysis["lovelace_start"] + 1
                dashboard_lines = ['  dashboards:'] + dashboard_lines
                self.log(f"📍 Creazione sezione dashboards alla riga {insert_position + 1}")
            
            # Inserisci le nuove righe
            result_lines = lines[:insert_position]
            result_lines.extend(dashboard_lines)
            result_lines.extend(lines[insert_position:])
            
            result = '\n'.join(result_lines)
            self.log("✅ Dashboard inserita in sezione lovelace esistente")
            return result
            
        except Exception as e:
            self.error(f"Errore inserimento dashboard in lovelace: {e}")
            raise

    def generate_main_dashboard(self, configurations, skip_backup=False):
        """Genera dashboard principale ui-lovelace-light-presence.yaml - CON BACKUP CONDIZIONALE"""
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.log(f"🎨 Generazione dashboard principale ({backup_status})...")
            
            if not configurations:
                self.log("⚠️ Nessuna configurazione per dashboard principale")
                return {"success": False, "error": "Nessuna configurazione fornita", "backup_created": False, "backup_skipped": skip_backup}
            
            dashboard_file = os.path.join(self.dashboard_path, "ui-lovelace-light-presence.yaml")
            
            # 🎯 BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(dashboard_file):
                self.log("📦 Backup dashboard principale...")
                try:
                    backup_files = [{
                        "source_path": dashboard_file,
                        "backup_name": "ui-lovelace-light-presence.bkp",
                        "type": "main_dashboard"
                    }]
                    
                    backup_result = self.create_structured_backup(
                        backup_type="single",
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.log(f"✅ Backup dashboard: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        backup_info = {
                            "backup_created": False,
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.error(f"❌ Errore backup dashboard: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.log("⏭️ Backup dashboard principale saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "file_not_exists", "backup_skipped": False}
                self.log("ℹ️ File dashboard principale non esiste, nessun backup necessario")
            
            # Genera contenuto dashboard
            dashboard_content = self.create_main_dashboard_content(configurations)
            
            # Scrivi file dashboard
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                f.write(dashboard_content)
            
            # Verifica file salvato
            if not os.path.exists(dashboard_file):
                raise Exception("File dashboard principale non creato")
            
            file_size = os.path.getsize(dashboard_file)
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.log(f"✅ Dashboard principale generata: {dashboard_file}")
            self.log(f"📊 Dashboard file: {file_size} bytes")
            self.log(f"📦 {backup_msg}")
            
            result = {
                "success": True, 
                "file": dashboard_file,
                "size": file_size,
                "views_count": len(configurations),
                **backup_info
            }
            
            return result
            
        except Exception as e:
            self.error(f"❌ Errore generazione dashboard principale: {e}")
            return {
                "success": False, 
                "error": str(e),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def create_main_dashboard_content(self, configurations):
        """Crea contenuto dashboard principale"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            content = f"# Dashboard Configurazione Luci Automatiche\n"
            content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
            content += f"# Configurazioni processate: {len(configurations)}\n\n"
            
            content += f"title: Configurazione Luci Automatiche\n"
            content += f"icon: mdi:lightbulb-outline\n"
            content += f"path: light-presence\n\n"
            
            content += f"views:\n"
            
            # View principale con riepilogo
            content += f"  - title: Panoramica\n"
            content += f"    path: overview\n"
            content += f"    icon: mdi:view-dashboard\n"
            content += f"    cards:\n"
            content += f"      - type: markdown\n"
            content += f"        content: |\n"
            content += f"          # 🏠 Configurazione Luci Automatiche\n"
            content += f"          \n"
            content += f"          **Luci configurate:** {len(configurations)}\n"
            content += f"          **Ultima generazione:** {timestamp}\n"
            content += f"          \n"
            content += f"          ### 💡 Luci Gestite:\n"
            
            for i, config in enumerate(configurations, 1):
                light_entity = config.get('light_entity', '')
                if light_entity:
                    friendly_name = self.get_entity_friendly_name(light_entity, light_entity.replace('light.', ''))
                    content += f"          {i}. **{friendly_name}** (`{light_entity}`)\n"
            
            content += f"          \n"
            content += f"          Usa le tab per configurare ogni singola luce.\n\n"
            
            # View per ogni configurazione
            for i, config in enumerate(configurations):
                light_entity = config.get('light_entity', '')
                if not light_entity:
                    self.log(f"⚠️ Configurazione {i+1} saltata: light_entity mancante")
                    continue
                    
                base_id = light_entity.replace('light.', '')
                friendly_name = self.get_entity_friendly_name(light_entity, base_id)
                
                self.log(f"🎨 Creazione view per: {friendly_name} ({base_id})")
                
                content += f"  - title: {friendly_name}\n"
                content += f"    path: opzioni_{base_id}\n"
                content += f"    icon: mdi:lightbulb\n"
                content += f"    type: custom:grid-layout\n"
                content += f"    layout:\n"
                content += f"      grid-template-columns: 1fr 1fr\n"
                content += f"      grid-gap: 16px\n"
                content += f"      mediaquery:\n"
                content += f"        '(max-width: 800px)':\n"
                content += f"          grid-template-columns: 1fr\n"
                content += f"    cards: !include light_configs/{base_id}.yaml\n\n"
            
            self.log(f"📝 Contenuto dashboard principale generato: {len(content)} caratteri")
            self.log(f"📊 Views create: {len(configurations) + 1} (1 panoramica + {len(configurations)} luci)")
            
            return content
            
        except Exception as e:
            self.error(f"Errore creazione contenuto dashboard: {e}")
            raise

#                         CONFIGURATION.YAML SUPPORT                           #
    def generate_light_config_files(self, configurations, skip_backup=False):
        """Genera file configurazione per ogni singola luce - CON BACKUP CONDIZIONALE"""
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.log(f"🔧 Generazione file configurazioni singole luci ({backup_status})...")
            
            if not configurations:
                return {
                    "success": True, 
                    "files_created": 0, 
                    "message": "Nessun file da generare",
                    "backup_created": False,
                    "backup_skipped": skip_backup
                }
            
            # 🎯 BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_files = []
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(self.light_configs_path):
                for config in configurations:
                    light_entity = config.get('light_entity', '')
                    if light_entity:
                        base_id = light_entity.replace('light.', '')
                        config_file = os.path.join(self.light_configs_path, f"{base_id}.yaml")
                        
                        if os.path.exists(config_file):
                            backup_files.append({
                                "source_path": config_file,
                                "backup_name": f"{base_id}.bkp",
                                "type": "light_config"
                            })
            
            if backup_files and not skip_backup:
                self.log(f"📦 Backup {len(backup_files)} file light_config...")
                try:
                    backup_result = self.create_structured_backup(
                        backup_type="single",
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.log(f"✅ Backup light_config: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        backup_info = {
                            "backup_created": False,
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.error(f"❌ Errore backup light_config: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.log("⏭️ Backup file light_config saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "no_existing_files", "backup_skipped": False}
                self.log("ℹ️ Nessun file light_config esistente da backuppare")
            
            # Genera nuovi file
            files_created = []
            files_failed = []
            
            for i, config in enumerate(configurations):
                light_entity = config.get('light_entity', '')
                if not light_entity:
                    self.log(f"⚠️ Configurazione {i+1} saltata: light_entity mancante")
                    files_failed.append(f"config_{i+1}_no_light_entity")
                    continue
                    
                base_id = light_entity.replace('light.', '')
                config_file = os.path.join(self.light_configs_path, f"{base_id}.yaml")
                
                try:
                    # Genera contenuto configurazione luce
                    light_config_content = self.create_light_config_content(config)
                    
                    # Salva file
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(light_config_content)
                    
                    # Verifica file creato
                    if not os.path.exists(config_file):
                        raise Exception(f"File {base_id}.yaml non creato")
                    
                    file_size = os.path.getsize(config_file)
                    files_created.append({
                        "file": config_file,
                        "base_id": base_id,
                        "light_entity": light_entity,
                        "size": file_size
                    })
                    
                    self.log(f"📄 Creato: {base_id}.yaml ({file_size} bytes)")
                    
                except Exception as e:
                    self.error(f"❌ Errore creazione file {base_id}.yaml: {e}")
                    files_failed.append(f"{base_id}: {str(e)}")
            
            total_size = sum(f["size"] for f in files_created)
            
            result = {
                "success": len(files_failed) == 0,
                "files_created": len(files_created),
                "files_failed": len(files_failed),
                "total_size": total_size,
                "files_details": files_created,
                **backup_info
            }
            
            if files_failed:
                result["errors"] = files_failed
                backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
                self.log(f"⚠️ File creati con errori: {len(files_created)} OK, {len(files_failed)} falliti - {backup_msg}")
            else:
                backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
                self.log(f"✅ Generati {len(files_created)} file configurazioni luci ({total_size} bytes totali) - {backup_msg}")
            
            return result
            
        except Exception as e:
            self.error(f"❌ Errore generazione file luci: {e}")
            return {
                "success": False, 
                "error": str(e),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def find_best_position_for_dashboard(self, content):
        """Trova la posizione migliore per inserire la dashboard in configuration.yaml"""
        try:
            lines = content.split('\n')
            
            # Strategia 1: Dopo una sezione lovelace esistente
            lovelace_end = -1
            in_lovelace = False
            
            for i, line in enumerate(lines):
                if line.strip().startswith('lovelace:'):
                    in_lovelace = True
                    self.log(f"📍 Trovata sezione lovelace esistente alla riga {i+1}")
                elif in_lovelace and line and not line.startswith(' ') and not line.startswith('\t'):
                    # Fine sezione lovelace
                    lovelace_end = sum(len(l) + 1 for l in lines[:i])  # Posizione carattere
                    self.log(f"📍 Fine sezione lovelace alla riga {i+1}")
                    break
            
            if lovelace_end != -1:
                return lovelace_end
            
            # Strategia 2: Dopo sezioni core (recorder, logger, etc.)
            core_sections = ['recorder:', 'logger:', 'history:', 'frontend:', 'api:', 'config:']
            last_core_section = -1
            
            for i, line in enumerate(lines):
                if any(line.strip().startswith(section) for section in core_sections):
                    # Trova fine di questa sezione
                    for j in range(i + 1, len(lines)):
                        if lines[j] and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                            last_core_section = sum(len(l) + 1 for l in lines[:j])
                            break
                    else:
                        # Sezione va fino alla fine
                        last_core_section = len(content)
            
            if last_core_section != -1:
                self.log(f"📍 Posizione dopo sezioni core: {last_core_section}")
                return last_core_section
            
            # Strategia 3: Dopo homeassistant: section
            for i, line in enumerate(lines):
                if line.strip().startswith('homeassistant:'):
                    # Trova fine sezione homeassistant
                    for j in range(i + 1, len(lines)):
                        if lines[j] and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                            ha_end = sum(len(l) + 1 for l in lines[:j])
                            self.log(f"📍 Posizione dopo homeassistant: {ha_end}")
                            return ha_end
            
            # Strategia 4: Dopo primi commenti/intestazioni
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith('#') and line.strip() != '---':
                    # Prima riga non commento
                    first_content = sum(len(l) + 1 for l in lines[:i])
                    self.log(f"📍 Posizione dopo commenti iniziali: {first_content}")
                    return first_content
            
            # Nessuna posizione ideale trovata
            self.log("📍 Nessuna posizione ideale trovata")
            return -1
            
        except Exception as e:
            self.error(f"Errore ricerca posizione dashboard: {e}")
            return -1

    def get_entity_friendly_name(self, entity_id, fallback):
        """Ottieni friendly name entità o usa fallback formattato"""
        try:
            # Prova a ottenere friendly name da Home Assistant
            try:
                entity_state = self.get_state(entity_id, attribute="all")
                if entity_state and "attributes" in entity_state:
                    friendly_name = entity_state["attributes"].get("friendly_name")
                    if friendly_name and friendly_name != entity_id:
                        return friendly_name
            except Exception as e:
                self.log(f"⚠️ Impossibile ottenere friendly_name per {entity_id}: {e}")
            
            # Fallback: formatta base_id
            if fallback:
                # Converti underscore in spazi e capitalizza
                formatted = fallback.replace('_', ' ')
                # Capitalizza ogni parola
                formatted = ' '.join(word.capitalize() for word in formatted.split())
                return formatted
            
            # Ultimo fallback: usa entity_id pulito
            if entity_id:
                clean_id = entity_id.split('.', 1)[-1] if '.' in entity_id else entity_id
                return clean_id.replace('_', ' ').title()
            
            return "Unknown Entity"
            
        except Exception as e:
            self.error(f"Errore get_entity_friendly_name per {entity_id}: {e}")
            return fallback if fallback else "Unknown Entity"

    def create_basic_configuration_yaml(self):
        """Crea un file configuration.yaml base se non esiste"""
        try:
            basic_content = """# Home Assistant Configuration File
    # Generated by SouthTech Configurator

    # Default configuration
    default_config:

    # Home Assistant Core
    homeassistant:
      name: Home
      unit_system: metric
      time_zone: Europe/Rome

    # Frontend
    frontend:
      themes: !include_dir_merge_named themes

    # API
    api:

    # Text to speech
    tts:
      - platform: google_translate

    # Automation and scripts
    automation: !include automations.yaml
    script: !include scripts.yaml
    scene: !include scenes.yaml

    """
            
            with open(self.configuration_yaml_path, 'w', encoding='utf-8') as f:
                f.write(basic_content)
            
            self.log(f"📄 Creato configuration.yaml base: {self.configuration_yaml_path}")
            
        except Exception as e:
            self.error(f"Errore creazione configuration.yaml base: {e}")
            raise

    def create_light_config_content(self, config):
        """Crea contenuto YAML per configurazione singola luce"""
        try:
            light_entity = config.get('light_entity', '')
            presence_sensor = config.get('presence_sensor_on', '')
            presence_sensor_off = config.get('presence_sensor_off', '')
            illuminance_sensor = config.get('illuminance_sensor', '')
            
            if not light_entity:
                raise Exception("light_entity mancante nella configurazione")
            
            base_id = light_entity.replace('light.', '')
            friendly_name = self.get_entity_friendly_name(light_entity, base_id)
            
            content = f"# Configurazione {friendly_name}\n"
            content += f"# Generato automaticamente da SouthTech Configurator\n"
            content += f"# Light Entity: {light_entity}\n"
            content += f"# Base ID: {base_id}\n\n"
            
            # Card intestazione con area dinamica
            content += f"- type: markdown\n"
            content += f"  content: >\n"
            content += f"    {{% set name = state_attr('{light_entity}', 'friendly_name') %}}\n"
            content += f"    {{% set area = area_name('{light_entity}') %}}\n"
            content += f"    {{% set icon = '💡' if is_state('{light_entity}', 'on') else '⚫' %}}\n\n"
            content += f"    # {{{{ icon }}}} {{{{ name or '{friendly_name}' }}}}\n\n"
            content += f"    {{% if area %}} 🏷️ Area: {{{{ area }}}} {{% endif %}}\n"
            content += f"  style: |\n"
            content += f"    ha-card {{\n"
            content += f"      text-align: center;\n"
            content += f"      padding: 24px 0 8px;\n"
            content += f"      font-size: 28px;\n"
            content += f"      font-weight: bold;\n"
            content += f"    }}\n"
            content += f"    h3 {{\n"
            content += f"      font-size: 18px;\n"
            content += f"      font-weight: normal;\n"
            content += f"      margin: 0;\n"
            content += f"    }}\n\n"
            
            # Card controllo luce mushroom
            content += f"- type: custom:mushroom-light-card\n"
            content += f"  entity: {light_entity}\n"
            content += f"  icon: mdi:lightbulb-outline\n"
            content += f"  layout: vertical\n"
            content += f"  show_brightness_control: true\n"
            content += f"  show_color_control: true\n"
            content += f"  show_color_temp_control: true\n"
            content += f"  use_light_color: true\n"
            content += f"  tap_action:\n"
            content += f"    action: toggle\n"
            content += f"  hold_action:\n"
            content += f"    action: more-info\n\n"
            
            # Card sensori
            content += f"- type: entities\n"
            content += f"  title: Sensori\n"
            content += f"  entities:\n"
            
            if presence_sensor:
                content += f"    - entity: {presence_sensor}\n"
                content += f"      name: Presenza Rilevata\n"
            
            if presence_sensor_off:
                content += f"    - entity: {presence_sensor_off}\n"
                content += f"      name: Sensore Spegnimento\n"
            
            if illuminance_sensor:
                content += f"    - entity: {illuminance_sensor}\n"
                content += f"      name: Illuminamento\n"
            
            if not presence_sensor and not illuminance_sensor:
                content += f"    - type: section\n"
                content += f"      label: Nessun sensore configurato\n"
            
            content += f"\n"
            
            # Card grafico o placeholder
            if illuminance_sensor:
                content += self.create_illuminance_chart(config, base_id)
            else:
                content += self.create_illuminance_placeholder()
            
            # Card timer e soglie
            content += self.create_timer_settings_card(base_id)
            
            # Card automazione
            content += self.create_automation_settings_card(base_id)
            
            self.log(f"📝 Contenuto configurazione luce generato per {base_id}: {len(content)} caratteri")
            return content
            
        except Exception as e:
            self.error(f"Errore creazione configurazione luce: {e}")
            raise

    def create_illuminance_chart(self, config, base_id):
        """Crea grafico illuminamento con sensori template"""
        light_entity = config.get('light_entity', '')
        illuminance_sensor = config.get('illuminance_sensor', '')
        
        content = f"- type: custom:apexcharts-card\n"
        content += f"  graph_span: 24h\n"
        content += f"  update_interval: 60s\n"
        content += f"  header:\n"
        content += f"    show: true\n"
        content += f"    title: Illuminamento + Stato Presenza/Luce\n"
        content += f"  stacked: true\n"
        content += f"  series:\n"
        content += f"    - entity: {illuminance_sensor}\n"
        content += f"      name: Illuminamento\n"
        content += f"      type: line\n"
        content += f"      yaxis_id: lux\n"
        content += f"      color: '#3498db'\n"
        content += f"      stroke_width: 2\n"
        content += f"    - entity: sensor.presenza_luce_{base_id}\n"
        content += f"      name: Presenza + Luce\n"
        content += f"      type: area\n"
        content += f"      yaxis_id: stato\n"
        content += f"      color: '#FFFF00'\n"
        content += f"      group_by:\n"
        content += f"        duration: 5min\n"
        content += f"        func: last\n"
        content += f"    - entity: sensor.solo_presenza_{base_id}\n"
        content += f"      name: Solo Presenza\n"
        content += f"      type: area\n"
        content += f"      yaxis_id: stato\n"
        content += f"      color: '#00FF00'\n"
        content += f"      group_by:\n"
        content += f"        duration: 5min\n"
        content += f"        func: last\n"
        content += f"    - entity: sensor.solo_luce_{base_id}\n"
        content += f"      name: Solo Luce\n"
        content += f"      type: area\n"
        content += f"      yaxis_id: stato\n"
        content += f"      color: '#FFA500'\n"
        content += f"      group_by:\n"
        content += f"        duration: 5min\n"
        content += f"        func: last\n"
        content += f"    - entity: sensor.vuoto_{base_id}\n"
        content += f"      name: Vuota\n"
        content += f"      type: area\n"
        content += f"      yaxis_id: stato\n"
        content += f"      color: '#444444'\n"
        content += f"      group_by:\n"
        content += f"        duration: 5min\n"
        content += f"        func: last\n"
        content += f"  yaxis:\n"
        content += f"    - id: lux\n"
        content += f"      show: true\n"
        content += f"      min: 0\n"
        content += f"      decimals: 0\n"
        content += f"    - id: stato\n"
        content += f"      show: false\n"
        content += f"      min: 0\n"
        content += f"      max: 1\n\n"
        
        return content

    def create_illuminance_placeholder(self):
        """Crea placeholder per sensore illuminazione mancante"""
        content = f"- type: markdown\n"
        content += f"  content: >\n"
        content += f"    ### ⚠️ Sensore di Illuminazione Non Registrato\n\n"
        content += f"    Non è stato configurato un sensore di illuminamento per questa luce.\n"
        content += f"    Il grafico dei dati di illuminamento non è disponibile.\n\n"
        content += f"    💡 **Suggerimento**: Configura un sensore di illuminamento\n"
        content += f"    nell'interfaccia SouthTech per abilitare il monitoraggio avanzato.\n\n"
        content += f"    🔧 **Come fare**:\n"
        content += f"    1. Vai alla configurazione SouthTech\n"
        content += f"    2. Modifica questa luce\n"
        content += f"    3. Aggiungi un sensore luminosità\n"
        content += f"    4. Rigenera la dashboard\n"
        content += f"  style: |\n"
        content += f"    ha-card {{\n"
        content += f"      text-align: center;\n"
        content += f"      padding: 40px 20px;\n"
        content += f"      background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);\n"
        content += f"      border: 2px dashed #e17055;\n"
        content += f"      color: #2d3436;\n"
        content += f"      font-size: 16px;\n"
        content += f"    }}\n"
        content += f"    h3 {{\n"
        content += f"      color: #e17055;\n"
        content += f"      margin-bottom: 16px;\n"
        content += f"    }}\n\n"
        
        return content

    def create_timer_settings_card(self, base_id):
        """Crea card impostazioni timer e soglie"""
        content = f"- type: entities\n"
        content += f"  title: Timer e Soglie\n"
        content += f"  entities:\n"
        content += f"    - entity: input_number.{base_id}_timer_minutes_on_push\n"
        content += f"      name: Timer Accensione Push (min)\n"
        content += f"    - entity: input_number.{base_id}_timer_filter_on_push\n"
        content += f"      name: Filtro Push (min)\n"
        content += f"    - entity: input_number.{base_id}_timer_minutes_on_time\n"
        content += f"      name: Timer Accensione Oraria (min)\n"
        content += f"    - entity: input_number.{base_id}_timer_filter_on_time\n"
        content += f"      name: Filtro Orario (min)\n"
        content += f"    - entity: input_number.{base_id}_timer_seconds_max_lux\n"
        content += f"      name: Timer Max Lux (sec)\n"
        content += f"    - entity: input_number.{base_id}_min_lux_activation\n"
        content += f"      name: Lux Minimi per Attivazione\n"
        content += f"    - entity: input_number.{base_id}_max_lux_activation\n"
        content += f"      name: Lux Massimi per Attivazione\n"
        content += f"    - entity: input_number.{base_id}_turn_on_light_offset\n"
        content += f"      name: Offset Accensione Luce\n"
        content += f"    - entity: input_number.{base_id}_turn_off_light_offset\n"
        content += f"      name: Offset Spegnimento Luce\n\n"
        
        return content

    def create_automation_settings_card(self, base_id):
        """Crea card impostazioni automazione"""
        content = f"- type: entities\n"
        content += f"  title: Automazione\n"
        content += f"  entities:\n"
        content += f"    - entity: input_boolean.{base_id}_enable_automation\n"
        content += f"      name: Abilita Automazione\n"
        content += f"    - entity: input_boolean.{base_id}_enable_sensor\n"
        content += f"      name: Abilita Sensore\n"
        content += f"    - entity: input_boolean.{base_id}_enable_manual_activation_sensor\n"
        content += f"      name: Attivazione Manuale da Sensore\n"
        content += f"    - entity: input_boolean.{base_id}_enable_manual_activation_light_sensor\n"
        content += f"      name: Attivazione Manuale da Luce\n"
        content += f"    - entity: input_boolean.{base_id}_enable_illuminance_filter\n"
        content += f"      name: Filtro Illuminamento\n"
        content += f"    - entity: input_boolean.{base_id}_enable_illuminance_automation\n"
        content += f"      name: Automazione Illuminamento\n"
        content += f"    - entity: input_select.{base_id}_automatic_enable_automation\n"
        content += f"      name: Modalità Automazione\n"
        content += f"    - entity: input_select.{base_id}_light_sensor_config\n"
        content += f"      name: Configurazione Sensore Luce\n\n"
        
        return content

    def log_complete_save_operation(self, method_type, configurations, success, error=None):
        """Log dettagliato dell'operazione di salvataggio completo"""
        try:
            operation_id = f"complete_save_{int(time.time())}"
            timestamp = datetime.now().isoformat()
            
            log_data = {
                "operation_id": operation_id,
                "method": method_type,
                "timestamp": timestamp,
                "success": success,
                "configurations_count": len(configurations),
                "configurations_processed": [cfg.get('light_entity', 'unknown') for cfg in configurations],
                "error": error
            }
            
            if success:
                self.log(f"✅ COMPLETE SAVE LOG: {operation_id} - Successo via {method_type}")
                self.log(f"📊 Configurazioni processate: {len(configurations)}")
            else:
                self.error(f"❌ COMPLETE SAVE LOG: {operation_id} - Fallito via {method_type}: {error}")
            
            # Salva log in sensore dedicato
            try:
                current_state = self.get_state("sensor.southtech_complete_save_log", attribute="all")
                if current_state and "attributes" in current_state:
                    existing_attrs = current_state["attributes"]
                    existing_attrs.update(log_data)
                    log_data = existing_attrs
                
                self.set_state("sensor.southtech_complete_save_log",
                              state="completed" if success else "failed",
                              attributes=log_data)
                              
            except Exception as e:
                self.error(f"Errore aggiornamento log sensor: {e}")
                
        except Exception as e:
            self.error(f"Errore logging operazione completa: {e}")

    # Aggiungi questo metodo alla classe SouthTechConfigurator per test diagnostici

    def test_configuration_yaml_update_step_by_step(self):
        """
        🧪 Test passo-passo per diagnosticare problemi configuration.yaml
        Chiamalo durante l'inizializzazione per vedere dove si blocca
        """
        self.log("🧪 === TEST DIAGNOSTICO CONFIGURATION.YAML ===")
        
        test_results = {
            "step1_file_exists": False,
            "step2_file_readable": False, 
            "step3_file_writable": False,
            "step4_yaml_valid": False,
            "step5_section_generation": False,
            "step6_merge_test": False,
            "step7_yaml_validation": False,
            "step8_write_test": False,
            "errors": []
        }
        
        try:
            # STEP 1: Verifica esistenza file
            self.log("🧪 STEP 1: Verifica esistenza file...")
            if os.path.exists(self.configuration_yaml_path):
                test_results["step1_file_exists"] = True
                self.log(f"✅ STEP 1: File esiste - {self.configuration_yaml_path}")
            else:
                test_results["errors"].append(f"STEP 1: File non esiste - {self.configuration_yaml_path}")
                self.log(f"❌ STEP 1: File NON esiste - {self.configuration_yaml_path}")
                return test_results
            
            # STEP 2: Test lettura
            self.log("🧪 STEP 2: Test lettura file...")
            try:
                with open(self.configuration_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                test_results["step2_file_readable"] = True
                self.log(f"✅ STEP 2: File leggibile - {len(existing_content)} caratteri")
            except Exception as read_error:
                test_results["errors"].append(f"STEP 2: Errore lettura - {read_error}")
                self.log(f"❌ STEP 2: Errore lettura - {read_error}")
                return test_results
            
            # STEP 3: Test scrittura
            self.log("🧪 STEP 3: Test permessi scrittura...")
            try:
                test_file = f"{self.configuration_yaml_path}.test_write"
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write("# Test scrittura SouthTech\n")
                os.remove(test_file)
                test_results["step3_file_writable"] = True
                self.log("✅ STEP 3: File scrivibile")
            except Exception as write_error:
                test_results["errors"].append(f"STEP 3: Errore scrittura - {write_error}")
                self.log(f"❌ STEP 3: Errore scrittura - {write_error}")
                return test_results
            
            # STEP 4: Test validazione YAML esistente
            self.log("🧪 STEP 4: Test validazione YAML esistente...")
            try:
                import yaml
                existing_parsed = yaml.safe_load(existing_content)
                if existing_parsed is not None:
                    test_results["step4_yaml_valid"] = True
                    self.log(f"✅ STEP 4: YAML esistente valido - {len(existing_parsed)} sezioni")
                else:
                    test_results["errors"].append("STEP 4: YAML esistente risulta vuoto")
                    self.log("❌ STEP 4: YAML esistente risulta vuoto")
            except yaml.YAMLError as yaml_error:
                test_results["errors"].append(f"STEP 4: YAML esistente non valido - {yaml_error}")
                self.log(f"❌ STEP 4: YAML esistente non valido - {yaml_error}")
                return test_results
            
            # STEP 5: Test generazione sezione dashboard
            self.log("🧪 STEP 5: Test generazione sezione dashboard...")
            try:
                dashboard_section = self.create_dashboards_section(mode="complete")
                if dashboard_section and len(dashboard_section) > 100:
                    test_results["step5_section_generation"] = True
                    self.log(f"✅ STEP 5: Sezione dashboard generata - {len(dashboard_section)} caratteri")
                else:
                    test_results["errors"].append("STEP 5: Sezione dashboard vuota o troppo corta")
                    self.log("❌ STEP 5: Sezione dashboard vuota o troppo corta")
                    return test_results
            except Exception as section_error:
                test_results["errors"].append(f"STEP 5: Errore generazione sezione - {section_error}")
                self.log(f"❌ STEP 5: Errore generazione sezione - {section_error}")
                return test_results
            
            # STEP 6: Test merge
            self.log("🧪 STEP 6: Test merge contenuto...")
            try:
                merged_content = self.merge_configuration_content(existing_content, dashboard_section)
                if merged_content and len(merged_content) > len(existing_content):
                    test_results["step6_merge_test"] = True
                    self.log(f"✅ STEP 6: Merge completato - da {len(existing_content)} a {len(merged_content)} caratteri")
                else:
                    test_results["errors"].append("STEP 6: Merge non ha aggiunto contenuto")
                    self.log("❌ STEP 6: Merge non ha aggiunto contenuto")
                    return test_results
            except Exception as merge_error:
                test_results["errors"].append(f"STEP 6: Errore merge - {merge_error}")
                self.log(f"❌ STEP 6: Errore merge - {merge_error}")
                return test_results
            
            # STEP 7: Test validazione YAML finale
            self.log("🧪 STEP 7: Test validazione YAML finale...")
            try:
                final_parsed = yaml.safe_load(merged_content)
                if final_parsed is not None:
                    # Verifica presenza sezione lovelace
                    if isinstance(final_parsed, dict) and 'lovelace' in final_parsed:
                        test_results["step7_yaml_validation"] = True
                        self.log("✅ STEP 7: YAML finale valido con sezione lovelace")
                    else:
                        test_results["errors"].append("STEP 7: YAML finale senza sezione lovelace")
                        self.log("❌ STEP 7: YAML finale senza sezione lovelace")
                else:
                    test_results["errors"].append("STEP 7: YAML finale risulta vuoto")
                    self.log("❌ STEP 7: YAML finale risulta vuoto")
                    return test_results
            except yaml.YAMLError as yaml_final_error:
                test_results["errors"].append(f"STEP 7: YAML finale non valido - {yaml_final_error}")
                self.log(f"❌ STEP 7: YAML finale non valido - {yaml_final_error}")
                return test_results
            
            # STEP 8: Test scrittura simulata
            self.log("🧪 STEP 8: Test scrittura simulata...")
            try:
                test_write_file = f"{self.configuration_yaml_path}.test_final"
                with open(test_write_file, 'w', encoding='utf-8') as f:
                    f.write(merged_content)
                
                # Verifica file scritto
                with open(test_write_file, 'r', encoding='utf-8') as f:
                    verify_content = f.read()
                
                if verify_content == merged_content:
                    test_results["step8_write_test"] = True
                    self.log("✅ STEP 8: Scrittura simulata completata")
                    os.remove(test_write_file)
                else:
                    test_results["errors"].append("STEP 8: Contenuto scritto non corrisponde")
                    self.log("❌ STEP 8: Contenuto scritto non corrisponde")
                    
            except Exception as write_test_error:
                test_results["errors"].append(f"STEP 8: Errore scrittura simulata - {write_test_error}")
                self.log(f"❌ STEP 8: Errore scrittura simulata - {write_test_error}")
                return test_results
            
            # Riepilogo finale
            success_count = sum(1 for key, value in test_results.items() 
                              if key.startswith('step') and value)
            total_steps = len([key for key in test_results.keys() if key.startswith('step')])
            
            self.log(f"🧪 === TEST COMPLETATO: {success_count}/{total_steps} step superati ===")
            
            if success_count == total_steps:
                self.log("✅ TUTTI I TEST SUPERATI - Configuration.yaml dovrebbe funzionare")
            else:
                self.log("❌ ALCUNI TEST FALLITI - Controlla gli errori sopra")
                for error in test_results["errors"]:
                    self.log(f"   🔴 {error}")
            
            return test_results
            
        except Exception as e:
            self.error(f"❌ Errore critico durante test diagnostico: {e}")
            import traceback
            self.error(f"Stack trace test: {traceback.format_exc()}")
            test_results["errors"].append(f"Errore critico: {e}")
            return test_results

    # === NUOVO SISTEMA BACKUP STRUTTURATO ===
    def create_structured_backup(self, backup_type="single", files_to_backup=None):
        """
        🎯 SISTEMA BACKUP STRUTTURATO
        Crea backup in cartelle timestamp con rotazione automatica
        
        Args:
            backup_type: "single" o "complete"
            files_to_backup: Lista di file da backuppare (per backup singoli)
        
        Returns:
            dict: Risultato operazione backup
        """
        try:
            self.log(f"📦 === INIZIO BACKUP STRUTTURATO ({backup_type.upper()}) ===")
            
            # 1. Genera timestamp cartella
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder_name = f"backup_{timestamp}"
            backup_folder_path = os.path.join(self.backup_path, backup_folder_name)
            
            self.log(f"📁 Cartella backup: {backup_folder_name}")
            
            # 2. Crea cartella backup
            os.makedirs(backup_folder_path, exist_ok=True)
            
            # 3. Determina file da backuppare
            backup_files = self.determine_backup_files(backup_type, files_to_backup)
            
            if not backup_files:
                self.log("⚠️ Nessun file da backuppare trovato")
                return {
                    "success": True,
                    "backup_folder": backup_folder_name,
                    "files_backed_up": 0,
                    "message": "Nessun file esistente da backuppare"
                }
            
            # 4. Esegui backup dei file
            backup_results = self.backup_files_to_folder(backup_files, backup_folder_path)
            
            # 5. Rotazione cartelle (mantieni solo 5)
            self.rotate_backup_folders()
            
            # 6. Risultato finale
            successful_backups = sum(1 for result in backup_results if result["success"])
            total_files = len(backup_results)
            
            result = {
                "success": successful_backups > 0,
                "backup_folder": backup_folder_name,
                "backup_path": backup_folder_path,
                "files_backed_up": successful_backups,
                "files_total": total_files,
                "backup_type": backup_type,
                "timestamp": timestamp,
                "details": backup_results
            }
            
            if successful_backups == total_files:
                self.log(f"✅ BACKUP COMPLETATO: {successful_backups}/{total_files} file salvati in {backup_folder_name}")
            elif successful_backups > 0:
                self.log(f"⚠️ BACKUP PARZIALE: {successful_backups}/{total_files} file salvati in {backup_folder_name}")
            else:
                self.error(f"❌ BACKUP FALLITO: 0/{total_files} file salvati")
            
            return result
            
        except Exception as e:
            self.error(f"❌ Errore critico backup strutturato: {e}")
            return {
                "success": False,
                "error": str(e),
                "backup_type": backup_type
            }

    def determine_backup_files(self, backup_type, files_to_backup=None):
        """
        🎯 Determina quali file backuppare in base al tipo operazione
        
        Returns:
            list: Lista di dict con path e nome file
        """
        try:
            backup_files = []
            
            if backup_type == "complete":
                # Backup completo - tutti i file potenziali
                potential_files = [
                    {
                        "source_path": self.apps_yaml_path,
                        "backup_name": "apps.bkp",
                        "type": "apps_yaml"
                    },
                    {
                        "source_path": self.templates_file,
                        "backup_name": "templates.bkp", 
                        "type": "templates"
                    },
                    {
                        "source_path": self.configuration_yaml_path,
                        "backup_name": "configuration.bkp",
                        "type": "configuration"
                    },
                    {
                        "source_path": os.path.join(self.dashboard_path, "ui-lovelace-light-presence.yaml"),
                        "backup_name": "ui-lovelace-light-presence.bkp",
                        "type": "main_dashboard"
                    }
                ]
                
                # Aggiungi file light_config esistenti
                if os.path.exists(self.light_configs_path):
                    for filename in os.listdir(self.light_configs_path):
                        if filename.endswith('.yaml'):
                            base_name = filename.replace('.yaml', '.bkp')
                            potential_files.append({
                                "source_path": os.path.join(self.light_configs_path, filename),
                                "backup_name": base_name,
                                "type": "light_config"
                            })
                
            elif backup_type == "single" and files_to_backup:
                # Backup singolo - solo file specificati
                potential_files = files_to_backup
                
            else:
                potential_files = []
            
            # Filtra solo file esistenti
            for file_info in potential_files:
                if os.path.exists(file_info["source_path"]):
                    backup_files.append(file_info)
                    self.log(f"📄 File da backuppare: {file_info['backup_name']}")
                else:
                    self.log(f"⚠️ File non esistente saltato: {file_info['source_path']}")
            
            self.log(f"📊 File selezionati per backup: {len(backup_files)}")
            return backup_files
            
        except Exception as e:
            self.error(f"Errore determinazione file backup: {e}")
            return []

    def backup_files_to_folder(self, backup_files, backup_folder_path):
        """
        🎯 Esegue il backup fisico dei file nella cartella
        
        Returns:
            list: Risultati backup per ogni file
        """
        results = []
        
        for file_info in backup_files:
            try:
                source_path = file_info["source_path"]
                backup_name = file_info["backup_name"]
                file_type = file_info.get("type", "unknown")
                
                backup_file_path = os.path.join(backup_folder_path, backup_name)
                
                # Copia file
                shutil.copy2(source_path, backup_file_path)
                
                # Verifica backup
                if os.path.exists(backup_file_path):
                    source_size = os.path.getsize(source_path)
                    backup_size = os.path.getsize(backup_file_path)
                    
                    if source_size == backup_size:
                        results.append({
                            "success": True,
                            "file": backup_name,
                            "type": file_type,
                            "size": backup_size,
                            "source": source_path
                        })
                        self.log(f"✅ Backup {backup_name}: {backup_size} bytes")
                    else:
                        raise Exception(f"Dimensione non corrisponde: {source_size} vs {backup_size}")
                else:
                    raise Exception("File backup non creato")
                    
            except Exception as e:
                self.error(f"❌ Errore backup {file_info['backup_name']}: {e}")
                results.append({
                    "success": False,
                    "file": file_info["backup_name"],
                    "type": file_info.get("type", "unknown"),
                    "error": str(e),
                    "source": file_info["source_path"]
                })
        
        return results

    def rotate_backup_folders(self):
        """
        🎯 ROTAZIONE BACKUP: Mantiene solo le ultime 5 cartelle
        """
        try:
            if not os.path.exists(self.backup_path):
                return
            
            # Lista cartelle backup
            backup_folders = []
            for item in os.listdir(self.backup_path):
                item_path = os.path.join(self.backup_path, item)
                if os.path.isdir(item_path) and item.startswith("backup_"):
                    try:
                        # Estrai timestamp dal nome
                        timestamp_str = item.replace("backup_", "")
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        backup_folders.append({
                            "name": item,
                            "path": item_path,
                            "timestamp": timestamp
                        })
                    except ValueError:
                        # Nome non conforme, salta
                        self.log(f"⚠️ Cartella backup nome non conforme saltata: {item}")
                        continue
            
            # Ordina per timestamp (più recenti prima)
            backup_folders.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Rimuovi cartelle oltre il limite (5)
            folders_to_remove = backup_folders[5:]  # Mantieni prime 5, rimuovi resto
            
            for folder_info in folders_to_remove:
                try:
                    shutil.rmtree(folder_info["path"])
                    self.log(f"🗑️ Rimossa cartella backup vecchia: {folder_info['name']}")
                except Exception as e:
                    self.error(f"❌ Errore rimozione cartella {folder_info['name']}: {e}")
            
            remaining_count = len(backup_folders) - len(folders_to_remove)
            self.log(f"📊 Rotazione backup: {remaining_count} cartelle mantenute, {len(folders_to_remove)} rimosse")
            
        except Exception as e:
            self.error(f"Errore rotazione backup: {e}")
