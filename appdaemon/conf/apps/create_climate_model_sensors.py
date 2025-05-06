import appdaemon.plugins.hass.hassapi as hass
import re

class CreateClimateModelSensors(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateClimateModelSensors...", level="INFO")
        
        # Cache per ottimizzare le richieste di stato
        self.temperature_cache = {}

        # Ascolta l'evento homeassistant_start e i cambiamenti di stato del sensore area_climate_list
        self.listen_event(self.create_climate_sensors, "homeassistant_start")
        self.listen_state(self.create_climate_sensors, "sensor.area_climate_list", attribute="all")

        self.log("App configurata per ascoltare gli eventi e i cambiamenti di stato del sensore area_climate_list.", level="INFO")
        
        # Esegui un aggiornamento iniziale
        self.create_climate_sensors()

    def create_climate_sensors(self, *args, **kwargs):
        self.log("Avvio creazione sensori modello per le entità climate...", level="DEBUG")

        try:
            areas_entity = self.get_state("sensor.area_climate_list", attribute="areas_entity")
            if not areas_entity:
                self.log("Nessun dato trovato nell'attributo 'areas_entity' del sensore area_climate_list.", level="WARNING")
                return

            for line_num, line in enumerate(areas_entity.splitlines(), start=1):
                entity, area = map(str.strip, line.split(" | ", 1)) if " | " in line else (None, None)
                if not entity or not area:
                    self.log(f"Linea non valida nel 'areas_entity' alla riga {line_num}: '{line}'. Formato atteso 'entity | area'.", level="WARNING")
                    continue

                climate_sensor_id = self.generate_sensor_id(entity)
                if not climate_sensor_id:
                    self.log(f"Impossibile creare un sensore per {entity}. Saltando...", level="ERROR")
                    continue

                temperature_sensor_id = f"sensor.{area}_temperature"
                temperature_state = self.get_validated_temperature(temperature_sensor_id)

                # Crea il sensore climate e inizia ad ascoltare i cambiamenti di stato
                self.create_sensor(climate_sensor_id, f"Temperature for {entity} in {area}", temperature_state)
                self.listen_state(self.update_climate_sensor, temperature_sensor_id, climate_sensor_id=climate_sensor_id, name=f"Temperature for {entity} in {area}")
        
        except Exception as e:
            self.log(f"Errore durante la creazione dei sensori climate: {str(e)}", level="ERROR")

    def generate_sensor_id(self, entity):
        digits = re.findall(r'\d+', entity)
        if digits:
            return f"sensor.temperature_{'_'.join(digits)}"
        
        # Se non ci sono cifre, usa l'ID di fallback
        safe_entity = re.sub(r'[^a-zA-Z0-9]', '_', entity)
        return f"sensor.temperature_{safe_entity}" if safe_entity else None

    def get_validated_temperature(self, sensor_id: str):
        if sensor_id in self.temperature_cache:
            self.log(f"Recuperato stato del sensore {sensor_id} dalla cache: {self.temperature_cache[sensor_id]}", level="DEBUG")
            return self.temperature_cache[sensor_id]

        state = self.get_state(sensor_id)
        try:
            validated_state = float(state) if state not in ["unknown", "unavailable", "null", None] else "unknown"
            self.temperature_cache[sensor_id] = validated_state
            self.log(f"Stato del sensore {sensor_id} convalidato: {validated_state}", level="DEBUG")
            return validated_state
        except (ValueError, TypeError):
            self.log(f"Stato del sensore {sensor_id} non valido: {state}. Impostato a 'unknown'.", level="WARNING")
            return "unknown"

    def update_climate_sensor(self, entity, attribute, old, new, kwargs):
        """ Aggiorna il sensore climate quando cambia lo stato del sensore della temperatura. """
        name = kwargs['name']
        climate_sensor_id = kwargs['climate_sensor_id']

        try:
            new_state = float(new)
            self.temperature_cache[entity] = new_state  # Aggiorna la cache
        except (ValueError, TypeError):
            self.log(f"Nuovo stato non valido per {entity}: {new}. Impostato a 'unknown'.", level="WARNING")
            new_state = "unknown"
            if entity in self.temperature_cache:
                del self.temperature_cache[entity]  # Rimuovi dalla cache se lo stato non è valido

        self.create_sensor(climate_sensor_id, name, new_state)

    def create_sensor(self, object_id: str, name: str, state):
        attributes = {
            "friendly_name": name,
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        }
        sensor_state = state if isinstance(state, (float, int)) else "unknown"

        try:
            self.set_state(object_id, state=sensor_state, attributes=attributes)
            self.log(f"Creato sensore '{name}' con stato '{sensor_state}'", level="INFO")
        except Exception as e:
            self.log(f"Errore durante la creazione del sensore '{object_id}': {str(e)}", level="ERROR")
