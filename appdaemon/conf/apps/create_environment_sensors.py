import appdaemon.plugins.hass.hassapi as hass
from typing import List, Dict

class CreateEnvironmentSensors(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateEnvironmentSensors...")
        
        # Inizia l'ascolto all'avvio di Home Assistant
        self.listen_event(self.update_groups, "homeassistant_start")
        
        # Memorizza i sensori già monitorati per evitare doppioni
        self.tracked_sensors = set()
        
        # Esegui subito l'aggiornamento dei gruppi
        self.update_groups()

    def update_groups(self, *args):
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        sensor_entity_ids = {
            "temperature": "sensor.area_temperature_list",
            "humidity": "sensor.area_humidity_list",
            "illuminance": "sensor.area_illuminance_list"
        }

        area_entity_map = {}
        for sensor_type, sensor_entity_id in sensor_entity_ids.items():
            self.process_sensor(sensor_entity_id, area_entity_map)

        for area, entities in area_entity_map.items():
            self.create_environment_sensors(area, entities)

    def process_sensor(self, sensor_entity_id: str, area_entity_map: Dict[str, List[str]]):
        sensor_state = self.get_state(sensor_entity_id)
        if sensor_state != "OK":
            self.log(f"Lo stato del sensore {sensor_entity_id} non è 'OK'. Entità non aggregate.", level="WARNING")
            return

        areas_entity = self.get_sensor_attributes(sensor_entity_id)
        if not areas_entity:
            self.log(f"Nessun dato trovato nell'attributo 'areas_entity' del sensore {sensor_entity_id}.", level="WARNING")
            return

        for line in areas_entity.splitlines():
            if " | " in line:
                entity, area = line.split(" | ")
                area_entity_map.setdefault(area, []).append(entity)
                
                # Aggiungi un listener per ogni sensore non ancora monitorato
                if entity not in self.tracked_sensors:
                    self.listen_state(self.update_groups, entity)
                    self.tracked_sensors.add(entity)

    def get_sensor_attributes(self, sensor_entity_id: str) -> str:
        attributes = self.get_state(sensor_entity_id, attribute="attributes")
        return attributes.get("areas_entity", "") if attributes else ""

    def create_environment_sensors(self, area: str, entities: List[str]):
        sensor_types = ["temperature", "humidity", "illuminance"]
        for sensor_type in sensor_types:
            filtered_entities = [
                e for e in entities
                if self.get_state(e, attribute="device_class") == sensor_type
                and self.get_state(e) not in ["unknown", "unavailable"]
            ]
            if filtered_entities:
                self.create_min_max_avg_sensors(area, sensor_type, filtered_entities)

    def create_min_max_avg_sensors(self, area: str, sensor_type: str, entities: List[str]):
        states = []
        for entity in entities:
            try:
                state = float(self.get_state(entity))
                states.append(state)
            except ValueError:
                self.log(f"Stato non valido per l'entità {entity}: {self.get_state(entity)}", level="WARNING")

        if not states:
            return

        min_value, max_value = min(states), max(states)
        avg_value = round(sum(states) / len(states), 1)

        self.create_sensor(f"{area}_{sensor_type}_min", f"Min {sensor_type} in {area}", min_value, sensor_type)
        self.create_sensor(f"{area}_{sensor_type}_max", f"Max {sensor_type} in {area}", max_value, sensor_type)
        self.create_sensor(f"{area}_{sensor_type}", f"{sensor_type} in {area}", avg_value, sensor_type)

    def create_sensor(self, object_id: str, name: str, state: float, sensor_type: str):
        attributes = {
            "friendly_name": name,
            "unit_of_measurement": {
                "temperature": "°C",
                "humidity": "%",
                "illuminance": "lux"
            }.get(sensor_type, ""),
            "device_class": sensor_type
        }

        self.set_state(f"sensor.{object_id}", state=state, attributes=attributes)
#        self.log(f"Creato sensore {name} con stato {state} e attributi {attributes}")
