import appdaemon.plugins.hass.hassapi as hass
from typing import List, Dict

class CreateEnvironmentSensors(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateEnvironmentSensors...")
        
        # Inizia l'ascolto all'avvio di Home Assistant
        self.listen_event(self.update_groups, "homeassistant_start")
        
        # Ascolta i cambiamenti del registry per aggiornamenti dinamici
        self.listen_event(self.update_groups, "area_registry_updated")
        self.listen_event(self.update_groups, "device_registry_updated")
        
        # Memorizza i sensori già monitorati per evitare doppioni
        self.tracked_sensors = set()
        
        # Esegui subito l'aggiornamento dei gruppi
        self.update_groups()

    def get_environment_sensors_by_area(self):
        """
        Recupera tutti i sensori ambientali raggruppati per area e tipo
        Restituisce un dizionario: {area_name: {sensor_type: [entity_ids]}}
        """
        self.log("Recupero sensori ambientali per area...", level="DEBUG")
        
        # Recupera tutte le entità
        all_entities = self.get_state()
        
        # Mappa area_name -> sensor_type -> lista entità
        area_sensors = {}
        
        # Tipi di sensori ambientali di interesse
        sensor_types = {
            'temperature': ['temperature'],
            'humidity': ['humidity'],
            'illuminance': ['illuminance']
        }
        
        for entity_id in all_entities:
            try:
                # Filtra solo i sensori
                if entity_id.startswith('sensor.'):
                    area_name = self.area_name(entity_id)
                    if area_name:  # solo se è assegnata a un'area
                        entity_state = self.get_state(entity_id, attribute="all")
                        if entity_state and 'attributes' in entity_state:
                            device_class = entity_state['attributes'].get('device_class', '')
                            unit_of_measurement = entity_state['attributes'].get('unit_of_measurement', '')
                            entity_name = entity_id.lower()
                            
                            # Categorizza il sensore per tipo
                            sensor_type = None
                            
                            # Controlla temperatura
                            if (device_class == 'temperature' or 
                                '°C' in unit_of_measurement or 
                                '°F' in unit_of_measurement or
                                'temperature' in entity_name):
                                sensor_type = 'temperature'
                            
                            # Controlla umidità
                            elif (device_class == 'humidity' or 
                                  '%' in unit_of_measurement or
                                  'humidity' in entity_name):
                                sensor_type = 'humidity'
                            
                            # Controlla illuminanza
                            elif (device_class == 'illuminance' or 
                                  'lx' in unit_of_measurement or 
                                  'lux' in unit_of_measurement or
                                  'illuminance' in entity_name or
                                  'light' in entity_name):
                                sensor_type = 'illuminance'
                            
                            # Se è un tipo di interesse, aggiungilo
                            if sensor_type:
                                if area_name not in area_sensors:
                                    area_sensors[area_name] = {}
                                if sensor_type not in area_sensors[area_name]:
                                    area_sensors[area_name][sensor_type] = []
                                
                                area_sensors[area_name][sensor_type].append(entity_id)
                                
            except Exception as e:
                self.log(f"Errore nel verificare il sensore {entity_id}: {e}", level="WARNING")
        
        return area_sensors

    def update_groups(self, *args):
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        # Ottieni i sensori ambientali raggruppati per area
        area_sensors = self.get_environment_sensors_by_area()
        
        if not area_sensors:
            self.log("Nessun sensore ambientale trovato con area assegnata.", level="WARNING")
            return
        
        # Per ogni area, crea i sensori aggregati
        for area_name, sensor_types in area_sensors.items():
            self.log(f"Processando area: {area_name} con tipi di sensori: {list(sensor_types.keys())}", level="DEBUG")
            
            for sensor_type, entities in sensor_types.items():
                # Filtra solo le entità con stato valido
                valid_entities = []
                for entity in entities:
                    state = self.get_state(entity)
                    if state not in ["unknown", "unavailable", "null", None]:
                        try:
                            float(state)  # Verifica che sia un numero valido
                            valid_entities.append(entity)
                            
                            # Aggiungi listener per aggiornamenti se non già monitorato
                            if entity not in self.tracked_sensors:
                                self.listen_state(self.update_groups, entity)
                                self.tracked_sensors.add(entity)
                                
                        except (ValueError, TypeError):
                            self.log(f"Stato non numerico per {entity}: {state}", level="DEBUG")
                
                if valid_entities:
                    self.log(f"Creando sensori aggregati per {area_name} - {sensor_type} con {len(valid_entities)} entità", level="DEBUG")
                    self.create_min_max_avg_sensors(area_name, sensor_type, valid_entities)

    def create_min_max_avg_sensors(self, area: str, sensor_type: str, entities: List[str]):
        """Crea sensori min, max e media per un'area e tipo di sensore"""
        states = []
        
        for entity in entities:
            try:
                state = float(self.get_state(entity))
                states.append(state)
            except (ValueError, TypeError):
                self.log(f"Stato non valido per l'entità {entity}: {self.get_state(entity)}", level="WARNING")

        if not states:
            self.log(f"Nessuno stato valido trovato per {area} - {sensor_type}", level="WARNING")
            return

        min_value = min(states)
        max_value = max(states)
        avg_value = round(sum(states) / len(states), 1)

        # Pulisci il nome dell'area per gli ID dei sensori
        clean_area = area.lower().replace(' ', '_').replace('-', '_')

        # Crea i tre sensori aggregati
        self.create_sensor(f"{clean_area}_{sensor_type}_min", f"Min {sensor_type.title()} in {area}", min_value, sensor_type)
        self.create_sensor(f"{clean_area}_{sensor_type}_max", f"Max {sensor_type.title()} in {area}", max_value, sensor_type)
        self.create_sensor(f"{clean_area}_{sensor_type}", f"{sensor_type.title()} in {area}", avg_value, sensor_type)

        self.log(f"Creati sensori per {area} - {sensor_type}: min={min_value}, max={max_value}, avg={avg_value}", level="INFO")

    def create_sensor(self, object_id: str, name: str, state: float, sensor_type: str):
        """Crea o aggiorna un sensore aggregato"""
        
        # Definisce unità di misura e altre proprietà per tipo
        sensor_properties = {
            "temperature": {
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "state_class": "measurement"
            },
            "humidity": {
                "unit_of_measurement": "%",
                "device_class": "humidity", 
                "state_class": "measurement"
            },
            "illuminance": {
                "unit_of_measurement": "lx",
                "device_class": "illuminance",
                "state_class": "measurement"
            }
        }
        
        properties = sensor_properties.get(sensor_type, {
            "unit_of_measurement": "",
            "device_class": sensor_type,
            "state_class": "measurement"
        })
        
        attributes = {
            "friendly_name": name,
            **properties
        }

        try:
            self.set_state(f"sensor.{object_id}", state=state, attributes=attributes)
            self.log(f"Creato/aggiornato sensore '{name}' con stato {state}", level="DEBUG")
        except Exception as e:
            self.log(f"Errore durante la creazione del sensore '{object_id}': {str(e)}", level="ERROR")
