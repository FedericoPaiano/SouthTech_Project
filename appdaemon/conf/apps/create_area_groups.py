import appdaemon.plugins.hass.hassapi as hass

class CreateAreaGroups(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione dell'app CreateAreaGroups...")
        
        # Ascolta l'evento homeassistant_start per eseguire lo script Python all'avvio
        self.listen_event(self.handle_event, "homeassistant_start")
        
        # Ascolta i cambiamenti delle entità per aggiornare i gruppi quando necessario
        # Invece di ascoltare sensori specifici, ascoltiamo gli eventi di area
        self.listen_event(self.handle_area_registry_update, "area_registry_updated")
        self.listen_event(self.handle_device_registry_update, "device_registry_updated")
        
        self.log("App configurata per ascoltare gli eventi di registry.")
        
        # Esegui un aggiornamento iniziale dei gruppi
        self.update_groups()

    def handle_event(self, event_name, data, kwargs):
        self.log(f"Evento rilevato: {event_name} con dati: {data}.", level="DEBUG")
        self.update_groups()

    def handle_area_registry_update(self, event_name, data, kwargs):
        self.log(f"Registry delle aree aggiornato: {event_name}", level="DEBUG")
        self.update_groups()

    def handle_device_registry_update(self, event_name, data, kwargs):
        self.log(f"Registry dei dispositivi aggiornato: {event_name}", level="DEBUG")
        self.update_groups()

    def get_entities_by_area_and_domain(self):
        """
        Recupera tutte le entità raggruppate per area e dominio
        Restituisce un dizionario: {area_name: {domain: [entity_ids]}}
        """
        self.log("Recupero entità per area e dominio...", level="DEBUG")
        
        # Recupera tutte le entità
        all_entities = self.get_state()
        
        # Mappa area_name -> dominio -> lista entità
        area_domain_entities = {}
        
        # Domini di interesse (corrispondenti ai sensori originali)
        domains_of_interest = {
            'light': 'light',
            'cover': 'cover', 
            'climate': 'climate',
            'sensor': ['temperature', 'humidity', 'illuminance'],  # sensori specifici
            'binary_sensor': 'presence'  # sensori di presenza
        }
        
        for entity_id in all_entities:
            try:
                area_name = self.area_name(entity_id)
                if area_name:  # solo se è assegnata a un'area
                    domain = entity_id.split('.')[0]
                    
                    # Filtra per domini di interesse
                    if domain in domains_of_interest:
                        if area_name not in area_domain_entities:
                            area_domain_entities[area_name] = {}
                        
                        # Gestione speciale per i sensori
                        if domain == 'sensor':
                            # Controlla il device_class o il nome per categorizzare
                            entity_state = self.get_state(entity_id, attribute="all")
                            if entity_state and 'attributes' in entity_state:
                                device_class = entity_state['attributes'].get('device_class', '')
                                unit_of_measurement = entity_state['attributes'].get('unit_of_measurement', '')
                                
                                # Categorizza i sensori
                                sensor_type = None
                                if device_class == 'temperature' or '°C' in unit_of_measurement or '°F' in unit_of_measurement:
                                    sensor_type = 'temperature'
                                elif device_class == 'humidity' or '%' in unit_of_measurement:
                                    sensor_type = 'humidity'
                                elif device_class == 'illuminance' or 'lx' in unit_of_measurement or 'lux' in unit_of_measurement:
                                    sensor_type = 'illuminance'
                                
                                if sensor_type:
                                    if sensor_type not in area_domain_entities[area_name]:
                                        area_domain_entities[area_name][sensor_type] = []
                                    area_domain_entities[area_name][sensor_type].append(entity_id)
                        
                        elif domain == 'binary_sensor':
                            # Controlla se è un sensore di presenza
                            entity_state = self.get_state(entity_id, attribute="all")
                            if entity_state and 'attributes' in entity_state:
                                device_class = entity_state['attributes'].get('device_class', '')
                                if device_class in ['motion', 'occupancy', 'presence'] or 'presence' in entity_id.lower() or 'motion' in entity_id.lower():
                                    if 'presence' not in area_domain_entities[area_name]:
                                        area_domain_entities[area_name]['presence'] = []
                                    area_domain_entities[area_name]['presence'].append(entity_id)
                        
                        else:
                            # Domini semplici (light, cover, climate)
                            if domain not in area_domain_entities[area_name]:
                                area_domain_entities[area_name][domain] = []
                            area_domain_entities[area_name][domain].append(entity_id)
                            
            except Exception as e:
                self.log(f"Errore nel recuperare area per {entity_id}: {e}", level="WARNING")
        
        return area_domain_entities

    def update_groups(self):
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        # Ottieni le entità raggruppate per area e dominio
        area_domain_entities = self.get_entities_by_area_and_domain()
        
        # Ottieni l'elenco dei gruppi esistenti
        existing_groups = self.get_state('group.all_groups', attribute='attributes')
        existing_groups = existing_groups.get('entity_id', []) if existing_groups else []
        
        # Mappa per tenere traccia di tutti i gruppi creati
        created_groups = set()
        
        # Crea gruppi per ogni area e per ogni dominio
        for area_name, domains in area_domain_entities.items():
            # Raccoglie tutte le entità dell'area per il gruppo generale
            all_area_entities = []
            
            for domain, entities in domains.items():
                if entities:  # solo se ci sono entità per questo dominio
                    # Crea gruppo specifico per dominio
                    domain_group_name = f"area_{area_name.lower().replace(' ', '_')}_{domain}"
                    domain_service_data = {
                        'object_id': domain_group_name,
                        'name': f"{area_name.title()} - {domain.title()}",
                        'entities': entities
                    }
                    
                    self.log(f"Creazione/aggiornamento gruppo {domain_group_name} con {len(entities)} entità")
                    self.call_service('group/set', **domain_service_data)
                    created_groups.add(domain_group_name)
                    
                    # Aggiungi le entità al gruppo generale dell'area
                    all_area_entities.extend(entities)
            
            # Crea gruppo generale per l'area (tutte le entità)
            if all_area_entities:
                area_group_name = f"area_{area_name.lower().replace(' ', '_')}_entities"
                area_service_data = {
                    'object_id': area_group_name,
                    'name': f"{area_name.title()} - Entities",
                    'entities': all_area_entities
                }
                
                self.log(f"Creazione/aggiornamento gruppo generale {area_group_name} con {len(all_area_entities)} entità")
                self.call_service('group/set', **area_service_data)
                created_groups.add(area_group_name)
        
        # Rimuove gruppi che non sono più necessari
        # (solo quelli che seguono il pattern dei nostri gruppi area)
        for group_name in existing_groups:
            if (group_name.startswith('area_') and 
                ('_entities' in group_name or '_light' in group_name or '_cover' in group_name or 
                 '_climate' in group_name or '_temperature' in group_name or '_humidity' in group_name or 
                 '_illuminance' in group_name or '_presence' in group_name) and
                group_name not in created_groups):
                self.log(f"Rimozione gruppo non più necessario: {group_name}")
                self.call_service('group/remove', object_id=group_name)
        
        self.log(f"Aggiornamento gruppi completato. Creati/aggiornati {len(created_groups)} gruppi.")
