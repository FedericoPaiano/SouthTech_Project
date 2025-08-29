import os
import yaml
import json
import time
import shutil
from datetime import datetime

class SouthTechConfiguratorYaml:
    """
    📝 SOUTHTECH CONFIGURATOR YAML
    Gestisce tutte le operazioni YAML, parsing, validazione e salvataggio files
    """
    
    def __init__(self, configurator):
        """Inizializza il modulo YAML"""
        self.configurator = configurator
        # Rimosse le assegnazioni dirette dei metodi di logging.
        # Si userà self.configurator.log/error/warning direttamente.
        # self.log = configurator.log
        # self.error = configurator.error
        # self.warning = configurator.warning
        
        self.configurator.log("📝 Inizializzazione modulo YAML...")
        
        # Verifica integrità file all'avvio
        is_valid, message = self.configurator.check_file_integrity()
        if not is_valid:
            self.configurator.warning(f"⚠️ Integrità YAML: {message}") # Correzione qui
        
        self.configurator.log("✅ Modulo YAML inizializzato")

    # ===============================================================
    # ESTRAZIONE E PARSING YAML
    # ===============================================================

    def _extract_yaml_section(self, content):
        """Estrae la sezione controllo luci dal contenuto YAML"""
        try:
            # Prova nuovo formato prima
            start_line_idx = content.find(self.configurator.new_start_line)
            if start_line_idx != -1:
                self.configurator.log("✅ Trovata sezione formato NUOVO") # Correzione qui
                start_block_idx = content.rfind(self.configurator.new_start_marker, 0, start_line_idx)
                end_line_idx = content.find(self.configurator.new_end_line, start_line_idx)
                
                if end_line_idx != -1:
                    end_block_idx = content.find(self.configurator.new_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.configurator.new_end_marker)
                        return content[start_block_idx:end_block_idx]
            
            # Prova formato vecchio
            old_start_idx = content.find(self.configurator.start_marker)
            old_end_idx = content.find(self.configurator.end_marker)
            
            if old_start_idx != -1 and old_end_idx != -1:
                self.configurator.log("✅ Trovata sezione formato VECCHIO") # Correzione qui
                old_end_idx += len(self.configurator.end_marker)
                return content[old_start_idx:old_end_idx]
            
            # Nessuna sezione trovata
            return None
            
        except Exception as e:
            self.configurator.error(f"Errore estrazione sezione YAML: {e}") # Correzione qui
            return None

    def read_existing_configs(self):
        """Legge le configurazioni esistenti da apps.yaml - Supporto doppio formato"""
        configurations = []
        
        try:
            if not os.path.exists(self.configurator.apps_yaml_path):
                self.configurator.log("⚠️ File apps.yaml non trovato") # Correzione qui
                return configurations
            
            with open(self.configurator.apps_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Estrai la sezione YAML dal contenuto
            yaml_content = self._extract_yaml_section(content)
            
            if yaml_content:
                configurations = self._parse_yaml_configurations(yaml_content)
            else:
                self.configurator.log("ℹ️ Sezione controllo luci non trovata in apps.yaml") # Correzione qui
            
            self.configurator.log(f"📋 Caricate {len(configurations)} configurazioni dal file apps.yaml") # Correzione qui
            return configurations
            
        except Exception as e:
            self.configurator.error(f"Errore lettura apps.yaml: {e}") # Correzione qui
            return configurations

    def _parse_yaml_configurations(self, yaml_content):
        """Parse delle configurazioni YAML"""
        configurations = []
        
        try:
            config_data = yaml.safe_load(yaml_content)
            
            if config_data and 'light_presence' in config_data:
                lights_config = config_data['light_presence'].get('light_presence', [])
                
                for cfg in lights_config:
                    # Estrai solo i parametri base per l'interfaccia
                    configurations.append({
                        'light_entity': cfg.get('light_entity', ''),
                        'presence_sensor_on': cfg.get('presence_sensor_on', ''),
                        'presence_sensor_off': cfg.get('presence_sensor_off', ''),
                        'illuminance_sensor': cfg.get('illuminance_sensor', '')
                    })
                    
        except yaml.YAMLError as e:
            self.configurator.error(f"Errore parsing YAML: {e}") # Correzione qui
        
        return configurations

    # ===============================================================
    # SALVATAGGIO E GESTIONE YAML
    # ===============================================================

    def save_yaml_configuration(self, yaml_content):
        """Salva la configurazione YAML con spazi di separazione corretti"""
        try:
            # Leggi il contenuto esistente
            existing_content = ""
            if os.path.exists(self.configurator.apps_yaml_path):
                with open(self.configurator.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Prova a sostituire nel nuovo formato prima
            new_content = self._replace_yaml_new_format(existing_content, yaml_content)
            if new_content is None:
                # Fallback al formato vecchio
                new_content = self._replace_yaml_old_format(existing_content, yaml_content)
            
            # Se nessuna sezione esistente trovata, aggiungi alla fine
            if new_content is None:
                # Mantieni spazio di separazione
                if existing_content and not existing_content.endswith('\n'):
                    existing_content += '\n'
                
                # Aggiungi con spazio di separazione dalla sezione precedente
                new_content = existing_content + '\n' + yaml_content.rstrip('\n') + '\n'
            
            # Scrivi il nuovo contenuto
            with open(self.configurator.apps_yaml_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.configurator.log("💾 Configurazione YAML salvata in apps.yaml") # Correzione qui
            return True
            
        except Exception as e:
            self.configurator.error(f"Errore salvataggio YAML: {e}") # Correzione qui
            raise

    def save_yaml_content_safe(self, yaml_content):
        """Salva contenuto YAML in modo sicuro"""
        try:
            # Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.configurator.apps_yaml_path):
                with open(self.configurator.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.configurator.log(f"📖 Letto file esistente: {len(existing_content)} caratteri") # Correzione qui
            
            # Unisci con nuovo contenuto
            new_content = self.merge_yaml_content_smart(existing_content, yaml_content)
            self.configurator.log(f"🔗 Contenuto unito: {len(new_content)} caratteri") # Correzione qui
            
            # Verifica YAML valido PRIMA di scrivere
            try:
                parsed = yaml.safe_load(new_content)
                if parsed is None:
                    raise Exception("YAML risulta vuoto dopo parsing")
                self.configurator.log("✅ YAML validato correttamente") # Correzione qui
            except yaml.YAMLError as e:
                raise Exception(f"YAML non valido: {e}")
            
            # Scrivi in file temporaneo
            temp_file = self.configurator.apps_yaml_path + ".tmp_save"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            self.configurator.log(f"💾 Scritto file temporaneo: {temp_file}") # Correzione qui
            
            # Verifica file temporaneo
            with open(temp_file, 'r', encoding='utf-8') as f:
                temp_content = f.read()
            
            if temp_content != new_content:
                raise Exception("Contenuto file temporaneo non corrisponde")
            
            # Crea backup di sicurezza
            if os.path.exists(self.configurator.apps_yaml_path):
                safety_backup = self.configurator.apps_yaml_path + ".safety_backup"
                shutil.copy2(self.configurator.apps_yaml_path, safety_backup)
                self.configurator.log(f"🛡️ Backup sicurezza: {safety_backup}") # Correzione qui
            
            # Sostituisci file originale
            shutil.move(temp_file, self.configurator.apps_yaml_path)
            self.configurator.log("🔄 File originale sostituito") # Correzione qui
            
        except Exception as e:
            # Pulizia in caso di errore
            temp_file = self.configurator.apps_yaml_path + ".tmp_save"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    self.configurator.log("🗑️ File temporaneo rimosso") # Correzione qui
                except:
                    pass
            raise e

    def merge_yaml_content_smart(self, existing_content, new_section):
        """Unisce contenuto YAML con spazi di separazione corretti"""
        
        # Marcatori nuovo formato (priorità)
        new_start_marker = self.configurator.new_start_marker
        new_start_line = self.configurator.new_start_line
        new_end_line = self.configurator.new_end_line
        new_end_marker = self.configurator.new_end_marker
        
        # Marcatori vecchio formato (compatibilità)
        old_start_marker = self.configurator.start_marker
        old_end_marker = self.configurator.end_marker
        
        self.configurator.log("🔍 Ricerca sezione esistente...") # Correzione qui
        
        # Prova formato nuovo
        start_line_idx = existing_content.find(new_start_line)
        if start_line_idx != -1:
            self.configurator.log("✅ Trovata sezione formato NUOVO") # Correzione qui
            start_block_idx = existing_content.rfind(new_start_marker, 0, start_line_idx)
            end_line_idx = existing_content.find(new_end_line, start_line_idx)
            
            if end_line_idx != -1:
                end_block_idx = existing_content.find(new_end_marker, end_line_idx)
                if end_block_idx != -1:
                    end_block_idx += len(new_end_marker)
                    
                    # CORREZIONE BILANCIATA: Mantiene 1 riga vuota prima e dopo
                    before = existing_content[:start_block_idx].rstrip('\n')
                    after = existing_content[end_block_idx:].lstrip('\n')
                    
                    # Assicura 1 riga vuota prima della sezione
                    if before and not before.endswith('\n'):
                        before += '\n'
                    
                    # Costruisci risultato con spazi corretti
                    result = before + '\n' + new_section.rstrip('\n')
                    
                    # Assicura 1 riga vuota dopo la sezione (se c'è contenuto dopo)
                    if after:
                        result += '\n\n' + after
                    else:
                        result += '\n'
                    
                    self.configurator.log(f"🔄 Sostituita sezione esistente (nuovo formato)") # Correzione qui
                    return result
        
        # Prova formato vecchio
        old_start_idx = existing_content.find(old_start_marker)
        old_end_idx = existing_content.find(old_end_marker)
        
        if old_start_idx != -1 and old_end_idx != -1:
            self.configurator.log("✅ Trovata sezione formato VECCHIO") # Correzione qui
            old_end_idx += len(old_end_marker)
            
            # CORREZIONE BILANCIATA: Mantiene 1 riga vuota prima e dopo
            before = existing_content[:old_start_idx].rstrip('\n')
            after = existing_content[old_end_idx:].lstrip('\n')
            
            # Assicura 1 riga vuota prima della sezione
            if before and not before.endswith('\n'):
                before += '\n'
            
            # Costruisci risultato con spazi corretti
            result = before + '\n' + new_section.rstrip('\n')
            
            # Assicura 1 riga vuota dopo la sezione (se c'è contenuto dopo)
            if after:
                result += '\n\n' + after
            else:
                result += '\n'
            
            self.configurator.log(f"🔄 Sostituita sezione esistente (vecchio formato)") # Correzione qui
            return result
        
        # Nessuna sezione esistente
        self.configurator.log("ℹ️ Nessuna sezione esistente, aggiunta alla fine") # Correzione qui
        
        # Mantiene spazio di separazione dalla sezione precedente
        if existing_content and not existing_content.endswith('\n'):
            existing_content += '\n'
        
        # Aggiungi con spazio di separazione
        return existing_content + '\n' + new_section.rstrip('\n') + '\n'

    def rebuild_apps_yaml_content(self, existing_content, new_section, start_idx, end_idx):
        """Ricostruisce il contenuto completo con spazi di separazione corretti"""
        try:
            if start_idx == -1 or end_idx == -1:
                # Nessuna sezione esistente, aggiungi alla fine
                if existing_content and not existing_content.endswith('\n'):
                    existing_content += '\n'
                
                # Mantieni spazio di separazione
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
            self.configurator.error(f"Errore ricostruzione contenuto apps.yaml: {e}") # Correzione qui
            raise

    def verify_saved_file(self, expected_yaml_content):
        """Verifica che il file sia stato salvato correttamente"""
        try:
            # Controlla che il file esista
            if not os.path.exists(self.configurator.apps_yaml_path):
                raise Exception("File apps.yaml non trovato dopo salvataggio")
            
            # Leggi contenuto salvato
            with open(self.configurator.apps_yaml_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            if not saved_content:
                raise Exception("File apps.yaml è vuoto")
            
            # Verifica che contenga la nostra sezione
            if "START CONTROLLO LUCI AUTOMATICHE" not in saved_content:
                raise Exception("Sezione light_presence non trovata nel file salvato")
            
            # Verifica YAML valido
            try:
                parsed = yaml.safe_load(saved_content)
                if parsed is None:
                    raise Exception("File YAML risulta vuoto")
            except yaml.YAMLError as e:
                raise Exception(f"File YAML non valido: {e}")
            
            file_size = os.path.getsize(self.configurator.apps_yaml_path)
            self.configurator.log(f"✅ File verificato: {len(saved_content)} caratteri, {file_size} bytes") # Correzione qui
            
        except Exception as e:
            self.configurator.error(f"❌ Verifica file fallita: {e}") # Correzione qui
            raise

    # ===============================================================
    # PROCESSAMENTO AVANZATO YAML
    # ===============================================================

    def process_apps_yaml_advanced(self, new_configurations, skip_backup=False):
        """
        🎯 METODO CORE MODIFICATO: Processamento avanzato apps.yaml
        Gestisce correttamente il caso di una lista di configurazioni vuota (pulizia).
        """
        try:
            self.configurator.log("🔧 CORE: Inizio processamento intelligente apps.yaml")
            
            # --- INIZIO LOGICA MODIFICATA ---
            # 1. Validazione configurazioni (non blocca se la lista è vuota)
            valid_configs = self.validate_configurations(new_configurations)
            
            # Se c'erano configurazioni in input ma nessuna è risultata valida, allora è un errore.
            if new_configurations and not valid_configs:
                return {"success": False, "error": "Le configurazioni fornite non sono valide"}
            # Se la lista è vuota dall'inizio (richiesta di pulizia), si procede.
            # --- FINE LOGICA MODIFICATA ---

            # BACKUP CONDIZIONALE: Solo se non skip_backup
            backup_info = {"backup_created": False, "backup_skipped": skip_backup}
            
            if not skip_backup and os.path.exists(self.configurator.apps_yaml_path):
                self.configurator.log("📦 Backup apps.yaml...")
                try:
                    backup_files = [{
                        "source_path": self.configurator.apps_yaml_path,
                        "backup_name": "apps.bkp",
                        "type": "apps_yaml"
                    }]
                    
                    backup_result = self.configurator.create_structured_backup(
                        backup_type="single", 
                        files_to_backup=backup_files
                    )
                    
                    if backup_result.get("success"):
                        self.configurator.log(f"✅ Backup apps.yaml completato: {backup_result.get('backup_folder')}")
                        backup_info = {
                            "backup_created": True,
                            "backup_folder": backup_result.get("backup_folder"),
                            "backup_path": backup_result.get("backup_path"),
                            "files_backed_up": backup_result.get("files_backed_up", 0),
                            "backup_skipped": False
                        }
                    else:
                        self.configurator.log(f"⚠️ Backup apps.yaml fallito: {backup_result.get('error')}")
                        backup_info = {
                            "backup_created": False, 
                            "backup_error": backup_result.get("error"),
                            "backup_skipped": False
                        }
                        
                except Exception as backup_error:
                    self.configurator.error(f"❌ Errore backup apps.yaml: {backup_error}")
                    backup_info = {
                        "backup_created": False,
                        "backup_error": str(backup_error),
                        "backup_skipped": False
                    }
            elif skip_backup:
                self.configurator.log("⏭️ Backup apps.yaml saltato (skip_backup=True)")
            else:
                backup_info = {"backup_created": False, "reason": "file_not_exists", "backup_skipped": False}
                self.configurator.log("ℹ️ File apps.yaml non esiste, nessun backup necessario")
            
            # 2. Leggi contenuto esistente
            existing_content = ""
            if os.path.exists(self.configurator.apps_yaml_path):
                with open(self.configurator.apps_yaml_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                self.configurator.log(f"📖 File esistente: {len(existing_content)} caratteri")
            else:
                existing_content = self.create_empty_apps_yaml_structure()
                self.configurator.log("📄 Creato template file vuoto")
            
            # 3. Analisi sezione esistente
            start_idx, end_idx = self.find_light_control_section(existing_content)
            existing_configs = set()
            
            if start_idx != -1 and end_idx != -1:
                section_content = existing_content[start_idx:end_idx]
                existing_configs = self.extract_lights_config_from_section(section_content)
                self.configurator.log(f"🔍 Configurazioni esistenti: {len(existing_configs)}")
            
            # 4. Calcola differenze
            new_config_ids = {self.generate_config_id(cfg) for cfg in valid_configs}
            configs_to_add = new_config_ids - existing_configs
            configs_to_remove = existing_configs - new_config_ids
            
            self.configurator.log(f"📊 Operazioni: +{len(configs_to_add)} -{len(configs_to_remove)}")
            
            # 5. Ottimizzazione: se identiche, non fare nulla
            if not configs_to_add and not configs_to_remove and start_idx != -1:
                return {
                    "success": True,
                    "message": "Configurazioni identiche, nessuna modifica necessaria",
                    "configurations_unchanged": len(existing_configs),
                    "optimized_skip": True,
                    **backup_info
                }
            
            # 6. Genera nuova sezione (qui `generate_light_control_section` riceverà la lista vuota e si comporterà correttamente)
            new_section = self.generate_light_control_section(valid_configs)
            
            # 7. Ricostruisci file completo
            new_content = self.rebuild_apps_yaml_content(
                existing_content, new_section, start_idx, end_idx
            )
            
            # 8. Salvataggio atomico e sicuro
            self.atomic_file_write(new_content)
            
            # 9. Verifica post-salvataggio
            self.verify_yaml_integrity(self.configurator.apps_yaml_path)
            
            # 10. Risultato dettagliato con info backup
            result = {
                "success": True,
                "message": f"apps.yaml aggiornato con processamento avanzato{' (backup saltato)' if skip_backup else ''}",
                "processing_method": "advanced_with_conditional_backup",
                "configurations_total": len(valid_configs),
                "configurations_added": len(configs_to_add),
                "configurations_removed": len(configs_to_remove),
                "configurations_unchanged": len(existing_configs & new_config_ids),
                "file_size": os.path.getsize(self.configurator.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "validation_passed": True,
                "integrity_verified": True,
                **backup_info
            }
            
            backup_msg = f"Backup: {backup_info.get('backup_folder', 'saltato' if skip_backup else 'N/A')}"
            self.configurator.log(f"✅ Apps.yaml processato con successo - {backup_msg}")
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ CORE: Errore processamento avanzato: {e}")
            
            # Tentativo di ripristino da backup se disponibile
            if 'backup_info' in locals() and backup_info.get("backup_created"):
                self.configurator.log("🛡️ Tentativo ripristino da backup in corso...")
                # TODO: Implementare ripristino automatico se necessario
            
            return {
                "success": False,
                "error": str(e),
                "processing_method": "advanced_with_conditional_backup",
                "timestamp": datetime.now().isoformat(),
                "backup_created": backup_info.get("backup_created", False) if 'backup_info' in locals() else False,
                "backup_skipped": skip_backup
            }

    def execute_save_advanced(self, method_type, configurations, request_data):
        """
        Metodo unificato per salvataggio avanzato
        Usato da WebSocket, Sensori e File System
        """
        return self.execute_complete_save_advanced(method_type, configurations, request_data)

    def execute_complete_save_advanced(self, method_type, configurations, request_data):
        """
        🎯 METODO CORE: Salvataggio completo Apps.yaml + Dashboard + Templates - CON BACKUP STRUTTURATO OTTIMIZZATO
        Utilizzato da tutti i sistemi di comunicazione (WebSocket, Sensori, File)
        """
        try:
            self.configurator.log(f"✨ COMPLETE SAVE ({method_type.upper()}): Inizio salvataggio completo v4.0.0 (backup ottimizzato)") # Correzione qui
            start_time = time.time()
            
            # Verifica autenticazione e blocchi
            user_id = self.configurator.security.get_user_id_unified(request_data, method_type)
            is_blocked, block_until = self.configurator.security.is_user_blocked(user_id)
            
            if is_blocked:
                return {
                    "success": False,
                    "error": "Utente temporaneamente bloccato",
                    "blocked": True,
                    "remaining_seconds": int(block_until - time.time()),
                    "method": f"{method_type}_blocked"
                }
            
            self.configurator.log(f"👤 Utente autorizzato: {user_id[:20]}") # Correzione qui
            
            # BACKUP STRUTTURATO COMPLETO UNICO (STEP 0)
            self.configurator.log("📦 STEP 0/4: Backup strutturato completo unico...") # Correzione qui
            try:
                backup_result = self.configurator.create_structured_backup(backup_type="complete")
                
                if backup_result.get("success"):
                    self.configurator.log(f"✅ STEP 0/4: Backup unico completato ({backup_result.get('files_backed_up', 0)} file)") # Correzione qui
                    backup_info = {
                        "backup_created": True,
                        "backup_folder": backup_result.get("backup_folder"),
                        "files_backed_up": backup_result.get("files_backed_up", 0),
                        "backup_path": backup_result.get("backup_path")
                    }
                else:
                    self.configurator.log(f"⚠️ STEP 0/4: Backup parziale o fallito") # Correzione qui
                    backup_info = {
                        "backup_created": False,
                        "backup_error": backup_result.get("error", "Unknown backup error")
                    }
                    
            except Exception as backup_error:
                self.configurator.error(f"❌ STEP 0/4: Errore critico backup: {backup_error}") # Correzione qui
                backup_info = {
                    "backup_created": False,
                    "backup_error": str(backup_error)
                }
            
            # STEP 1: Salva apps.yaml (SENZA backup individuale)
            self.configurator.log(f"📋 STEP 1/4: Salvataggio apps.yaml (skip backup)...") # Correzione qui
            try:
                apps_result = self.process_apps_yaml_advanced(configurations, skip_backup=True)
                
                if not apps_result.get("success"):
                    self.configurator.security.record_attempt(user_id, f"{method_type}_complete_save", False)
                    return {
                        "success": False,
                        "error": f"Errore apps.yaml: {apps_result.get('error')}",
                        "method": f"{method_type}_apps_failed",
                        "step_failed": "apps_yaml",
                        "partial_success": False,
                        **backup_info
                    }
                
                self.configurator.log(f"✅ STEP 1/4: Apps.yaml salvato ({apps_result.get('file_size', 0)} bytes)") # Correzione qui
                
            except Exception as apps_error:
                error_msg = str(apps_error)
                self.configurator.error(f"❌ STEP 1/4: Eccezione apps.yaml: {error_msg}") # Correzione qui
                self.configurator.security.record_attempt(user_id, f"{method_type}_complete_save", False)
                return {
                    "success": False,
                    "error": f"Eccezione apps.yaml: {error_msg}",
                    "method": f"{method_type}_apps_exception",
                    "step_failed": "apps_yaml",
                    **backup_info
                }
            
            # STEP 2: Genera dashboard e templates (SENZA backup individuali)
            self.configurator.log(f"🎨 STEP 2/4: Generazione dashboard e templates (skip backup)...") # Correzione qui
            try:
                dashboard_result = self.configurator.dashboard.generate_dashboard_and_templates(configurations, skip_backup=True)
                
                # Verifica dettagliata del risultato
                if dashboard_result.get("success"):
                    success_type = dashboard_result.get("success_type", "unknown")
                    self.configurator.log(f"✅ STEP 2/4: Dashboard completato - Tipo: {success_type}") # Correzione qui
                    
                    # Verifica ogni componente
                    details = dashboard_result.get("details", {})
                    templates_ok = details.get("templates", {}).get("success", False)
                    dashboard_ok = details.get("dashboard", {}).get("success", False)
                    config_ok = details.get("configuration", {}).get("success", False)
                    
                    self.configurator.log(f"📊 Componenti: Templates={templates_ok}, Dashboard={dashboard_ok}, Config={config_ok}") # Correzione qui
                    
                else:
                    self.configurator.error(f"❌ STEP 2/4: Dashboard fallita") # Correzione qui
                    self.configurator.error(f"   Errore: {dashboard_result.get('error', 'Sconosciuto')}") # Correzione qui
                    
                    # Crea notifica per l'utente
                    self.configurator.security.create_ha_notification(
                        "⚠️ SouthTech: Dashboard non generata",
                        f"Apps.yaml salvato ma dashboard richiede intervento manuale. Errore: {dashboard_result.get('error', 'Sconosciuto')[:100]}..."
                    )
                
            except Exception as dashboard_error:
                error_msg = str(dashboard_error)
                self.configurator.error(f"❌ STEP 2/4: Eccezione critica dashboard: {error_msg}") # Correzione qui
                import traceback
                self.configurator.error(f"Stack trace dashboard: {traceback.format_exc()}") # Correzione qui
                
                dashboard_result = {
                    "success": False,
                    "success_type": "critical_exception",
                    "error": error_msg,
                    "details": {
                        "templates": {"success": False, "error": f"Exception: {error_msg}"},
                        "configuration": {"success": False, "error": f"Exception: {error_msg}"},
                        "dashboard": {"success": False, "error": f"Exception: {error_msg}"},
                        "lights_config": {"success": False, "error": f"Exception: {error_msg}"}
                    }
                }
            
            # Calcola durata operazione
            operation_duration = round(time.time() - start_time, 2)
            
            # STEP 3: Risultato finale con 4 componenti
            dashboard_success = dashboard_result.get("success", False)
            success_type = dashboard_result.get("success_type", "unknown")
            
            # Crea details unificati con apps.yaml incluso
            unified_details = {
                "apps": {
                    "success": apps_result.get("success", False),
                    "error": apps_result.get("error") if not apps_result.get("success") else None,
                    "configurations_total": apps_result.get("configurations_total", 0),
                    "configurations_added": apps_result.get("configurations_added", 0),
                    "configurations_removed": apps_result.get("configurations_removed", 0),
                    "file_size": apps_result.get("file_size", 0),
                    "backup_skipped": True,
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
            
            # Calcola successo basato su 4 componenti
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
                    
                    # Details con 4 componenti + backup info UNICO
                    "details": unified_details,
                    "files_created": dashboard_result.get("files_created", {}),
                    "summary": dashboard_result.get("summary", {}),
                    
                    # Riepilogo operazione con 4 componenti
                    "operation_summary": {
                        "apps_yaml_updated": apps_success,
                        "templates_generated": templates_success,
                        "configuration_yaml_updated": config_success,
                        "dashboard_created": dashboard_files_success,
                        "total_configurations": len(configurations),
                        "total_sensors": len(configurations) * 4 + 1,
                        "dashboard_files": 1 + len(configurations),
                        "operation_duration": operation_duration,
                        "successful_components": successful_components,
                        "total_components": 4,
                        "backup_strategy": "single_complete_backup"
                    },
                    
                    # File modificati per 4 componenti
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
                    
                    # BACKUP INFO UNICO
                    **backup_info
                }
                
            else:
                # Fallimento con dettagli sui 4 componenti
                result = {
                    "success": False,
                    "message": message,
                    "method": f"{method_type}_failed",
                    "success_type": final_success_type,
                    
                    # Details con 4 componenti anche per fallimenti
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
                    
                    # BACKUP INFO UNICO anche per fallimenti
                    **backup_info
                }
            
            # Rimuovi None dai file modificati (solo per successi)
            if "files_modified" in result:
                result["files_modified"] = [f for f in result["files_modified"] if f is not None]
            
            # STEP 4: Registra tentativo e notifiche con logica 4 componenti
            success = result.get("success", False)
            self.configurator.security.record_attempt(user_id, f"{method_type}_complete_save", success)
            
            if success:
                self.configurator.log(f"✅ COMPLETE SAVE ({method_type.upper()}): Completato in {operation_duration}s") # Correzione qui
                self.configurator.log(f"📊 Componenti: Apps={apps_success}, Templates={templates_success}, Config={config_success}, Dashboard={dashboard_files_success}") # Correzione qui
                self.configurator.log(f"📦 Backup UNICO: {backup_info.get('backup_folder', 'N/A')} ({backup_info.get('files_backed_up', 0)} file)") # Correzione qui
                
                # Notifica successo con dettaglio 4 componenti + backup UNICO
                if final_success_type == "complete_success":
                    self.configurator.security.create_ha_notification(
                        "✨ SouthTech: Configurazione Completa Salvata",
                        f"Tutti e 4 i componenti generati per {len(configurations)} configurazioni via {method_type}. Backup unico: {backup_info.get('backup_folder', 'N/A')}"
                    )
                else:
                    failed_components = []
                    if not apps_success: failed_components.append("Apps.yaml")
                    if not templates_success: failed_components.append("Templates")
                    if not config_success: failed_components.append("Configuration.yaml")
                    if not dashboard_files_success: failed_components.append("Dashboard")
                    
                    self.configurator.security.create_ha_notification(
                        "⚠️ SouthTech: Salvataggio Parziale",
                        f"{successful_components}/4 componenti generati. Backup unico: {backup_info.get('backup_folder', 'N/A')}. Richiede intervento: {', '.join(failed_components)}"
                    )
                    
            else:
                self.configurator.log(f"❌ COMPLETE SAVE ({method_type.upper()}): Fallito ({successful_components}/4 componenti)") # Correzione qui
                self.configurator.log(f"📦 Backup UNICO: {backup_info.get('backup_folder', 'N/A')} ({backup_info.get('files_backed_up', 0)} file)") # Correzione qui
            
            return result
            
        except Exception as e:
            operation_duration = round(time.time() - start_time, 2) if 'start_time' in locals() else 0
            
            self.configurator.error(f"❌ COMPLETE SAVE ({method_type.upper()}): Errore critico: {e}") # Correzione qui
            import traceback
            self.configurator.error(f"Stack trace completo: {traceback.format_exc()}") # Correzione qui
            
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
            self.configurator.log("💾 WEBSOCKET: Inizio salvataggio apps.yaml...") # Correzione qui
            
            # 1. Backup se file esiste
            backup_file = None
            if os.path.exists(self.configurator.apps_yaml_path):
                backup_file = self.configurator.create_backup()
                self.configurator.log(f"📦 Backup creato: {backup_file}") # Correzione qui
            
            # 2. Salva contenuto usando metodo esistente
            self.save_yaml_content_safe(yaml_content)
            
            # 3. Verifica file salvato
            self.verify_saved_file(yaml_content)
            
            # 4. Genera helper opzionali
            helpers_created = 0
            try:
                helpers_created = self.configurator.generate_helpers_sync(configurations)
            except Exception as e:
                self.configurator.log(f"⚠️ Warning generazione helper: {e}") # Correzione qui
            
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
            
            self.configurator.log("✅ WEBSOCKET: Salvataggio completato con successo") # Correzione qui
            
            # Notifica successo
            self.configurator.security.create_ha_notification(
                "✅ SouthTech: Configurazione Salvata",
                f"Apps.yaml aggiornato con {len(configurations)} configurazioni via WebSocket"
            )
            
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ WEBSOCKET: Errore durante salvataggio: {e}") # Correzione qui
            return {
                "success": False,
                "error": str(e),
                "method": "websocket_error",
                "timestamp": datetime.now().isoformat()
            }

    def execute_yaml_save_sensor(self, yaml_content, configurations, user_id):
        """Esegue il salvataggio YAML per comando sensore (versione corretta)"""
        try:
            self.configurator.log("💾 SENSOR: Inizio salvataggio apps.yaml...") # Correzione qui
            
            # 1. Backup se file esiste
            backup_file = None
            if os.path.exists(self.configurator.apps_yaml_path):
                backup_file = self.configurator.create_backup()
                self.configurator.log(f"📦 Backup creato: {backup_file}") # Correzione qui
            else:
                self.configurator.log("📄 File apps.yaml non esiste, sarà creato") # Correzione qui
            
            # 2. Verifica/crea directory
            yaml_dir = os.path.dirname(self.configurator.apps_yaml_path)
            if not os.path.exists(yaml_dir):
                os.makedirs(yaml_dir, exist_ok=True)
                self.configurator.log(f"📁 Creata directory: {yaml_dir}") # Correzione qui
            
            # 3. Salva il contenuto usando il metodo esistente
            self.save_yaml_configuration(yaml_content)
            
            # 4. Genera helper opzionali
            helpers_created = 0
            try:
                helpers_created = self.configurator.generate_helpers_sync(configurations)
                if helpers_created > 0:
                    self.configurator.log(f"🔧 Generati {helpers_created} helper") # Correzione qui
            except Exception as e:
                self.configurator.log(f"⚠️ Warning generazione helper: {e}") # Correzione qui
            
            # 5. Risultato successo
            result = {
                "success": True,
                "message": "Configurazione salvata con successo via sensore",
                "backup_created": backup_file is not None,
                "backup_file": backup_file,
                "helpers_created": helpers_created,
                "configurations_count": len(configurations),
                "file_path": self.configurator.apps_yaml_path,
                "file_size": os.path.getsize(self.configurator.apps_yaml_path),
                "timestamp": datetime.now().isoformat(),
                "method": "sensor_success"
            }
            
            self.configurator.log("✅ SENSOR: Salvataggio completato con successo") # Correzione qui
            
            # Notifica successo in HA
            self.configurator.security.create_ha_notification(
                "✅ SouthTech: Configurazione Salvata",
                f"Apps.yaml aggiornato con {len(configurations)} configurazioni via sensore fallback"
            )
            
            return result
            
        except Exception as e:
            self.configurator.error(f"❌ SENSOR: Errore durante salvataggio: {e}") # Correzione qui
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "method": "sensor_error"
            }

    # ===============================================================
    # VALIDAZIONE E UTILITÀ
    # ===============================================================

    def validate_configurations(self, configurations):
        """Valida e filtra configurazioni valide"""
        valid_configs = []
        
        for i, config in enumerate(configurations):
            light_entity = config.get('light_entity', '').strip()
            presence_sensor_on = config.get('presence_sensor_on', '').strip()
            
            if not light_entity:
                self.configurator.log(f"⚠️ Config {i+1}: light_entity mancante, saltata") # Correzione qui
                continue
                
            if not light_entity.startswith('light.'):
                self.configurator.log(f"⚠️ Config {i+1}: light_entity non valida ({light_entity}), saltata") # Correzione qui
                continue
                
            if not presence_sensor_on:
                self.configurator.log(f"⚠️ Config {i+1}: presence_sensor_on mancante, saltata") # Correzione qui
                continue
            
            valid_configs.append(config)
        
        self.configurator.log(f"✅ Validazione: {len(valid_configs)}/{len(configurations)} configurazioni valide") # Correzione qui
        return valid_configs

    def atomic_file_write(self, content):
        """Scrittura atomica del file per evitare corruzioni"""
        temp_path = self.configurator.apps_yaml_path + ".tmp_atomic"
        
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
            os.replace(temp_path, self.configurator.apps_yaml_path)
            self.configurator.log("💾 Scrittura atomica completata") # Correzione qui
            
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
        temp_file = self.configurator.apps_yaml_path + ".tmp_write"
        
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
            os.replace(temp_file, self.configurator.apps_yaml_path)
            
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
            backup_path = os.path.join(self.configurator.backup_path, backup_file)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.configurator.apps_yaml_path)
                self.configurator.log(f"🛡️ Ripristinato da backup: {backup_file}") # Correzione qui
                return True
        except Exception as e:
            self.configurator.error(f"❌ Errore ripristino backup: {e}") # Correzione qui
        return False

    def _replace_yaml_new_format(self, content, yaml_content):
        """Sostituisce YAML nel nuovo formato con spazi corretti"""
        try:
            start_line_idx = content.find(self.configurator.new_start_line)
            if start_line_idx == -1:
                return None
            
            # Trova l'inizio del blocco (linea di #'s prima)
            start_block_idx = content.rfind(self.configurator.new_start_marker, 0, start_line_idx)
            if start_block_idx == -1:
                start_block_idx = start_line_idx
            
            # Trova la fine del blocco
            end_line_idx = content.find(self.configurator.new_end_line, start_line_idx)
            if end_line_idx != -1:
                # Trova la fine del blocco (linea di #'s dopo)
                end_block_idx = content.find(self.configurator.new_end_marker, end_line_idx)
                if end_block_idx != -1:
                    end_block_idx += len(self.configurator.new_end_marker)
                    
                    # CORREZIONE BILANCIATA: Mantiene spazi di separazione
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
            self.configurator.error(f"Errore sostituzione nuovo formato: {e}") # Correzione qui
            return None
    
    def _replace_yaml_old_format(self, content, yaml_content):
        """Sostituisce YAML nel formato vecchio con spazi corretti"""
        try:
            start_idx = content.find(self.configurator.start_marker)
            end_idx = content.find(self.configurator.end_marker)
            
            if start_idx != -1 and end_idx != -1:
                end_idx += len(self.configurator.end_marker)
                
                # CORREZIONE BILANCIATA: Mantieni spazi di separazione
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
            self.configurator.error(f"Errore sostituzione formato vecchio: {e}") # Correzione qui
            return None

    # ===============================================================
    # ANALISI E STRUTTURA YAML
    # ===============================================================

    def find_light_control_section(self, content):
        """
        Trova la sezione controllo luci nel contenuto YAML
        Supporta sia formato nuovo che vecchio
        
        Returns:
            tuple: (start_idx, end_idx) oppure (-1, -1) se non trovata
        """
        try:
            # Prova formato nuovo prima
            start_line_idx = content.find(self.configurator.new_start_line)
            if start_line_idx != -1:
                self.configurator.log("✅ Trovata sezione formato NUOVO") # Correzione qui
                # Trova l'inizio del blocco (linea di #'s prima)
                start_block_idx = content.rfind(self.configurator.new_start_marker, 0, start_line_idx)
                if start_block_idx == -1:
                    start_block_idx = start_line_idx
                
                # Trova la fine del blocco
                end_line_idx = content.find(self.configurator.new_end_line, start_line_idx)
                if end_line_idx != -1:
                    # Trova la fine del blocco (linea di #'s dopo)
                    end_block_idx = content.find(self.configurator.new_end_marker, end_line_idx)
                    if end_block_idx != -1:
                        end_block_idx += len(self.configurator.new_end_marker)
                        return (start_block_idx, end_block_idx)
            
            # Prova formato vecchio
            old_start_idx = content.find(self.configurator.start_marker)
            old_end_idx = content.find(self.configurator.end_marker)
            
            if old_start_idx != -1 and old_end_idx != -1:
                self.configurator.log("✅ Trovata sezione formato VECCHIO") # Correzione qui
                old_end_idx += len(self.configurator.end_marker)
                return (old_start_idx, old_end_idx)
            
            # Nessuna sezione trovata
            self.configurator.log("ℹ️ Nessuna sezione controllo luci trovata") # Correzione qui
            return (-1, -1)
            
        except Exception as e:
            self.configurator.error(f"Errore ricerca sezione controllo luci: {e}") # Correzione qui
            return (-1, -1)

    def extract_lights_config_from_section(self, section_content):
        """
        Estrae le configurazioni luci dalla sezione YAML
        
        Returns:
            set: Set di ID configurazioni esistenti
        """
        try:
            configs = set()
            
            # Parsing del contenuto YAML
            parsed = yaml.safe_load(section_content)
            
            if parsed and 'light_presence' in parsed:
                lights_config = parsed['light_presence'].get('light_presence', [])
                
                for cfg in lights_config:
                    if 'light_entity' in cfg:
                        # Genera ID configurazione basato su light_entity
                        config_id = self.generate_config_id(cfg)
                        configs.add(config_id)
            
            self.configurator.log(f"🔍 Estratte {len(configs)} configurazioni esistenti") # Correzione qui
            return configs
            
        except Exception as e:
            self.configurator.error(f"Errore estrazione configurazioni: {e}") # Correzione qui
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
            self.configurator.error(f"Errore generazione ID configurazione: {e}") # Correzione qui
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
            parsed = yaml.safe_load(content)
            
            if parsed is None and content.strip():
                raise Exception("YAML parsing risulta vuoto con contenuto presente")
            
            self.configurator.log(f"✅ Integrità YAML verificata: {file_path}") # Correzione qui
            return True
            
        except Exception as e:
            self.configurator.error(f"❌ Errore integrità YAML {file_path}: {e}") # Correzione qui
            raise

    def generate_light_control_section(self, configurations):
        """
        Genera la sezione di controllo luci completa - VERSIONE MODIFICATA
        Gestisce il caso in cui non ci siano configurazioni.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Inizio sezione con indentazione corretta
            yaml_content = "################################################################################\n"
            yaml_content += "#                      START CONTROLLO LUCI AUTOMATICHE                        #\n"
            yaml_content += "################################################################################\n"
            yaml_content += f"# Generato automaticamente da SouthTech Configurator il {timestamp}\n"
            yaml_content += "light_presence:\n"
            yaml_content += "  ##############################################################################\n"
            yaml_content += "  module: light_presence_control\n"
            yaml_content += "  class: LightPresenceControl\n"
            yaml_content += "  log_level: DEBUG\n"
            
            # --- INIZIO LOGICA MODIFICATA ---
            if not configurations:
                # Se non ci sono configurazioni, inserisci una lista vuota
                self.configurator.log("ℹ️ Nessuna configurazione luci fornita. Genero sezione con lista vuota.")
                yaml_content += "  light_presence: []\n"
            else:
                # Se ci sono configurazioni, procedi come prima
                yaml_content += "  light_presence:\n"
                for i, config in enumerate(configurations):
                    light_entity = config.get('light_entity', '')
                    if not light_entity:
                        continue
                        
                    base_id = light_entity.replace('light.', '')
                    
                    yaml_content += f"    # Configurazione {i + 1} - {base_id}\n"
                    yaml_content += f"    - light_entity: {light_entity}\n"
                    yaml_content += f"      presence_sensor_on: {config.get('presence_sensor_on', '')}\n"
                    yaml_content += f"      presence_sensor_off: {config.get('presence_sensor_off', '')}\n"
                    yaml_content += f"      illuminance_sensor: {config.get('illuminance_sensor', '')}\n"
                    # Parametri helper
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
            # --- FINE LOGICA MODIFICATA ---

            yaml_content += "################################################################################\n"
            yaml_content += "#                      END CONTROLLO LUCI AUTOMATICHE                          #\n"
            yaml_content += "################################################################################\n"
            
            return yaml_content
            
        except Exception as e:
            self.configurator.error(f"Errore generazione sezione controllo luci: {e}")
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
                    self.configurator.log(f"🔍 Errore constructor in file inclusi: {error_str}") # Correzione qui
                    
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
            self.configurator.log(f"Errore sostituzione include: {e}") # Correzione qui
            return content

    def debug_yaml_structure(self, content):
        """
        🔍 Debug della struttura YAML per verificare indentazioni
        """
        try:
            lines = content.split('\n')
            self.configurator.log("🔍 === DEBUG STRUTTURA YAML ===") # Correzione qui
            
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                    
                indent_count = len(line) - len(line.lstrip())
                
                if 'dashboards:' in line:
                    self.configurator.log(f"📍 Riga {i:3d}: dashboards: (indent: {indent_count})") # Correzione qui
                elif line.strip().endswith(':') and 'dashboards' not in line:
                    self.configurator.log(f"📍 Riga {i:3d}: {line.strip()} (indent: {indent_count})") # Correzione qui
                elif ':' in line and not line.strip().startswith('#'):
                    self.configurator.log(f"📋 Riga {i:3d}: {line.strip()} (indent: {indent_count})") # Correzione qui
            
            self.configurator.log("🔍 === FINE DEBUG STRUTTURA ===") # Correzione qui
            
        except Exception as e:
            self.configurator.log(f"Errore debug struttura: {e}") # Correzione qui

    # ===============================================================
    # GESTIONE CONFIGURAZIONE E CLEANUP
    # ===============================================================
    
    def on_configuration_change(self, change_type, data):
        """Gestisce notifiche di cambio configurazione per il modulo YAML"""
        self.configurator.log(f"📝 YAML: Ricevuta notifica cambio configurazione: {change_type}") # Correzione qui
        
        if change_type == "light_entity_changed":
            # Aggiorna configurazioni correlate
            self.configurator.log("🔄 Aggiornamento configurazioni per cambio light_entity") # Correzione qui
        elif change_type == "sensor_changed":
            # Aggiorna sensori correlati
            self.configurator.log("🔄 Aggiornamento sensori per cambio configurazione") # Correzione qui
    
    def cleanup(self):
        """Cleanup del modulo YAML alla terminazione"""
        try:
            self.configurator.log("🧹 YAML: Inizio cleanup...") # Correzione qui
            
            # Rimuovi file temporanei se esistono
            temp_files = [
                self.configurator.apps_yaml_path + ".tmp_save",
                self.configurator.apps_yaml_path + ".tmp_atomic",
                self.configurator.apps_yaml_path + ".tmp_write",
                self.configurator.apps_yaml_path + ".safety_backup"
            ]
            
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        self.configurator.log(f"🗑️ Rimosso file temporaneo: {os.path.basename(temp_file)}") # Correzione qui
                    except Exception as e:
                        self.configurator.error(f"Errore rimozione {temp_file}: {e}") # Correzione qui
            
            # Verifica finale integrità
            if os.path.exists(self.configurator.apps_yaml_path):
                is_valid, message = self.configurator.check_file_integrity()
                self.configurator.log(f"📋 Integrità finale apps.yaml: {message}") # Correzione qui
            
            self.configurator.log("✅ YAML: Cleanup completato") # Correzione qui
            
        except Exception as e:
            self.configurator.error(f"❌ Errore cleanup YAML: {e}") # Correzione qui
