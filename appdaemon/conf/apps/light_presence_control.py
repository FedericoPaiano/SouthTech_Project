import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
from timer_manager import TimerManager

class LightPresenceControl(hass.Hass):
  def initialize(self):
      """
      Inizializza la configurazione del controllo delle luci.
      Ottiene le configurazioni dal file YAML e imposta le strutture dati necessarie.
      """
      # Sostituzione strutture timer con TimerManager
      self.timer_manager = TimerManager(self)
      
      self.log_timer_status = {}

      # Inizializza il dizionario per i flag
      self.light_turned_off_by_illuminance = {}
      self.light_illuminance_lock_on = {}

      config = self.args["light_presence"]
      self.initialize_light_configurations(config)

    def initialize_light_configurations(self, config):
        """
        Inizializza le configurazioni per ogni luce specificata nel file YAML.
        """
        initialization_details = []  # Lista unica per tutte le configurazioni
        for light_config in config:
            self.setup_light_configuration(light_config, initialization_details)
        
        # Logga TUTTE le configurazioni insieme alla fine
        self.log_initialization_details(initialization_details)

    def setup_light_configuration(self, light_config, initialization_details):
        """
        Configura una singola luce con i parametri specificati nel file YAML.
        """
        presence_sensor_off = light_config.get("presence_sensor_off")
        
        # Imposta default solo se non è None
        if presence_sensor_off is None:
            presence_sensor_off = light_config["presence_sensor_on"]
            light_config["presence_sensor_off"] = presence_sensor_off

        # Ottieni i valori di configurazione con valori predefiniti se non specificati
        light_entity = light_config.get("light_entity", None)
        presence_sensor_on = light_config.get("presence_sensor_on", "off")
        presence_sensor_off = light_config.get("presence_sensor_off", presence_sensor_on)
        illuminance_sensor = light_config.get("illuminance_sensor")
        min_lux_activation = light_config.get("min_lux_activation", int(0))
        max_lux_activation = light_config.get("max_lux_activation", int(1000))
        enable_sensor = light_config.get("enable_sensor", "off")
        enable_illuminance_filter = light_config.get("enable_illuminance_filter", "off")
        enable_illuminance_automation = light_config.get("enable_illuminance_automation", "off")
        enable_automation = light_config.get("enable_automation", "off")
        automatic_enable_automation = light_config.get("automatic_enable_automation", "All")
        light_sensor_config = light_config.get("light_sensor_config", "All")
        timer_minutes_on_push = light_config.get("timer_minutes_on_push", int(5))
        timer_minutes_on_time = light_config.get("timer_minutes_on_time", int(30))
        timer_filter_on_push = light_config.get("timer_filter_on_push", int(30))
        timer_filter_on_time = light_config.get("timer_filter_on_time", int(5))
        timer_seconds_max_lux = light_config.get("timer_seconds_max_lux", int(5))
        turn_on_light_offset = light_config.get("turn_on_light_offset", float(0.0))
        turn_off_light_offset = light_config.get("turn_off_light_offset", int(30))
        illuminance_offset = light_config.get("illuminance_offset", "input_number.default_illuminance_offset")

        light_config.update({
            "enable_illuminance_filter": enable_illuminance_filter,
            "enable_illuminance_automation": enable_illuminance_automation,
            "enable_automation": enable_automation,
            "automatic_enable_automation": automatic_enable_automation,
            "light_sensor_config": light_sensor_config,
            "timer_minutes_on_push": timer_minutes_on_push,
            "timer_minutes_on_time": timer_minutes_on_time,
            "timer_filter_on_push": timer_filter_on_push,
            "timer_filter_on_time": timer_filter_on_time,
            "timer_seconds_max_lux": timer_seconds_max_lux,
            "turn_on_light_offset": turn_on_light_offset,
            "turn_off_light_offset": turn_off_light_offset,
            "illuminance_offset": illuminance_offset,
            "min_lux_activation": min_lux_activation,
            "max_lux_activation": max_lux_activation,
            "presence_sensor_on": presence_sensor_on,
            "presence_sensor_off": presence_sensor_off,
            "illuminance_sensor": illuminance_sensor,
            "enable_sensor": enable_sensor,
            "light_entity": light_entity,
        })

        # Registra i listener per gli eventi di stato
        self.register_listeners(light_config, light_entity, presence_sensor_on, presence_sensor_off,
                                illuminance_sensor, min_lux_activation, max_lux_activation,
                                timer_minutes_on_push, timer_minutes_on_time, timer_filter_on_push,
                                timer_filter_on_time, timer_seconds_max_lux, enable_automation,
                                automatic_enable_automation, turn_on_light_offset, turn_off_light_offset,
                                illuminance_offset, enable_illuminance_filter)

        # Costruisci la lista dei listener per il logging
        listeners = []
        if illuminance_sensor is not None:
            listeners.extend([
                f"Monitoraggio illuminanza: {illuminance_sensor}",
                f"Automatismi illuminanza: {illuminance_sensor}"
            ])

        listeners.extend([
            f"Presenza ON/OFF: {presence_sensor_on}",
            f"Presenza OFF: {presence_sensor_off}",
            f"Stato luce: {light_entity}",
            f"Parametri configurazione: {len(light_config)} impostazioni"
        ])

        # Aggiungi i dettagli di questa configurazione al log finale
        initialization_details.append({
            "entities": [
                f"Luce: {self.formatted_value(light_entity, light_entity is None)}",
                f"Sensore di presenza (on): {self.formatted_value(presence_sensor_on, presence_sensor_on == 'off')}",
                f"Sensore di presenza (off): {self.formatted_value(presence_sensor_off, presence_sensor_off == presence_sensor_on)}",
                f"Sensore illuminazione: {self.formatted_value(illuminance_sensor, illuminance_sensor is None)}",
                f"Soglia minima lux per attivazione luce: {self.formatted_value(min_lux_activation, min_lux_activation == 'input_number.default_min_lux_activation')}",
                f"Soglia massima lux per disattivazione luce: {self.formatted_value(max_lux_activation, max_lux_activation == 'input_number.default_max_lux_activation')}",
                f"Enable Sensor: {self.formatted_value(enable_sensor, enable_sensor == 'off')}",
                f"Enable Illuminance Filter: {self.formatted_value(enable_illuminance_filter, enable_illuminance_filter == 'off')}",
                f"Enable Illuminance Automation: {self.formatted_value(enable_illuminance_automation, enable_illuminance_automation == 'off')}",
                f"Enable Automation: {self.formatted_value(enable_automation, enable_automation == 'off')}",
                f"Automatic Enable Automation: {self.formatted_value(automatic_enable_automation, automatic_enable_automation == 'All')}",
                f"Light Sensor Config: {self.formatted_value(light_sensor_config, light_sensor_config == 'All')}",
                f"Timer Minutes On Push: {self.formatted_value(timer_minutes_on_push, timer_minutes_on_push == int(5))}",
                f"Timer Minutes On Time: {self.formatted_value(timer_minutes_on_time, timer_minutes_on_time == int(30))}",
                f"Timer Filter On Push: {self.formatted_value(timer_filter_on_push, timer_filter_on_push == int(30))}",
                f"Timer Filter On Time: {self.formatted_value(timer_filter_on_time, timer_filter_on_time == int(5))}",
                f"Timer Seconds Max Lux: {self.formatted_value(timer_seconds_max_lux, timer_seconds_max_lux == int(5))}",
                f"Turn On Light Offset: {self.formatted_value(turn_on_light_offset, turn_on_light_offset == float(0.0))}",
                f"Turn Off Light Offset: {self.formatted_value(turn_off_light_offset, turn_off_light_offset == int(30))}",
                f"Illuminance Offset: {self.formatted_value(illuminance_offset, illuminance_offset == 'input_number.default_illuminance_offset')}"
            ],
            "listeners": listeners
        })

    def register_listeners( self, light_config, light_entity, presence_sensor_on, presence_sensor_off,
                            illuminance_sensor, min_lux_activation, max_lux_activation,
                            timer_minutes_on_push, timer_minutes_on_time, timer_filter_on_push,
                            timer_filter_on_time, timer_seconds_max_lux, enable_automation,
                            automatic_enable_automation, turn_on_light_offset, turn_off_light_offset,
                            illuminance_offset, enable_illuminance_filter ):
        """
        Registra i listener per gli eventi di stato delle entità.
        """

        # Aggiungi solo se illuminance_sensor è configurato (non None)
        if illuminance_sensor is not None:
            self.listen_state(self.illuminance_on, illuminance_sensor, config=light_config)
            self.listen_state(self.illuminance_off, illuminance_sensor, config=light_config)

        self.listen_state(self.presence_on, presence_sensor_on, new="on", config=light_config)
        self.listen_state(self.presence_off, presence_sensor_off, new="off", config=light_config)
        self.listen_state(self.check_and_start_timer_on_time, presence_sensor_on, new="on", config=light_config)
        self.listen_state(self.check_and_start_timer_on_time, presence_sensor_off, new="off", config=light_config)
        self.listen_state(self.light_turned_on, light_entity, new="on", config=light_config)
        self.listen_state(self.light_turned_off, light_entity, new="off", config=light_config)
        self.listen_state(self.presence_on_off, presence_sensor_on, new="off", config=light_config)
        self.listen_state(self.value_changed, min_lux_activation, config=light_config)
        self.listen_state(self.value_changed, max_lux_activation, config=light_config)
        self.listen_state(self.value_changed, timer_minutes_on_push, config=light_config)
        self.listen_state(self.value_changed, timer_minutes_on_time, config=light_config)
        self.listen_state(self.value_changed, timer_filter_on_push, config=light_config)
        self.listen_state(self.value_changed, timer_filter_on_time, config=light_config)
        self.listen_state(self.value_changed, timer_seconds_max_lux, config=light_config)
        self.listen_state(self.value_changed, turn_on_light_offset, config=light_config)
        self.listen_state(self.value_changed, turn_off_light_offset, config=light_config)
        self.listen_state(self.value_changed, illuminance_offset, config=light_config)
        self.listen_state(self.cancel_timer_on_no_presence, presence_sensor_on, config=light_config)
        self.listen_state(self.cancel_timer_on_no_presence, presence_sensor_off, config=light_config)
        self.listen_state(self.cancel_on_time_if_presence_detected, presence_sensor_on, new="on", config=light_config)
        self.listen_state(self.cancel_on_time_if_presence_detected, presence_sensor_off, new="on", config=light_config)
        self.listen_state(self.check_and_cancel_timers, enable_automation, config=light_config)
        self.listen_state(self.check_and_cancel_timers, automatic_enable_automation, config=light_config)

    def log_initialization_details(self, initialization_details):
        """
        Crea un singolo log strutturato per tutte le configurazioni
        """
        prev_entities = []
        prev_listeners = []
        
        self.log("\n" + "*" * 80)
        self.log("*** INIZIALIZZAZIONE CONFIGURAZIONI LUCI ***")
        
        for i, details in enumerate(initialization_details, 1):
            # Intestazione configurazione
            self.log(f"\n*** Configurazione Luce #{i} ***")
            
            # Sezione Entità - Logga solo se diverse dalla precedente
            self.log("\n  ENTA' CONFIGURATE:")
            current_entities = [e.split(':')[0].strip() for e in details["entities"]]
            
            for entity in details["entities"]:
                self.log(f"  - {entity}")
            prev_entities = current_entities
            
            # Sezione Listener - Rimuovi duplicati
            self.log("\n  LISTENER ATTIVI:")
            current_listeners = details["listeners"]
            
            if current_listeners != prev_listeners:
                seen = set()
                for listener in current_listeners:
                    clean_listener = listener.split('->')[0].strip()
                    if clean_listener not in seen:
                        self.log(f"  - {listener}")
                        seen.add(clean_listener)
                prev_listeners = current_listeners
            else:
                self.log("  - Listener identici alla configurazione precedente [omessi]")
            
            self.log("-" * 60)
        
        self.log("\n*** INIZIALIZZAZIONE COMPLETATA ***")
        self.log("*" * 80 + "\n")

    def formatted_value(self, value, is_default):
        """
        Formatta il valore con (default) o (verified) in base al parametro is_default.
        """
        return f"{value} {'(default)' if is_default else '(verified)'}"

    def presence_on(self, entity, attribute, old, new, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        enable_sensor = config["enable_sensor"]
        enable_automation = config["enable_automation"]
        enable_illuminance_filter = config["enable_illuminance_filter"]
        illuminance_sensor = config["illuminance_sensor"]
        min_lux_activation = config["min_lux_activation"]
        timer_seconds_max_lux = config["timer_seconds_max_lux"]
        turn_off_light_offset = config["turn_off_light_offset"]
        turn_on_light_offset = config["turn_on_light_offset"]

        # Controllo della modalità selezionata
        light_sensor_mode = self.get_state(config["light_sensor_config"]).lower() if config["light_sensor_config"] else "all"
        if light_sensor_mode not in ["on", "all"]:
            self.log(f"⏭️ Modalità '{light_sensor_mode}': accensione disabilitata")
            return

        # Verifica transizione OFF->ON
        if not (old == "off" and new == "on"):
            return

        # Controllo abilitazione automazione
        if not (self.get_state(enable_automation) == "on" and self.get_state(enable_sensor) == "on"):
            self.log(f"⏻ Automazione disabilitata per {light_entity}", level="DEBUG")
            return

        timer_push_key = f"{light_entity}_timer_on_push" 

        # +++ CONTROLLO BLOCCANTE +++
        if self.timer_manager.is_timer_active(timer_push_key):
            self.log(f"🚫 Blocco accensione per {light_entity}: timer_on_push attivo")
            return

        # Controllo timer conflittuali
        timer_illuminance_key = f"{light_entity}_illuminance_timer"
        timer_filter_key = f"{light_entity}_timer_filter"
        timer_filter_on_push_key = f"{light_entity}_timer_filter_on_push"

        # Verifica timer filter push
        if self.timer_manager.is_timer_active(timer_filter_on_push_key, is_filter=True):
            self.log(f"⏳ Timer filter_on_push attivo, ignoro presenza su {entity}")
            return

        # Verifica illuminance
        if timer_illuminance_key in self.timer_manager.timers:
            self.log(f"☀️ Timer illuminance attivo, ignoro presenza su {entity}")
            return

        # Cancellazione timer spegnimento
        timer_offset_key = f"{light_entity}_turn_off_timer"
        self.timer_manager.cancel_timer(timer_offset_key)

        # Cancella timer filtro se presente
        if timer_filter_key in self.timer_manager.filter_timers:
            self.log(f"⚡ Cancello timer filtro per {light_entity} per presenza rilevata")
            self.timer_manager.cancel_timer(timer_filter_key, is_filter=True)

        # Gestione del timer filter_on_push
        if self.timer_manager.is_timer_active(timer_filter_on_push_key, is_filter=True):
            self.timer_manager.cancel_timer(timer_filter_on_push_key, is_filter=True)
            self.turn_off(config["enable_automation"])
            self.log(f"⏳ Timer filter_on_push cancellato per {light_entity}")

        # Avvia timer di accensione ritardata
        try:
            turn_on_offset = int(float(self.get_state(turn_on_light_offset)))
        except (TypeError, ValueError):
            turn_on_offset = 0

        timer_key = f"{light_entity}_turn_on_timer"
        if turn_on_offset > 0:
            self.timer_manager.start_timer(
                key=timer_key,
                delay=turn_on_offset,
                callback=self.delayed_turn_on,
                is_filter=False,
                light_entity=light_entity,
                config=config
            )
            self.log(f"⏳ Avviato timer di accensione ({turn_on_offset}s) per {light_entity}")
        else:
            # Accensione immediata se offset = 0
            self.execute_turn_on(config, light_entity)

    def presence_off(self, entity, attribute, old, new, kwargs):
        """
        Gestisce la transizione ON->OFF dei sensori di presenza.
        Avvia il timer di spegnimento se la luce è accesa.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        presence_sensor_on = config["presence_sensor_on"]
        presence_sensor_off = config["presence_sensor_off"]
        turn_off_light_offset = config["turn_off_light_offset"]
        enable_sensor = config["enable_sensor"]
        enable_automation = config["enable_automation"]

        # Ottieni stato attuale dei sensori
        presence_on_state = self.get_state(presence_sensor_on)
        presence_off_state = self.get_state(presence_sensor_off)

        # Controllo della modalità selezionata
        light_sensor_mode = self.get_state(config["light_sensor_config"]).lower() if config["light_sensor_config"] else "all"
        if light_sensor_mode not in ["off", "all"]:
            self.log(f"⏭️ Modalità '{light_sensor_mode}': spegnimento disabilitato")
            return

        # Verifica se l'automazione è abilitata
        if not (self.get_state(enable_sensor) == "on" and self.get_state(enable_automation) == "on"):
            return

        # Se almeno un sensore è ON, cancella tutti i timer
        if presence_on_state == "on" or presence_off_state == "on":
            self.cancel_offset_timer(light_entity)
            return

        # Cancella timer di accensione se presente
        timer_key = f"{light_entity}_turn_on_timer"
        self.log(f"⏹️ Cancellato timer accensione per {light_entity}: presenza persa", level = "INFO")
        self.timer_manager.cancel_timer(timer_key)  # Metodo di TimerManager

        # Solo se entrambi i sensori sono OFF e la luce è accesa
        if (self.get_state(presence_sensor_on) == "off" 
            and self.get_state(presence_sensor_off) == "off"
            and self.get_state(light_entity) == "on"):

            # Avvia timer di accensione ritardata
            try:
                turn_off_light_offset_value = int(float(self.get_state(turn_off_light_offset)))
                self.log(f"Valore turn_off_light_offset letto: {turn_off_light_offset_value} -> {turn_off_light_offset}s", level="DEBUG")
            except (TypeError, ValueError) as e:
                turn_off_light_offset_value = 30
                self.log(f"⚠️ Errore lettura turn_off_light_offset: {e}. Usato default: 30s", level="WARNING")

            # Se offset = 0, spegni immediatamente
            if turn_off_light_offset_value == 0:
                self.log(f"🛑 Spegnimento immediato per {light_entity} (offset = 0)")
                self.turn_off_light_after_offset({
                    "light_entity": light_entity,
                    "enable_sensor": enable_sensor,
                    "enable_automation": enable_automation
                })
            else:
                self.start_offset_timer(
                    light_entity=light_entity,
                    turn_off_light_offset=turn_off_light_offset,
                    enable_sensor=enable_sensor,
                    enable_automation=enable_automation
                )

        # Se entrambi i sensori sono OFF, cancella il filter timer
        if (self.get_state(presence_sensor_on) == "off" and 
            self.get_state(presence_sensor_off) == "off"):
            filter_timer_key = f"{light_entity}_timer_filter_on_time"
            self.timer_manager.cancel_timer(filter_timer_key, is_filter=True)
            self.log(f"🛑 Cancellato filter timer per {light_entity} (sensori OFF)", level = "DEBUG")

    def presence_on_off(self, entity, attribute, old, new, kwargs):
        """
        Gestisce la transizione a 'off' del sensore di presenza principale.
        Se è attivo un timer di accensione, viene cancellato.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        timer_key = f"{light_entity}_turn_on_timer"
        
        if self.timer_manager.is_valid(timer_key, self.timer_manager.generations.get(timer_key, 0)):
            self.log(f"⏹️ Cancellato timer accensione per {light_entity}: sensore {entity} disattivato")
            self.timer_manager.cancel_timer(timer_key)

    def turn_off_light_after_offset(self, kwargs):
        light_entity = kwargs["light_entity"]
        timer_key = kwargs.get("timer_key")
        enable_sensor = kwargs["enable_sensor"]
        enable_automation = kwargs["enable_automation"]
        generation = kwargs.get("generation")

        # Resetta il flag light_turned_off_by_illuminance
        self.light_turned_off_by_illuminance[light_entity] = False

        # Verifica validità solo se chiamato tramite timer
        if timer_key is not None:
            if not self.timer_manager.is_valid(timer_key, generation or 0):
                self.log(f"🕰️ Ignorato timer scaduto {timer_key} (generazione {generation} obsoleta)")
                return

        # Controllo finale: automazione e sensore devono essere attivi
        if not (self.get_state(enable_sensor) == "on" and self.get_state(enable_automation) == "on"):
            self.log(f"⏹️ Automazione disabilitata, annullo spegnimento di {light_entity}")
            return

        # Spegni la luce solo se ancora accesa
        if self.get_state(light_entity) == "on":
            self.turn_off(light_entity)
            self.log(f"💡 Luce {light_entity} spenta {'immediatamente' if timer_key is None else 'per timer scaduto'}", 
                    level="INFO")
            self.log(f"🔓 Sblocco spegnimento per {light_entity} (light_illuminance_lock_on = False)", 
                    level="INFO")

    def execute_turn_on(self, config, light_entity):
        """Esegue i controlli illuminanza e accende la luce"""
        enable_illuminance_filter = config["enable_illuminance_filter"]
        illuminance_sensor = config.get("illuminance_sensor")
        min_lux_activation = config["min_lux_activation"]
        timer_key = f"{light_entity}_turn_on_timer"  # Chiave del timer di accensione

        # Cancella eventuali timer di accensione pendenti
        self.timer_manager.cancel_timer(timer_key)

        # Controllo coerenza configurazione filtro illuminanza
        if self.get_state(enable_illuminance_filter) == "on":
            if not illuminance_sensor:
                self.log(f"🚨 Configurazione errata: filtro illuminanza attivo senza sensore. Disattivo il filtro per {light_entity}", level="ERROR")
                self.turn_off(config["enable_illuminance_filter"])  # Disabilita l'input_boolean
                self.turn_on(light_entity)  # Accensione comunque per sicurezza
                self.log(f"💡 Luce {light_entity} accesa (filtro disattivato per errore configurazione)")
                self.light_state_changed_on(light_entity, None, None, None, {"config": config})
                return

            try:
                illuminance = float(self.get_state(illuminance_sensor))
                min_lux = float(self.get_state(min_lux_activation))
                
                if illuminance < min_lux:
                    self.turn_on(light_entity)
                    self.log(f"💡 Luce {light_entity} accesa per presenza + illuminanza {illuminance} < {min_lux} lux")
                else:
                    self.log(f"🟢 Illuminazione sufficiente ({illuminance} lux), luce non accesa", level="DEBUG")
                    return  # Non accendere la luce

            except (TypeError, ValueError) as e:
                self.log(f"⚠️ Errore lettura sensori: {e} - Accensione comunque per sicurezza", level="WARNING")
                self.turn_on(light_entity)  # Fallback in caso di errore

            # Aggiorna lo stato dopo l'accensione
            self.light_state_changed_on(light_entity, None, None, None, {"config": config})
        
        else:
            # Caso senza filtro illuminanza
            self.turn_on(light_entity)
            self.log(f"💡 Luce {light_entity} accesa per presenza rilevata")
            self.light_state_changed_on(light_entity, None, None, None, {"config": config})

    def light_turned_on(self, entity, attribute, old, new, kwargs):
        """
        Gestisce l'accensione della luce della luce, con controllo del flag di illuminanza e generazioni dei timer.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        presence_sensor_on = config["presence_sensor_on"]
        presence_sensor_off = config["presence_sensor_off"]
        enable_automation = config["enable_automation"]
        automatic_enable_automation = config["automatic_enable_automation"]
        enable_sensor = config["enable_sensor"]

        timer_push_key = f"{light_entity}_timer_on_push"

        # Cancella il timer_on_push se attivo
        if self.timer_manager.is_timer_active(timer_push_key):
            self.timer_manager.cancel_timer(timer_push_key)
            self.log(f"⚡ Timer_on_push annullato per accensione manuale di {light_entity}")

        # Riattiva l'automazione SOLO se necessario
        if self.get_state(config["enable_sensor"]) == "on" and self.get_state(config["enable_automation"]) == "off":
            self.turn_on(config["enable_automation"])
            self.log(f"🔌 Riattivazione automazione per {light_entity}")

        # Imposta il flag a True per la luce corrente
        self.light_illuminance_lock_on[light_entity] = True
        self.log(f"🔒 Blocco spegnimento per {entity}")

        # Timer "on_push" e controllo presenza
        presence_active = (
            self.get_state(presence_sensor_on) == "on" or
            self.get_state(presence_sensor_off) == "on"
        )

        auto_enable_mode = self.get_state(automatic_enable_automation).lower()

        if auto_enable_mode in ["push", "all"]:
            self.turn_on(enable_automation)
            self.log(f"🔓 Automazione abilitata automaticamente ({auto_enable_mode})")
        else:
            self.log(f"⚠️ Modalità '{auto_enable_mode}' non supportata per {light_entity}", level="WARNING")

    def light_turned_off(self, entity, attribute, old, new, kwargs):
        """
        Gestisce lo spegnimento della luce, con controllo del flag di illuminanza e generazioni dei timer.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        presence_sensor_on = config["presence_sensor_on"]
        presence_sensor_off = config["presence_sensor_off"]
        timer_minutes_on_push = config["timer_minutes_on_push"]
        timer_key = f"{light_entity}_timer_on_push"

        # Resetta il flag a False per questa luce
        self.light_illuminance_lock_on[light_entity] = False

        # Controlla se la luce è stata spenta dalla logica di illuminanza
        if self.light_turned_off_by_illuminance.get(light_entity, False):
            self.log(f"⏭️ Timer 'on_push' non avviato per {light_entity}: spenta da illuminanza")
            return

        # Verifica presenza attiva
        presence_active = (
            self.get_state(presence_sensor_on) == "on" or
            self.get_state(presence_sensor_off) == "on"
        )

        # Mantieni enable_automation nello stato precedente
        if presence_active:
            # Cancella timer precedente (se esiste) e avvia nuovo timer solo se enable_automation è ON
            if self.get_state(config["enable_automation"]) == "on":
                if self.timer_manager.is_valid(timer_key, self.timer_manager.generations.get(timer_key, 0)):
                    self.log(f"♻️ Cancellazione timer 'on_push' esistente per {light_entity}")
                    self.timer_manager.cancel_timer(timer_key)

                try:
                    timer_duration = int(float(self.get_state(timer_minutes_on_push)))
                except (TypeError, ValueError):
                    timer_duration = 0

                if timer_duration > 0:
                    self.timer_manager.start_timer(
                        timer_key,
                        timer_duration * 60,
                        self.check_presence_and_disable_automation,
                        False,
                        config=config
                    )
                    self.log(f"⏳ Timer 'on_push' avviato: {timer_duration} minuti")

    def light_state_changed_on(self, entity, attribute, old, new, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        timer_seconds_max_lux_entity = config["timer_seconds_max_lux"]
        illuminance_offset = config.get("illuminance_offset") 

        # Ottieni il valore numerico dall'entità
        try:
            timer_seconds = int(float(self.get_state(timer_seconds_max_lux_entity)))
        except (TypeError, ValueError) as e:
            timer_seconds = 5  # Default a 5 secondi
            self.log(f"⚠️ Errore lettura timer: {e}. Usato default: {timer_seconds}s", level="WARNING")

        # Avvia il timer con il valore corretto
        self.timer_manager.start_timer(
            key=f"{entity}_illuminance_timer",
            delay=timer_seconds,
            callback=self.check_luminosity_after_delay,
            is_filter=True,
            light_entity=light_entity,
            timer_illuminance_key=f"{entity}_illuminance_timer",
            illuminance_sensor=config["illuminance_sensor"],
            max_lux_activation=config["max_lux_activation"],
            illuminance_offset=illuminance_offset,
            config=config
        )

    def check_presence_and_disable_automation(self, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        enable_automation = config["enable_automation"]
        timer_push_key = f"{light_entity}_timer_on_push"
        filter_timer_key = f"{light_entity}_timer_filter_on_push"

        # 1. Cancella entrambi i timer
        self.timer_manager.cancel_timer(timer_push_key)
        self.timer_manager.cancel_timer(filter_timer_key, is_filter=True)

        # 2. Disabilita l'automazione SOLO allo scadere naturale del timer_on_push
        self.turn_off(enable_automation)
        self.log(f"⏹️ Automazione disabilitata per timer_on_push scaduto su {light_entity}")

    def check_and_start_timer_on_time(self, entity, attribute, old, new, kwargs):
        """Avvia timer_on_time solo se i sensori sono OFF e nessun timer è attivo"""
        try:
            config = kwargs["config"]
            light_entity = config["light_entity"]
            enable_automation = config["enable_automation"]
            timer_key = f"{light_entity}_timer_on_time"
            filter_timer_key = f"{light_entity}_timer_filter_on_time"

            # Verifica obbligatoria delle chiavi di configurazione
            if not all(key in config for key in ["enable_automation", "presence_sensor_on", "presence_sensor_off", "timer_minutes_on_time"]):
                self.log("Configurazione incompleta", level="ERROR")
                return

            # Aggiunta condizione enable_automation
            enable_automation_state = self.get_state(enable_automation)
            if enable_automation_state == "on":
                self.log(f"⏭️ Timer_on_time non avviato: enable_automation attivo per {light_entity}", level = "DEBUG")
                return

            # Lettura sicura degli stati
            state_on = self.get_state(config["presence_sensor_on"])
            state_off = self.get_state(config["presence_sensor_off"])

            # Controllo esplicito dello stato timer
            on_time_active = self.timer_manager.is_timer_active(timer_key)
            filter_on_time_active = self.timer_manager.is_timer_active(filter_timer_key, is_filter=True)

            # Logica di avvio condizionata
            if (state_on == "off" and 
                state_off == "off" and 
                not on_time_active and 
                not filter_on_time_active):

                try:
                    raw_value = self.get_state(config["timer_minutes_on_time"])
                    timer_duration = int(float(raw_value)) * 60  # Conversione esplicita
                    
                    self.timer_manager.start_timer(
                        key=timer_key,
                        delay=timer_duration,
                        callback=self.timer_on_time_expired,
                        is_filter=False,
                        config=config
                    )
                    self.log(f"⏳ Timer_on_time avviato per {light_entity}: {timer_duration//60} minuti",
                          level="INFO")

                except (ValueError, TypeError) as e:
                    self.log(f"Valore timer non valido: {raw_value} ({str(e)})", level="ERROR")
                except Exception as e:
                    self.log(f"Errore generico: {str(e)}", level="ERROR")

        except KeyError as e:
            self.log(f"Chiave mancante: {str(e)}", level="ERROR")

    def illuminance_on(self, entity, attribute, old, new, kwargs):
        """Gestisce l'accensione della luce basata sull'illuminanza."""
        config = kwargs["config"]
        light_entity = config["light_entity"]
        enable_sensor = config["enable_sensor"]
        enable_automation = config["enable_automation"]
        enable_illuminance_automation = config["enable_illuminance_automation"]
        presence_sensor_on = config["presence_sensor_on"]
        presence_sensor_off = config["presence_sensor_off"]
        illuminance_sensor = config["illuminance_sensor"]
        min_lux_activation = config["min_lux_activation"]

        # Chiave del timer "on push"
        timer_push_key = f"{light_entity}_timer_on_push"

        # Esci se non c'è un sensore di illuminazione configurato
        if not illuminance_sensor:
            return

        # Verifica se il sensore e l'automazione sono abilitati
        if not (self.get_state(enable_sensor) == "on" and self.get_state(enable_automation) == "on"):
            self.log(f"Automazione o sensore disabilitati per {light_entity}. Nessuna azione.", level="DEBUG")
            return

        # Controlla se il timer "on push" è attivo tramite TimerManager
        if self.timer_manager.is_valid(timer_push_key, self.timer_manager.generations.get(timer_push_key, 0)):
            self.log(f"Illuminazione rilevata, ma il timer 'on push' è attivo per {light_entity}. Nessuna azione.", level="DEBUG")
            return

        try:
            current_lux = float(new)
        except (TypeError, ValueError):
            self.log(f"Valore non valido per il sensore di illuminazione {entity}. Ignoro.", level="WARNING")
            return

        # Logica di accensione con filtro illuminanza
        if self.get_state(enable_illuminance_automation) == "on":
            try:
                min_lux = float(self.get_state(min_lux_activation))
            except (TypeError, ValueError):
                self.log(f"Soglia lux non valida per {light_entity}", level="ERROR")
                return

            presence_active = (
                self.get_state(presence_sensor_on) == "on" or
                self.get_state(presence_sensor_off) == "on"
            )

            if presence_active and current_lux < min_lux and self.get_state(light_entity) == "off":
                self.turn_on(light_entity)
                self.log(f"Luce {light_entity} accesa: luminosità ({current_lux}) sotto soglia ({min_lux}) con presenza rilevata.", level="INFO")
                # Passa il controllo a light_state_changed_on che usa TimerManager
                self.light_state_changed_on(light_entity, None, old, new, kwargs)
            else:
                self.log(f"Tentativo di attivazione luce {light_entity} già accesa. Nessuna azione.", level="DEBUG")

    def illuminance_off(self, entity, attribute, old, new, kwargs):
        """
        Gestisce lo spegnimento della luce basato sull'illuminanza, solo se entrambi i sensori sono OFF.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        presence_sensor_on = config["presence_sensor_on"]
        presence_sensor_off = config["presence_sensor_off"]
        enable_sensor = config["enable_sensor"]
        enable_automation = config["enable_automation"]
        max_lux_activation = config["max_lux_activation"]

        # Verifica preliminare automazione
        if not (self.get_state(enable_sensor) == "on" and self.get_state(enable_automation) == "on"):
            return

        # Controlla se lo spegnimento è bloccato dal flag
        if self.light_illuminance_lock_on.get(light_entity, False):
            self.log(f"🚫 Spegnimento di {light_entity} bloccato (light_illuminance_lock_on = True)", level = "DEBUG")
            return

        presence_active = (
            self.get_state(presence_sensor_on) == "on" or
            self.get_state(presence_sensor_off) == "on"
        )

        if not presence_active:
            return

        try:
            current_lux = float(new)
            max_lux = float(self.get_state(max_lux_activation))
        except (TypeError, ValueError):
            return

        # Spegnimento per alta illuminanza + presenza
        if current_lux > max_lux and self.get_state(light_entity) == "on":
            self.turn_off(light_entity)
            self.light_turned_off_by_illuminance[light_entity] = True
            self.log(f"💡 Luce {light_entity} spenta: luminosità {current_lux} > {max_lux} lux con presenza attiva")

            # Resetta il flag a False per questa luce
            self.light_illuminance_lock_on[light_entity] = False
            self.log(f"🔓 Sblocco spegnimento per {light_entity} (light_illuminance_lock_on = False)")

    def start_illuminance_timer(self, light_entity, timer_key, illuminance_sensor, max_lux_activation, timer_seconds_max_lux):
        """
        Configura e avvia il timer per il controllo della luminosità.
        """
        try:
            timer_seconds_value = int(float(self.get_state(timer_seconds_max_lux)))
            self.log(f"Valore convertito di timer_seconds_max_lux: {timer_seconds_value}", level="DEBUG")
        except (TypeError, ValueError) as e:
            self.log(f"Errore nella conversione di timer_seconds_max_lux: {e}. Imposto il timer a 5 secondi.", level="INFO")
            timer_seconds_value = 5

        if timer_seconds_value <= 0:
            self.log(f"Valore timer non valido ({timer_seconds_value}) per '{timer_seconds_max_lux}'. Imposto a 5 secondi.", level="WARNING")
            timer_seconds_value = 5

        # Recupera la configurazione associata alla luce
        config = None
        for light_config in self.args["light_presence"]:
            if light_config.get("light_entity") == light_entity:
                config = light_config
                break

        if not config:
            self.log(f"Configurazione non trovata per {light_entity}. Impossibile avviare il timer.", level="ERROR")
            return

        if not illuminance_sensor:
            self.log(f"Impossibile avviare timer: sensore di illuminazione non configurato per {light_entity}", level="ERROR")
            return

        # Ottieni illuminance_offset dalla configurazione
        illuminance_offset = config.get("illuminance_offset")

        # Avvia il timer (gestisce cancellazione e generazioni automaticamente)
        self.timer_manager.start_timer(
            key=timer_key,
            delay=timer_seconds_value,
            callback=self.check_luminosity_after_delay,
            is_filter=True,
            light_entity=light_entity,
            timer_illuminance_key=timer_key,
            illuminance_sensor=illuminance_sensor,
            max_lux_activation=max_lux_activation,
            illuminance_offset=illuminance_offset,
            config=config
        )
        self.log(f"⏳ Timer controllo luminosità avviato per {light_entity}: {timer_seconds_value}s")

    def check_luminosity_after_delay(self, kwargs):
        """
        Controlla la luminosità dopo un ritardo specificato dal timer.
        Gestito ora da TimerManager per validità e generazioni.
        """
        timer_illuminance_key = None
        try:
            config = kwargs["config"]
            light_entity = kwargs["light_entity"]
            enable_sensor = config["enable_sensor"]
            enable_automation = config["enable_automation"]
            illuminance_sensor = kwargs["illuminance_sensor"]
            max_lux_activation = kwargs["max_lux_activation"]
            illuminance_offset = kwargs["illuminance_offset"]
            timer_illuminance_key = kwargs.get("timer_illuminance_key")

            # Verifica automazione (mantenuta come logica di business)
            if not (self.get_state(enable_sensor) == "on" and self.get_state(enable_automation) == "on"):
                self.log(f"🚫 Automazione disabilitata, ignorato aggiornamento lux per {light_entity}")
                return

            # Verifica stato luce (mantenuta come logica di business)
            if self.get_state(light_entity) != "on":
                self.log(f"Luce {light_entity} spenta. Timer non eseguito.", level="INFO")
                self.timer_manager.cancel_timer(timer_illuminance_key, is_filter=True)
                return

            # Verifica blocco illuminanza (mantenuta come logica di business)
            if not self.light_illuminance_lock_on.get(light_entity, False):
                self.log(f"🔓 Blocco non attivo per '{light_entity}'. Timer annullato.", level="INFO")
                self.timer_manager.cancel_timer(timer_illuminance_key, is_filter=True)
                return

            # Conversione parametri con gestione errori
            try:
                max_lux = float(self.get_state(max_lux_activation))
                offset = float(self.get_state(illuminance_offset))
                current_lux = float(self.get_state(illuminance_sensor))
            except (TypeError, ValueError) as e:
                self.log(f"Errore conversione valori: {e}. Annullato controllo lux per {light_entity}", level="WARNING")
                self.timer_manager.cancel_timer(timer_illuminance_key, is_filter=True)
                return

            # Modifica il valore del sensore di illuminazione aggiungendo il valore di offset
            current_lux_plus = current_lux + offset
            if current_lux_plus < max_lux:
                # Disattiva il blocco perché non c'è rischio di spegnimento
                self.light_illuminance_lock_on[light_entity] = False
                self.log(f"🔓 Sblocco sicuro per {light_entity} (illuminanza + offset = {current_lux_plus} < {max_lux} lux)")
            elif current_lux_plus > max_lux and self.light_turned_off_by_illuminance.get(light_entity, False):
                self.light_illuminance_lock_on[light_entity] = False
                self.log(f"🔓 Sblocco sicuro per {light_entity} (illuminanza + offset = {current_lux_plus} > {max_lux} lux)")
            else:
                # Mantieni il blocco attivo e logga
                self.log(f"🔒 Blocco mantenuto per {light_entity} (illuminanza + offset = {current_lux_plus} ≥ {max_lux} lux)")

        except KeyError as e:
            self.log(f"Parametro mancante: {e}", level="ERROR")
        except Exception as e:
            self.log(f"Errore generico: {e}", level="ERROR")

    def delayed_turn_on(self, kwargs):
        """Esegue l'accensione dopo il ritardo se la presenza è ancora attiva"""
        config = kwargs["config"]
        light_entity = kwargs["light_entity"]
        timer_key = f"{light_entity}_turn_on_timer"

        # Verifica validità (gestita automaticamente dal wrapper)
        presence_active = (
            self.get_state(config["presence_sensor_on"]) == "on" or
            self.get_state(config["presence_sensor_off"]) == "on"
        )
        
        if presence_active and self.get_state(light_entity) == "off":
            self.execute_turn_on(config, light_entity)
        
        # Pulizia garantita
        self.timer_manager.cancel_timer(timer_key)

    def value_changed(self, entity, attribute, old, new, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        timer_minutes_on_push = config["timer_minutes_on_push"]
        timer_minutes_on_time = config["timer_minutes_on_time"]
        timer_filter_on_push = config["timer_filter_on_push"]
        timer_filter_on_time = config["timer_filter_on_time"]
        timer_seconds_max_lux = config["timer_seconds_max_lux"]
        min_lux_activation = config["min_lux_activation"]
        max_lux_activation = config["max_lux_activation"]
        illuminance_offset = config["illuminance_offset"]
        turn_on_light_offset = config["turn_on_light_offset"]
        turn_off_light_offset = config["turn_off_light_offset"]

        # Converte old e new in interi o float per gestire correttamente i valori
        try:
            float_old = float(old) if old else None
            float_new = float(new) if new else None
        except (ValueError, TypeError):
            float_old = old
            float_new = new

        # Determina quale valore è stato modificato
        if entity == timer_minutes_on_push:
            self.log(f"Timer 'On Push' modificato per {light_entity}: da {float_old} a {float_new} minuti")
            # Aggiorna automaticamente i timer associati
            self.timer_manager.cancel_timer(f"{light_entity}_timer_on_push")
        elif entity == timer_minutes_on_time:
            self.log(f"Timer 'On Time' modificato per {light_entity}: da {float_old} a {float_new} minuti")
            self.timer_manager.cancel_timer(f"{light_entity}_timer_on_time")
        elif entity == timer_filter_on_push:
            self.log(f"Timer 'Filter On Push' modificato per {light_entity}: da {float_old} a {float_new} secondi")
            self.timer_manager.cancel_timer(f"{light_entity}_timer_filter_on_push", is_filter=True)
        elif entity == timer_filter_on_time:
            self.log(f"Timer 'Filter On Time' modificato per {light_entity}: da {float_old} a {float_new} secondi")
            self.timer_manager.cancel_timer(f"{light_entity}_timer_filter_on_time", is_filter=True)
        elif entity == timer_seconds_max_lux:
            self.log(f"Timer 'Max Lux' modificato per {light_entity}: da {float_old} a {float_new} secondi")
            self.timer_manager.cancel_timer(f"{light_entity}_illuminance_timer", is_filter=True)
        elif entity == min_lux_activation:
            self.log(f"Min Lux Activation Light modificato per {light_entity}: da {float_old} lux a {float_new} lux")
        elif entity == max_lux_activation:
            self.log(f"Max Lux Activation Light modificato per {light_entity}: da {float_old} lux a {float_new} lux")
        elif entity == illuminance_offset:
            self.log(f"Illuminance Offset modificato per {light_entity}: da {float_old} lux a {float_new} lux")
        elif entity == turn_on_light_offset:
            self.log(f"Turn On Offset modificato per {light_entity}: da {float_old} a {float_new} secondi")
        elif entity == turn_off_light_offset:
            self.log(f"Turn Off Offset modificato per {light_entity}: da {float_old} a {float_new} secondi")
        else:
            self.log(f"Modifica sconosciuta per {light_entity}: {entity} da {old} a {new}")

    def timer_on_time_expired(self, kwargs):
        """
        Gestisce la scadenza del timer on_time con controllo di generazione.
        Validità garantita dal TimerManager.
        """
        config = kwargs["config"]
        light_entity = config["light_entity"]
        enable_automation = config["enable_automation"]
        timer_key = f"{light_entity}_timer_on_time"

        # Riattiva enable_automation se è disattivato
        if self.get_state(enable_automation) == "off":
            self.turn_on(enable_automation)
            self.log(f"💡 Automazione abilitata per timer on_time scaduto su {light_entity}")

        # 2. Cancella solo il timer on_time
        self.timer_manager.cancel_timer(timer_key)
        self.log(f"✅ Timer on_time completato per {light_entity}")

    def cancel_timer_on_no_presence(self, entity, attribute, old, new, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        enable_automation = config["enable_automation"]
        timer_filter_key = f"{light_entity}_timer_filter_on_push"
        timer_push_key = f"{light_entity}_timer_on_push"
        filter_on_time_key = f"{light_entity}_timer_filter_on_time"

        # Verifica se la luce è stata spenta manualmente in presenza
        if (self.get_state(light_entity) == "off" and 
            self.light_turned_off_by_illuminance.get(light_entity, False) is False and
            self.get_state(config["enable_automation"]) == "on"):

            # Avvia il timer filter_on_push solo se i sensori sono OFF
            if (self.get_state(config["presence_sensor_on"]) == "off" and
                self.get_state(config["presence_sensor_off"]) == "off"):
                
                try:
                    filter_duration = int(float(self.get_state(config["timer_filter_on_push"])))
                    if filter_duration > 0:
                        self.timer_manager.cancel_timer(timer_filter_key, is_filter=True)
                        self.timer_manager.start_timer(
                            key=timer_filter_key,
                            delay=filter_duration,
                            callback=self.on_filter_on_push_expired,
                            is_filter=True,
                            light_entity=light_entity,
                            timer_filter_key=timer_filter_key,
                            timer_push_key=timer_push_key,
                            enable_automation=enable_automation,
                            config=config
                        )
                except (TypeError, ValueError):
                    self.log(f"Valore timer filter non valido per {light_entity}", level="WARNING")

        # Nuovo controllo per filter_on_time ⚡
        if (self.get_state(config["presence_sensor_on"]) == "off" and 
            self.get_state(config["presence_sensor_off"]) == "off" and 
            self.timer_manager.is_timer_active(filter_on_time_key, is_filter=True)):
            
            self.timer_manager.cancel_timer(filter_on_time_key, is_filter=True)
            self.log(f"⏹️ Cancellato filter_on_time per {light_entity}: sensori OFF durante l'esecuzione")

    def cancel_on_time_if_presence_detected(self, entity, attribute, old, new, kwargs):
        """Avvia filter_on_time solo se on_time è attivo e nessun filter è già attivo"""
        try:
            config = kwargs["config"]
            light_entity = config["light_entity"]
            enable_automation = config["enable_automation"]
            timer_key = f"{light_entity}_timer_on_time"
            filter_timer_key = f"{light_entity}_timer_filter_on_time"

            # Aggiunta condizione enable_automation
            if self.get_state(enable_automation) == "on":
                self.log(f"⏭️ Timer_filter_on_time non avviato: enable_automation attivo per {light_entity}", level = "DEBUG")
                return

            # Verifica che on_time sia attivo E filter_on_time non sia attivo
            if (self.timer_manager.is_timer_active(timer_key) and 
                not self.timer_manager.is_timer_active(filter_timer_key, is_filter=True)):

                try:
                    # Avvia il nuovo filter_on_time
                    filter_duration = int(float(self.get_state(config["timer_filter_on_time"])))
                    self.timer_manager.start_timer(
                        key=filter_timer_key,
                        delay=filter_duration,
                        callback=self.on_filter_on_time_expired,
                        is_filter=True,
                        config=config,
                        scenario="presence"
                    )
                    self.log(f"⏳ Timer filter_on_time avviato per {light_entity}: {filter_duration}s", level="INFO")

                except (TypeError, ValueError):
                    self.log(f"Valore timer non valido per {light_entity}", level="WARNING")

            else:
                self.log(f"⏭️ Filter_on_time non avviato: on_time={self.timer_manager.is_timer_active(timer_key)}, filter={self.timer_manager.is_timer_active(filter_timer_key, True)}", level="DEBUG")

        except Exception as e:
            self.log(f"Errore in cancel_on_time: {str(e)}", level="ERROR")

    def cancel_offset_timer(self, light_entity):
        """
        Cancella il timer di spegnimento offset se presente.
        """
        timer_key = f"{light_entity}_turn_off_timer"
        # Verifica esistenza tramite TimerManager
        if self.timer_manager.is_timer_active(timer_key):  # Controllo diretto dell'esistenza
            self.log(f"🛑 Cancellazione timer {timer_key} per presenza rilevata")
            self.timer_manager.cancel_timer(timer_key)

    def check_and_cancel_timers(self, entity, attribute, old, new, kwargs):
        config = kwargs["config"]
        light_entity = config["light_entity"]
        automatic_enable_automation = config["automatic_enable_automation"]

        # Lista delle chiavi timer con distinzione tra main e filter
        timer_keys = [
            (f"{light_entity}_timer_on_push", False),
            (f"{light_entity}_timer_on_time", False),
            (f"{light_entity}_timer_filter_on_push", True),
            (f"{light_entity}_timer_filter_on_time", True)
        ]

        try:
            # Caso 1: Cambiamento automatic_enable_automation
            if entity == automatic_enable_automation:
                target_mode = new
                opposite_mode = "Push" if target_mode == "Time" else "Time"

                # Cancella timer dell'altra modalità
                for key, is_filter in timer_keys:
                    if opposite_mode.lower() in key:
                        self.timer_manager.cancel_timer(key, is_filter=is_filter)
                self.log(f"Modalità '{target_mode}': Cancellati timer {opposite_mode.lower()} e relativi filter")

            # Caso 2: Cambiamento enable_automation
            elif entity == config["enable_automation"]:
                auto_mode = self.get_state(automatic_enable_automation)
                canceled_timers = []
                for key, is_filter in timer_keys:
                    if auto_mode == "All":
                        continue
                    if (auto_mode == "Push" and "on_push" in key) or (auto_mode == "Time" and "on_time" in key):
                        continue
                    else:
                        self.timer_manager.cancel_timer(key, is_filter=is_filter)
                        canceled_timers.append(key)

                # Cancella SEMPRE il timer on_time quando enable_automation viene attivato
                if new == "on":
                    self.timer_manager.cancel_timer(f"{light_entity}_timer_on_time")
                    canceled_timers.append(f"{light_entity}_timer_on_time")
                    self.log(f"🛑 enable_automation attivato: timer on_time cancellato per {light_entity}")
                
                # Logica per avviare il timer on_time
                if new == "off" and auto_mode in ["All", "Time"]:
                    presence_off = (
                        self.get_state(config["presence_sensor_on"]) == "off" and
                        self.get_state(config["presence_sensor_off"]) == "off"
                    )
                    if presence_off:
                        self.check_and_start_timer_on_time(
                            entity=config["presence_sensor_on"],
                            attribute=None,
                            old=None,
                            new="off",
                            kwargs={"config": config}
                        )

                # Log delle azioni
                action = "abilitata" if new == "on" else "disabilitata"
                message = (
                    f"Automazione {action}: modalità {auto_mode} "
                    f"- Timer cancellati per {light_entity}" if canceled_timers else 
                    f"Automazione {action}: (modalità {auto_mode})"
                )
                self.log(message, level="INFO")

        except Exception as e:
            self.log(f"❌ Errore in check_and_cancel_timers: {str(e)}", level="ERROR")

    def start_offset_timer(self, light_entity, turn_off_light_offset, enable_sensor, enable_automation):
        timer_key = f"{light_entity}_turn_off_timer"
        
        # Forza cancellazione timer esistente tramite TimerManager
        self.timer_manager.cancel_timer(timer_key)

        try:
            offset_seconds = int(float(self.get_state(turn_off_light_offset)))
        except (TypeError, ValueError):
            offset_seconds = 0

        if offset_seconds > 0:
            # Avvia il timer spegnimento
            self.timer_manager.start_timer(
                key=timer_key,
                delay=offset_seconds,
                callback=self.turn_off_light_after_offset,
                is_filter=False,
                timer_key=timer_key,
                light_entity=light_entity,
                enable_sensor=enable_sensor,
                enable_automation=enable_automation
            )
            self.log(f"⏳ Avviato timer spegnimento ({offset_seconds}s) per {light_entity}")
        else:
            # Spegni immediatamente
            self.log(f"🛑 Spegnimento immediato richiesto (offset = {offset_seconds}s)", level="INFO")
            self.turn_off_light_after_offset({
                "light_entity": light_entity,
                "enable_sensor": enable_sensor,
                "enable_automation": enable_automation
            })

    def on_filter_on_push_expired(self, kwargs):
        config = kwargs["config"]
        light_entity = kwargs["light_entity"]
        timer_filter_key = kwargs["timer_filter_key"]
        timer_push_key = kwargs["timer_push_key"]
        enable_automation = kwargs["enable_automation"]

        # Cancella entrambi i timer e disabilita automazione
        self.timer_manager.cancel_timer(timer_push_key)
        self.timer_manager.cancel_timer(timer_filter_key, is_filter=True)
        self.log(f"🛑 Entrambi i timer cancellati e automazione disabilitata per {light_entity}")

    def on_filter_on_time_expired(self, kwargs):
        """Gestione scadenza naturale del filter_on_time"""
        try:
            config = kwargs.get("config")
            light_entity = config["light_entity"]
            
            timer_key = f"{light_entity}_timer_on_time"
            filter_timer_key = f"{light_entity}_timer_filter_on_time"

            # Cancellazione incondizionata di entrambi i timer
            self.timer_manager.cancel_timer(timer_key)
            self.timer_manager.cancel_timer(filter_timer_key, is_filter=True)
            self.log(f"🛑 SCADUTO filter_on_time: Cancellati entrambi i timers per {light_entity}")

        except Exception as e:
            self.log(f"ERRORE: {str(e)}", level="ERROR")
