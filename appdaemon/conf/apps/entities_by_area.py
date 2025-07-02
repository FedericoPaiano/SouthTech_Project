import appdaemon.plugins.hass.hassapi as hass

class EntitiesByArea(hass.Hass):
    """
    Modulo per recuperare le entità organizzate per aree da Home Assistant.
    Questa classe fornisce metodi per ottenere le aree e le entità associate.
    """

    def initialize(self):
        """Inizializzazione del modulo"""
        self.log("📊 EntitiesByArea inizializzato")
        
        # Cache per le aree e le entità
        self.areas_cache = None
        self.entities_by_area_cache = None
        self.last_cache_update = None
        
        # Cache lifetime (in secondi)
        self.cache_lifetime = 300  # 5 minuti di default
        
        # Log iniziale
        self.log_config()
    
    def log_config(self):
        """Log della configurazione"""
        self.log("✅ EntitiesByArea pronto")
        self.log(f"⏱️ Cache lifetime: {self.cache_lifetime} secondi")
    
    def get_areas(self, use_cache=True):
        """
        Recupera tutte le aree da Home Assistant
        
        Args:
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            list: Lista di aree ordinate per nome
        """
        try:
            # Usa cache se richiesto e disponibile
            if use_cache and self.areas_cache is not None:
                self.log("🔍 Usando cache per le aree")
                return self.areas_cache.copy()
            
            self.log("🔍 Recuperando aree da Home Assistant...")
            areas = self.call_service("homeassistant/list_areas", return_result=True)
            
            # Ordina le aree per nome
            sorted_areas = sorted(areas, key=lambda area: area.get("name", "").lower())
            
            # Aggiorna la cache
            self.areas_cache = sorted_areas.copy()
            
            self.log(f"✅ Recuperate {len(sorted_areas)} aree da Home Assistant")
            return sorted_areas
            
        except Exception as e:
            self.error(f"❌ Errore recupero aree: {e}")
            return []
    
    def get_area_id_to_name_map(self, use_cache=True):
        """
        Crea un dizionario di mappatura da ID area a nome area
        
        Args:
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            dict: Mappatura {area_id: area_name}
        """
        areas = self.get_areas(use_cache=use_cache)
        return {area["id"]: area["name"] for area in areas}
    
    def get_entities_by_area(self, use_cache=True):
        """
        Recupera entità organizzate per area da Home Assistant
        
        Args:
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            dict: Dizionario di mappatura {entity_id: area_name}
        """
        try:
            # Usa cache se richiesto e disponibile
            if use_cache and self.entities_by_area_cache is not None:
                self.log("🔍 Usando cache per entità per area")
                return self.entities_by_area_cache.copy()
            
            self.log("🔍 Recuperando entità per area da Home Assistant...")
            
            # Ottieni mappatura area_id -> area_name
            area_map = self.get_area_id_to_name_map(use_cache=use_cache)
            
            # Recupera dispositivi e entità con relative aree
            devices = self.call_service("homeassistant/list_devices", return_result=True)
            entity_registry = self.call_service("homeassistant/list_entities", return_result=True)
            
            # Crea mappatura device_id -> area_id
            device_area_map = {}
            for device in devices:
                if "area_id" in device and device["area_id"]:
                    device_area_map[device["id"]] = device["area_id"]
            
            # Crea mappatura entity_id -> area_name
            entity_area_map = {}
            for entity in entity_registry:
                if "device_id" in entity and entity["device_id"] in device_area_map:
                    area_id = device_area_map[entity["device_id"]]
                    if area_id in area_map:
                        entity_area_map[entity["entity_id"]] = area_map[area_id]
                elif "area_id" in entity and entity["area_id"] in area_map:
                    # Alcune entità hanno area_id direttamente
                    entity_area_map[entity["entity_id"]] = area_map[entity["area_id"]]
            
            # Aggiorna la cache
            self.entities_by_area_cache = entity_area_map.copy()
            
            self.log(f"✅ Mappate {len(entity_area_map)} entità con le loro aree")
            return entity_area_map
            
        except Exception as e:
            self.error(f"❌ Errore recupero entità per area: {e}")
            return {}
    
    def get_entities_in_area(self, area_name, entity_type=None, use_cache=True):
        """
        Ottiene tutte le entità in una specifica area, con opzionale filtro per tipo
        
        Args:
            area_name (str): Nome dell'area
            entity_type (str, optional): Tipo di entità da filtrare (e.g., 'light', 'sensor')
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            list: Lista di entity_id in quell'area
        """
        try:
            # Ottieni mappatura entità -> area
            entity_area_map = self.get_entities_by_area(use_cache=use_cache)
            
            # Filtra per area
            entities_in_area = [
                entity_id for entity_id, area in entity_area_map.items()
                if area.lower() == area_name.lower()
            ]
            
            # Filtra per tipo se specificato
            if entity_type:
                entities_in_area = [
                    entity_id for entity_id in entities_in_area
                    if entity_id.startswith(f"{entity_type}.")
                ]
            
            return sorted(entities_in_area)
            
        except Exception as e:
            self.error(f"❌ Errore recupero entità in area {area_name}: {e}")
            return []
    
    def get_areas_for_entity_type(self, entity_type, use_cache=True):
        """
        Ottiene tutte le aree che contengono entità di un certo tipo
        
        Args:
            entity_type (str): Tipo di entità (e.g., 'light', 'sensor')
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            list: Lista di nomi di aree ordinate alfabeticamente
        """
        try:
            # Ottieni mappatura entità -> area
            entity_area_map = self.get_entities_by_area(use_cache=use_cache)
            
            # Filtra aree con entità del tipo specificato
            areas = set()
            for entity_id, area in entity_area_map.items():
                if entity_id.startswith(f"{entity_type}."):
                    areas.add(area)
            
            return sorted(list(areas))
            
        except Exception as e:
            self.error(f"❌ Errore recupero aree per tipo {entity_type}: {e}")
            return []
    
    def get_unique_areas(self, use_cache=True):
        """
        Ottiene tutte le aree uniche che hanno entità assegnate
        
        Args:
            use_cache (bool): Usa la cache se disponibile
            
        Returns:
            list: Lista di nomi di aree ordinate alfabeticamente
        """
        try:
            # Ottieni mappatura entità -> area
            entity_area_map = self.get_entities_by_area(use_cache=use_cache)
            
            # Estrai aree uniche
            areas = set(entity_area_map.values())
            
            return sorted(list(areas))
            
        except Exception as e:
            self.error(f"❌ Errore recupero aree uniche: {e}")
            return []
    
    def force_cache_refresh(self):
        """
        Forza l'aggiornamento della cache
        
        Returns:
            bool: True se l'aggiornamento è riuscito
        """
        try:
            self.log("🔄 Aggiornamento forzato della cache...")
            
            # Rimuovi cache esistente
            self.areas_cache = None
            self.entities_by_area_cache = None
            
            # Ricarica aree ed entità
            areas = self.get_areas(use_cache=False)
            entity_area_map = self.get_entities_by_area(use_cache=False)
            
            self.log(f"✅ Cache aggiornata: {len(areas)} aree, {len(entity_area_map)} entità mappate")
            return True
            
        except Exception as e:
            self.error(f"❌ Errore aggiornamento cache: {e}")
            return False
    
    def get_formatted_area_name(self, area_name):
        """
        Formatta il nome dell'area (es. "living_room" -> "Living Room")
        
        Args:
            area_name (str): Nome dell'area da formattare
            
        Returns:
            str: Nome dell'area formattato
        """
        if not area_name:
            return ""
        
        # Sostituisci "_" con spazi e formatta
        formatted = area_name.replace("_", " ")
        
        # Capitalizza le parole
        return " ".join(word.capitalize() for word in formatted.split())