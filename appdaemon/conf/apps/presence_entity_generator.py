import appdaemon.plugins.hass.hassapi as hass
import os
import re
from datetime import datetime

class PresenceEntityGenerator(hass.Hass):
    def initialize(self):
        self.log("Attendo inizializzazione di LightPresenceControl...", level="INFO")
        self.run_in(self.try_generate, 1)

    def try_generate(self, kwargs):
        lpc_app = self.get_app("light_presence")
        if not lpc_app:
            self.log("⏳ LightPresenceControl non ancora disponibile, ritento tra 2 secondi...", level="WARNING")
            self.run_in(self.try_generate, 2)
            return

        presence_configs = lpc_app.args.get("light_presence", [])
        self.generate_files(presence_configs)

    def generate_files(self, presence_configs):
        self.log("✅ LightPresenceControl trovato, procedo con la generazione.", level="INFO")
        
        config_path = "/homeassistant/www/configurations"
        ib_path = os.path.join(config_path, "input_boolean.yaml")
        in_path = os.path.join(config_path, "input_number.yaml")
        is_path = os.path.join(config_path, "input_select.yaml")

        # Genera gli ID dalle configurazioni
        config_ib_ids = set()
        config_in_ids = set()
        config_is_ids = set()
        
        for cfg in presence_configs:
            light_entity = cfg.get("light_entity", "").strip()
            if not light_entity:
                continue
                
            base_id = light_entity.split(".")[-1] if "." in light_entity else light_entity
            
            # Genera gli ID per ogni tipo di entità
            self.generate_entity_ids(cfg, base_id, config_ib_ids, config_in_ids, config_is_ids)

        # Processa i file
        self.process_yaml_file(ib_path, "input_boolean", config_ib_ids, presence_configs)
        self.process_yaml_file(in_path, "input_number", config_in_ids, presence_configs)
        self.process_yaml_file(is_path, "input_select", config_is_ids, presence_configs)

        self.log(f"✅ Sincronizzazione completata per {len(config_ib_ids)} input boolean, {len(config_in_ids)} input number e {len(config_is_ids)} input select", level="INFO")
        self.log("ℹ️ Assicurati di avere in configuration.yaml:", level="WARNING")
        self.log("  input_boolean: !include input_boolean.yaml", level="WARNING")
        self.log("  input_number: !include input_number.yaml", level="WARNING")
        self.log("  input_select: !include input_select.yaml", level="WARNING")

    def generate_entity_ids(self, cfg, base_id, ib_ids, in_ids, is_ids):
        """Genera gli ID delle entità per ogni configurazione"""
        # Input Boolean entities
        boolean_fields = [
            "enable_sensor", "enable_manual_activation_sensor", 
            "enable_manual_activation_light_sensor", "enable_automation",
            "enable_illuminance_filter", "enable_illuminance_automation"
        ]
        
        for field in boolean_fields:
            # 🔧 FIX: Aggiunto str() per sicurezza
            if field in cfg and str(cfg[field]).startswith("input_boolean."):
                ib_ids.add(f"{base_id}_{field}")

        # Input Number entities
        number_fields = [
            "timer_minutes_on_push", "timer_filter_on_push", "timer_minutes_on_time",
            "timer_filter_on_time", "timer_seconds_max_lux", "min_lux_activation",
            "max_lux_activation", "turn_on_light_offset", "turn_off_light_offset"
        ]
        
        for field in number_fields:
            # 🔧 FIX: Aggiunto str() per sicurezza
            if field in cfg and str(cfg[field]).startswith("input_number."):
                in_ids.add(f"{base_id}_{field}")

        # Input Select entities
        select_fields = ["automatic_enable_automation", "light_sensor_config"]
        
        for field in select_fields:
            # 🔧 FIX: Aggiunto str() per sicurezza
            if field in cfg and str(cfg[field]).startswith("input_select."):
                is_ids.add(f"{base_id}_{field}")

    def process_yaml_file(self, path, entity_type, config_ids, presence_configs):
        """Processa un file YAML gestendo la sincronizzazione completa"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Leggi il contenuto esistente
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().splitlines()
            else:
                content = []

            # Controlla se il file è vuoto o non esiste
            file_is_empty = self.is_file_empty_or_nonexistent(path)
            
            if file_is_empty:
                # Crea file con header decorativo e struttura base
                content = self.create_empty_file_structure(entity_type)
                self.log(f"📋 Creato nuovo file {path} con struttura base", level="INFO")

            # Trova le sezioni generate automaticamente
            start_marker, end_marker = self.get_section_markers(entity_type)
            start_idx, end_idx = self.find_generated_section(content, start_marker, end_marker)
            
            # Leggi le entità esistenti nella sezione generata
            existing_generated_ids = set()
            if start_idx != -1 and end_idx != -1:
                section_content = content[start_idx:end_idx+1]
                existing_generated_ids = self.extract_ids_from_section(section_content, entity_type)

            # Determina operazioni necessarie
            ids_to_add = config_ids - existing_generated_ids
            ids_to_remove = existing_generated_ids - config_ids
            
            self.log(f"📊 {entity_type}: da aggiungere {len(ids_to_add)}, da rimuovere {len(ids_to_remove)}", level="INFO")

            # Se non ci sono cambiamenti, esci
            if not ids_to_add and not ids_to_remove:
                self.log(f"ℹ️ Nessuna modifica necessaria per {path}", level="DEBUG")
                return

            # Genera i nuovi blocchi
            new_blocks = []
            if config_ids:  # Solo se ci sono configurazioni
                for cfg in presence_configs:
                    light_entity = cfg.get("light_entity", "").strip()
                    if not light_entity:
                        continue
                    
                    base_id = light_entity.split(".")[-1] if "." in light_entity else light_entity
                    friendly_base = " ".join([word.capitalize() for word in base_id.split("_")])
                    
                    # Genera i blocchi per ogni tipo di entità
                    if entity_type == "input_boolean":
                        new_blocks.extend(self.generate_input_boolean_blocks(cfg, base_id, friendly_base, config_ids))
                    elif entity_type == "input_number":
                        new_blocks.extend(self.generate_input_number_blocks(cfg, base_id, friendly_base, config_ids))
                    elif entity_type == "input_select":
                        new_blocks.extend(self.generate_input_select_blocks(cfg, base_id, friendly_base, config_ids))

            # Ricostruisci il contenuto
            new_content = self.rebuild_file_content(content, entity_type, new_blocks, start_idx, end_idx)

            # Scrivi il file
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_content).rstrip() + "\n")
            
            self.log(f"📄 File {path} aggiornato correttamente", level="INFO")

        except Exception as e:
            self.log(f"❌ Errore durante l'elaborazione di {path}: {str(e)}", level="ERROR")

    def generate_input_boolean_blocks(self, cfg, base_id, friendly_base, config_ids):
        """Genera i blocchi per gli input boolean"""
        blocks = []
        boolean_fields = [
            ("enable_sensor", "Enable Sensor"),
            ("enable_manual_activation_sensor", "Enable Manual Activation Sensor"),
            ("enable_manual_activation_light_sensor", "Enable Manual Activation Light Sensor"),
            ("enable_automation", "Enable Automation"),
            ("enable_illuminance_filter", "Enable Illuminance Filter"),
            ("enable_illuminance_automation", "Enable Illuminance Automation")
        ]
        
        for field, friendly_name in boolean_fields:
            entity_id = f"{base_id}_{field}"
            # 🔧 FIX: Aggiunto str() per sicurezza
            if entity_id in config_ids and field in cfg and str(cfg[field]).startswith("input_boolean."):
                blocks.append(
                    f"{entity_id}:\n"
                    f"  name: {friendly_base} {friendly_name}"
                )
        
        return blocks

    def generate_input_number_blocks(self, cfg, base_id, friendly_base, config_ids):
        """Genera i blocchi per gli input number"""
        blocks = []
        number_configs = {
            "timer_minutes_on_push": {
                "name": "Timer Minutes On Push",
                "min": 0, "max": 60, "step": 1, "unit": "min"
            },
            "timer_filter_on_push": {
                "name": "Timer Filter On Push",
                "min": 0, "max": 600, "step": 1, "unit": "sec"
            },
            "timer_minutes_on_time": {
                "name": "Timer Minutes On Time",
                "min": 0, "max": 60, "step": 1, "unit": "min"
            },
            "timer_filter_on_time": {
                "name": "Timer Filter On Time",
                "min": 0, "max": 600, "step": 1, "unit": "sec"
            },
            "timer_seconds_max_lux": {
                "name": "Timer Seconds Max Lux",
                "min": 0, "max": 10, "step": 1, "unit": "sec"
            },
            "min_lux_activation": {
                "name": "Min Lux Activation",
                "min": 0, "max": 100, "step": 0.1, "unit": "lux"
            },
            "max_lux_activation": {
                "name": "Max Lux Activation",
                "min": 0, "max": 300, "step": 0.1, "unit": "lux"
            },
            "turn_on_light_offset": {
                "name": "Turn On Light Offset",
                "min": 0, "max": 60, "step": 0.1, "unit": "sec"
            },
            "turn_off_light_offset": {
                "name": "Turn Off Light Offset",
                "min": 0, "max": 600, "step": 1, "unit": "sec"
            }
        }
        
        for field, config in number_configs.items():
            entity_id = f"{base_id}_{field}"
            # 🔧 FIX: Aggiunto str() per sicurezza
            if entity_id in config_ids and field in cfg and str(cfg[field]).startswith("input_number."):
                blocks.append(
                    f"{entity_id}:\n"
                    f"  name: {friendly_base} {config['name']}\n"
                    f"  min: {config['min']}\n"
                    f"  max: {config['max']}\n"
                    f"  step: {config['step']}\n"
                    f"  unit_of_measurement: \"{config['unit']}\"\n"
                    f"  mode: box"
                )
        
        return blocks

    def generate_input_select_blocks(self, cfg, base_id, friendly_base, config_ids):
        """Genera i blocchi per gli input select"""
        blocks = []
        select_configs = {
            "automatic_enable_automation": {
                "name": "Automatic Enable Automation",
                "icon": "mdi:motion-sensor",
                "options": ["Push", "Time", "All"]
            },
            "light_sensor_config": {
                "name": "Light Sensor Config",
                "icon": "mdi:motion-sensor",
                "options": ["On", "Off", "All"]
            }
        }
        
        for field, config in select_configs.items():
            entity_id = f"{base_id}_{field}"
            # 🔧 FIX: Aggiunto str() per sicurezza
            if entity_id in config_ids and field in cfg and str(cfg[field]).startswith("input_select."):
                options_str = "\n".join([f"    - \"{option}\"" for option in config['options']])
                blocks.append(
                    f"{entity_id}:\n"
                    f"  name: {friendly_base} {config['name']}\n"
                    f"  icon: {config['icon']}\n"
                    f"  options:\n{options_str}"
                )
        
        return blocks

    def create_empty_file_structure(self, entity_type):
        """Crea la struttura base per un file vuoto"""
        headers = {
            "input_boolean": "INPUT BOOLEAN",
            "input_number": "INPUT NUMBER",
            "input_select": "INPUT SELECT"
        }
        
        header = headers.get(entity_type, entity_type.upper())
        
        return [
            "################################################################################",
            "#                                                                              #",
            f"#                                {header:^14}                                #",
            "#                                                                              #",
            "################################################################################"
        ]

    def get_section_markers(self, entity_type):
        """Restituisce i marcatori di inizio e fine sezione"""
        start_marker = "################################################################################"
        end_marker = "################################################################################"
        
        return start_marker, end_marker

    def find_generated_section(self, content, start_marker, end_marker):
        """Trova la sezione generata automaticamente"""
        start_idx = -1
        end_idx = -1
        
        # Cerca i marcatori specifici per le sezioni generate
        start_pattern = "START PRESENCE ENTITY GENERATOR"
        end_pattern = "END PRESENCE ENTITY GENERATOR"
        
        for i, line in enumerate(content):
            if start_pattern in line:
                start_idx = i
            elif end_pattern in line and start_idx != -1:
                end_idx = i
                break
        
        return start_idx, end_idx

    def extract_ids_from_section(self, section_content, entity_type):
        """Estrae gli ID delle entità dalla sezione generata"""
        ids = set()
        pattern = r"^([a-zA-Z0-9_]+):"
        
        for line in section_content:
            match = re.match(pattern, line)
            if match:
                entity_id = match.group(1)
                # Verifica che sia un'entità presence generata (contiene i campi noti)
                presence_fields = [
                    "enable_sensor", "enable_manual_activation_sensor", 
                    "enable_manual_activation_light_sensor", "enable_automation",
                    "enable_illuminance_filter", "enable_illuminance_automation",
                    "timer_minutes_on_push", "timer_filter_on_push", "timer_minutes_on_time",
                    "timer_filter_on_time", "timer_seconds_max_lux", "min_lux_activation",
                    "max_lux_activation", "turn_on_light_offset", "turn_off_light_offset",
                    "automatic_enable_automation", "light_sensor_config"
                ]
                
                if any(field in entity_id for field in presence_fields):
                    ids.add(entity_id)
        
        return ids

    def rebuild_file_content(self, content, entity_type, new_blocks, start_idx, end_idx):
        """Ricostruisce il contenuto del file con le nuove entità"""
        if not new_blocks:
            # Se non ci sono nuovi blocchi, rimuovi solo la sezione esistente
            if start_idx != -1 and end_idx != -1:
                return content[:start_idx] + content[end_idx+1:]
            return content

        # Prepara i marcatori
        start_marker = "################################################################################"
        start_comment = "#                     START PRESENCE ENTITY GENERATOR                          #"
        end_comment = "#                      END PRESENCE ENTITY GENERATOR                           #"
        end_marker = "################################################################################"

        # Costruisci la nuova sezione
        new_section = []
        new_section.append("")  # Riga vuota prima della cornice
        new_section.append(start_marker)
        new_section.append(start_comment)
        new_section.append(start_marker)
        
        # Aggiungi i blocchi delle entità
        for i, block in enumerate(new_blocks):
            lines = block.split("\n")
            for line in lines:
                if line.strip():
                    new_section.append(line)
                else:
                    new_section.append("")
            
            # Aggiungi separatore dopo ogni blocco, escluso l'ultimo
            if i < len(new_blocks) - 1:
                new_section.append("################################################################################")
        
        new_section.append(start_marker)
        new_section.append(end_comment)
        new_section.append(end_marker)

        # Determina dove inserire la nuova sezione
        if start_idx != -1 and end_idx != -1:
            # Sostituisci la sezione esistente
            return content[:start_idx] + new_section + content[end_idx+1:]
        else:
            # Inserisci la nuova sezione alla fine del file
            return content + new_section

    def is_file_empty_or_nonexistent(self, path):
        """Controlla se il file non esiste o è vuoto (ignorando spazi e commenti)"""
        if not os.path.exists(path):
            return True
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            if not content:
                return True
            
            # Controlla se ci sono solo commenti e spazi
            lines = content.split('\n')
            meaningful_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            return len(meaningful_lines) == 0
            
        except Exception as e:
            self.log(f"❌ Errore controllo file vuoto {path}: {e}", level="ERROR")
            return True
