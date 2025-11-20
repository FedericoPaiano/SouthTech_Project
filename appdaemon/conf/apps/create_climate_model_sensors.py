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
        
        # Ascolta quando create_environment_sensors ha completato
        self.listen_event(self.on_environment_sensors_ready, "environment_sensors_ready")

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

    def on_environment_sensors_ready(self, event_name, data, kwargs):
        """Ri-crea i sensori quando gli aggregati ambientali sono pronti"""
        self.log("♻️ Sensori ambientali pronti, ri-creo i sensori climate...", level="INFO")
        self.create_climate_sensors()

    def find_temperature_sensors_for_area(self, area_name):
        """
        Trova il sensore di temperatura per una specifica area.
        Priorità:
        1. Sensore aggregato creato da create_environment_sensors (sensor.<area>_temperature)
        2. Primo sensore fisico disponibile (fallback)
        Restituisce una lista di entity_id dei sensori di temperatura
        """
        self.log(f"Ricerca sensori di temperatura per area: {area_name}", level="DEBUG")
        
        safe_area_name = area_name.lower().replace(' ', '_').replace('-', '_')
        
        # PRIORITÀ 1: Cerca il sensore aggregato (sia medio che singolo hanno lo stesso nome)
        aggregated_sensor = f"sensor.{safe_area_name}_temperature"
        if self.entity_exists(aggregated_sensor):
            self.log(f"✅ Trovato sensore aggregato: {aggregated_sensor}", level="INFO")
            return [aggregated_sensor]
        
        # PRIORITÀ 3: Fallback ai sensori fisici (se non esistono aggregati)
        self.log(f"⚠️ Nessun sensore aggregato trovato, cerco sensori fisici...", level="WARNING")
        
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
        
        self.log(f"Trovati {len(temperature_sensors)} sensori fisici per l'area {area_name}: {temperature_sensors}", level="DEBUG")
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
                self.log(f"🏠 Processando area: {area_name} con {len(climate_entities)} entità climate: {climate_entities}", level="INFO")
                
                # Trova il sensore di temperatura (priorità agli aggregati)
                temperature_sensors = self.find_temperature_sensors_for_area(area_name)
                
                if not temperature_sensors:
                    self.log(f"⚠️ Nessun sensore di temperatura trovato per l'area '{area_name}'. Saltata.", level="WARNING")
                    continue

                # Usa il primo sensore (che sarà l'aggregato se esiste, grazie alla priorità)
                primary_temp_sensor = temperature_sensors[0]
                
                self.log(f"📍 Sensore temperatura selezionato per '{area_name}': {primary_temp_sensor}", level="INFO")
                
                # Cerca l'entità climate con numeri nell'ID (ignora wrapper senza numeri)
                climate_with_numbers = None
                for climate_entity in climate_entities:
                    digits = re.findall(r'\d+', climate_entity)
                    if digits:
                        climate_with_numbers = climate_entity
                        self.log(f"🔢 Trovata entità climate con numeri: {climate_entity} (numeri: {digits})", level="DEBUG")
                        break
                    else:
                        self.log(f"⏭️ Saltata entità senza numeri: {climate_entity}", level="DEBUG")
                
                # Se nessuna entità ha numeri, salta questa area
                if not climate_with_numbers:
                    self.log(f"⚠️ Nessuna entità climate con numeri trovata in '{area_name}'. Entità presenti: {climate_entities}", level="WARNING")
                    continue
                
                # Estrai i numeri dall'entità climate
                digits = re.findall(r'\d+', climate_with_numbers)
                
                # --- LOGICA PER ID E NOME ---
                # ID del sensore: es. "sensor.temperature_01_06"
                climate_sensor_id = f"sensor.temperature_{'_'.join(digits)}"

                # Nome del sensore: recupera il friendly_name dell'entità climate e aggiunge l'area
                # es. "Temperatura Relay 06 in Ingresso"
                climate_friendly_name = self.friendly_name(climate_with_numbers)
                sensor_name = f"Temperatura {climate_friendly_name} in {area_name}"
                
                # --- FINE LOGICA ---

                temperature_state = self.get_validated_temperature(primary_temp_sensor)

                # Crea il sensore e inizia ad ascoltare i cambiamenti di stato
                self.create_sensor(climate_sensor_id, sensor_name, temperature_state)
                
                # Rimuovi eventuali listener precedenti per evitare duplicati
                if climate_sensor_id in self.climate_sensors_created:
                    old_handle = self.climate_sensors_created[climate_sensor_id].get('handle')
                    if old_handle:
                        self.cancel_listen_state(old_handle)
                
                # Crea un nuovo listener e salva l'handle con la sorgente
                handle = self.listen_state(
                    self.update_climate_sensor, 
                    primary_temp_sensor,
                    name=sensor_name,
                    climate_sensor_id=climate_sensor_id
                )
                
                self.climate_sensors_created[climate_sensor_id] = {
                    'source': primary_temp_sensor,
                    'handle': handle
                }
                
                self.log(f"✅ Creato sensore climate '{climate_sensor_id}' collegato a '{primary_temp_sensor}'", level="INFO")
        
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
