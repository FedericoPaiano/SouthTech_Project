import appdaemon.plugins.hass.hassapi as hass
import re

class CreateAreaGroups(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateAreaGroups...")
        
        # Ascolta l'evento homeassistant_start per eseguire lo script Python all'avvio
        self.listen_event(self.handle_event, "homeassistant_start")
        
        # Ascolta i cambiamenti di stato dei sensori
        sensors = [
            "sensor.area_light_list",
            "sensor.area_cover_list",
            "sensor.area_climate_list",
            "sensor.area_temperature_list",
            "sensor.area_humidity_list",
            "sensor.area_illuminance_list"
        ]
        for sensor in sensors:
            self.listen_state(self.handle_sensor_change, sensor, attribute="all")

        self.log("App configurata per ascoltare gli eventi e i cambiamenti di stato dei sensori.")
        
        # Esegui un aggiornamento iniziale dei gruppi
        self.update_groups()

    def handle_event(self, event_name, data, kwargs):
        self.log(f"Evento rilevato: {event_name} con dati: {data}.", level="DEBUG")
        self.update_groups()

    def handle_sensor_change(self, entity, attribute, old, new, kwargs):
        self.log(f"Cambiamento stato o attributo del sensore {entity}: {new}.", level="DEBUG")
        
        # Se "new" è un dizionario, potrebbe contenere sia lo stato che gli attributi
        if isinstance(new, dict):
            new_state = new.get('state')
            new_attributes = new.get('attributes')
            
            self.log(f"Nuovo stato: {new_state}, Nuovi attributi: {new_attributes}", level="DEBUG")
        
        self.update_groups()

    def update_groups(self):
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        # Lista dei sensori che contengono le informazioni sulle entità e aree
        sensor_entity_ids = {
            "light": "sensor.area_light_list",
            "cover": "sensor.area_cover_list",
            "climate": "sensor.area_climate_list",
            "temperature": "sensor.area_temperature_list",
            "humidity": "sensor.area_humidity_list",
            "illuminance": "sensor.area_illuminance_list"
        }

        # Mappa per raccogliere le entità per area
        area_entity_map = {}

        # Funzione di utilità per ottenere lo stato e gli attributi del sensore
        def get_sensor_attributes(sensor_entity_id):
            try:
                attributes = self.get_state(sensor_entity_id, attribute="attributes")
                if attributes:
                    return attributes.get("areas_entity", "")
                else:
                    self.log(f"Nessun attributo trovato per {sensor_entity_id}.")
            except Exception as e:
                self.log(f"Errore durante il recupero degli attributi per {sensor_entity_id}: {e}", level="ERROR")
            return ""

        # Funzione per processare ciascun sensore e aggregare entità per area
        def process_sensor(sensor_entity_id):
            self.log(f"Processando sensore {sensor_entity_id}...", level="DEBUG")
            
            try:
                sensor_state = self.get_state(sensor_entity_id)
                if sensor_state == "OK":
                    areas_entity = get_sensor_attributes(sensor_entity_id)
                    
                    if areas_entity:
                        # Processa ogni riga del risultato ottenuto dal sensore
                        for line in areas_entity.splitlines():
                            if " | " in line:
                                entity, area = line.split(" | ")
                                
                                # Aggiungi l'entità alla lista di entità per ogni area
                                if area in area_entity_map:
                                    area_entity_map[area].append(entity)
                                else:
                                    area_entity_map[area] = [entity]
                    else:
                        self.log(f"Nessun dato trovato nell'attributo 'areas_entity' del sensore {sensor_entity_id}.")
                else:
                    self.log(f"Lo stato del sensore {sensor_entity_id} non è 'OK'. Entità non aggregate.")
            except Exception as e:
                self.log(f"Errore durante il processamento del sensore {sensor_entity_id}: {e}", level="ERROR")

        # Processa ogni sensore nella lista per aggregare tutte le entità per area
        for sensor_entity_id in sensor_entity_ids.values():
            process_sensor(sensor_entity_id)

        # Ottieni l'elenco dei gruppi esistenti
        existing_groups = self.get_state('group.all_groups', attribute='attributes')
        existing_groups = existing_groups.get('entity_id', []) if existing_groups else []

        # Crea o aggiorna gruppi per ogni area con tutte le entità associate
        for area, entities in area_entity_map.items():
            group_name = f"area_{area.lower().replace(' ', '_')}_entities"
            service_data = {
                'object_id': group_name,
                'name': f"Entità {area.replace('_', ' ')}",
                'entities': entities
            }
            
            if group_name in existing_groups:
                self.log(f"Aggiornamento gruppo {group_name} con entità: {entities}")
                self.call_service('group/set', **service_data)
            else:
                self.log(f"Creazione gruppo {group_name} con entità: {entities}")
                self.call_service('group/set', **service_data)

        # Rimuove gruppi che non sono più necessari
        for group_name in existing_groups:
            if not any(group_name.startswith(f"area_{area.lower().replace(' ', '_')}_entities") for area in area_entity_map):
                self.log(f"Rimozione gruppo {group_name}")
                self.call_service('group/remove', object_id=group_name)
