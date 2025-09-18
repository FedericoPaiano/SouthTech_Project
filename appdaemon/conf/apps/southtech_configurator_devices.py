"""
Classe per il parsing dei dispositivi dalle configurazioni YAML di ESPHome
"""
import os
import yaml
import re
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple
from functools import lru_cache

class DeviceConfig:
    """Rappresenta la configurazione di un dispositivo"""
    def __init__(self, model: str, number: str, filename: str, friendly_name: str, configuration: Optional[Dict] = None):
        self.model = model
        self.number = number
        self.filename = filename
        self.friendly_name = friendly_name
        self.configuration = configuration or {}
    
    def __repr__(self) -> str:
        return f"DeviceConfig(model={self.model}, number={self.number}, filename={self.filename})"

    def to_dict(self) -> Dict:
        """Converte la configurazione in un dizionario per serializzazione JSON"""
        return {
            "model": self.model,
            "number": self.number,
            "filename": self.filename,
            "friendly_name": self.friendly_name,
            "configuration": self.configuration
        }

class DeviceConfigurationParser:
    """Parser per le configurazioni dei dispositivi con caching"""
    def __init__(self, hardware_path: str):
        """Inizializza il parser con il percorso alla cartella hardware"""
        self.hardware_path = hardware_path
        self._cache: Dict[str, Tuple[float, DeviceConfig]] = {}  # {filename: (timestamp, config)}
        self._cache_ttl = 300  # 5 minuti di TTL per la cache

    def _is_cache_valid(self, filename: str) -> bool:
        """Verifica se la cache per un file è ancora valida"""
        if filename not in self._cache:
            return False
        timestamp, _ = self._cache[filename]
        return time.time() - timestamp < self._cache_ttl

    @lru_cache(maxsize=32)
    def _custom_yaml_constructor(self, tag: str, value: str) -> str:
        """Gestisce tag YAML personalizzati come !secret e !lambda con caching"""
        return f"{tag} {value}"

    def _create_custom_loader(self) -> yaml.SafeLoader:
        """Crea un loader YAML personalizzato che gestisce i tag speciali"""
        class CustomLoader(yaml.SafeLoader):
            pass

        def constructor(loader: yaml.SafeLoader, node: yaml.Node) -> str:
            if isinstance(node, yaml.ScalarNode):
                return self._custom_yaml_constructor(node.tag, loader.construct_scalar(node))
            elif isinstance(node, yaml.SequenceNode):
                return self._custom_yaml_constructor(node.tag, str(loader.construct_sequence(node)))
            return self._custom_yaml_constructor(node.tag, "Unknown")

        # Registra handler per tag comuni
        for tag in ['!secret', '!lambda', '!include']:
            CustomLoader.add_constructor(tag, constructor)

        return CustomLoader

    def _extract_model_info(self, filename: str) -> tuple[Optional[str], Optional[str]]:
        """Estrae il modello e il numero dal nome file"""
        try:
            # Rimuovi l'estensione
            base = os.path.splitext(filename)[0].lower()

            # Cerca la presenza di a8s o a8 nel nome del file
            if '_a8s_' in base:
                # Cerca un numero a 2 cifre dopo "a8s"
                match = re.search(r'a8s_(\d{2})', base)
                if match:
                    return 'AION_A8SR', match.group(1)
            elif '_a8_' in base:
                # Cerca un numero a 2 cifre dopo "a8"
                match = re.search(r'a8_(\d{2})', base)
                if match:
                    return 'AION_A8R', match.group(1)

            # Se nessun pattern corrisponde, prova a determinare il tipo dal contenuto del nome
            if '_a8s_' in base:
                # Cerca un numero a 2 cifre dopo "a8s"
                match = re.search(r'a8s_(\d{2})', base)
                if match:
                    return 'AION_A8SR', match.group(1)
            elif '_a8_' in base:
                # Cerca un numero a 2 cifre dopo "a8"
                match = re.search(r'a8_(\d{2})', base)
                if match:
                    return 'AION_A8R', match.group(1)

            return None, None

        except Exception as e:
            print(f"Errore nell'estrazione delle informazioni dal nome file {filename}: {e}")
            return None, None

    def _parse_relay_configuration(self, data: dict) -> List[dict]:
        """Estrae la configurazione dei relè dal file YAML con analisi dettagliata"""
        entities = []
        
        # Estrai informazioni dalle sezioni principali
        lights = self._normalize_component_list(data.get('light', []))
        covers = self._normalize_component_list(data.get('cover', []))
        climate = self._normalize_component_list(data.get('climate', []))
        switches = self._normalize_component_list(data.get('switch', []))

        # Crea una mappa dei relè per tipo
        relay_map = {}
        
        # Prima mappa tutti gli switch di base
        for switch in switches:
            if not isinstance(switch, dict) or not ('id' in switch and 'pin' in switch):
                continue
            
            switch_id = switch['id']
            if not isinstance(switch_id, str) or not switch_id.startswith('switch_'):
                continue
            
            try:
                relay_num = int(switch_id.replace('switch_', ''))
                relay_map[relay_num] = {
                    'number': relay_num,
                    'name': switch.get('name', f'Relay {relay_num}'),
                    'id': switch_id,
                    'pin': self._extract_pin_info(switch['pin']),
                    'internal': switch.get('internal', False),
                    'type': 'switch'  # tipo default
                }
            except ValueError:
                continue

        # Processa le luci
        for light in lights:
            if not isinstance(light, dict) or 'id' not in light:
                continue
                
            light_id = light['id']
            if isinstance(light_id, str) and light_id.startswith('light_'):
                try:
                    relay_num = int(light_id.replace('light_', ''))
                    if relay_num in relay_map:
                        # Mantiene il nome originale dello switch
                        relay_map[relay_num].update({
                            'type': 'light'
                            # Il nome rimane quello originale estratto dallo switch
                        })
                except ValueError:
                    continue

        # Processa le tapparelle
        for cover in covers:
            if not isinstance(cover, dict):
                continue
            
            cover_id = cover.get('id', '')
            if not cover_id:
                continue
                
            cover_name = cover.get('name', '')
            
            def process_actions(actions, action_type):
                if not actions:
                    return
                    
                if not isinstance(actions, list):
                    actions = [actions]
                
                def find_switch_turn_on(obj, depth=0):
                    """Ricerca ricursiva di switch.turn_on nelle strutture annidate"""
                    if depth > 10:  # Previene ricorsione infinita
                        return
                        
                    if isinstance(obj, dict):
                        # Caso diretto: switch.turn_on
                        if 'switch.turn_on' in obj:
                            try:
                                switch_action = obj['switch.turn_on']
                                if isinstance(switch_action, str):
                                    switch_id = switch_action
                                else:
                                    switch_id = str(switch_action)
                                
                                relay_num = int(switch_id.replace('switch_', ''))
                                if relay_num in relay_map:
                                    # Mantiene il nome originale dello switch invece di sovrascriverlo con il nome del cover
                                    relay_map[relay_num].update({
                                        'type': f'cover_{action_type}'
                                        # Il nome rimane quello originale estratto dallo switch
                                    })
                            except (ValueError, AttributeError, TypeError):
                                pass
                        
                        # Ricerca ricorsiva in if/then/else
                        if 'if' in obj:
                            if_block = obj.get('if', {})
                            # Processa then
                            if 'then' in if_block:
                                then_actions = if_block['then']
                                if not isinstance(then_actions, list):
                                    then_actions = [then_actions]
                                for then_action in then_actions:
                                    find_switch_turn_on(then_action, depth + 1)
                            
                            # Processa else
                            if 'else' in if_block:
                                else_actions = if_block['else']
                                if not isinstance(else_actions, list):
                                    else_actions = [else_actions]
                                for else_action in else_actions:
                                    find_switch_turn_on(else_action, depth + 1)
                        
                        # Ricerca in tutte le altre chiavi
                        for key, value in obj.items():
                            if key not in ['switch.turn_on', 'if']:
                                find_switch_turn_on(value, depth + 1)
                    
                    elif isinstance(obj, list):
                        for item in obj:
                            find_switch_turn_on(item, depth + 1)
                    
                # Avvia la ricerca ricorsiva
                for action in actions:
                    find_switch_turn_on(action)
            
            process_actions(cover.get('open_action', []), 'open')
            process_actions(cover.get('close_action', []), 'close')

        # Processa i termostati
        for therm in climate:
            if not isinstance(therm, dict):
                continue
            
            climate_id = therm.get('id', '')
            if not climate_id:
                continue
                
            climate_name = therm.get('name', '')
            
            def process_climate_actions(actions):
                if not actions:
                    return
                    
                if not isinstance(actions, list):
                    actions = [actions]
                    
                for action in actions:
                    if isinstance(action, dict):
                        # Gestisce azioni dirette switch.turn_on
                        if 'switch.turn_on' in action:
                            try:
                                switch_action = action['switch.turn_on']
                                # Gestisce sia stringhe che ID diretti
                                if isinstance(switch_action, str):
                                    switch_id = switch_action
                                else:
                                    switch_id = str(switch_action)
                                
                                relay_num = int(switch_id.replace('switch_', ''))
                                if relay_num in relay_map:
                                    if relay_map[relay_num]['type'] == 'switch':
                                        # Mantiene il nome originale dello switch
                                        relay_map[relay_num].update({
                                            'type': 'climate'
                                            # Il nome rimane quello originale estratto dallo switch
                                        })
                            except (ValueError, AttributeError, TypeError):
                                continue
                                
                        # Gestisce strutture if/then
                        elif 'if' in action:
                            if_block = action.get('if', {})
                            then_actions = if_block.get('then', [])
                            if not isinstance(then_actions, list):
                                then_actions = [then_actions]
                                
                            for then_action in then_actions:
                                if isinstance(then_action, dict) and 'switch.turn_on' in then_action:
                                    try:
                                        switch_action = then_action['switch.turn_on']
                                        # Gestisce sia stringhe che ID diretti
                                        if isinstance(switch_action, str):
                                            switch_id = switch_action
                                        else:
                                            switch_id = str(switch_action)
                                        
                                        relay_num = int(switch_id.replace('switch_', ''))
                                        if relay_num in relay_map:
                                            # Mantiene il nome originale dello switch
                                            relay_map[relay_num].update({
                                                'type': 'climate'
                                                # Il nome rimane quello originale estratto dallo switch
                                            })
                                    except (ValueError, AttributeError, TypeError):
                                        continue
            
            # Processa le azioni di riscaldamento
            process_climate_actions(therm.get('heat_action', []))
            # Processa anche le azioni di raffreddamento se presenti
            process_climate_actions(therm.get('cool_action', []))

        # Converti la mappa in lista ordinata
        return sorted(relay_map.values(), key=lambda x: x['number'])

    def _normalize_component_list(self, component: Union[List, Dict]) -> List:
        """Normalizza una componente YAML in una lista"""
        if isinstance(component, dict):
            return [{'id': key, **value} for key, value in component.items()]
        return component if isinstance(component, list) else []

    def _get_cover_relays(self, covers: List[Dict]) -> Dict[int, str]:
        """Identifica i relè usati nelle tapparelle"""
        cover_relays = {}
        for cover in covers:
            open_relay = self._extract_relay_number(str(cover.get('open_action', '')))
            close_relay = self._extract_relay_number(str(cover.get('close_action', '')))
            
            if open_relay:
                cover_relays[open_relay] = 'cover_open'
            if close_relay:
                cover_relays[close_relay] = 'cover_close'
        return cover_relays

    def _get_light_relays(self, lights: List[Dict]) -> set:
        """Identifica i relè usati nelle luci"""
        light_relays = set()
        for light in lights:
            # Cerca nelle azioni di output
            if 'output' in light:
                output = str(light.get('output', ''))
                if 'output_' in output:
                    relay_num = int(output.replace('output_', ''))
                    light_relays.add(relay_num)
            # Cerca negli switch_id
            elif 'switch_id' in light:
                relay_num = self._extract_relay_number(str(light.get('switch_id', '')))
                if relay_num:
                    light_relays.add(relay_num)
        return light_relays

    def _get_climate_relays(self, climate: List[Dict]) -> set:
        """Identifica i relè usati nei termostati"""
        climate_relays = set()
        for therm in climate:
            # Cerca nelle heat_action per i termostati
            if 'heat_action' in therm:
                heat_actions = therm.get('heat_action', [])
                if isinstance(heat_actions, list):
                    for action in heat_actions:
                        if isinstance(action, dict) and 'switch.turn_on' in action:
                            switch_name = str(action.get('switch.turn_on', ''))
                            relay_num = self._extract_relay_number(switch_name)
                            if relay_num:
                                climate_relays.add(relay_num)
        return climate_relays

    def _extract_relay_number(self, text: str) -> Optional[int]:
        """Estrae il numero del relè da una stringa"""
        match = re.search(r'relay[_-]?(\d+)', text.lower())
        return int(match.group(1)) if match else None

    def _extract_relay_info(self, switch: Dict, cover_relays: Dict[int, str], 
                          light_relays: set, climate_relays: set) -> Optional[Dict]:
        """Estrae le informazioni complete di un relè"""
        if not isinstance(switch, dict) or not ('id' in switch or 'platform' in switch):
            return None

        relay_num = None
        switch_id = switch.get('id', '')
        
        # Cerca prima nell'ID poi nel nome
        relay_num = self._extract_relay_number(str(switch_id))
        if relay_num is None and 'name' in switch:
            relay_num = self._extract_relay_number(str(switch.get('name', '')))

        if relay_num is None:
            return None

        # Estrai il pin
        pin = self._extract_pin_info(switch.get('pin', {}))
        
        # Determina il tipo specifico e il nome appropriato
        entity_type = "switch"  # tipo di default
        custom_name = switch.get('name', f'Relay {relay_num}')

        if relay_num in cover_relays:
            entity_type = cover_relays[relay_num]
            # Mantiene il nome originale dal campo 'name' del switch invece di generarlo automaticamente
            # custom_name rimane quello estratto da switch.get('name', f'Relay {relay_num}')
        elif relay_num in light_relays:
            entity_type = "light"
            custom_name = f'Light {relay_num}'
        elif relay_num in climate_relays:
            entity_type = "thermostat"
            custom_name = f'Climate {relay_num}'

        relay_info = {
            "number": relay_num,
            "name": custom_name,
            "pin": pin,
            "id": switch_id or f'relay_{relay_num}',
            "internal": switch.get('internal', False),
            "type": entity_type
        }

        return relay_info

    def _extract_pin_info(self, pin_data: Union[str, int, Dict]) -> str:
        """Estrae l'informazione del pin in formato standardizzato"""
        if isinstance(pin_data, (str, int)):
            return f"GPIO{pin_data}"
        elif isinstance(pin_data, dict) and 'number' in pin_data:
            return f"GPIO{pin_data['number']}"
        return ''

    def _parse_input_configuration(self, data: Dict) -> List[Dict]:
        """Estrae la configurazione degli input dalla sezione binary_sensor"""
        inputs = []
        
        # Cerca la sezione binary_sensor
        binary_sensors = data.get('binary_sensor', [])
        if not isinstance(binary_sensors, list):
            return inputs
        
        for sensor in binary_sensors:
            if not isinstance(sensor, dict):
                continue
                
            # Verifica che sia un input GPIO (non un sensore di altro tipo)
            if sensor.get('platform') != 'gpio':
                continue
                
            # Estrai informazioni base
            input_id = sensor.get('id', '')
            input_name = sensor.get('name', '')
            pin_info = sensor.get('pin', {})
            
            # Estrai il numero dell'input dall'id (es. input_01 -> 1)
            input_number = None
            if input_id:
                match = re.search(r'input_(\d+)', input_id)
                if match:
                    input_number = int(match.group(1))
            
            # Se non trovato nell'id, prova dal nome
            if not input_number and input_name:
                match = re.search(r'(\d+)', input_name)
                if match:
                    input_number = int(match.group(1))
            
            if not input_number:
                continue
                
            # Estrai il pin
            pin = ''
            if isinstance(pin_info, dict):
                if 'number' in pin_info:
                    pin = f"GPIO{pin_info['number']}"
                elif 'pcf8574' in pin_info and 'number' in pin_info:
                    # Per i pin su PCF8574 (espansore I/O)
                    pin = f"PCF8574 Pin {pin_info['number']}"
            
            # Analizza le azioni on_press e on_release per trovare controlli (luce o copertura)
            controlled_device = None
            device_relay_number = None
            control_type = None
            
            # Cerca azioni di controllo in on_press e on_release
            on_press_actions = sensor.get('on_press', [])
            on_release_actions = sensor.get('on_release', [])
            
            # Normalizza a liste
            if not isinstance(on_press_actions, list):
                on_press_actions = [on_press_actions] if on_press_actions else []
            if not isinstance(on_release_actions, list):
                on_release_actions = [on_release_actions] if on_release_actions else []
                
            # Cerca azioni light.turn_on e light.turn_off
            light_on_action = self._find_action_in_structure(on_press_actions, "light.turn_on")
            light_off_action = self._find_action_in_structure(on_release_actions, "light.turn_off")
            
            # Cerca azioni cover.open e cover.close
            cover_open_action = self._find_action_in_structure(on_press_actions, "cover.open")
            cover_close_action = self._find_action_in_structure(on_press_actions, "cover.close")
            
            if light_on_action:
                # Input controlla una luce
                entity_id = ""
                if isinstance(light_on_action, dict):
                    entity_id = light_on_action.get("target", {}).get("entity_id", "")
                elif isinstance(light_on_action, str):
                    entity_id = light_on_action
                    
                if entity_id:
                    relay_match = re.search(r'light[._](\d+)', entity_id)
                    if relay_match:
                        device_relay_number = int(relay_match.group(1))
                        control_type = "light"
                        controlled_device = entity_id
                        
            elif cover_open_action:
                # Input controlla apertura copertura
                cover_id = cover_open_action
                if isinstance(cover_id, dict):
                    cover_id = str(cover_id)
                elif not isinstance(cover_id, str):
                    cover_id = str(cover_id)
                    
                # Estrai numeri copertura (es: cover_03_04 -> "3-4")
                cover_match = re.search(r'cover[._](\d+)[._](\d+)', cover_id)
                if cover_match:
                    relay1, relay2 = cover_match.groups()
                    device_relay_number = f"{int(relay1)}-{int(relay2)}"
                    control_type = "cover_open"
                    controlled_device = cover_id
                    
            elif cover_close_action:
                # Input controlla chiusura copertura  
                cover_id = cover_close_action
                if isinstance(cover_id, dict):
                    cover_id = str(cover_id)
                elif not isinstance(cover_id, str):
                    cover_id = str(cover_id)
                    
                # Estrai numeri copertura (es: cover_03_04 -> "3-4")
                cover_match = re.search(r'cover[._](\d+)[._](\d+)', cover_id)
                if cover_match:
                    relay1, relay2 = cover_match.groups()
                    device_relay_number = f"{int(relay1)}-{int(relay2)}"
                    control_type = "cover_close"
                    controlled_device = cover_id
            
            # Crea l'oggetto input
            input_info = {
                "number": input_number,
                "name": input_name,
                "pin": pin,
                "id": input_id,
                "controlled_device": controlled_device,
                "control_type": control_type,
                "feedback_for_relay": device_relay_number
            }
            
            inputs.append(input_info)
        
        # Filtra gli input duplicati mantenendo solo quelli che controllano dispositivi
        # (luci o coperture) o se non ci sono controlli, mantieni il primo per ogni numero
        unique_inputs = {}
        for inp in inputs:
            num = inp['number']
            if num not in unique_inputs:
                unique_inputs[num] = inp
            elif inp['feedback_for_relay'] is not None:
                # Preferisci gli input che controllano dispositivi (luci/coperture)
                unique_inputs[num] = inp
        
        # Converti di nuovo in lista e ordina per numero
        return sorted(unique_inputs.values(), key=lambda x: x['number'])

    def _find_action_in_structure(self, structure, action_type, depth=0):
        """Cerca ricorsivamente un'azione specifica nella struttura YAML (if/then/else, etc.)"""
        if depth > 10:  # Previene ricorsione infinita
            return None
            
        if isinstance(structure, dict):
            # Caso diretto: azione trovata
            if action_type in structure:
                return structure[action_type]
            
            # Ricerca ricorsiva in if/then/else
            if 'if' in structure:
                if_block = structure.get('if', {})
                # Processa then
                if 'then' in if_block:
                    then_actions = if_block['then']
                    if not isinstance(then_actions, list):
                        then_actions = [then_actions]
                    for then_action in then_actions:
                        result = self._find_action_in_structure(then_action, action_type, depth + 1)
                        if result:
                            return result
                
                # Processa else
                if 'else' in if_block:
                    else_actions = if_block['else']
                    if not isinstance(else_actions, list):
                        else_actions = [else_actions]
                    for else_action in else_actions:
                        result = self._find_action_in_structure(else_action, action_type, depth + 1)
                        if result:
                            return result
            
            # Ricerca in tutte le altre chiavi
            for key, value in structure.items():
                if key not in [action_type, 'if']:
                    result = self._find_action_in_structure(value, action_type, depth + 1)
                    if result:
                        return result
        
        elif isinstance(structure, list):
            for item in structure:
                result = self._find_action_in_structure(item, action_type, depth + 1)
                if result:
                    return result
        
        return None

    def parse_device_file(self, filename: str) -> Optional[DeviceConfig]:
        """Parse di un singolo file di configurazione dispositivo con caching"""
        filepath = os.path.join(self.hardware_path, filename)
        
        # Verifica la cache
        if self._is_cache_valid(filename):
            return self._cache[filename][1]

        if not os.path.isfile(filepath):
            return None

        # Estrai informazioni modello dal nome file
        model, number = self._extract_model_info(filename)
        if not model or not number:
            return None

        try:
            # Leggi e fai il parse del file YAML usando il loader personalizzato
            with open(filepath, 'r') as f:
                data = yaml.load(f, Loader=self._create_custom_loader())

            # Estrai configurazione relè
            relay_config = self._parse_relay_configuration(data)

            # Estrai configurazione input
            input_config = self._parse_input_configuration(data)

            # Crea il nome amichevole
            friendly_name = f"{model} ({number})"

            # Crea la configurazione
            config = DeviceConfig(
                model=model,
                number=number,
                filename=filename,
                friendly_name=friendly_name,
                configuration={'relays': relay_config, 'inputs': input_config}
            )

            # Aggiorna la cache
            self._cache[filename] = (time.time(), config)
            
            return config

        except Exception as e:
            print(f"Errore nel parse del file {filename}: {e}")
            config = DeviceConfig(
                model=model,
                number=number,
                filename=filename,
                friendly_name=f"{model} ({number})",
                configuration={'relays': [], 'error': str(e)}
            )
            
            # Cache anche gli errori per evitare continui tentativi
            self._cache[filename] = (time.time(), config)
            
            return config

    def get_all_devices(self) -> List[DeviceConfig]:
        """Ottiene la configurazione di tutti i dispositivi nella cartella hardware"""
        devices = []
        
        if not os.path.isdir(self.hardware_path):
            return devices

        # Parse di tutti i file .yaml nella directory
        for filename in os.listdir(self.hardware_path):
            if not filename.endswith('.yaml'):
                continue

            device = self.parse_device_file(filename)
            if device:
                devices.append(device)

        return sorted(devices, key=lambda x: x.model)
