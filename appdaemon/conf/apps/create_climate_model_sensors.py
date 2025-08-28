import appdaemon.plugins.hass.hassapi as hass
import re

class CreateClimateModelSensors(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateClimateModelSensors...", level="INFO")
        
        # Cache per ottimizzare le richieste di stato
        self.temperature_cache = {}
        self.climate_sensors_created = {}  # Traccia i sensori creati per evitare duplicati

        # Ascolta l'evento homeassistant_start per l'inizializzazione
        self.listen_event(self.create_climate_sensors, "homeassistant_start")
        
        # Ascolta i cambiamenti del registry per aggiornamenti dinamici
        self.listen_event(self.create_climate_sensors, "area_registry_updated")
        self.listen_event(self.create_climate_sensors, "device_registry_updated")

        self.log("App configurata per ascoltare gli eventi di registry.", level="INFO")
        
        # Esegui un aggiornamento iniziale
        self.create_climate_sensors()

    def get_climate_entities_by_area(self):
        """
        Recupera tutte le entità climate raggruppate per area
        Restituisce un dizionario: {area_name: [climate_entity_ids]}
        """
        self.log("Recupero entità climate per area...", level="DEBUG")
        
        # Recupera tutte le entità
        all_entities = self.get_state()
        
        # Mappa area_name -> lista entità climate
        area_climate_entities = {}
        
        for entity_id in all_entities:
            try:
                # Filtra solo le entità climate
                if entity_id.startswith('climate.'):
                    area_name = self.area_name(entity_id)
                    if area_name:  # solo se è assegnata a un'area
                        if area_name not in area_climate_entities:
                            area_climate_entities[area_name] = []
                        area_climate_entities[area_name].append(entity_id)
                        
            except Exception as e:
                self.log(f"Errore nel recuperare area per {entity_id}: {e}", level="WARNING")
        
        return area_climate_entities

    def find_temperature_sensors_for_area(self, area_name):
        """
        Trova tutti i sensori di temperatura per una specifica area
        Restituisce una lista di entity_id dei sensori di temperatura
        """
        self.log(f"Ricerca sensori di temperatura per area: {area_name}", level="DEBUG")
        
        # Recupera tutte le entità
        all_entities = self.get_state()
        temperature_sensors = []
        
        for entity_id in all_entities:
            try:
                # Filtra solo i sensori
                if entity_id.startswith('sensor.'):
                    entity_area = self.area_name(entity_id)
                    if entity_area == area_name:
                        # Controlla se è un sensore di temperatura
                        entity_state = self.get_state(entity_id, attribute="all")
                        if entity_state and 'attributes' in entity_state:
                            device_class = entity_state['attributes'].get('device_class', '')
                            unit_of_measurement = entity_state['attributes'].get('unit_of_measurement', '')
                            
                            # Verifica se è un sensore di temperatura
                            if (device_class == 'temperature' or 
                                '°C' in unit_of_measurement or 
                                '°F' in unit_of_measurement or
                                'temperature' in entity_id.lower()):
                                temperature_sensors.append(entity_id)
                                
            except Exception as e:
                self.log(f"Errore nel verificare il sensore {entity_id}: {e}", level="WARNING")
        
        self.log(f"Trovati {len(temperature_sensors)} sensori di temperatura per l'area {area_name}: {temperature_sensors}", level="DEBUG")
        return temperature_sensors

    def create_climate_sensors(self, *args, **kwargs):
        self.log("Avvio creazione sensori modello per le entità climate...", level="DEBUG")

        try:
            # Ottieni le entità climate raggruppate per area
            area_climate_entities = self.get_climate_entities_by_area()
            
            if not area_climate_entities:
                self.log("Nessuna entità climate trovata con area assegnata.", level="WARNING")
                return

            # Per ogni area con entità climate
            for area_name, climate_entities in area_climate_entities.items():
                self.log(f"Processando area: {area_name} con {len(climate_entities)} entità climate", level="DEBUG")
                
                # Trova TUTTI i sensori di temperatura per questa area
                all_temperature_sensors_in_area = self.find_temperature_sensors_for_area(area_name)
                
                if not all_temperature_sensors_in_area:
                    self.log(f"Nessun sensore di temperatura trovato per l'area {area_name}. Saltando...", level="WARNING")
                    continue

                # Costruisci l'ID del sensore da escludere
                safe_area_name = area_name.lower().replace(' ', '_')
                excluded_sensor_id = f"sensor.temperature_in_{safe_area_name}"
                
                primary_temp_sensor = None
                # Cerca il primo sensore di temperatura disponibile che NON abbia l'ID escluso
                for sensor_id in all_temperature_sensors_in_area:
                    if sensor_id != excluded_sensor_id:
                        primary_temp_sensor = sensor_id
                        self.log(f"Trovato sensore sorgente valido '{self.friendly_name(sensor_id)}' con entity_id: {primary_temp_sensor}", level="INFO")
                        break

                if not primary_temp_sensor:
                    self.log(f"Nessun sensore di temperatura valido trovato nell'area {area_name} (escluso l'ID '{excluded_sensor_id}'). Saltando...", level="WARNING")
                    continue
                
                # Usa la prima entità climate nell'area per generare sia l'ID che il nome
                first_climate_entity = climate_entities[0]
                digits = re.findall(r'\d+', first_climate_entity)
                
                if not digits:
                    self.log(f"Nessun numero trovato nell'ID dell'entità {first_climate_entity}. Impossibile creare il sensore. Saltando...", level="WARNING")
                    continue

                # --- NUOVA LOGICA PER ID E NOME ---
                # ID del sensore: es. "sensor.temperature_01_06"
                climate_sensor_id = f"sensor.temperature_{'_'.join(digits)}"

                # Nome del sensore: recupera il friendly_name dell'entità climate e aggiunge l'area
                # es. "Temperatura Termostato in Ingresso"
                climate_friendly_name = self.friendly_name(first_climate_entity)
                sensor_name = f"Temperatura {climate_friendly_name} in {area_name}"
                
                # --- FINE NUOVA LOGICA ---

                temperature_state = self.get_validated_temperature(primary_temp_sensor)

                # Crea il sensore e inizia ad ascoltare i cambiamenti di stato
                self.create_sensor(climate_sensor_id, sensor_name, temperature_state)
                
                # Rimuovi eventuali listener precedenti per evitare duplicati
                if climate_sensor_id in self.climate_sensors_created:
                    self.cancel_listen_state(self.climate_sensors_created[climate_sensor_id])
                
                # Crea un nuovo listener e salva l'handle
                listen_handle = self.listen_state(
                    self.update_climate_sensor, 
                    primary_temp_sensor, 
                    climate_sensor_id=climate_sensor_id, 
                    name=sensor_name
                )
                self.climate_sensors_created[climate_sensor_id] = listen_handle
        
        except Exception as e:
            self.log(f"Errore durante la creazione dei sensori climate: {str(e)}", level="ERROR")

    def get_validated_temperature(self, sensor_id: str):
        """Ottiene e valida lo stato del sensore di temperatura"""
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
        """Aggiorna il sensore climate quando cambia lo stato del sensore della temperatura"""
        name = kwargs['name']
        climate_sensor_id = kwargs['climate_sensor_id']

        try:
            new_state = float(new)
            self.temperature_cache[entity] = new_state  # Aggiorna la cache
            self.log(f"Aggiornamento sensore {climate_sensor_id}: nuovo stato {new_state}°C", level="DEBUG")
        except (ValueError, TypeError):
            self.log(f"Nuovo stato non valido per {entity}: {new}. Impostato a 'unknown'.", level="WARNING")
            new_state = "unknown"
            if entity in self.temperature_cache:
                del self.temperature_cache[entity]  # Rimuovi dalla cache se lo stato non è valido

        self.create_sensor(climate_sensor_id, name, new_state)

    def create_sensor(self, object_id: str, name: str, state):
        """Crea o aggiorna un sensore di temperatura"""
        attributes = {
            "friendly_name": name, # Usiamo friendly_name che è l'attributo corretto
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement"
        }
        sensor_state = state if isinstance(state, (float, int)) else "unknown"

        try:
            self.set_state(object_id, state=sensor_state, attributes=attributes)
            self.log(f"Creato/aggiornato sensore '{name}' ({object_id}) con stato '{sensor_state}'", level="INFO")
        except Exception as e:
            self.log(f"Errore durante la creazione del sensore '{object_id}': {str(e)}", level="ERROR")
