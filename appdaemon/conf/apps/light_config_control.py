import appdaemon.plugins.hass.hassapi as hass

class LightConfigControl(hass.Hass):

    def initialize(self):
        self.log("Inizializzazione LightConfigControl con fallback", level="INFO")
        self.light_configs = self.args.get("light_config", [])

        for cfg in self.light_configs:
            light_name = cfg.get("light_entity", "").strip()
            relay = cfg.get("relay_light")
            smart = cfg.get("smart_light")
            mode = cfg.get("smart_mode")

            if not light_name:
                self.log("❌ 'light_entity' mancante o vuoto. Configurazione ignorata.", level="ERROR")
                continue

            if not relay and not smart:
                self.log(f"❌ '{light_name}': né 'relay_light' né 'smart_light' sono definiti. Ignorato.", level="ERROR")
                continue

            # Normalize the light name (convert spaces to underscores, lowercase)
            normalized_name = light_name.lower().replace(" ", "_")
            template_light = f"light.{normalized_name}_template_light"
            template_state = f"input_boolean.{normalized_name}_template_state"

            # Check if template entities exist before setting up listeners
            if not self.entity_exists(template_light):
                self.log(f"❌ Template light '{template_light}' non esiste. Assicurati che sia stato creato.", level="ERROR")
                continue
                
            if not self.entity_exists(template_state):
                self.log(f"❌ Template state '{template_state}' non esiste. Assicurati che sia stato creato.", level="ERROR")
                continue

            self.listen_state(self.template_light_changed, template_light, light_cfg=cfg)
            self.log(f"✅ Luce virtuale '{template_light}' monitorata per '{light_name}'", level="INFO")

            if smart and self.entity_exists(smart):
                self.listen_state(self.physical_light_changed, smart, source="smart", light_cfg=cfg)
            elif smart:
                self.log(f"⚠️ Smart light '{smart}' non esiste, monitoraggio disabilitato", level="WARNING")

            if relay and self.entity_exists(relay):
                self.listen_state(self.physical_light_changed, relay, source="relay", light_cfg=cfg)
            elif relay:
                self.log(f"⚠️ Relay light '{relay}' non esiste, monitoraggio disabilitato", level="WARNING")

    def entity_exists(self, entity_id):
        """Check if an entity exists in Home Assistant"""
        try:
            state = self.get_state(entity_id)
            return state is not None
        except Exception as e:
            self.log(f"Errore controllo esistenza entità {entity_id}: {e}", level="DEBUG")
            return False

    def get_mode_state(self, mode):
        if not mode:
            return "off"
        if not self.entity_exists(mode):
            return "off"
        state = self.get_state(mode)
        return state if state in ["on", "off"] else "off"

    def template_light_changed(self, entity, attribute, old, new, kwargs):
        cfg = kwargs["light_cfg"]
        light_name = cfg.get("light_entity")
        relay = cfg.get("relay_light")
        smart = cfg.get("smart_light")
        mode = cfg.get("smart_mode")

        mode_state = self.get_mode_state(mode)
        action = "turn_on" if new == "on" else "turn_off"

        if mode_state == "on" and smart and self.entity_exists(smart):
            state = self.get_state(smart)
            if state in ["unavailable", None]:
                self.notify_fallback(light_name, "smart_light", smart, relay, new)
            else:
                self.call_service("light/" + action, entity_id=smart)
                self.run_in(self.check_execution, 2, cfg=cfg, target=smart, expected=new, fallback_relay=relay)
        elif mode_state == "on" and not smart:
            self.notify_fallback(light_name, "smart_light", smart, relay, new)
        elif relay and self.entity_exists(relay):
            domain = relay.split(".")[0]
            self.call_service(f"{domain}/{action}", entity_id=relay)

    def check_execution(self, kwargs):
        target = kwargs["target"]
        expected = kwargs["expected"]
        actual = self.get_state(target)
        if actual != expected:
            self.log(f"⚠️ Entità '{target}' non ha risposto. Stato atteso: {expected}, stato reale: {actual}", level="WARNING")
            relay = kwargs.get("fallback_relay")
            cfg = kwargs.get("cfg")
            if relay and self.entity_exists(relay):
                fallback_action = "turn_on" if expected == "on" else "turn_off"
                domain = relay.split(".")[0]
                self.call_service(f"{domain}/{fallback_action}", entity_id=relay)
                self.notify_fallback(cfg["light_entity"], "fallback", target, relay, expected)

    def notify_fallback(self, light_name, motivo, smart, relay, stato):
        messaggio = (
            f"Luce '{light_name}': modalità SMART fallita ({motivo}). "
            f"Eseguito fallback su '{relay}' con stato '{stato}'."
        )
        self.log(messaggio, level="ERROR")
        self.call_service("persistent_notification/create", title="Light Fallback Attivo", message=messaggio)

    def physical_light_changed(self, entity, attribute, old, new, kwargs):
        cfg = kwargs["light_cfg"]
        light_name = cfg.get("light_entity")
        mode = cfg.get("smart_mode")
        relay = cfg.get("relay_light")
        smart = cfg.get("smart_light")
        
        # Normalize the light name for template entities
        normalized_name = light_name.lower().replace(" ", "_")
        template_state = f"input_boolean.{normalized_name}_template_state"
        source = kwargs.get("source")
        mode_state = self.get_mode_state(mode)

        if not self.entity_exists(template_state):
            self.log(f"❌ Template state '{template_state}' non esiste", level="ERROR")
            return

        current_virtual = self.get_state(template_state)

        # Ripristino automatico: smart torna online in modalità SMART
        if source == "smart" and old == "unavailable" and new in ["on", "off"] and mode_state == "on":
            self.log(f"[{light_name}] Ripristino automatico: smart_light tornata online", level="INFO")
            if relay and self.entity_exists(relay) and self.get_state(relay) == "on":
                domain = relay.split(".")[0]
                self.call_service(f"{domain}/turn_off", entity_id=relay)
            if current_virtual == "on":
                self.call_service("light/turn_on", entity_id=smart)
            else:
                self.call_service("light/turn_off", entity_id=smart)
            self.call_service("persistent_notification/create", title="Ripristino SMART", message=f"La luce smart '{smart}' è tornata online. Ripristinato controllo elettronico.")

        # Sincronizza stato fisico con virtuale (solo nella modalità attiva)
        if (mode_state == "on" and source != "smart") or (mode_state == "off" and source != "relay"):
            return

        if new != current_virtual:
            service = "input_boolean.turn_on" if new == "on" else "input_boolean.turn_off"
            self.call_service(service, entity_id=template_state)
            self.log(f"[{light_name}] Sincronizzato stato fisico '{source}' -> virtuale: {new}", level="DEBUG")
