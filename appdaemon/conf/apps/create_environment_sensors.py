import appdaemon.plugins.hass.hassapi as hass
from typing import List, Dict, Set

class CreateEnvironmentSensors(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateEnvironmentSensors...")
        
        # Set per tenere traccia dei sensori che stiamo monitorando
        self.tracked_sensors: Set[str] = set()
        # Set per tenere traccia dei sensori aggregati che creiamo noi
        self.created_sensors: Set[str] = set()
        # Cache della mappa sensori per area/tipo per evitare scansioni ripetute
        self.area_sensors_cache: Dict[str, Dict[str, List[str]]] = {}
        
        # Tipi di sensori di interesse con unità di misura
        self.sensor_criteria = {
            'temperature': {
                'unit': '°C'
            },
            'humidity': {
                'unit': '%'
            },
            'illuminance': {
                'unit': 'lx'
            }
        }

        # Mappa per tradurre i nomi dei sensori in italiano
        self.sensor_type_map = {
            'temperature': 'Temperatura',
            'humidity': 'Umidità',
            'illuminance': 'Illuminazione'
        }
        
        # Avvio aggiornamento iniziale
        self.run_in(self.initial_setup, 2)

    def initial_setup(self, *args):
        """Setup iniziale: crea i sensori aggregati e imposta i listener"""
        self.log("Avvio setup iniziale...")
        
        # Crea la cache dei sensori e i sensori aggregati iniziali
        self.area_sensors_cache = self.get_environment_sensors_by_area()
        self.update_all_aggregate_sensors()
        
        # Imposta i listener per i cambi di stato dei sensori di interesse
        self.setup_state_listeners()
        
        self.log("Setup iniziale completato")

    def is_sensor_of_interest(self, entity_id: str, entity_data: dict) -> str:
        """
        Verifica se un sensore è di nostro interesse basandosi SOLO sul device_class.
        Restituisce il tipo di sensore o None se non è di interesse.
        """
        if not entity_id.startswith('sensor.'):
            return None
        
        # IMPORTANTE: Esclude i sensori aggregati che creiamo noi
        if entity_id in self.created_sensors:
            return None
            
        attributes = entity_data.get("attributes", {})
        device_class = attributes.get("device_class", "").lower()
        
        # Considera SOLO i device_class specifici
        if device_class == 'temperature':
            return 'temperature'
        elif device_class == 'humidity':
            return 'humidity'
        elif device_class == 'illuminance':
            return 'illuminance'
                
        return None

    def get_environment_sensors_by_area(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Recupera tutti i sensori ambientali raggruppati per area e tipo.
        Considera SOLO sensori con device_class: temperature, humidity, illuminance
        e con un'area assegnata.
        Restituisce un dizionario: {area_name: {sensor_type: [entity_ids]}}
        """
        self.log("Recupero sensori ambientali per area...", level="DEBUG")
        
        all_entities = self.get_state()
        area_sensors: Dict[str, Dict[str, List[str]]] = {}
        
        for entity_id, entity_data in all_entities.items():
            # Prima verifica se è un sensore di interesse
            sensor_type = self.is_sensor_of_interest(entity_id, entity_data)
            if not sensor_type:
                continue
                
            try:
                # Solo ora verifica l'area
                area_name = self.area_name(entity_id)
                if not area_name:
                    # Log ridotto per sensori senza area (spesso normali come sensori meteo)
                    continue
                    
                # Aggiungi al dizionario
                area_sensors.setdefault(area_name, {}).setdefault(sensor_type, []).append(entity_id)
                self.log(f"Trovato sensore {sensor_type} in {area_name}: {entity_id}", level="DEBUG")
                
            except Exception as e:
                self.log(f"Errore nel processare {entity_id}: {e}", level="WARNING")
        
        return area_sensors

    def setup_state_listeners(self):
        """Imposta i listener per i sensori di interesse usando la cache"""        
        for area_name, sensor_types in self.area_sensors_cache.items():
            for sensor_type, entities in sensor_types.items():
                for entity_id in entities:
                    if entity_id not in self.tracked_sensors:
                        self.listen_state(
                            self.on_sensor_change,
                            entity_id,
                            area=area_name,
                            sensor_type=sensor_type
                        )
                        self.tracked_sensors.add(entity_id)
                        self.log(f"Listener aggiunto per {entity_id} ({sensor_type} in {area_name})", level="DEBUG")

    def on_sensor_change(self, entity, attribute, old, new, kwargs):
        """Callback per il cambio di stato di un sensore"""
        # Ignora cambiamenti se lo stato non è cambiato realmente
        if old == new:
            return
            
        # Ignora stati non validi
        if new in [None, "unknown", "unavailable", "null"]:
            return
            
        try:
            # Verifica che sia un numero valido
            float(new)
        except (ValueError, TypeError):
            return
            
        area = kwargs["area"]
        sensor_type = kwargs["sensor_type"]
        
        self.log(f"Sensore cambiato: {entity} ({sensor_type} in {area}) = {new}", level="DEBUG")
        
        # Aggiorna i sensori aggregati per questa area e tipo
        self.update_area_aggregate_sensors(area, sensor_type)

    def update_all_aggregate_sensors(self):
        """Aggiorna tutti i sensori aggregati usando la cache"""        
        for area_name, sensor_types in self.area_sensors_cache.items():
            for sensor_type, entities in sensor_types.items():
                self.log(f"Creazione sensori aggregati per {area_name} - {sensor_type} con {len(entities)} sensori", level="INFO")
                self.create_aggregate_sensors(area_name, sensor_type, entities)

    def update_area_aggregate_sensors(self, area_name: str, sensor_type: str):
        """Aggiorna efficientemente i sensori aggregati per una specifica area e tipo usando la cache"""
        # Usa la cache invece di fare una scansione completa
        entities = self.area_sensors_cache.get(area_name, {}).get(sensor_type, [])
        
        if not entities:
            self.log(f"Nessun sensore {sensor_type} trovato per {area_name} nella cache", level="DEBUG")
            return
            
        # Raccoglie i valori validi
        states = []
        for entity in entities:
            raw_state = self.get_state(entity)
            
            if raw_state in [None, "unknown", "unavailable", "null"]:
                continue
            
            try:
                value = float(raw_state)
                states.append(value)
            except (ValueError, TypeError):
                continue

        if not states:
            self.log(f"Nessuno stato valido trovato per {area_name} - {sensor_type}", level="DEBUG")
            return

        clean_area = area_name.lower().replace(' ', '_').replace('-', '_')
        unit = self.sensor_criteria[sensor_type]['unit']

        # Funzione per arrotondare in base al tipo
        def round_value(val):
            return round(val, 1) if sensor_type == 'temperature' else round(val)

        if len(states) == 1:
            # Un solo sensore: aggiorna solo il sensore principale
            avg_value = round_value(states[0])
            self.update_sensor_value(f"{clean_area}_{sensor_type}", avg_value, sensor_type, unit)
            
            # Rimuovi eventuali sensori min/max/avg se esistono
            self.remove_sensor(f"{clean_area}_{sensor_type}_min")
            self.remove_sensor(f"{clean_area}_{sensor_type}_max")
            self.remove_sensor(f"{clean_area}_{sensor_type}_avg")
            
        else:
            # Più sensori: aggiorna min, max e media
            min_value = round_value(min(states))
            max_value = round_value(max(states))
            avg_value = round_value(sum(states) / len(states))

            # Rimuovi il sensore singolo (senza suffisso) se esiste, per evitare duplicati
            self.remove_sensor(f"{clean_area}_{sensor_type}")

            # Aggiorna i sensori min, max e avg
            self.update_sensor_value(f"{clean_area}_{sensor_type}_min", min_value, sensor_type, unit)
            self.update_sensor_value(f"{clean_area}_{sensor_type}_max", max_value, sensor_type, unit)
            # *** MODIFICA: L'ID del sensore media ora ha il suffisso _avg ***
            self.update_sensor_value(f"{clean_area}_{sensor_type}_avg", avg_value, sensor_type, unit)

    def update_sensor_value(self, object_id: str, new_value: float, sensor_type: str, unit: str):
        """Aggiorna direttamente il valore di un sensore esistente"""
        full_entity_id = f"sensor.{object_id}"
        current_state = self.get_state(full_entity_id)
        
        # Se il sensore non esiste, lo crea
        if current_state is None:
            italian_name = self.sensor_type_map.get(sensor_type, sensor_type.title())
            
            # *** MODIFICA: Logica per la creazione del friendly_name gestisce anche _avg ***
            if object_id.endswith('_min'):
                area_part = '_'.join(object_id.split('_')[:-2])
                area_name = area_part.replace('_', ' ').title()
                name = f"Min {italian_name} in {area_name}"
            elif object_id.endswith('_max'):
                area_part = '_'.join(object_id.split('_')[:-2])
                area_name = area_part.replace('_', ' ').title()
                name = f"Max {italian_name} in {area_name}"
            elif object_id.endswith('_avg'):
                area_part = '_'.join(object_id.split('_')[:-2])
                area_name = area_part.replace('_', ' ').title()
                name = f"{italian_name} in {area_name}"
            else:
                area_part = '_'.join(object_id.split('_')[:-1])
                area_name = area_part.replace('_', ' ').title()
                name = f"{italian_name} in {area_name}"
            
            self.create_sensor(object_id, name, new_value, sensor_type, unit)
            return
        
        # Confronto numerico
        try:
            current_value = float(current_state)
            if abs(current_value - new_value) < 0.001:  # Tolleranza per float
                return  # Nessun aggiornamento necessario
        except (ValueError, TypeError):
            pass  # Forza aggiornamento se non riesco a convertire
        
        # Aggiorna solo il valore mantenendo gli attributi esistenti
        self.set_state(full_entity_id, state=new_value)
        self.created_sensors.add(full_entity_id)
        self.log(f"Aggiornato {object_id}: {current_state} → {new_value}", level="DEBUG")

    def create_aggregate_sensors(self, area: str, sensor_type: str, entities: List[str]):
        """Crea sensori aggregati per un'area e tipo di sensore"""
        if not entities:
            self.log(f"Nessun sensore trovato per {area} - {sensor_type}", level="WARNING")
            return
            
        # Raccoglie i valori validi
        states = []
        for entity in entities:
            raw_state = self.get_state(entity)
            
            if raw_state in [None, "unknown", "unavailable", "null"]:
                self.log(f"Entità {entity} ignorata per stato non valido: {raw_state}", level="DEBUG")
                continue
            
            try:
                value = float(raw_state)
                states.append(value)
            except (ValueError, TypeError):
                self.log(f"Impossibile convertire {raw_state} in float per l'entità {entity}", level="DEBUG")

        if not states:
            self.log(f"Nessuno stato valido trovato per {area} - {sensor_type}", level="WARNING")
            return

        clean_area = area.lower().replace(' ', '_').replace('-', '_')
        unit = self.sensor_criteria[sensor_type]['unit']
        
        italian_name = self.sensor_type_map.get(sensor_type, sensor_type.title())

        # Funzione per arrotondare in base al tipo
        def round_value(val):
            return round(val, 1) if sensor_type == 'temperature' else round(val)

        if len(states) == 1:
            # Un solo sensore: crea solo il sensore principale
            avg_value = round_value(states[0])
            self.create_sensor(
                f"{clean_area}_{sensor_type}",
                f"{italian_name} in {area}", # Nome in italiano
                avg_value,
                sensor_type,
                unit
            )
            self.log(f"Creato sensore singolo per {area} - {sensor_type}: {avg_value}", level="INFO")
            
            # Rimuovi eventuali sensori min/max/avg esistenti
            self.remove_sensor(f"{clean_area}_{sensor_type}_min")
            self.remove_sensor(f"{clean_area}_{sensor_type}_max")
            self.remove_sensor(f"{clean_area}_{sensor_type}_avg")
            
        else:
            # Più sensori: crea min, max e media
            min_value = round_value(min(states))
            max_value = round_value(max(states))
            avg_value = round_value(sum(states) / len(states))

            # Rimuovi il sensore singolo (senza suffisso) se esiste, per evitare duplicati
            self.remove_sensor(f"{clean_area}_{sensor_type}")

            self.create_sensor(
                f"{clean_area}_{sensor_type}_min",
                f"Min {italian_name} in {area}", # Nome in italiano
                min_value,
                sensor_type,
                unit
            )
            self.create_sensor(
                f"{clean_area}_{sensor_type}_max",
                f"Max {italian_name} in {area}", # Nome in italiano
                max_value,
                sensor_type,
                unit
            )
            # *** MODIFICA: L'ID del sensore media ora ha il suffisso _avg ***
            self.create_sensor(
                f"{clean_area}_{sensor_type}_avg",
                f"{italian_name} in {area}", # Nome in italiano, senza prefisso
                avg_value,
                sensor_type,
                unit
            )
            self.log(
                f"Creati sensori per {area} - {sensor_type}: min={min_value}, max={max_value}, avg={avg_value}",
                level="INFO"
            )

    def create_sensor(self, object_id: str, name: str, state: float, sensor_type: str, unit: str):
        """Crea o aggiorna un sensore"""
        full_entity_id = f"sensor.{object_id}"

        attributes = {
            "friendly_name": name,
            "unit_of_measurement": unit,
            "device_class": sensor_type,
            "state_class": "measurement"
        }

        # Verifica se è necessario aggiornare (confronto numerico)
        current_state = self.get_state(full_entity_id)
        
        # Confronto più robusto per lo stato
        same_state = False
        if current_state is not None:
            try:
                current_value = float(current_state)
                same_state = abs(current_value - state) < 0.001  # Tolleranza per numeri float
            except (ValueError, TypeError):
                same_state = False
        
        current_attrs = self.get_state(full_entity_id, attribute="all")
        same_attrs = current_attrs and all(
            current_attrs.get("attributes", {}).get(k) == v for k, v in attributes.items()
        )

        if same_state and same_attrs:
            self.log(f"Nessun aggiornamento necessario per {full_entity_id} (valore: {state})", level="DEBUG")
            return

        self.set_state(full_entity_id, state=state, attributes=attributes)
        
        # Aggiungi al set dei sensori creati da noi
        self.created_sensors.add(full_entity_id)

        if current_state is None:
            self.log(f"Creato nuovo sensore '{name}' = {state}", level="INFO")
        else:
            self.log(f"Aggiornato sensore '{name}': {current_state} → {state}", level="DEBUG")

    def remove_sensor(self, object_id: str):
        """Rimuove un sensore se esiste"""
        full_entity_id = f"sensor.{object_id}"
        current_state = self.get_state(full_entity_id)
        
        if current_state is not None:
            # Invece di rimuovere, imposta lo stato a non disponibile per evitare errori
            self.set_state(full_entity_id, state="unavailable", attributes={"friendly_name": f"{object_id} (rimosso)"})
            # Rimuovi dal set dei sensori creati
            self.created_sensors.discard(full_entity_id)
            self.log(f"Sensore {full_entity_id} contrassegnato come non disponibile.", level="DEBUG")
