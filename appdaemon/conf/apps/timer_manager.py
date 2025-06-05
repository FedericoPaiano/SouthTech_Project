"""
Timer Manager Module for AppDaemon
Gestisce timer con controllo generazionale per evitare esecuzioni spurie
"""

class TimerManager:
    """
    Gestisce timer con controllo generazionale per AppDaemon.
    
    Questa classe fornisce un sistema robusto per la gestione dei timer che:
    - Previene l'esecuzione di timer obsoleti
    - Gestisce automaticamente la cancellazione e il cleanup
    - Supporta due tipi di timer: normali e filter
    - Usa un sistema di generazioni per tracciare la validità dei timer
    """
    
    def __init__(self, hass_instance):
        """
        Inizializza il TimerManager.
        
        Args:
            hass_instance: Istanza dell'app AppDaemon che fornisce i metodi run_in, cancel_timer, etc.
        """
        self.hass = hass_instance
        self.timers = {}        # {key: (handle, generation)}
        self.filter_timers = {} # {key: (handle, generation)}
        self.generations = {}   # {key: generation}

    def start_timer(self, key, delay, callback, is_filter=False, *args, **kwargs):
        """
        Avvia un timer con gestione generazionale.
        
        Args:
            key: Chiave univoca per identificare il timer
            delay: Ritardo in secondi prima dell'esecuzione
            callback: Funzione da eseguire allo scadere del timer
            is_filter: True se è un timer di tipo filter
            *args, **kwargs: Argomenti aggiuntivi passati al callback
            
        Returns:
            handle: Handle del timer creato
        """
        # Cancella eventuali timer esistenti con la stessa chiave
        self.cancel_timer(key, is_filter)
        
        # Incrementa la generazione
        current_gen = self.generations.get(key, 0) + 1
        self.generations[key] = current_gen
        
        # Crea un wrapper per il callback che include il controllo generazionale
        wrapped_callback = self._wrap_callback(callback, key, current_gen, is_filter)
        
        # Avvia il timer
        handle = self.hass.run_in(wrapped_callback, delay, *args, **kwargs)
        
        # Memorizza il timer nel dizionario appropriato
        if is_filter:
            self.filter_timers[key] = (handle, current_gen)
        else:
            self.timers[key] = (handle, current_gen)
            
        return handle

    def _wrap_callback(self, callback, key, expected_gen, is_filter):
        """
        Crea un wrapper per il callback che verifica la validità generazionale.
        
        Args:
            callback: Callback originale
            key: Chiave del timer
            expected_gen: Generazione attesa per questo timer
            is_filter: True se è un timer di tipo filter
            
        Returns:
            wrapped: Funzione wrapper che esegue il controllo generazionale
        """
        def wrapped(kwargs):
            try:
                # Verifica se il timer è ancora valido
                if self.is_valid(key, expected_gen, is_filter):
                    # Aggiungi la generazione ai kwargs per riferimento
                    kwargs['generation'] = expected_gen
                    callback(kwargs)
                else:
                    self.hass.log(f"Ignored expired timer {key} (gen {expected_gen})", level="DEBUG")
            except Exception as e:
                self.hass.log(f"Error in timer callback: {str(e)}", level="ERROR")
            finally:
                # Esegui cleanup solo se il timer è ancora presente
                if key in (self.filter_timers if is_filter else self.timers):
                    self.cleanup(key, is_filter)
        return wrapped

    def cancel_timer(self, key, is_filter=False):
        """
        Cancella un timer e incrementa la generazione.
        
        Args:
            key: Chiave del timer da cancellare
            is_filter: True se è un timer di tipo filter
        """
        target = self.filter_timers if is_filter else self.timers
        
        if key in target:
            handle, gen = target.pop(key)
            # Incrementa la generazione per invalidare eventuali timer in esecuzione
            self.generations[key] = self.generations.get(key, 0) + 1
            
            try:
                # Verifica se il timer esiste ancora in AppDaemon
                if self.hass.timer_running(handle):
                    self.hass.cancel_timer(handle)
                    self.hass.log(f"Cancellato timer {key} (gen {gen})", level="DEBUG")
                else:
                    self.hass.log(f"Timer {key} già scaduto, nessuna azione", level="DEBUG")
            except Exception as e:
                self.hass.log(f"Timer {key} già cancellato: {str(e)}", level="DEBUG")
        else:
            self.hass.log(f"Tentativo di cancellare timer inesistente: {key}", level="DEBUG")

    def is_valid(self, key, expected_gen, is_filter=False):
        """
        Verifica la validità generazionale di un timer.
        
        Args:
            key: Chiave del timer
            expected_gen: Generazione attesa
            is_filter: True se è un timer di tipo filter
            
        Returns:
            bool: True se il timer è valido, False altrimenti
        """
        target = self.filter_timers if is_filter else self.timers
        current_gen = self.generations.get(key, 0)
        return key in target and current_gen == expected_gen

    def cleanup(self, key, is_filter=False):
        """
        Rimuove timer scaduti dalla memoria.
        
        Args:
            key: Chiave del timer
            is_filter: True se è un timer di tipo filter
        """
        target = self.filter_timers if is_filter else self.timers
        if key in target:
            del target[key]
            self.hass.log(f"Cleanup timer {key}", level="DEBUG")

    def is_timer_active(self, key, is_filter=False):
        """
        Verifica se un timer è attivo.
        
        Args:
            key: Chiave del timer
            is_filter: True se è un timer di tipo filter
            
        Returns:
            bool: True se il timer è attivo, False altrimenti
        """
        target = self.filter_timers if is_filter else self.timers
        return key in target

    def get_active_timers(self, is_filter=None):
        """
        Ottiene la lista dei timer attivi.
        
        Args:
            is_filter: None per tutti, True per solo filter, False per solo normali
            
        Returns:
            list: Lista delle chiavi dei timer attivi
        """
        if is_filter is None:
            return list(self.timers.keys()) + list(self.filter_timers.keys())
        elif is_filter:
            return list(self.filter_timers.keys())
        else:
            return list(self.timers.keys())

    def cancel_all_timers(self, is_filter=None):
        """
        Cancella tutti i timer.
        
        Args:
            is_filter: None per tutti, True per solo filter, False per solo normali
        """
        if is_filter is None or is_filter is False:
            keys = list(self.timers.keys())
            for key in keys:
                self.cancel_timer(key, is_filter=False)
                
        if is_filter is None or is_filter is True:
            keys = list(self.filter_timers.keys())
            for key in keys:
                self.cancel_timer(key, is_filter=True)
