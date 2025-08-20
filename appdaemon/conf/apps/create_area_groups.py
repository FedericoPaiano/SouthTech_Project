import appdaemon.plugins.hass.hassapi as hass
import re

class CreateAreaGroups(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateAreaGroups (Versione Italiana)...")
        
        self.translation_map = {
            'light': 'Luci',
            'cover': 'Coperture',
            'climate': 'Clima',
            'temperature': 'Temperatura',
            'humidity': 'Umidità',
            'illuminance': 'Illuminazione',
            'presence': 'Presenza',
            'entities': 'Entità'
        }
        
        self.listen_event(self.handle_event, "homeassistant_start")
        self.listen_event(self.handle_area_registry_update, "area_registry_updated")
        self.listen_event(self.handle_device_registry_update, "device_registry_updated")
        
        self.log("App configurata per ascoltare gli eventi di registry.")
        self.update_groups()

    def handle_event(self, event_name, data, kwargs):
        self.log(f"Evento rilevato: {event_name}", level="DEBUG")
        self.update_groups()

    def handle_area_registry_update(self, event_name, data, kwargs):
        self.log(f"Registry delle aree aggiornato: {event_name}", level="DEBUG")
        self.update_groups()

    def handle_device_registry_update(self, event_name, data, kwargs):
        self.log(f"Registry dei dispositivi aggiornato: {event_name}", level="DEBUG")
        self.update_groups()

    def get_entities_by_area_and_domain(self):
        """
        Recupera tutte le entità, raggruppandole per area e dominio.
        Le entità senza area vengono raggruppate sotto una chiave speciale.
        """
        self.log("Recupero entità per area e dominio...", level="DEBUG")
        
        all_entities = self.get_state()
        area_domain_entities = {}
        # Chiave speciale per le entità non assegnate
        NO_AREA_KEY = "__SenzaArea__"
        
        domains_of_interest = {
            'light', 'cover', 'climate', 'sensor', 'binary_sensor'
        }
        
        for entity_id in all_entities:
            domain = entity_id.split('.')[0]
            if domain not in domains_of_interest:
                continue

            try:
                # Assegna l'area o la chiave speciale se non trovata
                area_name = self.area_name(entity_id) or NO_AREA_KEY
                
                if area_name not in area_domain_entities:
                    area_domain_entities[area_name] = {}
                
                entity_type = None
                
                if domain == 'sensor':
                    entity_state = self.get_state(entity_id, attribute="all")
                    if entity_state and 'attributes' in entity_state:
                        attrs = entity_state['attributes']
                        device_class = attrs.get('device_class', '')
                        unit = attrs.get('unit_of_measurement', '')
                        
                        if device_class == 'temperature' or '°' in unit:
                            entity_type = 'temperature'
                        elif device_class == 'humidity' or '%' in unit:
                            entity_type = 'humidity'
                        elif device_class == 'illuminance' or 'lx' in unit or 'lux' in unit:
                            entity_type = 'illuminance'
                
                elif domain == 'binary_sensor':
                    entity_state = self.get_state(entity_id, attribute="all")
                    if entity_state and 'attributes' in entity_state:
                        attrs = entity_state['attributes']
                        device_class = attrs.get('device_class', '')
                        if device_class in ['motion', 'occupancy', 'presence'] or 'presence' in entity_id.lower() or 'motion' in entity_id.lower():
                            entity_type = 'presence'
                
                else: # light, cover, climate
                    entity_type = domain

                if entity_type:
                    if entity_type not in area_domain_entities[area_name]:
                        area_domain_entities[area_name][entity_type] = []
                    area_domain_entities[area_name][entity_type].append(entity_id)

            except Exception as e:
                self.log(f"Errore nel processare l'entità {entity_id}: {e}", level="WARNING")
        
        return area_domain_entities

    def slugify(self, text):
        """Converte una stringa in un formato 'slug' sicuro per gli ID."""
        text = text.lower()
        text = re.sub(r'[\s\W-]+', '_', text)
        return text.strip('_')

    def update_groups(self):
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        area_domain_entities = self.get_entities_by_area_and_domain()
        NO_AREA_KEY = "__SenzaArea__"
        
        for area_name, domains in area_domain_entities.items():
            all_area_entities = []
            
            is_no_area_group = (area_name == NO_AREA_KEY)

            for domain, entities in domains.items():
                if not entities:
                    continue

                italian_name = self.translation_map.get(domain, domain.title())
                italian_slug = self.slugify(italian_name)
                
                if is_no_area_group:
                    # Logica per entità SENZA area
                    object_id = f"{italian_slug}_senza_area"
                    friendly_name = f"Gruppo {italian_name} Senza Area"
                else:
                    # Logica per entità CON area
                    area_slug = self.slugify(area_name)
                    object_id = f"{italian_slug}_{area_slug}"
                    friendly_name = f"Gruppo {italian_name} in {area_name.title()}"
                
                service_data = {
                    'object_id': object_id,
                    'name': friendly_name,
                    'entities': entities
                }
                
                self.log(f"Creazione/aggiornamento gruppo '{friendly_name}' (group.{object_id}) con {len(entities)} entità")
                self.call_service('group/set', **service_data)
                
                if not is_no_area_group:
                    all_area_entities.extend(entities)
            
            # Crea il gruppo generale solo per le aree definite (escludendo "Senza Area")
            if all_area_entities and not is_no_area_group:
                area_slug = self.slugify(area_name)
                entities_slug = self.slugify(self.translation_map['entities'])
                
                object_id = f"{entities_slug}_{area_slug}"
                friendly_name = f"Gruppo {self.translation_map['entities']} in {area_name.title()}"
                
                area_service_data = {
                    'object_id': object_id,
                    'name': friendly_name,
                    'entities': all_area_entities
                }
                
                self.log(f"Creazione/aggiornamento gruppo generale '{friendly_name}' (group.{object_id}) con {len(all_area_entities)} entità")
                self.call_service('group/set', **area_service_data)

        self.log("Aggiornamento gruppi completato.")
