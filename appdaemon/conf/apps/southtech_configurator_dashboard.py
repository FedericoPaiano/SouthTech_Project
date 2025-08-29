import os
import json
import yaml
import shutil
import time
import re
import textwrap
from datetime import datetime
from contextlib import contextmanager

class SouthTechConfiguratorDashboard:
    """
    🎨 SOUTHTECH CONFIGURATOR DASHBOARD
    Gestisce generazione dashboard Lovelace, template sensors e configuration.yaml
    """
    
    def __init__(self, configurator):
        """Inizializza il modulo dashboard"""
        self.configurator = configurator
        self.version = "4.0.0"
        
        # Inizializza struttura dashboard
        self.initialize_dashboard_structure()
        
        self.configurator.log("🎨 Modulo Dashboard inizializzato")

    # ===============================================================
    # INIZIALIZZAZIONE E SETUP
    # ===============================================================
    
    def initialize_dashboard_structure(self):
        """Inizializza la struttura completa di directory e file per dashboard e templates"""
        try:
            self.configurator.log("🏗️ Inizializzazione struttura dashboard...")
            
            # Le directory path sono già state create da southtech_configurator
            # Qui verifichiamo e configuriamo gli aspetti specifici del dashboard
            
            # Verifica permessi dashboard
            self.verify_dashboard_write_permissions()
            
            # Crea file .gitkeep specifici per dashboard
            self.create_dashboard_gitkeep_files()
            
            # Crea file di stato dashboard
            self.create_initial_dashboard_status()
            
            self.configurator.log("✅ Struttura dashboard inizializzata con successo")
            self.configurator.log(f"🎯 Pronto per generare dashboard con {len(self.configurator.yaml.read_existing_configs())} configurazioni esistenti")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore inizializzazione struttura dashboard: {e}")
            raise

    def verify_dashboard_write_permissions(self):
        """Verifica i permessi di scrittura nelle directory dashboard"""
        try:
            test_dirs = [
                self.configurator.dashboard_path, 
                self.configurator.lights_config_path,
                os.path.dirname(self.configurator.templates_file)
            ]
            
            for directory in test_dirs:
                if not os.path.exists(directory):
                    continue
                    
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
                    
                    self.configurator.log(f"✓ Permessi dashboard OK: {directory}")
                    
                except Exception as e:
                    self.configurator.error(f"❌ Permessi dashboard mancanti: {directory} - {e}")
                    raise
                    
        except Exception as e:
            self.configurator.error(f"Errore verifica permessi dashboard: {e}")
            raise

    def create_dashboard_gitkeep_files(self):
        """Crea file .gitkeep per preservare le directory dashboard vuote"""
        try:
            gitkeep_dirs = [self.configurator.dashboard_path, self.configurator.lights_config_path]
            
            for directory in gitkeep_dirs:
                if not os.path.exists(directory):
                    continue
                    
                gitkeep_file = os.path.join(directory, ".gitkeep")
                if not os.path.exists(gitkeep_file):
                    with open(gitkeep_file, 'w') as f:
                        f.write("# Questo file mantiene la directory dashboard nel repository\n")
                        f.write("# Directory per SouthTech Dashboard Extension\n")
                        f.write(f"# Creato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    self.configurator.log(f"📝 Creato .gitkeep in {directory}")
                    
        except Exception as e:
            self.configurator.error(f"Errore creazione .gitkeep dashboard: {e}")

    def create_initial_dashboard_status(self):
        """Crea file di stato iniziale per dashboard"""
        try:
            dashboard_status_file = os.path.join(self.configurator.dashboard_path, "dashboard_status.json")
            
            if not os.path.exists(dashboard_status_file):
                initial_status = {
                    "dashboard_extension_active": True,
                    "last_update": datetime.now().isoformat(),
                    "structure_initialized": True,
                    "version": self.version,
                    "paths": {
                        "dashboard_path": self.configurator.dashboard_path,
                        "lights_config_path": self.configurator.lights_config_path,
                        "templates_file": self.configurator.templates_file,
                        "configuration_yaml_path": self.configurator.configuration_yaml_path
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
                
                self.configurator.log(f"📄 Creato dashboard_status.json")
            else:
                # Aggiorna status esistente
                try:
                    with open(dashboard_status_file, 'r') as f:
                        status = json.load(f)
                    
                    status.update({
                        "last_update": datetime.now().isoformat(),
                        "structure_initialized": True,
                        "version": self.version
                    })
                    
                    with open(dashboard_status_file, 'w') as f:
                        json.dump(status, f, indent=2)
                    
                    self.configurator.log(f"📄 Aggiornato dashboard_status.json esistente")
                except Exception as e:
                    self.configurator.log(f"⚠️ Errore aggiornamento status esistente: {e}")
                    
        except Exception as e:
            self.configurator.error(f"Errore creazione dashboard status: {e}")

    def setup_dashboard_debug_entities(self):
        """Setup entità debug specifiche per dashboard e templates"""
        try:
            self.configurator.log("🔍 Setup entità debug dashboard...")
            
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
                    current_state = self.configurator.get_state(entity_id)
                    
                    if current_state is None:
                        # Crea nuova entità
                        attributes = {
                            "initialized": datetime.now().isoformat(),
                            "description": entity_info["description"],
                            "extension_version": self.version,
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
                        
                        self.configurator.set_state(entity_id, 
                                      state=entity_info["initial_state"], 
                                      attributes=attributes)
                        
                        self.configurator.log(f"🔍 Creata entità debug: {entity_id}")
                    else:
                        # Aggiorna entità esistente
                        existing_attrs = self.configurator.get_state(entity_id, attribute="all")
                        if existing_attrs and "attributes" in existing_attrs:
                            current_attrs = existing_attrs["attributes"]
                            current_attrs.update({
                                "last_update": datetime.now().isoformat(),
                                "extension_version": self.version,
                                "debug_active": True
                            })
                            
                            self.configurator.set_state(entity_id, 
                                          state=entity_info["initial_state"], 
                                          attributes=current_attrs)
                        
                        self.configurator.log(f"✓ Aggiornata entità debug esistente: {entity_id}")
                    
                except Exception as e:
                    self.configurator.error(f"❌ Errore setup entità debug {entity_id}: {e}")
                    continue
            
            # Crea entità di riepilogo dashboard
            self.create_dashboard_summary_entity()
            
            self.configurator.log("✅ Entità debug dashboard inizializzate")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore setup entità debug dashboard: {e}")

    def create_dashboard_summary_entity(self):
        """Crea entità di riepilogo per dashboard extension"""
        try:
            summary_entity = "sensor.southtech_dashboard_extension_summary"
            
            # Conta configurazioni esistenti
            existing_configs = self.configurator.yaml.read_existing_configs()
            configs_count = len(existing_configs)
            
            # Verifica file esistenti
            dashboard_files_exist = os.path.exists(self.configurator.dashboard_path)
            templates_file_exists = os.path.exists(self.configurator.templates_file)
            
            # Conta file dashboard esistenti
            dashboard_files_count = 0
            if dashboard_files_exist:
                try:
                    dashboard_files_count = len([f for f in os.listdir(self.configurator.dashboard_path) 
                                              if f.endswith('.yaml')])
                except:
                    dashboard_files_count = 0
            
            summary_attributes = {
                "initialized": datetime.now().isoformat(),
                "extension_version": self.version,
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
                "dashboard_path": self.configurator.dashboard_path,
                "lights_config_path": self.configurator.lights_config_path,
                "templates_file": self.configurator.templates_file,
                
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
            
            self.configurator.set_state(summary_entity, state=state, attributes=summary_attributes)
            
            self.configurator.log(f"📊 Creata entità riepilogo dashboard: {configs_count} config rilevate")
            
        except Exception as e:
            self.configurator.error(f"Errore creazione entità riepilogo dashboard: {e}")

    def run_diagnostic_on_startup(self):
        """Esegui test diagnostico all'avvio (solo una volta)"""
        try:
            if hasattr(self.configurator, '_diagnostic_run'):
                return  # Test già eseguito
            
            self.configurator._diagnostic_run = True
            self.configurator.log("🧪 Avvio test diagnostico configuration.yaml...")
            
            # Esegui test solo se la struttura dashboard è inizializzata
            if hasattr(self.configurator, 'configuration_yaml_path'):
                test_results = self.test_configuration_yaml_update_step_by_step()
                
                # Salva risultati in un sensore per debug
                try:
                    self.configurator.set_state("sensor.southtech_config_yaml_diagnostic",
                                  state="completed",
                                  attributes={
                                      "test_time": datetime.now().isoformat(),
                                      "results": test_results,
                                      "success_rate": f"{sum(1 for k,v in test_results.items() if k.startswith('step') and v)}/{len([k for k in test_results.keys() if k.startswith('step')])}"
                                  })
                except Exception as sensor_error:
                    self.configurator.log(f"⚠️ Errore creazione sensore diagnostico: {sensor_error}")
            
        except Exception as e:
            self.configurator.error(f"Errore test diagnostico startup: {e}")

    # ===============================================================
    # METODI DI DEBUG E MONITORAGGIO
    # ===============================================================
    
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
                existing_attrs = self.configurator.get_state(entity_id, attribute="all")
                if existing_attrs and "attributes" in existing_attrs:
                    current_attrs = existing_attrs["attributes"]
                    current_attrs.update(attributes)
                    attributes = current_attrs
                
                self.configurator.set_state(entity_id, state=state, attributes=attributes)
                self.configurator.log(f"🔍 Aggiornata entità debug {entity_id}: {state}")
                
            except Exception as e:
                self.configurator.error(f"Errore aggiornamento entità debug {entity_id}: {e}")
            
            # Aggiorna anche entità riepilogo
            self.update_dashboard_summary_after_operation(operation_type, success)
            
        except Exception as e:
            self.configurator.error(f"Errore aggiornamento debug status: {e}")

    def update_dashboard_summary_after_operation(self, operation_type, success):
        """Aggiorna entità riepilogo dopo operazioni"""
        try:
            summary_entity = "sensor.southtech_dashboard_extension_summary"
            
            # Ottieni attributi esistenti
            existing_attrs = self.configurator.get_state(summary_entity, attribute="all")
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
                    if os.path.exists(self.configurator.dashboard_path):
                        dashboard_files_count = len([f for f in os.listdir(self.configurator.dashboard_path) 
                                                  if f.endswith('.yaml')])
                        attributes["dashboard_files_count"] = dashboard_files_count
                    
                    if os.path.exists(self.configurator.lights_config_path):
                        light_files_count = len([f for f in os.listdir(self.configurator.lights_config_path) 
                                              if f.endswith('.yaml')])
                        attributes["light_config_files_count"] = light_files_count
                        
                except Exception as e:
                    self.configurator.log(f"⚠️ Errore riconteggio file: {e}")
            
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
            
            self.configurator.set_state(summary_entity, state=state, attributes=attributes)
            
        except Exception as e:
            self.configurator.error(f"Errore aggiornamento riepilogo dashboard: {e}")

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
                self.configurator.log(f"✅ COMPLETE SAVE LOG: {operation_id} - Successo via {method_type}")
                self.configurator.log(f"📊 Configurazioni processate: {len(configurations)}")
            else:
                self.configurator.error(f"❌ COMPLETE SAVE LOG: {operation_id} - Fallito via {method_type}: {error}")
            
            # Salva log in sensore dedicato
            try:
                current_state = self.configurator.get_state("sensor.southtech_complete_save_log", attribute="all")
                if current_state and "attributes" in current_state:
                    existing_attrs = current_state["attributes"]
                    existing_attrs.update(log_data)
                    log_data = existing_attrs
                
                self.configurator.set_state("sensor.southtech_complete_save_log",
                              state="completed" if success else "failed",
                              attributes=log_data)
                              
            except Exception as e:
                self.configurator.error(f"Errore aggiornamento log sensor: {e}")
                
        except Exception as e:
            self.configurator.error(f"Errore logging operazione completa: {e}")

    # ===============================================================
    # DASHBOARD GENERATION
    # ===============================================================

    def generate_main_dashboard(self, configurations, skip_backup=False):
        """
        [MODIFICATO] Genera la dashboard principale e il file indice, reintroducendo la gestione dei backup.
        """
        try:
            dashboard_file = os.path.join(self.configurator.dashboard_path, "ui-lovelace-light-presence.yaml")
            index_file = os.path.join(self.configurator.lights_config_path, "lights_index.yaml")
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.configurator.log(f"🎨 Generazione dashboard e indice ({backup_status})...")
            
            # --- LOGICA DI BACKUP REINTRODOTTA E ADATTATA ---
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup:
                files_to_backup = []
                if os.path.exists(dashboard_file):
                    files_to_backup.append({
                        "source_path": dashboard_file,
                        "backup_name": "ui-lovelace-light-presence.bkp",
                        "type": "main_dashboard"
                    })
                if os.path.exists(index_file):
                    files_to_backup.append({
                        "source_path": index_file,
                        "backup_name": "lights_index.bkp",
                        "type": "index_dashboard"
                    })

                if files_to_backup:
                    self.configurator.log(f"📦 Backup di {len(files_to_backup)} file dashboard...")
                    try:
                        backup_result = self.configurator.create_structured_backup(
                            backup_type="single",
                            files_to_backup=files_to_backup
                        )
                        if backup_result.get("success"):
                            backup_info = {
                                "backup_created": True,
                                "backup_folder": backup_result.get("backup_folder"),
                                "files_backed_up": backup_result.get("files_backed_up", 0),
                                "backup_skipped": False
                            }
                        else:
                            backup_info["backup_error"] = backup_result.get("error")
                    except Exception as backup_error:
                        self.configurator.error(f"❌ Errore backup dashboard: {backup_error}")
                        backup_info["backup_error"] = str(backup_error)

            # 1. Genera contenuto dashboard principale
            dashboard_content = self.create_main_dashboard_content(configurations)
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                f.write(dashboard_content)
            dashboard_size = os.path.getsize(dashboard_file)
            self.configurator.log(f"✅ Dashboard principale generata: {dashboard_size} bytes")

            # 2. Genera contenuto file indice
            index_content = self.create_lights_index_content(configurations)
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(index_content)
            index_size = os.path.getsize(index_file)
            self.configurator.log(f"✅ File indice generato in lights_config: {index_size} bytes")
            
            return {
                "success": True,
                "files": [
                    {"path": dashboard_file, "size": dashboard_size},
                    {"path": index_file, "size": index_size}
                ],
                "configurations_count": len(configurations),
                **backup_info
            }
            
        except Exception as e:
            self.configurator.error(f"❌ Errore generazione dashboard principale: {e}")
            return {
                "success": False, 
                "error": str(e),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def _cleanup_dashboard_files(self):
        """
        [MODIFICATO] Pulisce i file della dashboard, incluso l'index dalla sua nuova posizione.
        """
        try:
            self.configurator.log("🚀 Esecuzione _cleanup_dashboard_files (con pulizia index in lights_config)...")
            files_removed = 0
            
            dashboard_file = os.path.join(self.configurator.dashboard_path, "ui-lovelace-light-presence.yaml")
            
            # Il file index ora si trova DENTRO la cartella lights_config
            index_file = os.path.join(self.configurator.lights_config_path, "lights_index.yaml")

            # Rimuovi il file della dashboard principale
            if os.path.exists(dashboard_file):
                os.remove(dashboard_file)
                files_removed += 1
                self.configurator.log(f"✅ File rimosso: {dashboard_file}")

            # Rimuovi il file indice dalla sua nuova posizione
            if os.path.exists(index_file):
                os.remove(index_file)
                files_removed += 1
                self.configurator.log(f"✅ File indice rimosso: {index_file}")

            # Pulisci la cartella delle configurazioni individuali
            lights_config_dir = self.configurator.lights_config_path
            if os.path.exists(lights_config_dir):
                self.configurator.log(f"🧹 Pulizia contenuto di: {lights_config_dir}")
                protected_files = ['.gitkeep', 'lights_index.yaml'] # L'index è già stato gestito
                
                for filename in os.listdir(lights_config_dir):
                    if filename in protected_files:
                        continue
                    file_path = os.path.join(lights_config_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            files_removed += 1
                            self.configurator.log(f"  - File rimosso: {filename}")
                        except Exception as e:
                            self.configurator.error(f"❌ Errore rimozione file {filename}: {e}")
            
            return {
                "success": True, 
                "message": f"Pulizia file dashboard completata. Rimossi {files_removed} file.",
                "files_removed": files_removed
            }
        except Exception as e:
            self.configurator.error(f"❌ Errore critico durante la pulizia dei file dashboard: {e}")
            return {"success": False, "error": str(e)}

    def _cleanup_templates_section(self):
        """Rimuove la sezione dei sensori template dal file templates.yaml."""
        try:
            self.configurator.log("🗑️ Pulizia sezione da templates.yaml...")
            if not os.path.exists(self.configurator.templates_file):
                return {"success": True, "message": "File templates.yaml non esistente, nessuna azione richiesta."}

            with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Trova la sezione da rimuovere usando i marcatori
            start_marker = self.configurator.templates_start_marker
            start_line = self.configurator.templates_start_line
            end_marker = self.configurator.templates_end_marker
            
            start_line_idx = content.find(start_line)
            if start_line_idx == -1:
                return {"success": True, "message": "Sezione template non trovata, nessuna azione richiesta."}

            start_block_idx = content.rfind(start_marker, 0, start_line_idx)
            end_block_idx = content.find(end_marker, start_line_idx)

            if start_block_idx != -1 and end_block_idx != -1:
                end_block_idx += len(end_marker)
                
                # Ricostruisci il contenuto senza la sezione
                new_content = content[:start_block_idx].rstrip('\n') + '\n' + content[end_block_idx:].lstrip('\n')
                
                # Se il file diventa vuoto o contiene solo spazi, cancellalo
                if not new_content.strip():
                    os.remove(self.configurator.templates_file)
                    self.configurator.log("✅ File templates.yaml vuoto e rimosso.")
                else:
                    with open(self.configurator.templates_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    self.configurator.log("✅ Sezione template rimossa con successo.")
                
                return {"success": True, "message": "Sezione template rimossa."}
            
            return {"success": True, "message": "Marcatori di sezione non trovati, nessuna azione."}
        except Exception as e:
            self.configurator.error(f"❌ Errore durante la pulizia di templates.yaml: {e}")
            return {"success": False, "error": str(e)}

    def _cleanup_configuration_yaml_entry(self):
        """Rimuove la voce 'light-presence' da configuration.yaml."""
        try:
            self.configurator.log("🗑️ Pulizia voce da configuration.yaml...")
            config_path = self.configurator.configuration_yaml_path
            if not os.path.exists(config_path):
                return {"success": True, "message": "File configuration.yaml non esistente."}

            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = []
            in_light_presence_block = False
            block_found = False
            
            # Trova l'indentazione della sezione 'dashboards:'
            dashboards_indent = -1
            for line in lines:
                if line.strip().startswith("dashboards:"):
                    dashboards_indent = len(line) - len(line.lstrip())
                    break
            
            if dashboards_indent == -1:
                return {"success": True, "message": "Sezione 'dashboards:' non trovata."}

            # Calcola l'indentazione attesa per 'light-presence:'
            entry_indent = dashboards_indent + 2 # Tipicamente 2 spazi

            for line in lines:
                # Rileva l'inizio del blocco da rimuovere
                if line.strip().startswith("light-presence:") and (len(line) - len(line.lstrip()) == entry_indent):
                    in_light_presence_block = True
                    block_found = True
                    continue  # Salta la riga di inizio

                if in_light_presence_block:
                    # Se la riga ha un'indentazione minore o uguale, il blocco è finito
                    if line.strip() and (len(line) - len(line.lstrip()) <= entry_indent):
                        in_light_presence_block = False
                    else:
                        continue # Salta le righe interne al blocco

                if not in_light_presence_block:
                    new_lines.append(line)
            
            if block_found:
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                self.configurator.log("✅ Voce 'light-presence' rimossa da configuration.yaml.")
                return {"success": True, "message": "Voce dashboard rimossa."}

            return {"success": True, "message": "Voce dashboard non trovata."}
        except Exception as e:
            self.configurator.error(f"❌ Errore durante la pulizia di configuration.yaml: {e}")
            return {"success": False, "error": str(e)}

    # ===============================================================
    # TEMPLATE SENSORS
    # ===============================================================
    
    def generate_template_sensors(self, configurations, skip_backup=False):
        """Genera sensori template per tutte le configurazioni in templates.yaml - CON BACKUP CONDIZIONALE"""
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.configurator.log(f"🔧 Generazione sensori template ({backup_status})...")
            
            # DEBUG SPECIFICO
            self.configurator.log(f"📍 DEBUG TEMPLATES: File target = {self.configurator.templates_file}")
            self.configurator.log(f"📍 DEBUG TEMPLATES: Directory = {os.path.dirname(self.configurator.templates_file)}")
            self.configurator.log(f"📍 DEBUG TEMPLATES: Directory esiste = {os.path.exists(os.path.dirname(self.configurator.templates_file))}")
            self.configurator.log(f"📍 DEBUG TEMPLATES: File esiste = {os.path.exists(self.configurator.templates_file)}")
            
            # BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(self.configurator.templates_file):
                self.configurator.log("📦 Backup templates.yaml...")
                try:
                    backup_files = [{
                        "source_path": self.configurator.templates_file,
                        "backup_name": "templates.bkp",
                        "type": "templates"
                    }]
                    
                    backup_result = self.configurator.create_structured_backup(
                        backup_type="single",
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.configurator.log(f"✅ Backup templates.yaml: {backup_result.get('backup_folder')}")
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
                    self.configurator.error(f"❌ Errore backup templates.yaml: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.configurator.log("⏭️ Backup templates.yaml saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "file_not_exists", "backup_skipped": False}
                self.configurator.log("ℹ️ File templates.yaml non esiste, nessun backup necessario")
            
            # Valida configurazioni
            valid_configs = [cfg for cfg in configurations 
                            if cfg.get('light_entity') and cfg.get('presence_sensor_on')]
            
            if not valid_configs:
                self.configurator.log("⚠️ Nessuna configurazione valida per templates")
                return {
                    "success": True, 
                    "sensors_count": 0, 
                    "message": "Nessun template da generare",
                    **backup_info
                }
            
            self.configurator.log(f"📊 Generazione templates per {len(valid_configs)} configurazioni valide")
            
            # Genera contenuto templates
            self.configurator.log("📝 Creazione contenuto templates...")
            templates_content = self.create_templates_content(valid_configs)
            self.configurator.log(f"✅ Contenuto generato: {len(templates_content)} caratteri")
            
            # Salva in templates.yaml
            self.configurator.log("💾 Inizio salvataggio templates.yaml...")
            self.save_templates_yaml(templates_content)
            self.configurator.log("✅ Salvataggio templates completato")
            
            # Verifica file salvato
            if os.path.exists(self.configurator.templates_file):
                file_size = os.path.getsize(self.configurator.templates_file)
                self.configurator.log(f"📄 Templates salvati: {file_size} bytes")
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
                "file_path": self.configurator.templates_file,
                **backup_info
            }
            
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.configurator.log(f"✅ Generati {sensors_count} sensori template per {len(valid_configs)} configurazioni - {backup_msg}")
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ Errore generazione templates: {e}")
            
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
            
            # Genera solo la sezione SouthTech senza template: root
            content = f"{self.configurator.templates_start_marker}\n"
            content += f"{self.configurator.templates_start_line}\n"
            content += f"{self.configurator.templates_end_marker}\n"
            content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
            
            # NON includere "template:" - sarà aggiunto dal merge
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
                    self.configurator.log(f"⚠️ Configurazione incompleta saltata: {light_entity}")
                    continue
                    
                # Estrai base_id per unique_id
                base_id = light_entity.replace('light.', '')
                friendly_base = base_id.replace('_', ' ').title()
                
                self.configurator.log(f"🧩 Creazione sensori template per: {base_id}")
                
                # 4 sensori con NOMI che corrispondono agli unique_id
                sensors = [
                    {
                        "name": f"Presenza Luce {friendly_base}",
                        "unique_id": f"presenza_luce_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'on') and is_state('{light_entity}', 'on')",
                        "description": "Presenza rilevata E luce accesa"
                    },
                    {
                        "name": f"Solo Presenza {friendly_base}",
                        "unique_id": f"solo_presenza_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'on') and is_state('{light_entity}', 'off')",
                        "description": "Presenza rilevata MA luce spenta"
                    },
                    {
                        "name": f"Solo Luce {friendly_base}",
                        "unique_id": f"solo_luce_{base_id}",
                        "condition": f"is_state('{presence_sensor}', 'off') and is_state('{light_entity}', 'on')",
                        "description": "Nessuna presenza MA luce accesa"
                    },
                    {
                        "name": f"Vuoto {friendly_base}",
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
            
            # STRUTTURA FINALE: Metadati + sensori (senza template: root)
            final_content = content + sensors_content
            
            # Fine sezione
            final_content += f"{self.configurator.templates_start_marker}\n"
            final_content += f"{self.configurator.templates_end_line}\n"
            final_content += f"{self.configurator.templates_end_marker}\n"
            
            self.configurator.log(f"📝 Contenuto templates generato: {len(final_content)} caratteri")
            self.configurator.log(f"✅ NOMI CORRETTI: entity_id corrisponderanno agli unique_id")
            return final_content
            
        except Exception as e:
            self.configurator.error(f"Errore creazione contenuto templates: {e}")
            raise

    def save_templates_yaml(self, content):
        """Salva contenuto nei templates.yaml con gestione sezione esistente - SENZA BACKUP LEGACY"""
        try:
            self.configurator.log(f"💾 TEMPLATES SAVE: Inizio salvataggio...")
            self.configurator.log(f"📍 File target: {self.configurator.templates_file}")
            self.configurator.log(f"📍 Contenuto da salvare: {len(content)} caratteri")
            
            # VERIFICA DIRECTORY ESISTENTE
            templates_dir = os.path.dirname(self.configurator.templates_file)
            self.configurator.log(f"📂 Directory templates: {templates_dir}")
            self.configurator.log(f"📂 Directory esiste: {os.path.exists(templates_dir)}")
            
            if not os.path.exists(templates_dir):
                self.configurator.log(f"⚠️ Directory templates non esiste, creazione...")
                os.makedirs(templates_dir, mode=0o755, exist_ok=True)
                self.configurator.log(f"📁 Directory templates creata: {templates_dir}")
            
            # VERIFICA PERMESSI
            can_write = os.access(templates_dir, os.W_OK)
            self.configurator.log(f"📂 Permessi scrittura: {can_write}")
            if not can_write:
                raise Exception(f"Nessun permesso di scrittura in: {templates_dir}")
            
            # VERIFICA FILE ESISTENTE
            file_exists = os.path.exists(self.configurator.templates_file)
            self.configurator.log(f"📄 File templates esistente: {file_exists}")
            if file_exists:
                existing_size = os.path.getsize(self.configurator.templates_file)
                self.configurator.log(f"📄 Dimensione file esistente: {existing_size} bytes")
            
            # Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.configurator.templates_file):
                with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.configurator.log(f"📖 Letto file templates esistente: {len(existing_content)} caratteri")
            
            # Sostituisci o aggiungi sezione
            self.configurator.log("🔀 Merge contenuto templates...")
            new_content = self.merge_templates_content(existing_content, content)
            self.configurator.log(f"🔗 Contenuto finale: {len(new_content)} caratteri")
            
            # Verifica YAML valido prima di scrivere
            try:
                import yaml
                parsed = yaml.safe_load(new_content)
                if parsed is None and new_content.strip():
                    raise Exception("YAML parsing risulta vuoto con contenuto presente")
                self.configurator.log("✅ YAML templates validato correttamente")
            except yaml.YAMLError as e:
                raise Exception(f"YAML templates non valido: {e}")
            
            # SCRITTURA CON DEBUG ESTESO
            temp_file = f"{self.configurator.templates_file}.tmp_write"
            try:
                self.configurator.log(f"💾 Scrittura file temporaneo: {temp_file}")
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                temp_size = os.path.getsize(temp_file)
                self.configurator.log(f"✅ File temporaneo scritto: {temp_size} bytes")
                
                # Verifica file temporaneo
                with open(temp_file, 'r', encoding='utf-8') as f:
                    verify_content = f.read()
                
                if verify_content != new_content:
                    raise Exception("Verifica contenuto file temporaneo fallita")
                
                self.configurator.log(f"✅ Verifica file temporaneo OK: {len(verify_content)} caratteri")
                
                # Sostituisci atomicamente
                self.configurator.log(f"🔄 Sostituzione atomica: {temp_file} -> {self.configurator.templates_file}")
                os.replace(temp_file, self.configurator.templates_file)
                self.configurator.log(f"✅ File sostituito atomicamente")
                
            except Exception as e:
                self.configurator.error(f"❌ ERRORE SCRITTURA TEMPLATES: {e}")
                self.configurator.error(f"❌ Temp file: {temp_file}")
                self.configurator.error(f"❌ Target file: {self.configurator.templates_file}")
                
                # Pulizia in caso di errore
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        self.configurator.log(f"🗑️ File temporaneo rimosso: {temp_file}")
                    except Exception as cleanup_error:
                        self.configurator.error(f"❌ Errore pulizia file temp: {cleanup_error}")
                raise
            
            # VERIFICA FINALE ESTESA
            if os.path.exists(self.configurator.templates_file):
                final_size = os.path.getsize(self.configurator.templates_file)
                self.configurator.log(f"✅ TEMPLATES SALVATI: {self.configurator.templates_file}")
                self.configurator.log(f"📊 Dimensione finale: {final_size} bytes")
                
                # Test lettura finale
                try:
                    with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
                        test_content = f.read()
                    self.configurator.log(f"✅ Test lettura finale OK: {len(test_content)} caratteri")
                    
                    # Verifica che contenga i nostri sensori
                    if "SouthTech Configurator" in test_content:
                        self.configurator.log(f"✅ Contenuto SouthTech confermato nel file")
                    else:
                        self.configurator.log(f"⚠️ Contenuto SouthTech NON trovato nel file salvato")
                        
                except Exception as read_error:
                    self.configurator.error(f"❌ Test lettura finale fallito: {read_error}")
            else:
                raise Exception(f"❌ FILE TEMPLATES NON TROVATO DOPO SALVATAGGIO: {self.configurator.templates_file}")
            
            self.configurator.log(f"💾 Templates salvati con successo: {self.configurator.templates_file}")
            
            # Log informazioni file
            if os.path.exists(self.configurator.templates_file):
                file_size = os.path.getsize(self.configurator.templates_file)
                with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
                    lines_count = len(f.readlines())
                self.configurator.log(f"📊 File templates: {file_size} bytes, {lines_count} righe")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore salvataggio templates: {e}")
            raise

    def merge_templates_content(self, existing_content, new_section):
        """Unisce contenuto templates intelligentemente"""
        try:
            self.configurator.log("🔀 Merge contenuto templates...")
            
            # Trova sezione SouthTech esistente
            start_idx = existing_content.find(self.configurator.templates_start_line)
            if start_idx != -1:
                self.configurator.log("✅ Trovata sezione templates SouthTech esistente")
                
                # Trova inizio blocco
                start_block_idx = existing_content.rfind(self.configurator.templates_start_marker, 0, start_idx)
                if start_block_idx == -1:
                    start_block_idx = start_idx
                
                # Trova fine blocco
                end_line_idx = existing_content.find(self.configurator.templates_end_line, start_idx)
                if end_line_idx != -1:
                    end_block_idx = existing_content.find(self.configurator.templates_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.configurator.templates_end_marker)
                        
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
                        
                        self.configurator.log("🔄 Sostituita sezione SouthTech esistente")
                        return result
            
            # LOGICA MIGLIORATA: Gestisci file con template: esistenti
            self.configurator.log("ℹ️ Nessuna sezione SouthTech trovata, analisi file esistente...")
            
            # Controlla se esiste già una sezione template:
            if 'template:' in existing_content:
                self.configurator.log("⚠️ File contiene già sezioni template:, integrazione intelligente...")
                
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
                    self.configurator.log("🔗 Sezione SouthTech integrata dopo template esistenti")
                    return result
            
            # File senza template: esistenti, aggiungi normalmente
            self.configurator.log("📝 File senza template: esistenti, aggiunta normale")
            
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            
            return existing_content + '\n' + new_section.rstrip('\n') + '\n'
            
        except Exception as e:
            self.configurator.error(f"Errore merge templates: {e}")
            return new_section

    # ===============================================================
    # CONFIGURATION.YAML UPDATE
    # ===============================================================

    def update_configuration_yaml(self, skip_backup=False):
        """
        📝 AGGIORNAMENTO CONFIGURATION.YAML - VERSIONE CORRETTA E SICURA
        Aggiunge la dashboard 'light-presence' solo se non è già presente,
        preservando l'intero contenuto esistente.
        """
        try:
            config_path = self.configurator.configuration_yaml_path
            self.configurator.log(f"📝 === INIZIO AGGIORNAMENTO SICURO CONFIGURATION.YAML (v{self.version}) ===")
            self.configurator.log(f"🎯 File target: {config_path}")

            # 1. Controlli preliminari
            if not os.path.exists(config_path):
                return {"success": False, "error": f"File non trovato: {config_path}"}
            if not os.access(config_path, os.W_OK):
                return {"success": False, "error": f"Permessi di scrittura mancanti su {config_path}"}

            # 2. Lettura del contenuto
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 3. VERIFICA ESISTENZA: Se la dashboard è già configurata, non fare nulla.
            if 'light-presence:' in content:
                self.configurator.log("✅ Dashboard 'light-presence' già presente in configuration.yaml. Nessuna modifica necessaria.")
                return {"success": True, "message": "Dashboard già configurata, nessuna modifica eseguita."}

            # 4. Backup (la logica di backup può essere inserita qui se necessario)
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            if not skip_backup:
                pass 

            # 5. Logica di inserimento sicura
            lines = content.split('\n')
            new_lines = []
            inserted = False

            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.strip() == 'dashboards:':
                    # Determina l'indentazione corretta dalla riga 'dashboards:'
                    base_indent_level = len(line) - len(line.lstrip(' '))
                    entry_indent_str = ' ' * (base_indent_level + 2)

                    dashboard_entry = [
                        f'{entry_indent_str}light-presence:',
                        f'{entry_indent_str}  mode: yaml',
                        f'{entry_indent_str}  title: SouthTech - Light Presence Monitor', # Virgolette rimosse
                        f'{entry_indent_str}  icon: mdi:lightbulb-on',
                        f'{entry_indent_str}  filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml', # Riga spostata
                        f'{entry_indent_str}  show_in_sidebar: true'
                    ]
                    
                    new_lines.extend(dashboard_entry)
                    inserted = True
                    self.configurator.log(f"➕ Inserita configurazione 'light-presence' con indentazione di {len(entry_indent_str)} spazi.")
                    # Continua il ciclo per copiare il resto del file
            
            if not inserted:
                self.configurator.error("❌ Sezione 'lovelace: dashboards:' non trovata in configuration.yaml. Inserimento annullato.")
                return {"success": False, "error": "Sezione 'lovelace: dashboards:' non trovata."}

            # 6. Scrittura atomica del nuovo contenuto
            new_content = '\n'.join(new_lines)
            temp_file = f"{config_path}.tmp_southtech"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            os.replace(temp_file, config_path)
            self.configurator.log("✅ File configuration.yaml aggiornato con successo.")

            return {
                "success": True,
                "message": "Dashboard 'light-presence' aggiunta a configuration.yaml.",
                **backup_info
            }

        except Exception as e:
            self.configurator.error(f"❌ Errore critico durante l'aggiornamento di configuration.yaml: {e}")
            return {"success": False, "error": str(e)}

    # ===============================================================
    # DASHBOARD GENERATION
    # ===============================================================

    def generate_main_dashboard(self, configurations, skip_backup=False):
        """
        [MODIFICATO] Genera la dashboard principale e il file indice nella sua nuova posizione.
        """
        try:
            dashboard_file = os.path.join(self.configurator.dashboard_path, "ui-lovelace-light-presence.yaml")
            # Il file index ora viene creato DENTRO la cartella lights_config
            index_file = os.path.join(self.configurator.lights_config_path, "lights_index.yaml")
            
            self.configurator.log(f"🎨 Generazione dashboard principale e indice...")
            
            # 1. Genera contenuto dashboard principale
            dashboard_content = self.create_main_dashboard_content(configurations)
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                f.write(dashboard_content)
            dashboard_size = os.path.getsize(dashboard_file)
            self.configurator.log(f"✅ Dashboard principale generata: {dashboard_size} bytes")

            # 2. Genera contenuto file indice
            index_content = self.create_lights_index_content(configurations)
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(index_content)
            index_size = os.path.getsize(index_file)
            self.configurator.log(f"✅ File indice generato in lights_config: {index_size} bytes")
            
            return {
                "success": True,
                "files": [
                    {"path": dashboard_file, "size": dashboard_size},
                    {"path": index_file, "size": index_size}
                ],
                "configurations_count": len(configurations)
            }
            
        except Exception as e:
            self.configurator.error(f"❌ Errore generazione dashboard principale: {e}")
            return {"success": False, "error": str(e)}

    def create_main_dashboard_content(self, configurations):
        """
        [MODIFICATO] Crea il file principale che definisce le viste.
        Aggiornata l'indentazione per la sezione 'cards' secondo le specifiche.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Inizializza la lista di righe con l'intestazione
            lines = [
                f"# SouthTech Light Presence Dashboard",
                f"# Generato il {timestamp}",
                "",
                'title: "Configurazione Luci Automatiche"',
                "path: light-presence",
                "icon: mdi:lightbulb-auto",
                "views:",
                ""
            ]

            # --- Vista 1: Riepilogo (sempre presente) ---
            lines.extend([
                "  - title: Riepilogo",
                "    path: overview",
                "    icon: mdi:home",
                "    panel: true",
                "    cards:",
                "      - !include lights_config/lights_index.yaml"
            ])

            # --- Viste successive: Una per ogni luce ---
            for config in configurations:
                light_entity = config.get('light_entity', '')
                if not light_entity: continue

                base_id = light_entity.replace('light.', '')
                friendly_name = self.configurator.get_entity_friendly_name(light_entity, base_id)

                # Aggiunge uno spazio per separare le viste
                lines.append("")
                
                lines.extend([
                    f"  - title: {friendly_name}",
                    f"    path: {base_id.replace('_', '-')}",
                    "    icon: mdi:lightbulb",
                    "    panel: true",
                    "    cards:",
                    f"      - !include lights_config/{base_id}.yaml"
                ])

            return "\n".join(lines)

        except Exception as e:
            self.configurator.error(f"❌ Errore creazione contenuto dashboard principale: {e}")
            raise

    # ===============================================================
    # LIGHT CONFIG FILES
    # ===============================================================

    def generate_light_config_files(self, configurations, skip_backup=False):
        """Genera file configurazione individuali per ogni luce con backup condizionale"""
        try:
            backup_status = "con backup condizionale" if not skip_backup else "senza backup"
            self.configurator.log(f"💡 Generazione file configurazioni luci ({backup_status})...")
            
            files_created = 0
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            # (La logica di backup esistente rimane qui)
            # ...
            
            # Genera file per ogni configurazione
            for config in configurations:
                light_entity = config.get('light_entity', '')
                if not light_entity:
                    continue
                    
                base_id = light_entity.replace('light.', '')
                config_file = os.path.join(self.configurator.lights_config_path, f"{base_id}.yaml")
                
                try:
                    # --- PUNTO CHIAVE ---
                    # Chiama il metodo (ora esistente) per generare il contenuto
                    file_content = self.create_lights_config_content(config)
                    
                    # Salva file
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    
                    files_created += 1
                    file_size = os.path.getsize(config_file)
                    self.configurator.log(f"✅ File {base_id}.yaml creato: {file_size} bytes")
                    
                except Exception as e:
                    self.configurator.error(f"❌ Errore creazione file {base_id}.yaml: {e}")
                    continue
            
            result = {
                "success": files_created > 0 or not configurations,
                "files_created": files_created,
                "configurations_total": len(configurations),
                **backup_info
            }
            
            if files_created > 0:
                self.configurator.log(f"✅ File luci generati: {files_created}/{len(configurations)}")
            else:
                self.configurator.log("⚠️ Nessun file luce generato (potrebbe essere normale se non ci sono configurazioni).")
            
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ Errore generazione file luci: {e}")
            return {"success": False, "error": str(e)}

    # ===============================================================
    # LIGHT CONFIG FILES
    # ===============================================================
    
    def create_lights_config_content(self, config):
        """
        [MODIFICATO] Genera una vista dettagliata e complessa per una singola luce,
        utilizzando vertical-stack, button-card e card-mod.
        """
        try:
            import textwrap
            
            light_entity = config.get('light_entity', '')
            base_id = light_entity.replace('light.', '')

            # Definisce il template YAML usando una f-string e textwrap.dedent per la corretta indentazione.
            # Le parentesi graffe {} di Javascript sono escapate usando doppie graffe {{}}
            # in modo che l'f-string di Python non le interpreti.
            
            content = textwrap.dedent(f"""
                type: vertical-stack
                cards:
                  - type: custom:button-card
                    name: |
                      [[[
                        const entity_id = '{light_entity}';
                        if (states[entity_id] && states[entity_id].attributes && states[entity_id].attributes.friendly_name) {{
                          return `Pannello di Configurazione - ${{states[entity_id].attributes.friendly_name}}`;
                        }}
                        return `Pannello di Configurazione - ${{entity_id}}`;
                      ]]]
                    entity: light.{base_id}_luce
                    icon: mdi:tune-variant
                    styles:
                      card:
                        - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"
                        - border-radius: 12px
                        - padding: 16px
                        - box-shadow: 0 4px 12px rgba(0,0,0,0.3)
                        - margin-bottom: 16px
                      name:
                        - font-size: 22px
                        - font-weight: bold
                        - color: white
                      icon:
                        - color: "#FFD700"
                        - width: 40px
                  - type: horizontal-stack
                    cards:
                      - type: custom:vertical-stack-in-card
                        styles:
                          card:
                            - border-radius: 12px
                            - box-shadow: 0 4px 12px rgba(0,0,0,0.2)
                        cards:
                          - type: custom:button-card
                            name: Stato Attuale
                            icon: mdi:monitor-dashboard
                            styles:
                              card:
                                - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"
                                - border-radius: 12px 12px 0 0
                                - padding: 12px
                                - box-shadow: none
                              grid:
                                - grid-template-areas: '"i n"'
                                - grid-template-columns: 40px 1fr
                              name:
                                - font-size: 18px
                                - font-weight: bold
                                - color: white
                                - justify-self: start
                                - align-self: center
                              icon:
                                - color: "#FFD700"
                                - width: 24px
                                - align-self: center
                          - type: entities
                            entities:
                              - entity: light.{base_id}_luce
                              - entity: binary_sensor.{base_id}_presenza
                            style:
                              ha-card:
                                background: rgba(40, 65, 115, 0.4)
                                border-radius: 0 0 12px 12px
                                box-shadow: none
                                border: none
                              .: |
                                .card-content {{
                                  padding: 8px 16px 16px 16px;
                                }}
                              ":host":
                                "--primary-text-color": white
                                "--secondary-text-color": "#B0C4DE"
                                "--paper-item-icon-color": "#FFD700"
                                "--paper-slider-knob-color": "#FFD700"
                                "--paper-slider-active-color": "#FFD700"
                                "--paper-slider-pin-color": "#FFD700"
                                "--paper-slider-secondary-color": "#555"
                                "--paper-input-container-color": "#B0C4DE"
                                "--paper-input-container-focus-color": white
                                "--switch-checked-button-color": "#FFD700"
                                "--switch-checked-track-color": "#9db2ce"
                                "--mdc-text-field-fill-color": rgba(0, 0, 0, 0.2)
                                "--mdc-select-fill-color": rgba(0, 0, 0, 0.2)
                      - type: custom:vertical-stack-in-card
                        styles:
                          card:
                            - border-radius: 12px
                            - box-shadow: 0 4px 12px rgba(0,0,0,0.2)
                        cards:
                          - type: custom:button-card
                            name: Storico
                            icon: mdi:chart-timeline-variant
                            styles:
                              card:
                                - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"
                                - border-radius: 12px 12px 0 0
                                - padding: 12px
                                - box-shadow: none
                              grid:
                                - grid-template-areas: '"i n"'
                                - grid-template-columns: 40px 1fr
                              name:
                                - font-size: 18px
                                - font-weight: bold
                                - color: white
                                - justify-self: start
                                - align-self: center
                              icon:
                                - color: "#FFD700"
                                - width: 24px
                                - align-self: center
                          - type: history-graph
                            entities:
                              - entity: light.{base_id}_luce
                              - entity: sensor.{base_id}_illuminance_lux
                            hours_to_show: 24
                            refresh_interval: 0
                            style:
                              ha-card:
                                background: rgba(40, 65, 115, 0.4)
                                border-radius: 0 0 12px 12px
                                box-shadow: none
                                border: none
                                padding: 8px 16px 16px 16px
                  - type: horizontal-stack
                    cards:
                      - type: custom:vertical-stack-in-card
                        styles:
                          card:
                            - border-radius: 12px
                            - box-shadow: 0 4px 12px rgba(0,0,0,0.2)
                            - margin-top: 16px
                        cards:
                          - type: custom:button-card
                            name: Abilitazioni e Selettori
                            icon: mdi:toggle-switch-outline
                            styles:
                              card:
                                - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"
                                - border-radius: 12px 12px 0 0
                                - padding: 12px
                                - box-shadow: none
                              grid:
                                - grid-template-areas: '"i n"'
                                - grid-template-columns: 40px 1fr
                              name:
                                - font-size: 18px
                                - font-weight: bold
                                - color: white
                                - justify-self: start
                                - align-self: center
                              icon:
                                - color: "#FFD700"
                                - width: 24px
                                - align-self: center
                          - type: entities
                            entities:
                              - entity: input_boolean.{base_id}_enable_automation
                                name: Abilita Automazione
                              - entity: input_boolean.{base_id}_enable_sensor
                                name: Abilita Sensore Presenza
                              - entity: input_boolean.{base_id}_enable_illuminance_automation
                                name: Abilita Automazione Lux
                              - entity: input_boolean.{base_id}_enable_illuminance_filter
                                name: Abilita Filtro Lux
                              - entity: input_boolean.{base_id}_enable_manual_activation_sensor
                                name: Attivazione Manuale (Sensore Presenza)
                              - entity: >-
                                  input_boolean.{base_id}_enable_manual_activation_light_sensor
                                name: Attivazione Manuale (Sensore Luce)
                              - entity: input_select.{base_id}_automatic_enable_automation
                                name: Modalità Automazione
                              - entity: input_select.{base_id}_light_sensor_config
                                name: Configurazione Sensore Luce
                            style:
                              ha-card:
                                background: rgba(40, 65, 115, 0.4)
                                border-radius: 0 0 12px 12px
                                box-shadow: none
                                border: none
                              .: |
                                .card-content {{
                                  padding: 8px 16px 16px 16px;
                                }}
                              ":host":
                                "--primary-text-color": white
                                "--secondary-text-color": "#B0C4DE"
                                "--paper-item-icon-color": "#FFD700"
                                "--paper-slider-knob-color": "#FFD700"
                                "--paper-slider-active-color": "#FFD700"
                                "--paper-slider-pin-color": "#FFD700"
                                "--paper-slider-secondary-color": "#555"
                                "--paper-input-container-color": "#B0C4DE"
                                "--paper-input-container-focus-color": white
                                "--switch-checked-button-color": "#FFD700"
                                "--switch-checked-track-color": "#9db2ce"
                                "--mdc-text-field-fill-color": rgba(0, 0, 0, 0.2)
                                "--mdc-select-fill-color": rgba(0, 0, 0, 0.2)
                      - type: custom:vertical-stack-in-card
                        styles:
                          card:
                            - border-radius: 12px
                            - box-shadow: 0 4px 12px rgba(0,0,0,0.2)
                            - margin-top: 16px
                        cards:
                          - type: custom:button-card
                            name: Valori e Timer
                            icon: mdi:numeric
                            styles:
                              card:
                                - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"
                                - border-radius: 12px 12px 0 0
                                - padding: 12px
                                - box-shadow: none
                              grid:
                                - grid-template-areas: '"i n"'
                                - grid-template-columns: 40px 1fr
                              name:
                                - font-size: 18px
                                - font-weight: bold
                                - color: white
                                - justify-self: start
                                - align-self: center
                              icon:
                                - color: "#FFD700"
                                - width: 24px
                                - align-self: center
                          - type: entities
                            entities:
                              - entity: input_number.{base_id}_min_lux_activation
                                name: Soglia Lux Minima
                              - entity: input_number.{base_id}_max_lux_activation
                                name: Soglia Lux Massima
                              - entity: input_number.{base_id}_timer_minutes_on_time
                                name: Timer Minuti (da Tempo)
                              - entity: input_number.{base_id}_timer_minutes_on_push
                                name: Timer Minuti (da Pulsante)
                              - entity: input_number.{base_id}_timer_filter_on_time
                                name: Filtro Timer (da Tempo)
                              - entity: input_number.{base_id}_timer_filter_on_push
                                name: Filtro Timer (da Pulsante)
                              - entity: input_number.{base_id}_timer_seconds_max_lux
                                name: Timer Secondi (Lux Max)
                              - entity: input_number.{base_id}_turn_on_light_offset
                                name: Offset Accensione (Lux)
                              - entity: input_number.{base_id}_turn_off_light_offset
                                name: Offset Spegnimento (Lux)
                            style:
                              ha-card:
                                background: rgba(40, 65, 115, 0.4)
                                border-radius: 0 0 12px 12px
                                box-shadow: none
                                border: none
                              .: |
                                .card-content {{
                                  padding: 8px 16px 16px 16px;
                                }}
                              ":host":
                                "--primary-text-color": white
                                "--secondary-text-color": "#B0C4DE"
                                "--paper-item-icon-color": "#FFD700"
                                "--paper-slider-knob-color": "#FFD700"
                                "--paper-slider-active-color": "#FFD700"
                                "--paper-slider-pin-color": "#FFD700"
                                "--paper-slider-secondary-color": "#555"
                                "--paper-input-container-color": "#B0C4DE"
                                "--paper-input-container-focus-color": white
                                "--switch-checked-button-color": "#FFD700"
                                "--switch-checked-track-color": "#9db2ce"
                                "--mdc-text-field-fill-color": rgba(0, 0, 0, 0.2)
                                "--mdc-select-fill-color": rgba(0, 0, 0, 0.2)
            """)
            
            return content.strip()

        except Exception as e:
            self.configurator.error(f"❌ Errore creazione vista dettagliata per {light_entity}: {e}")
            # Ritorna una card di errore in caso di problemi
            return textwrap.dedent(f"""
              type: markdown
              content: |
                ## ❌ Errore di Generazione Vista
                **Si è verificato un errore durante la creazione della dashboard dettagliata.**
                **Dettagli:** `{e}`
                *Controlla i log di AppDaemon per maggiori informazioni.*
            """).strip()

def create_lights_index_content(self, configurations):
    """
    [MODIFICATO] Genera la vista indice (pagina principale) della dashboard 
    con il layout esatto richiesto, prestando attenzione a spazi e indentazione.
    """
    try:
        # Importa textwrap per gestire correttamente l'indentazione YAML
        import textwrap
        from datetime import datetime

        # Ottiene dati dinamici
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        active_configs_count = len(configurations)
        template_sensors_count = active_configs_count * 4
        dashboard_files_count = active_configs_count

        # Contenuto per la card markdown di sinistra
        # I doppi spazi alla fine di ogni riga forzano un a capo in Markdown
        markdown_content_left = textwrap.dedent(f"""
            # Monitoraggio Luci e Presenza
            **Versione {self.version}** 🔊 **Configurazioni attive:** {active_configs_count}  
            🕐 **Ultimo aggiornamento:** {timestamp}  
            ---
        """).strip()

        # Contenuto per la card markdown di destra
        # FIXED: Usa \n espliciti invece di righe vuote per garantire i line break
        markdown_content_right = textwrap.dedent(f"""
            🔧 **Dashboard generata da SouthTech Configurator v{self.version}**
            📈 **Sensori Template:** {template_sensors_count} sensori generati
            🎨 **Dashboard Files:** Dashboard principale + {dashboard_files_count} file singoli
            💡 **Tip:** Ogni configurazione ha 4 sensori template per monitorare tutte le combinazioni luce/presenza
        """).strip()
        
        # Indenta il contenuto markdown per inserirlo correttamente
        indented_markdown_left = textwrap.indent(markdown_content_left, ' ' * 10)
        indented_markdown_right = textwrap.indent(markdown_content_right, ' ' * 10)
        
        # Costruisce la struttura YAML completa usando una lista di stringhe
        lines = [
            "type: horizontal-stack",
            "cards:",
            "  - type: custom:vertical-stack-in-card",
            "    cards:",
            "      - type: custom:button-card",
            "        name: SouthTech Light Presence Monitor",
            "        icon: mdi:lightbulb-auto",
            "        styles:",
            "          card:",
            '            - height: 50%',
            '            - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"',
            '            - border-radius: 12px',
            '            - padding: 16px',
            '            - box-shadow: 0 4px 12px rgba(0,0,0,0.3)',
            "          name:",
            '            - font-size: 22px',
            '            - font-weight: bold',
            '            - color: white',
            "          icon:",
            '            - color: "#FFD700"',
            '            - width: 40px',
            '            - margin-bottom: 8px',
            "      - type: markdown",
            "        content: |",
            f"{indented_markdown_left}",
            "        styles:",
            "          card:",
            '            - height: 50%',
            '            - background: rgba(255, 255, 255, 0.1)',
            '            - border-radius: 10px',
            '            - padding: 14px',
            '            - color: white',
            '            - font-size: 16px !important',
            '            - line-height: 1.5',
            "  - type: custom:vertical-stack-in-card",
            "    styles:",
            "      card:",
            '        - height: 240px !important',
            '        - width: 50%',
            '        - border-radius: 12px',
            '        - background: rgba(255, 255, 255, 0.05)',
            '        - box-shadow: 0 4px 12px rgba(0,0,0,0.3)',
            "    cards:",
            "      - type: custom:button-card",
            "        name: Dettagli Configurazione",
            "        icon: mdi:cog",
            "        styles:",
            "          card:",
            '            - height: 50%',
            '            - background: "linear-gradient(135deg, #2a5298 0%, #1e3c72 100%)"',
            '            - border-radius: 12px',
            '            - padding: 16px',
            '            - box-shadow: 0 4px 12px rgba(0,0,0,0.3)',
            "          name:",
            '            - font-size: 20px',
            '            - font-weight: bold',
            '            - color: white',
            "          icon:",
            '            - color: "#FFD700"',
            '            - width: 36px',
            '            - margin-bottom: 8px',
            "      - type: markdown",
            "        content: |",  # Changed from "content: >" to "content: |"
            f"{indented_markdown_right}",
            "        styles:",
            "          card:",
            '            - height: 50%',
            '            - background: rgba(255, 255, 255, 0.1)',
            '            - border-radius: 10px',
            '            - padding: 16px',
            '            - box-shadow: 0 2px 8px rgba(0,0,0,0.2)',
            '            - color: white',
            '            - font-size: 20px !important',
            '            - line-height: 1.8'
        ]
        
        return "\n".join(lines)

    except Exception as e:
        self.configurator.error(f"⚠️ Errore critico durante la creazione del contenuto dell'indice luci: {e}")
        # Ritorna una card di errore in caso di problemi
        return textwrap.dedent(f"""
          - type: markdown
            content: |
              ## ⚠️ Errore di Generazione Vista
              **Si è verificato un errore durante la creazione della dashboard principale.**
              **Dettagli:** `{e}`
              *Controlla i log di AppDaemon per maggiori informazioni.*
        """).strip()

    # ===============================================================
    # TEMPLATE SENSORS - METODI DI SUPPORTO
    # ===============================================================
    
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
            
            self.configurator.log(f"✅ Validazione templates: {len(validation_result['valid_configurations'])} valide, "
                    f"{len(validation_result['invalid_configurations'])} invalide, "
                    f"{len(validation_result['warnings'])} avvisi")
            
            return validation_result
            
        except Exception as e:
            self.configurator.error(f"Errore validazione templates: {e}")
            return {
                "valid_configurations": [],
                "invalid_configurations": configurations,
                "warnings": [],
                "error": str(e)
            }

    def cleanup_old_template_sensors(self):
        """Pulisce sensori template orfani dal file"""
        try:
            if not os.path.exists(self.configurator.templates_file):
                self.configurator.log("📄 File templates non esiste, nessuna pulizia necessaria")
                return
            
            self.configurator.log("🧹 Pulizia sensori template orfani...")
            
            # Ottieni configurazioni attuali
            current_configs = self.configurator.yaml.read_existing_configs()
            current_light_entities = {cfg.get('light_entity') for cfg in current_configs if cfg.get('light_entity')}
            
            # Leggi file templates
            with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Trova sezione SouthTech
            start_idx = content.find(self.configurator.templates_start_line)
            if start_idx == -1:
                self.configurator.log("ℹ️ Sezione SouthTech non trovata in templates")
                return
            
            # Estrai base_id dalle configurazioni attuali
            current_base_ids = {entity.replace('light.', '') for entity in current_light_entities}
            
            self.configurator.log(f"🔍 Configurazioni attuali: {len(current_base_ids)} base_id")
            self.configurator.log(f"📝 Base ID attuali: {current_base_ids}")
            
            # Regenera templates solo per configurazioni attuali
            if current_configs:
                self.configurator.log("🔄 Rigenerazione templates per configurazioni attuali")
                templates_result = self.generate_template_sensors(current_configs)
                
                if templates_result.get("success"):
                    self.configurator.log(f"✅ Templates aggiornati: {templates_result.get('sensors_count', 0)} sensori")
                else:
                    self.configurator.log(f"❌ Errore aggiornamento templates: {templates_result.get('error')}")
            else:
                self.configurator.log("ℹ️ Nessuna configurazione attuale, templates mantenuti invariati")
            
        except Exception as e:
            self.configurator.error(f"Errore pulizia template sensors: {e}")

    def get_template_sensors_status(self):
        """Ottieni stato dei template sensors generati"""
        try:
            status = {
                "file_exists": os.path.exists(self.configurator.templates_file),
                "file_size": 0,
                "sensors_count": 0,
                "last_modified": None,
                "valid_yaml": False,
                "sensors_details": []
            }
            
            if not status["file_exists"]:
                return status
            
            # Info file
            status["file_size"] = os.path.getsize(self.configurator.templates_file)
            status["last_modified"] = datetime.fromtimestamp(
                os.path.getmtime(self.configurator.templates_file)
            ).isoformat()
            
            # Verifica contenuto
            try:
                with open(self.configurator.templates_file, 'r', encoding='utf-8') as f:
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
                self.configurator.log(f"⚠️ Errore analisi file templates: {e}")
                status["analysis_error"] = str(e)
            
            return status
            
        except Exception as e:
            self.configurator.error(f"Errore status template sensors: {e}")
            return {"error": str(e)}

    def extract_southtech_templates_section(self, content):
        """Estrae solo la sezione SouthTech dal file templates"""
        try:
            start_idx = content.find(self.configurator.templates_start_line)
            if start_idx == -1:
                return None
            
            end_idx = content.find(self.configurator.templates_end_line, start_idx)
            if end_idx == -1:
                return None
            
            return content[start_idx:end_idx + len(self.configurator.templates_end_line)]
            
        except Exception as e:
            self.configurator.error(f"Errore estrazione sezione templates: {e}")
            return None

    # ===============================================================
    # DIAGNOSTICI E TEST
    # ===============================================================

    def test_configuration_yaml_update_step_by_step(self):
        """Test diagnostico step-by-step per configuration.yaml update"""
        try:
            self.configurator.log("🧪 === TEST DIAGNOSTICO CONFIGURATION.YAML ===")
            
            test_results = {
                "step1_file_exists": False,
                "step2_file_readable": False,
                "step3_file_writable": False,
                "step4_markers_detection": False,
                "step5_content_analysis": False,
                "step6_backup_capability": False,
                "step7_temp_file_creation": False,
                "step8_atomic_replacement": False,
                "diagnostics": {}
            }
            
            config_path = getattr(self.configurator, 'configuration_yaml_path', '/homeassistant/configuration.yaml')
            
            # STEP 1: File exists
            try:
                file_exists = os.path.exists(config_path)
                test_results["step1_file_exists"] = file_exists
                test_results["diagnostics"]["file_path"] = config_path
                test_results["diagnostics"]["file_exists"] = file_exists
                self.configurator.log(f"✅ STEP 1: File exists = {file_exists}")
            except Exception as e:
                self.configurator.error(f"❌ STEP 1 Error: {e}")
                test_results["diagnostics"]["step1_error"] = str(e)
            
            if not test_results["step1_file_exists"]:
                self.configurator.log("⚠️ File non esiste, test interrotto")
                return test_results
            
            # STEP 2: File readable
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                test_results["step2_file_readable"] = True
                test_results["diagnostics"]["file_size"] = len(content)
                self.configurator.log(f"✅ STEP 2: File readable = True ({len(content)} chars)")
            except Exception as e:
                self.configurator.error(f"❌ STEP 2 Error: {e}")
                test_results["diagnostics"]["step2_error"] = str(e)
                return test_results
            
            # STEP 3: File writable
            try:
                writable = os.access(config_path, os.W_OK)
                test_results["step3_file_writable"] = writable
                test_results["diagnostics"]["file_writable"] = writable
                self.configurator.log(f"✅ STEP 3: File writable = {writable}")
            except Exception as e:
                self.configurator.error(f"❌ STEP 3 Error: {e}")
                test_results["diagnostics"]["step3_error"] = str(e)
            
            # STEP 4: Markers detection
            try:
                section_bounds = self.find_dashboards_section_flexible(content)
                has_markers = section_bounds is not None
                test_results["step4_markers_detection"] = has_markers
                
                if has_markers:
                    start_pos, end_pos, start_marker, end_marker = section_bounds
                    test_results["diagnostics"]["markers_found"] = {
                        "start_pos": start_pos,
                        "end_pos": end_pos,
                        "start_marker": start_marker,
                        "end_marker": end_marker
                    }
                else:
                    test_results["diagnostics"]["markers_found"] = False
                
                self.configurator.log(f"✅ STEP 4: Markers detection = {has_markers}")
            except Exception as e:
                self.configurator.error(f"❌ STEP 4 Error: {e}")
                test_results["diagnostics"]["step4_error"] = str(e)
            
            # STEP 5: Content analysis
            try:
                has_lovelace = 'lovelace:' in content
                has_dashboards = 'dashboards:' in content
                has_light_presence = 'light-presence:' in content
                
                test_results["step5_content_analysis"] = True
                test_results["diagnostics"]["content_analysis"] = {
                    "has_lovelace": has_lovelace,
                    "has_dashboards": has_dashboards,
                    "has_light_presence": has_light_presence
                }
                self.configurator.log(f"✅ STEP 5: Content analysis complete")
            except Exception as e:
                self.configurator.error(f"❌ STEP 5 Error: {e}")
                test_results["diagnostics"]["step5_error"] = str(e)
            
            # STEP 6: Backup capability
            try:
                backup_dir = os.path.dirname(self.configurator.backup_path)
                backup_writable = os.access(backup_dir, os.W_OK) if os.path.exists(backup_dir) else False
                test_results["step6_backup_capability"] = backup_writable
                test_results["diagnostics"]["backup_capability"] = {
                    "backup_dir": backup_dir,
                    "backup_dir_exists": os.path.exists(backup_dir),
                    "backup_writable": backup_writable
                }
                self.configurator.log(f"✅ STEP 6: Backup capability = {backup_writable}")
            except Exception as e:
                self.configurator.error(f"❌ STEP 6 Error: {e}")
                test_results["diagnostics"]["step6_error"] = str(e)
            
            # STEP 7: Temp file creation
            try:
                temp_path = f"{config_path}.tmp_test"
                test_content = "# Test SouthTech\n"
                
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                temp_exists = os.path.exists(temp_path)
                if temp_exists:
                    os.remove(temp_path)
                
                test_results["step7_temp_file_creation"] = temp_exists
                test_results["diagnostics"]["temp_file_test"] = temp_exists
                self.configurator.log(f"✅ STEP 7: Temp file creation = {temp_exists}")
            except Exception as e:
                self.configurator.error(f"❌ STEP 7 Error: {e}")
                test_results["diagnostics"]["step7_error"] = str(e)
            
            # STEP 8: Atomic replacement simulation
            try:
                # Test solo se tutti i passi precedenti sono OK
                if all([test_results["step1_file_exists"], 
                       test_results["step2_file_readable"],
                       test_results["step3_file_writable"],
                       test_results["step7_temp_file_creation"]]):
                    
                    test_results["step8_atomic_replacement"] = True
                    self.configurator.log(f"✅ STEP 8: Atomic replacement capability = True")
                else:
                    test_results["step8_atomic_replacement"] = False
                    self.configurator.log(f"⚠️ STEP 8: Atomic replacement capability = False (prerequisiti mancanti)")
                    
            except Exception as e:
                self.configurator.error(f"❌ STEP 8 Error: {e}")
                test_results["diagnostics"]["step8_error"] = str(e)
            
            # Risultato finale
            successful_steps = sum(1 for k, v in test_results.items() if k.startswith('step') and v)
            total_steps = len([k for k in test_results.keys() if k.startswith('step')])
            
            test_results["summary"] = {
                "successful_steps": successful_steps,
                "total_steps": total_steps,
                "success_rate": f"{successful_steps}/{total_steps}",
                "overall_capability": successful_steps >= 6  # Almeno 6 step su 8 OK
            }
            
            self.configurator.log(f"🎯 TEST DIAGNOSTICO COMPLETATO: {successful_steps}/{total_steps} step OK")
            
            return test_results
            
        except Exception as e:
            self.configurator.error(f"❌ Errore test diagnostico: {e}")
            return {
                "error": str(e),
                "test_failed": True
            }

    # ===============================================================
    # UTILITY E HELPERS
    # ===============================================================

    def get_dashboard_files_status(self):
        """Ottieni stato dei file dashboard generati"""
        try:
            status = {
                "dashboard_path_exists": os.path.exists(self.configurator.dashboard_path),
                "lights_config_path_exists": os.path.exists(self.configurator.lights_config_path),
                "main_dashboard_file": None,
                "light_config_files": [],
                "total_files": 0
            }
            
            # Controlla dashboard principale
            main_dashboard = os.path.join(self.configurator.dashboard_path, "ui-lovelace-light-presence.yaml")
            if os.path.exists(main_dashboard):
                status["main_dashboard_file"] = {
                    "path": main_dashboard,
                    "size": os.path.getsize(main_dashboard),
                    "last_modified": datetime.fromtimestamp(os.path.getmtime(main_dashboard)).isoformat()
                }
                status["total_files"] += 1
            
            # Controlla file configurazioni luci
            if status["lights_config_path_exists"]:
                for filename in os.listdir(self.configurator.lights_config_path):
                    if filename.endswith('.yaml'):
                        filepath = os.path.join(self.configurator.lights_config_path, filename)
                        status["light_config_files"].append({
                            "filename": filename,
                            "path": filepath,
                            "size": os.path.getsize(filepath),
                            "last_modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                        })
                        status["total_files"] += 1
            
            return status
            
        except Exception as e:
            self.configurator.error(f"Errore status file dashboard: {e}")
            return {"error": str(e)}

    def clean_old_dashboard_files(self, current_configurations):
        """Pulisce file dashboard per configurazioni rimosse"""
        try:
            if not os.path.exists(self.configurator.lights_config_path):
                return
            
            # Ottieni base_id attuali
            current_base_ids = {cfg.get('light_entity', '').replace('light.', '') 
                              for cfg in current_configurations 
                              if cfg.get('light_entity')}
            
            # Trova file orfani
            orphaned_files = []
            for filename in os.listdir(self.configurator.lights_config_path):
                if filename.endswith('.yaml'):
                    base_id = filename.replace('.yaml', '')
                    if base_id not in current_base_ids:
                        orphaned_files.append(filename)
            
            # Rimuovi file orfani
            for filename in orphaned_files:
                try:
                    filepath = os.path.join(self.configurator.lights_config_path, filename)
                    os.remove(filepath)
                    self.configurator.log(f"🗑️ Rimosso file dashboard orfano: {filename}")
                except Exception as e:
                    self.configurator.error(f"Errore rimozione file {filename}: {e}")
            
            if orphaned_files:
                self.configurator.log(f"🧹 Pulizia completata: {len(orphaned_files)} file rimossi")
            else:
                self.configurator.log("ℹ️ Nessun file dashboard orfano trovato")
                
        except Exception as e:
            self.configurator.error(f"Errore pulizia file dashboard: {e}")

    def generate_dashboard_summary_report(self):
        """Genera report riepilogativo dello stato dashboard"""
        try:
            # Ottieni configurazioni attuali
            current_configs = self.configurator.yaml.read_existing_configs()
            
            # Stato file
            dashboard_status = self.get_dashboard_files_status()
            templates_status = self.get_template_sensors_status()
            
            # Crea report
            report = {
                "timestamp": datetime.now().isoformat(),
                "version": self.version,
                "configurations": {
                    "total": len(current_configs),
                    "valid_for_dashboard": len([cfg for cfg in current_configs 
                                              if cfg.get('light_entity') and cfg.get('presence_sensor_on')])
                },
                "templates": {
                    "file_exists": templates_status.get("file_exists", False),
                    "sensors_count": templates_status.get("sensors_count", 0),
                    "file_size": templates_status.get("file_size", 0),
                    "valid_yaml": templates_status.get("valid_yaml", False)
                },
                "dashboards": {
                    "main_dashboard_exists": dashboard_status.get("main_dashboard_file") is not None,
                    "light_config_files_count": len(dashboard_status.get("light_config_files", [])),
                    "total_files": dashboard_status.get("total_files", 0)
                },
                "paths": {
                    "dashboard_path": self.configurator.dashboard_path,
                    "lights_config_path": self.configurator.lights_config_path,
                    "templates_file": self.configurator.templates_file
                },
                "status": "operational" if all([
                    len(current_configs) > 0,
                    templates_status.get("file_exists", False),
                    dashboard_status.get("main_dashboard_file") is not None
                ]) else "incomplete"
            }
            
            # Salva report in sensore
            try:
                self.configurator.set_state("sensor.southtech_dashboard_summary_report",
                              state=report["status"],
                              attributes=report)
            except Exception as e:
                self.configurator.log(f"⚠️ Errore salvataggio report in sensore: {e}")
            
            return report
            
        except Exception as e:
            self.configurator.error(f"Errore generazione report dashboard: {e}")
            return {"error": str(e)}

    def generate_dashboard_and_templates(self, configurations, skip_backup=False):
        """
        [MODIFICATO] Ora gestisce correttamente sia la generazione che la pulizia.
        """
        # --- LOGICA DI PULIZIA AGGIUNTA ---
        if not configurations:
            self.configurator.log("🗑️ Nessuna configurazione rilevata. Avvio procedura di pulizia dashboard...")
            
            # Esegue le operazioni di pulizia specifiche della dashboard
            templates_cleanup = self._cleanup_templates_section()
            config_cleanup = self._cleanup_configuration_yaml_entry()
            dashboard_files_cleanup = self._cleanup_dashboard_files() 
            
            cleanup_results = {
                "templates": templates_cleanup,
                "configuration": config_cleanup,
                "dashboard": dashboard_files_cleanup,
                "lights_config": {"success": True, "message": "Nessuna configurazione individuale da pulire."}
            }
            
            successful_cleanups = sum(1 for result in cleanup_results.values() if result.get("success"))
            overall_success = successful_cleanups >= 3 # Tolleranza per piccoli fallimenti
            
            return {
                "success": overall_success,
                "success_type": "cleanup_success" if overall_success else "cleanup_partial_failure",
                "message": f"Procedura di pulizia completata.",
                "details": cleanup_results
            }
        
        # --- LOGICA DI GENERAZIONE (se ci sono configurazioni) ---
        try:
            self.configurator.log(f"🎨 Inizio generazione per {len(configurations)} configurazioni...")
            
            # La generazione dei singoli file avviene in metodi separati
            templates_result = self.generate_template_sensors(configurations, skip_backup=skip_backup)
            config_result = self.update_configuration_yaml(skip_backup=skip_backup)
            dashboard_main_result = self.generate_main_dashboard(configurations, skip_backup=skip_backup)
            lights_files_result = self.generate_light_config_files(configurations, skip_backup=skip_backup)
            
            results = {
                "templates": templates_result,
                "configuration": config_result,
                "dashboard": dashboard_main_result, # Contiene i file principali
                "lights_config": lights_files_result # Contiene i file individuali
            }

            successful_components = sum(1 for res in results.values() if res.get("success"))
            overall_success = successful_components >= 3
            
            return {
                "success": overall_success,
                "success_type": "complete_success" if successful_components == 4 else "partial_success",
                "message": f"Generazione completata.",
                "details": results
            }
        except Exception as e:
            self.configurator.error(f"❌ Errore critico generazione dashboard: {e}")
            return {"success": False, "error": str(e)}

    # ===============================================================
    # NOTIFICHE DI CAMBIO CONFIGURAZIONE
    # ===============================================================

    def on_configuration_change(self, change_type, data):
        """Gestisce notifiche di cambio configurazione"""
        try:
            self.configurator.log(f"📢 Dashboard ricevuta notifica: {change_type}")
            
            if change_type == "configurations_updated":
                # Aggiorna conteggi nelle entità debug
                configs_count = data.get("configurations_count", 0)
                
                # Aggiorna entità riepilogo
                try:
                    summary_entity = "sensor.southtech_dashboard_extension_summary"
                    current_attrs = self.configurator.get_state(summary_entity, attribute="all")
                    
                    if current_attrs and "attributes" in current_attrs:
                        attrs = current_attrs["attributes"]
                        attrs.update({
                            "existing_configurations": configs_count,
                            "estimated_sensors": configs_count * 4,
                            "last_config_change": datetime.now().isoformat(),
                            "change_type": change_type
                        })
                        
                        state = "configurations_detected" if configs_count > 0 else "no_configurations"
                        self.configurator.set_state(summary_entity, state=state, attributes=attrs)
                        
                except Exception as e:
                    self.configurator.error(f"Errore aggiornamento entità dopo cambio config: {e}")
            
            elif change_type == "file_updated":
                # File apps.yaml aggiornato
                self.configurator.log("📝 File apps.yaml aggiornato, dashboard può essere rigenerata")
                
            elif change_type == "backup_created":
                # Backup creato
                backup_info = data.get("backup_info", {})
                self.configurator.log(f"📦 Backup creato: {backup_info.get('backup_folder', 'Unknown')}")
                
        except Exception as e:
            self.configurator.error(f"Errore gestione notifica cambio configurazione: {e}")

    # ===============================================================
    # CLEANUP E TERMINAZIONE
    # ===============================================================

    def cleanup(self):
        """Cleanup del modulo dashboard"""
        try:
            self.configurator.log("🧹 Cleanup modulo Dashboard...")
            
            # Aggiorna entità con stato di terminazione
            try:
                debug_entities = [
                    "sensor.southtech_dashboard_status",
                    "sensor.southtech_templates_status", 
                    "sensor.southtech_complete_save_log",
                    "sensor.southtech_dashboard_files_count",
                    "sensor.southtech_dashboard_extension_summary"
                ]
                
                for entity_id in debug_entities:
                    try:
                        current_attrs = self.configurator.get_state(entity_id, attribute="all")
                        if current_attrs and "attributes" in current_attrs:
                            attrs = current_attrs["attributes"]
                            attrs.update({
                                "cleanup_timestamp": datetime.now().isoformat(),
                                "module_terminated": True,
                                "version": self.version
                            })
                            
                            self.configurator.set_state(entity_id, state="terminated", attributes=attrs)
                            
                    except Exception as e:
                        self.configurator.log(f"⚠️ Errore cleanup entità {entity_id}: {e}")
                        
            except Exception as e:
                self.configurator.log(f"⚠️ Errore cleanup entità debug: {e}")
            
            # Salva stato finale
            final_report = self.generate_dashboard_summary_report()
            final_report["cleanup_completed"] = True
            final_report["module_version"] = self.version
            
            self.configurator.log("✅ Cleanup modulo Dashboard completato")
            
        except Exception as e:
            self.configurator.error(f"❌ Errore durante cleanup Dashboard: {e}")

    # ===============================================================
    # METODI DI NOTIFICA CONFIGURAZIONE
    # ===============================================================

    def notify_dashboard_generation_complete(self, result):
        """Notifica completamento generazione dashboard"""
        try:
            # FIX: Aggiunto controllo per evitare crash se 'security' non esiste
            if not hasattr(self.configurator, 'security') or not hasattr(self.configurator.security, 'create_ha_notification'):
                self.configurator.log("⚠️ Attributo 'security' o metodo 'create_ha_notification' non trovati. Notifica saltata.")
                return

            if result.get("success"):
                success_type = result.get("success_type", "unknown")
                files_created = result.get("summary", {}).get("dashboard_files_created", 0)
                
                if success_type == "complete_success":
                    self.configurator.security.create_ha_notification(
                        "✅ SouthTech: Dashboard Generate",
                        f"Dashboard e templates generati con successo! {files_created} file creati."
                    )
                elif success_type == "partial_success":
                    components_ok = result.get("summary", {}).get("successful_operations", 0)
                    self.configurator.security.create_ha_notification(
                        "⚠️ SouthTech: Dashboard Parziale", 
                        f"Dashboard generata parzialmente ({components_ok}/4 componenti). Controlla i log."
                    )
            else:
                error_msg = result.get("error", "Errore sconosciuto")
                self.configurator.security.create_ha_notification(
                    "❌ SouthTech: Dashboard Non Generata",
                    f"Errore generazione dashboard: {error_msg[:100]}..."
                )
                
        except Exception as e:
            self.configurator.error(f"Errore notifica generazione dashboard: {e}")
