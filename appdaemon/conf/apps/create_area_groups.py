import appdaemon.plugins.hass.hassapi as hass
import re

class CreateAreaGroups(hass.Hass):

    def initialize(self):
        """
        Inizializza l'app, imposta le mappe di traduzione e si mette in ascolto
        degli eventi di Home Assistant per aggiornare i gruppi.
        """
        self.log("Inizializzazione dell'app CreateAreaGroups (Versione Italiana)...")
        
        # Mappa per i nomi dei gruppi specifici per area
        self.translation_map = {
            'light': 'Luci',
            'cover': 'Coperture',
            'climate': 'Clima',
            'switch': 'Prese',
            'temperature': 'Temperatura',
            'humidity': 'Umidità',
            'illuminance': 'Illuminazione',
            'presence': 'Presenza',
            'entities': 'Entità'
        }
        
        # MODIFICA: Aggiornati i nomi dei gruppi globali mantenendo gli ID originali
        self.global_name_map = {
            'light': {'name': 'Gruppo Luci', 'id': 'luci_tutte'},
            'cover': {'name': 'Gruppo Coperture', 'id': 'coperture_tutte'},
            'climate': {'name': 'Gruppo Clima', 'id': 'clima_tutti'},
            'switch': {'name': 'Gruppo Prese', 'id': 'prese_tutte'},
            'temperature': {'name': 'Gruppo Temperature', 'id': 'temperature_tutte'},
            'humidity': {'name': 'Gruppo Umidità', 'id': 'umidita_tutte'},
            'illuminance': {'name': "Gruppo Illuminazione", 'id': 'illuminazione_tutta'},
            'presence': {'name': 'Gruppo Presenza', 'id': 'presenza_tutta'}
        }
        
        # Listener per gli eventi che scatenano l'aggiornamento
        self.listen_event(self.handle_event, "homeassistant_start")
        self.listen_event(self.handle_area_registry_update, "area_registry_updated")
        self.listen_event(self.handle_device_registry_update, "device_registry_updated")
        
        self.log("App configurata per ascoltare gli eventi di registry.")
        self.update_groups() # Esegue un primo aggiornamento all'avvio

    def handle_event(self, event_name, data, kwargs):
        """Gestore generico per eventi."""
        self.log(f"Evento rilevato: {event_name}", level="DEBUG")
        self.update_groups()

    def handle_area_registry_update(self, event_name, data, kwargs):
        """Gestore per aggiornamenti al registro delle aree."""
        self.log(f"Registry delle aree aggiornato: {event_name}", level="DEBUG")
        self.update_groups()

    def handle_device_registry_update(self, event_name, data, kwargs):
        """Gestore per aggiornamenti al registro dei dispositivi."""
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
        NO_AREA_KEY = "__SenzaArea__"
        
        # Domini di interesse da processare
        domains_of_interest = {
            'light', 'cover', 'climate', 'switch', 'sensor', 'binary_sensor'
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
                
                # Classificazione dei sensori in base a device_class o unità di misura
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
                
                # Classificazione dei binary_sensor in base a device_class o nome
                elif domain == 'binary_sensor':
                    entity_state = self.get_state(entity_id, attribute="all")
                    if entity_state and 'attributes' in entity_state:
                        attrs = entity_state['attributes']
                        device_class = attrs.get('device_class', '')
                        if device_class in ['motion', 'occupancy', 'presence'] or 'presence' in entity_id.lower() or 'motion' in entity_id.lower():
                            entity_type = 'presence'
                
                # Per gli altri domini, il tipo corrisponde al dominio stesso
                else: 
                    entity_type = domain

                # Aggiunge l'entità alla struttura dati
                if entity_type:
                    if entity_type not in area_domain_entities[area_name]:
                        area_domain_entities[area_name][entity_type] = []
                    area_domain_entities[area_name][entity_type].append(entity_id)

            except Exception as e:
                self.log(f"Errore nel processare l'entità {entity_id}: {e}", level="WARNING")
        
        return area_domain_entities

    def slugify(self, text):
        """Converte una stringa in un formato 'slug' sicuro per gli ID, rimuovendo gli accenti."""
        import unicodedata
        text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[\s\W-]+', '_', text)
        return text.strip('_')

    def update_groups(self):
        """
        Funzione principale che orchestra la creazione e l'aggiornamento di tutti i gruppi.
        """
        self.log("Avvio aggiornamento dei gruppi...", level="DEBUG")
        
        area_domain_entities = self.get_entities_by_area_and_domain()
        NO_AREA_KEY = "__SenzaArea__"
        
        # Dizionario e lista per raccogliere le entità per i gruppi globali
        all_entities_by_type_with_area = {}
        all_entities_with_area = []

        # --- FASE 1: Creazione dei gruppi per area e "Senza Area" ---
        for area_name, domains in area_domain_entities.items():
            all_area_entities = []
            is_no_area_group = (area_name == NO_AREA_KEY)

            for domain, entities in domains.items():
                if not entities:
                    continue
                
                # Popola le liste per i gruppi globali solo con entità che hanno un'area
                if not is_no_area_group:
                    if domain not in all_entities_by_type_with_area:
                        all_entities_by_type_with_area[domain] = []
                    all_entities_by_type_with_area[domain].extend(entities)
                    all_entities_with_area.extend(entities)

                # Creazione dei gruppi specifici (es. "Luci in Salotto" o "Prese Senza Area")
                italian_name = self.translation_map.get(domain, domain.title())
                italian_slug = self.slugify(italian_name)
                
                if is_no_area_group:
                    object_id = f"{italian_slug}_senza_area"
                    friendly_name = f"Gruppo {italian_name} Senza Area"
                else:
                    area_slug = self.slugify(area_name)
                    object_id = f"{italian_slug}_{area_slug}"
                    friendly_name = f"Gruppo {italian_name} in {area_name.title()}"
                
                service_data = {'object_id': object_id, 'name': friendly_name, 'entities': entities}
                self.log(f"Creazione/aggiornamento gruppo '{friendly_name}' (group.{object_id}) con {len(entities)} entità")
                self.call_service('group/set', **service_data)
                
                if not is_no_area_group:
                    all_area_entities.extend(entities)
            
            # Creazione del gruppo generale dell'area (es. "Entità in Salotto")
            if all_area_entities and not is_no_area_group:
                area_slug = self.slugify(area_name)
                entities_slug = self.slugify(self.translation_map['entities'])
                object_id = f"{entities_slug}_{area_slug}"
                friendly_name = f"Gruppo {self.translation_map['entities']} in {area_name.title()}"
                area_service_data = {'object_id': object_id, 'name': friendly_name, 'entities': all_area_entities}
                self.log(f"Creazione/aggiornamento gruppo generale '{friendly_name}' (group.{object_id}) con {len(all_area_entities)} entità")
                self.call_service('group/set', **area_service_data)

        # --- FASE 2: Creazione dei gruppi globali ---
        self.log("Creazione/aggiornamento gruppi globali per tipo...")
        for domain, entities in all_entities_by_type_with_area.items():
            if not entities:
                continue
            
            name_info = self.global_name_map.get(domain)
            if name_info:
                object_id = name_info['id']
                friendly_name = name_info['name']
                service_data = {'object_id': object_id, 'name': friendly_name, 'entities': entities}
                self.log(f"Creazione/aggiornamento gruppo globale '{friendly_name}' (group.{object_id}) con {len(entities)} entità")
                self.call_service('group/set', **service_data)

        # Creazione del gruppo globale di tutte le entità con un'area
        self.log("Creazione/aggiornamento gruppo globale di tutte le entità...")
        if all_entities_with_area:
            object_id = 'entita_tutte'
            # MODIFICA: Aggiornato il nome del gruppo globale di tutte le entità
            friendly_name = 'Gruppo Entità'
            service_data = {'object_id': object_id, 'name': friendly_name, 'entities': all_entities_with_area}
            self.log(f"Creazione/aggiornamento gruppo globale '{friendly_name}' (group.{object_id}) con {len(all_entities_with_area)} entità")
            self.call_service('group/set', **service_data)

        self.log("Aggiornamento gruppi completato.")
