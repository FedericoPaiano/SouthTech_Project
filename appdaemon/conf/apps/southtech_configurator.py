import appdaemon.plugins.hass.hassapi as hass
import yaml
import os
import re
import json
import hashlib
import secrets
import time
import threading
from datetime import datetime, timedelta
import shutil
from contextlib import contextmanager
from southtech_configurator_devices import DeviceConfigurationParser

class SouthTechConfigurator(hass.Hass):
    """
    🎯 SOUTHTECH CONFIGURATOR - CLASSE PRINCIPALE
    Coordina tutte le operazioni e gestisce l'inizializzazione del sistema
    """
    
    def initialize(self):
        """Inizializzazione principale del sistema SouthTech"""
        self.log("🚀 SouthTech Configurator inizializzato - Versione Modulare 4.0.0")
        
        # ===============================================================
        # VARIABILI DI ISTANZA CENTRALIZZATE
        # ===============================================================
        
        # Path dei file - CORRETTI per Home Assistant OS con AppDaemon addon
        # ✅ MODIFICA: Rendi i percorsi base configurabili in apps.yaml per maggiore flessibilità
        self.apps_yaml_path = self.args.get("apps_yaml_path", "/homeassistant/appdaemon/apps/apps.yaml")
        self.www_base_path = self.args.get("www_base_path", "/homeassistant/www")
        
        self.www_path = os.path.join(self.www_base_path, "southtech")
        self.auth_file = os.path.join(self.www_path, "json", "auth.json")
        self.backup_path = os.path.join(self.www_path, "backups")
        self.security_file = os.path.join(self.www_path, "json", "security.json")
        
        # File per comunicazione con il frontend
        self.api_path = os.path.join(self.www_path, "api")
        
        # Path aggiuntivi per dashboard e templates
        self.esphome_hardware_path = self.args.get("esphome_hardware_path", "/homeassistant/esphome/hardware")
        self.dashboard_path = os.path.join(self.www_path, "dashboards")
        self.lights_config_path = os.path.join(self.dashboard_path, "lights_config")
        self.templates_file = os.path.join(self.www_base_path, "configurations/templates.yaml")
        self.configuration_yaml_path = "/homeassistant/configuration.yaml"
        
        # Marcatori per il file YAML - Supporto doppio formato
        self.start_marker = "# START CONTROLLO LUCI AUTOMATICHE"
        self.end_marker = "# END CONTROLLO LUCI AUTOMATICHE"
        # Nuovo formato con bordi
        self.new_start_marker = "################################################################################"
        self.new_start_line = "#                      START CONTROLLO LUCI AUTOMATICHE                        #"
        self.new_end_line = "#                      END CONTROLLO LUCI AUTOMATICHE                          #"
        self.new_end_marker = "################################################################################"
        
        # Marcatori per templates.yaml
        self.templates_start_marker = "################################################################################"
        self.templates_start_line = "#                    START SENSORI TEMPLATE LUCI AUTOMATICHE                   #"
        self.templates_end_line = "#                     END SENSORI TEMPLATE LUCI AUTOMATICHE                    #"
        self.templates_end_marker = "################################################################################"
        
        # Marcatori per configuration.yaml
        self.config_start_marker = "################################################################################"
        self.config_start_line = "#                               START DASHBOARDS                                #"
        self.config_end_line = "#                                END DASHBOARDS                                 #"
        self.config_end_marker = "################################################################################"
        
        # Token attivi (in memoria)
        self.active_tokens = {}
        
        # Sistema anti-bruteforce
        self.blocked_users = {}  # {user_id: block_until_timestamp}
        self.attempt_counters = {}  # {type: count}
        
        # Inizializza last_processed
        self.last_processed = {}
        
        # Thread safety
        self._operation_lock = threading.Lock()
        
        # Stato moduli
        self.modules_ready = {
            "security": False,
            "yaml": False,
            "dashboard": False,
            "communication": False
        }
        
        # ===============================================================
        # INIZIALIZZAZIONE MODULI SPECIALIZZATI
        # ===============================================================
        
        # Importa e inizializza i moduli specializzati
        try:
            # Changed relative imports to absolute imports
            from southtech_configurator_security import SouthTechConfiguratorSecurity
            from southtech_configurator_yaml import SouthTechConfiguratorYaml
            # Corrected typo: 'soouthtech_configurator_dashboard' to 'southtech_configurator_dashboard'
            from southtech_configurator_dashboard import SouthTechConfiguratorDashboard
            from southtech_configurator_communication import SouthTechConfiguratorCommunication
            from southtech_configurator_devices import DeviceConfigurationParser  # Aggiornato import al nuovo file
            
            self.log("🔧 Inizializzazione moduli specializzati...")
            
            try:
                # 1. Security (nessuna dipendenza)
                self.security = SouthTechConfiguratorSecurity(self)
                self.modules_ready["security"] = True
                self.log("✅ Modulo Security inizializzato")
            except Exception as e:
                self.error(f"❌ Errore inizializzazione Security: {e}")
                raise
            
            try:
                # 2. YAML (dipende da security per validazioni)
                self.yaml = SouthTechConfiguratorYaml(self)
                self.modules_ready["yaml"] = True
                self.log("✅ Modulo YAML inizializzato")
            except Exception as e:
                self.error(f"❌ Errore inizializzazione YAML: {e}")
                raise
            
            try:
                # 3. Dashboard (dipende da yaml per configurazioni)
                self.dashboard = SouthTechConfiguratorDashboard(self)
                self.modules_ready["dashboard"] = True
                self.log("✅ Modulo Dashboard inizializzato")
            except Exception as e:
                self.error(f"❌ Errore inizializzazione Dashboard: {e}")
                raise
            
            try:
                # 4. Communication (dipende da tutti gli altri)
                self.communication = SouthTechConfiguratorCommunication(self)
                self.modules_ready["communication"] = True
                self.log("✅ Modulo Communication inizializzato")
            except Exception as e:
                self.error(f"❌ Errore inizializzazione Communication: {e}")
                raise
            
        except ImportError as e:
            self.error(f"❌ Errore importazione moduli: {e}")
            raise
        except Exception as e:
            self.error(f"❌ Errore inizializzazione moduli: {e}")
            raise        # ===============================================================
        # INIZIALIZZAZIONE SISTEMA
        # ===============================================================
        
        # Inizializza la struttura completa delle directory e file
        self.initialize_directory_structure()
        
        # Inizializza struttura dashboard
        self.dashboard.initialize_dashboard_structure()
        
        # Verifica integrità file
        is_valid, message = self.check_file_integrity()
        if not is_valid:
            self.log(f"⚠️ WARNING - Integrità YAML: {message}")

        # Test diagnostico all'avvio
        self.run_diagnostic_on_startup()
        
        # Carica i dati di sicurezza esistenti
        self.security.load_security_data()
        
        # Setup sistemi di comunicazione
        self.communication.setup_internal_websocket_handler()
        self.communication.setup_sensor_fallback()
        
        # Crea file di stato iniziale
        self.communication.update_auth_status_file()
        
        # Setup entità di comunicazione per fallback
        self.communication.setup_communication_entities()
        self.dashboard.setup_dashboard_debug_entities()
        
        # Registra endpoint API alla fine (dopo che tutti i metodi sono definiti)
        self.security.setup_endpoints()
        
        # ===============================================================
        # SETUP CALLBACK E TIMER PERIODICI
        # ===============================================================
        
        # Monitora richieste via sensori ogni 5 secondi (sistema fallback)
        self.run_every(self.communication.monitor_sensor_requests, "now+5", 5)

        # Monitora richieste via file ogni 3 secondi (sistema fallback)
        self.run_every(self.communication.monitor_file_requests, "now+3", 3)
        
        # Pulizia periodica
        self.run_every(self.security.cleanup_expired_tokens, "now+3600", 3600)
        self.run_every(self.security.cleanup_expired_blocks, "now+60", 60)
        
        # Pulizia backup vecchi ogni giorno
        self.run_every(self.cleanup_old_backups, "now+86400", 86400)
        
        # Controllo integrità file ogni 6 ore
        self.run_every(self.periodic_integrity_check, "now+21600", 21600)
        
        # Heartbeat per monitoraggio sistema
        self.run_every(self.system_heartbeat, "now+60", 60)
        
        # Salva dati sicurezza ogni 5 minuti
        self.run_every(self.security.save_security_data, "now+300", 300)
        
        # ===============================================================
        # LOGGING FINALE
        # ===============================================================
        
        self.log("✅ SouthTech Configurator pronto con sistema modulare!")
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
        
        # Verifica che tutti i moduli siano pronti
        if self.all_modules_ready():
            self.log("🎯 Tutti i moduli pronti - Sistema operativo!")
        else:
            self.error("❌ Alcuni moduli non sono pronti!")

    # ===============================================================
    # METODI DI COORDINAMENTO E STATO
    # ===============================================================
    
    def all_modules_ready(self):
        """Verifica che tutti i moduli siano pronti"""
        return all(self.modules_ready.values())
    
    @contextmanager
    def operation_context(self, operation_name):
        """Context manager per operazioni complesse con logging centralizzato"""
        self.log(f"🔄 Inizio operazione: {operation_name}")
        start_time = time.time()
        try:
            with self._operation_lock:
                yield
            duration = round(time.time() - start_time, 2)
            self.log(f"✅ Operazione completata: {operation_name} ({duration}s)")
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            self.error(f"❌ Operazione fallita {operation_name} ({duration}s): {e}")
            raise
    
    def execute_atomic_operation(self, operation_name, steps):
        """
        Esegue operazione atomica multi-classe con rollback
        
        Args:
            operation_name: Nome dell'operazione per logging
            steps: Lista di step da eseguire
                [
                    {
                        "class": "yaml", 
                        "method": "save_yaml", 
                        "args": [...], 
                        "rollback": "restore_backup"
                    }
                ]
        
        Returns:
            dict: Risultato operazione con results o error
        """
        with self.operation_context(f"ATOMIC_{operation_name}"):
            completed_steps = []
            try:
                for i, step in enumerate(steps):
                    self.log(f"🔧 Step {i+1}/{len(steps)}: {step['class']}.{step['method']}")
                    
                    # Ottieni riferimento alla classe
                    target_class = getattr(self, step["class"])
                    method = getattr(target_class, step["method"])
                    
                    # Esegui step
                    result = method(*step.get("args", []), **step.get("kwargs", {}))
                    completed_steps.append((step, result))
                    
                    self.log(f"✅ Step {i+1} completato")
                
                return {
                    "success": True, 
                    "results": completed_steps,
                    "operation": operation_name
                }
                
            except Exception as e:
                self.error(f"❌ Errore step {len(completed_steps)+1}: {e}")
                
                # Rollback in ordine inverso
                for step, result in reversed(completed_steps):
                    try:
                        if "rollback" in step:
                            self.log(f"🔄 Rollback: {step['class']}.{step['rollback']}")
                            target_class = getattr(self, step["class"])
                            rollback_method = getattr(target_class, step["rollback"])
                            rollback_method(result)
                    except Exception as rollback_error:
                        self.error(f"❌ Errore rollback: {rollback_error}")
                
                return {
                    "success": False,
                    "error": str(e),
                    "operation": operation_name,
                    "completed_steps": len(completed_steps)
                }
    
    def notify_configuration_change(self, change_type, data):
        """Notifica tutte le classi di cambi configurazione"""
        self.log(f"📢 Notifica cambio configurazione: {change_type}")
        
        for module_name in ["security", "yaml", "dashboard", "communication"]:
            try:
                module = getattr(self, module_name)
                if hasattr(module, "on_configuration_change"):
                    module.on_configuration_change(change_type, data)
            except Exception as e:
                self.error(f"Errore notifica cambio a {module_name}: {e}")

    # ===============================================================
    # METODI DI INIZIALIZZAZIONE E STRUTTURA
    # ===============================================================
    
    def log_system_info(self):
        """Log informazioni del sistema - VERSIONE SEMPLIFICATA"""
        try:
            info = {
                "paths": {
                    "apps_yaml": self.apps_yaml_path,
                    "www_path": self.www_path,
                    "api_path": self.api_path,
                    "backup_path": self.backup_path,
                    "dashboard_path": self.dashboard_path,
                    "esphome_hardware_path": self.esphome_hardware_path,
                    "templates_file": self.templates_file
                },
                "files": {
                    "apps_yaml": os.path.exists(self.apps_yaml_path),
                    "index_html": os.path.exists(os.path.join(self.www_path, "index.html")),
                    "light_presence_html": os.path.exists(os.path.join(self.www_path, "light_presence.html")),
                    "auth_file": os.path.exists(self.auth_file),
                    "templates_file": os.path.exists(self.templates_file)
                },
                "system": {
                    "active_tokens": len(self.active_tokens),
                    "blocked_users": len(self.blocked_users),
                    "version": "4.0.0",
                    "mode": "modular_architecture",
                    "modules_ready": self.modules_ready
                }
            }
            
            self.log(f"📊 INFO SISTEMA: {json.dumps(info, indent=2)}")
            
        except Exception as e:
            self.error(f"Errore log system info: {e}")

    def initialize_directory_structure(self):
        """Inizializza la struttura completa di directory e file necessari"""
        try:
            self.log("🏗️ Inizializzazione struttura directory...")
            self.log(f"🎯 Percorso target: {self.www_path}")
            
            # Crea le directory necessarie con gestione errori
            directories = [
                self.www_path,
                self.backup_path, 
                self.api_path,
                self.dashboard_path,
                self.esphome_hardware_path,
                self.lights_config_path,
                os.path.dirname(self.templates_file)
            ]
            
            for directory in directories:
                try:
                    if not os.path.exists(directory):
                        os.makedirs(directory, mode=0o755, exist_ok=True)
                        self.log(f"📁 Creata directory: {directory}")
                    else:
                        self.log(f"✓ Directory già esistente: {directory}")
                        
                    # Verifica permessi dopo creazione
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
            self.communication.create_initial_auth_status()
            
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

    def create_gitkeep_files(self):
        """Crea file .gitkeep per preservare le directory vuote"""
        try:
            gitkeep_dirs = [
                self.backup_path, 
                self.api_path,
                self.dashboard_path,
                self.lights_config_path,
                self.esphome_hardware_path
            ]
            
            for directory in gitkeep_dirs:
                gitkeep_file = os.path.join(directory, ".gitkeep")
                if not os.path.exists(gitkeep_file):
                    with open(gitkeep_file, 'w') as f:
                        f.write("# Questo file mantiene la directory nel repository\n")
                        f.write("# Directory per SouthTech Configurator v4.0.0\n")
                        f.write(f"# Creato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    self.log(f"📝 Creato .gitkeep in {directory}")
                    
        except Exception as e:
            self.error(f"Errore creazione .gitkeep: {e}")

    def verify_write_permissions(self):
        """Verifica i permessi di scrittura nelle directory"""
        try:
            test_dirs = [
                self.www_path, 
                self.backup_path, 
                self.api_path,
                self.dashboard_path,
                self.lights_config_path,
                self.esphome_hardware_path
            ]
            
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

    def run_diagnostic_on_startup(self):
        """Esegui test diagnostico all'avvio (solo una volta)"""
        try:
            if hasattr(self, '_diagnostic_run'):
                return  # Test già eseguito
            
            self._diagnostic_run = True
            self.log("🧪 Avvio test diagnostico configuration.yaml...")
            
            # Esegui test solo se la struttura dashboard è inizializzata
            if hasattr(self, 'configuration_yaml_path'):
                test_results = self.dashboard.test_configuration_yaml_update_step_by_step()
                
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

    # ===============================================================
    # METODI DI MONITORAGGIO E CONTROLLO
    # ===============================================================
    
    def system_heartbeat(self, kwargs):
        """Heartbeat del sistema per monitoraggio con protezione errori"""
        try:
            # Aggiorna sensore di sistema
            self.set_state("sensor.southtech_system_status",
                          state="online",
                          attributes={
                              "last_heartbeat": datetime.now().isoformat(),
                              "active_tokens": len(self.active_tokens),
                              "api_endpoints": 12,  # Aggiornato per nuova architettura
                              "fallback_modes": ["sensor", "file"],
                              "version": "4.0.0",
                              "architecture": "modular",
                              "modules_ready": self.modules_ready,
                              "yaml_format_support": "dual",
                              "websocket_service": {
                                  "handler_available": hasattr(self.communication, 'handle_websocket_save'),
                                  "service_name": "appdaemon.southtech_save_yaml",
                                  "test_mode_supported": True
                              },
                              "security_features": {
                                  "anti_bruteforce": True,
                                  "blocked_users": len(self.blocked_users),
                                  "attempt_counters": len(self.attempt_counters),
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

    def get_system_info(self):
        """Restituisce informazioni di sistema avanzate"""
        return {
            "apps_yaml_exists": os.path.exists(self.apps_yaml_path),
            "auth_configured": os.path.exists(self.auth_file),
            "backup_count": len([f for f in os.listdir(self.backup_path) 
                               if f.startswith("backup_")]) if os.path.exists(self.backup_path) else 0,
            "active_sessions": len(self.active_tokens),
            "esphome_devices": len([f for f in os.listdir(self.esphome_hardware_path) if f.endswith('.yaml')]) if os.path.exists(self.esphome_hardware_path) else 0,
            "version": "4.0.0",
            "architecture": "modular",
            "modules_ready": self.modules_ready,
            "yaml_format_support": "dual",
            "communication_modes": ["api_direct", "sensor_fallback", "file_fallback"],
            "endpoints_available": 12,
            "fallback_status": "active",
            "security": {
                "anti_bruteforce": True,
                "blocked_users": len(self.blocked_users),
                "attempt_counters": len(self.attempt_counters),
                "notifications_enabled": True
            },
            "dashboard": {
                "templates_file_exists": os.path.exists(self.templates_file),
                "dashboard_path_exists": os.path.exists(self.dashboard_path),
                "configuration_yaml_exists": os.path.exists(self.configuration_yaml_path)
            }
        }

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

    # ===============================================================
    # METODI DI BACKUP E UTILITY
    # ===============================================================
    
    def cleanup_old_backups(self, kwargs):
        """Pulisce i backup vecchi mantenendo solo gli ultimi"""
        keep_count = 10
        
        try:
            if not os.path.exists(self.backup_path):
                return
            
            # Lista tutti i file di backup legacy
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

    def create_backup(self):
        """Crea un backup del file apps.yaml (metodo legacy)"""
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

    def _get_available_device_numbers(self, request_data):
        """Scansiona la cartella hardware di ESPHome e restituisce i numeri disponibili."""
        try:
            if not os.path.exists(self.esphome_hardware_path):
                os.makedirs(self.esphome_hardware_path)
                self.log(f"Creata directory hardware ESPHome: {self.esphome_hardware_path}")
            
            pattern = re.compile(r'AION_A8R_(\d{2})\.yaml$')
            
            used_numbers = set()
            for filename in os.listdir(self.esphome_hardware_path):
                match = pattern.search(filename)
                if match:
                    used_numbers.add(int(match.group(1)))
            
            all_numbers = set(range(1, 100))
            available_numbers = sorted(list(all_numbers - used_numbers))
            
            next_number = "01"
            if available_numbers:
                next_number = f"{available_numbers[0]:02d}"

            available_numbers_str = [f"{n:02d}" for n in available_numbers]

            return {
                "success": True, 
                "available_numbers": available_numbers_str, 
                "next_number": next_number,
                "request_id": request_data.get("request_id")
            }
        except Exception as e:
            self.error(f"Errore nel calcolare i numeri di dispositivo disponibili: {e}")
            return {"success": False, "error": str(e), "request_id": request_data.get("request_id")}



    def _get_existing_devices(self, request_data):
        """Scansiona la cartella hardware di ESPHome e restituisce i dispositivi esistenti."""
        try:
            if not os.path.exists(self.esphome_hardware_path):
                self.log(f"Directory hardware ESPHome non trovata: {self.esphome_hardware_path}", level="WARNING")
                return {"success": True, "devices": [], "request_id": request_data.get("request_id")}

            # Usa il parser di configurazione dispositivi
            parser = DeviceConfigurationParser(self.esphome_hardware_path)
            devices = parser.get_all_devices()

            # Converte gli oggetti DeviceConfig in dizionari per JSON
            devices_json = []
            for device in devices:
                devices_json.append({
                    "model": device.model,
                    "number": device.number,
                    "filename": device.filename,
                    "friendly_name": device.friendly_name,
                    "configuration": device.configuration
                })

            return {"success": True, "devices": devices_json, "request_id": request_data.get("request_id")}
        except Exception as e:
            self.error(f"Errore nel leggere i dispositivi esistenti: {e}")
            return {"success": False, "error": str(e), "request_id": request_data.get("request_id")}

    def _save_esphome_device(self, request_data):
        """Salva un nuovo file di configurazione del dispositivo ESPHome."""
        try:
            filename = request_data.get("filename")
            content = request_data.get("content")
            
            if not filename or not content:
                return {"success": False, "error": "Nome file o contenuto mancante.", "request_id": request_data.get("request_id")}
                
            if not re.match(r'^AION_A8R_\d{2}\.yaml$', filename):
                return {"success": False, "error": "Nome file non valido.", "request_id": request_data.get("request_id")}
                
            file_path = os.path.join(self.esphome_hardware_path, filename)
            
            if os.path.exists(file_path):
                self.log(f"Sovrascrittura del file esistente: {filename}", level="WARNING")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.log(f"File dispositivo ESPHome salvato: {file_path}")
            return {"success": True, "message": f"File {filename} salvato con successo.", "request_id": request_data.get("request_id")}
            
        except Exception as e:
            self.error(f"Errore nel salvataggio del file dispositivo ESPHome: {e}")
            return {"success": False, "error": str(e), "request_id": request_data.get("request_id")}

    # ===============================================================
    # SISTEMA BACKUP STRUTTURATO
    # ===============================================================
    
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
                if os.path.exists(self.lights_config_path):
                    for filename in os.listdir(self.lights_config_path):
                        if filename.endswith('.yaml'):
                            base_name = filename.replace('.yaml', '.bkp')
                            potential_files.append({
                                "source_path": os.path.join(self.lights_config_path, filename),
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

    # ===============================================================
    # TERMINAZIONE E CLEANUP
    # ===============================================================
    
    def terminate(self):
        """Cleanup alla terminazione con coordinamento dei moduli"""
        try:
            self.log("🛑 SouthTech Configurator terminazione in corso...")
            
            # Termina moduli in ordine inverso di inizializzazione
            for module_name in reversed(["communication", "dashboard", "yaml", "security"]):
                try:
                    module = getattr(self, module_name, None)
                    if module and hasattr(module, "cleanup"):
                        self.log(f"🧹 Cleanup modulo {module_name}...")
                        module.cleanup()
                        self.modules_ready[module_name] = False
                except Exception as e:
                    self.error(f"Errore cleanup {module_name}: {e}")
            
            # Salva dati di sicurezza
            self.security.save_security_data()
            
            # Salva stato finale
            self.set_state("sensor.southtech_system_status",
                          state="offline", 
                          attributes={
                              "shutdown_time": datetime.now().isoformat(),
                              "final_token_count": len(self.active_tokens),
                              "final_blocked_users": len(self.blocked_users),
                              "clean_shutdown": True,
                              "architecture": "modular",
                              "modules_terminated": list(self.modules_ready.keys())
                          })
            
            # Pulisci token e contatori
            self.active_tokens.clear()
            self.blocked_users.clear()
            self.attempt_counters.clear()
            
            self.log("✅ SouthTech Configurator terminato correttamente con architettura modulare")
            
        except Exception as e:
            self.error(f"Errore durante terminazione: {e}")
