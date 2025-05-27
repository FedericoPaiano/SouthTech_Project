import appdaemon.plugins.hass.hassapi as hass
import os
import re
from datetime import datetime

class LightTemplateGenerator(hass.Hass):
    def initialize(self):
        self.log("Attendo inizializzazione di LightConfigControl...", level="INFO")
        self.run_in(self.try_generate, 1)

    def try_generate(self, kwargs):
        lcc_app = self.get_app("light_config")
        if not lcc_app:
            self.log("⏳ LightConfigControl non ancora disponibile, ritento tra 2 secondi...", level="WARNING")
            self.run_in(self.try_generate, 2)
            return

        light_configs = lcc_app.args.get("light_config", [])
        self.generate_files(light_configs)

    def generate_files(self, light_configs):
        self.log("✅ LightConfigControl trovato, procedo con la generazione.", level="INFO")
        
        config_path = "/homeassistant/www/configurations"
        ib_path = os.path.join(config_path, "input_boolean.yaml")
        tl_path = os.path.join(config_path, "lights.yaml")

        # Genera gli ID dalle configurazioni
        config_ib_ids = set()
        config_tl_ids = set()
        
        for cfg in light_configs:
            light_entity = cfg.get("light_entity", "").strip()
            if not light_entity:
                continue
                
            base_id = light_entity.split(".")[-1] if "." in light_entity else light_entity
            normalized_base_id = base_id.lower().replace(" ", "_")
            template_id = f"{normalized_base_id}_template_state"
            light_id = f"{normalized_base_id}_template_light"
            
            config_ib_ids.add(template_id)
            config_tl_ids.add(light_id)

        # Processa i file
        self.process_yaml_file(ib_path, "input_boolean", config_ib_ids, light_configs)
        self.process_yaml_file(tl_path, "template_lights", config_tl_ids, light_configs)

        self.log(f"✅ Sincronizzazione completata per {len(config_ib_ids)} input boolean e {len(config_tl_ids)} template lights", level="INFO")
        self.log("ℹ️ Assicurati di avere in configuration.yaml:", level="WARNING")
        self.log("  input_boolean: !include input_boolean.yaml", level="WARNING")
        self.log("  light: !include lights.yaml", level="WARNING")

    def process_yaml_file(self, path, entity_type, config_ids, light_configs):
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
                for cfg in light_configs:
                    light_entity = cfg.get("light_entity", "").strip()
                    if not light_entity:
                        continue
                    
                    base_id = light_entity.split(".")[-1] if "." in light_entity else light_entity
                    normalized_base_id = base_id.lower().replace(" ", "_")
                    
                    if entity_type == "input_boolean":
                        template_id = f"{normalized_base_id}_template_state"
                        if template_id in config_ids:
                            new_blocks.append(self.generate_input_boolean_block(template_id, base_id))
                    else:  # template_lights
                        light_id = f"{normalized_base_id}_template_light"
                        if light_id in config_ids:
                            template_id = f"{normalized_base_id}_template_state"
                            new_blocks.append(self.generate_template_light_block(light_id, normalized_base_id, template_id, base_id))

            # Ricostruisci il contenuto
            new_content = self.rebuild_file_content(content, entity_type, new_blocks, start_idx, end_idx)

            # Scrivi il file
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_content).rstrip() + "\n")
            
            self.log(f"📄 File {path} aggiornato correttamente", level="INFO")

        except Exception as e:
            self.log(f"❌ Errore durante l'elaborazione di {path}: {str(e)}", level="ERROR")

    def create_empty_file_structure(self, entity_type):
        """Crea la struttura base per un file vuoto"""
        if entity_type == "template_lights":
            return [
                "################################################################################",
                "#                                                                              #",
                "#                                   LIGHTS                                     #",
                "#                                                                              #",
                "################################################################################",
                "- platform: template",
                "  lights:"
            ]
        else:  # input_boolean
            return [
                "################################################################################",
                "#                                                                              #",
                "#                                INPUT BOOLEAN                                 #",
                "#                                                                              #",
                "################################################################################"
            ]

    def get_section_markers(self, entity_type):
        """Restituisce i marcatori di inizio e fine sezione"""
        if entity_type == "template_lights":
            start_marker = "    ############################################################################"
            end_marker = "    ############################################################################"
        else:  # input_boolean
            start_marker = "################################################################################"
            end_marker = "################################################################################"
        
        return start_marker, end_marker

    def find_generated_section(self, content, start_marker, end_marker):
        """Trova la sezione generata automaticamente"""
        start_idx = -1
        end_idx = -1
        
        # Cerca i marcatori specifici per le sezioni generate
        start_pattern = "START LIGHT TEMPLATE GENERATOR ENTITY"
        end_pattern = "END LIGHT TEMPLATE GENERATOR ENTITY"
        
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
        if entity_type == "template_lights":
            pattern = r"^\s{4}([a-zA-Z0-9_]+):"
        else:  # input_boolean
            pattern = r"^([a-zA-Z0-9_]+):"
        
        for line in section_content:
            match = re.match(pattern, line)
            if match:
                # Verifica che sia un'entità template generata
                entity_id = match.group(1)
                if entity_id.endswith("_template_state") or entity_id.endswith("_template_light"):
                    ids.add(entity_id)
        
        return ids

    def generate_input_boolean_block(self, template_id, base_id):
        """Genera il blocco per un input boolean"""
        return (
            f"{template_id}:\n"
            f"  name: Stato Smart Mode {base_id.capitalize()}"
        )

    def generate_template_light_block(self, light_id, normalized_base_id, template_id, base_id):
        """Genera il blocco per una template light"""
        return (
            f"{light_id}:\n"
            f"  unique_id: {normalized_base_id}_template_light\n"
            f"  friendly_name: Luce Virtuale {base_id.capitalize()}\n"
            f"  value_template: \"{{{{ is_state('input_boolean.{template_id}', 'on') }}}}\"\n"
            f"  turn_on:\n"
            f"    action: input_boolean.turn_on\n"
            f"    target:\n"
            f"      entity_id: input_boolean.{template_id}\n"
            f"  turn_off:\n"
            f"    action: input_boolean.turn_off\n"
            f"    target:\n"
            f"      entity_id: input_boolean.{template_id}"
        )

    def rebuild_file_content(self, content, entity_type, new_blocks, start_idx, end_idx):
        """Ricostruisce il contenuto del file con le nuove entità"""
        if not new_blocks:
            # Se non ci sono nuovi blocchi, rimuovi solo la sezione esistente
            if start_idx != -1 and end_idx != -1:
                return content[:start_idx] + content[end_idx+1:]
            return content

        # Prepara i marcatori e l'indentazione
        if entity_type == "template_lights":
            start_marker = "    ############################################################################"
            start_comment = "    #                 START LIGHT TEMPLATE GENERATOR ENTITY                    #"
            end_comment = "    #                  END LIGHT TEMPLATE GENERATOR ENTITY                     #"
            end_marker = "    ############################################################################"
            indent = 4
        else:  # input_boolean
            start_marker = "################################################################################"
            start_comment = "#                   START LIGHT TEMPLATE GENERATOR ENTITY                      #"
            end_comment = "#                    END LIGHT TEMPLATE GENERATOR ENTITY                       #"
            end_marker = "################################################################################"
            indent = 0

        # Costruisci la nuova sezione
        new_section = []
        new_section.append("")  # Riga vuota prima della cornice
        new_section.append(start_marker)
        new_section.append(start_comment)
        new_section.append(start_marker)
        
        # Aggiungi i blocchi delle entità
        for i, block in enumerate(new_blocks):
            if i > 0:
                new_section.append("")  # Riga vuota tra i blocchi
            
            lines = block.split("\n")
            for line in lines:
                if line.strip():
                    new_section.append(" " * indent + line)
                else:
                    new_section.append("")
            
            # Aggiungi separatore dopo ogni blocco, escluso l'ultimo
            if i < len(new_blocks) - 1:
                if entity_type == "template_lights":
                    new_section.append("    ############################################################################")
                else:  # input_boolean
                    new_section.append("################################################################################")
        
        new_section.append(end_marker)
        new_section.append(end_comment)
        new_section.append(end_marker)

        # Determina dove inserire la nuova sezione
        if start_idx != -1 and end_idx != -1:
            # Sostituisci la sezione esistente
            return content[:start_idx] + new_section + content[end_idx+1:]
        else:
            # Inserisci la nuova sezione alla fine del file
            insert_pos = self.find_insertion_point(content, entity_type)
            return content[:insert_pos] + new_section + content[insert_pos:]

    def find_insertion_point(self, content, entity_type):
        """Trova il punto dove inserire la nuova sezione"""
        if entity_type == "template_lights":
            # Trova "lights:" e inserisci dopo
            for i, line in enumerate(content):
                if "lights:" in line and not line.strip().startswith("#"):
                    return i + 1
            return len(content)
        else:  # input_boolean
            # Inserisci alla fine del file
            return len(content)

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
