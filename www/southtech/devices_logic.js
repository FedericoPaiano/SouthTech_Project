let haToken = null;
let browserId = null;

// Aggiungo una mappa per le specifiche dei modelli
const MODEL_SPECS = {
    'AION_A8R': { inputs: 8, relays: 8, friendly_name: 'AION Model: A8R' }
    // Aggiungere qui altri modelli
};

/**
 * Inizializza la pagina: recupera token, numeri di dispositivo e imposta i listener.
 */
async function initializePage() {
    haToken = sessionStorage.getItem('southtech_ha_token');
    browserId = sessionStorage.getItem('southtech_browser_id');
    setupEventListeners();
    // La popolazione di input/relay ora è gestita da updateDeviceDescription
    await fetchExistingDevices(); // Deve essere eseguito prima di fetchAvailableDeviceNumbers
    await fetchAvailableDeviceNumbers();

    // Mostra la descrizione iniziale
    updateDeviceDescription();
}

/**
 * Imposta i listener per gli eventi della UI.
 */
function setupEventListeners() {
    document.getElementById('deviceModel').addEventListener('change', () => updateDeviceDescription(true));
    document.getElementById('deviceAction').addEventListener('change', handleDeviceActionChange);
}

/**
 * Aggiorna la descrizione del dispositivo e popola i campi di input/output.
 * @param {boolean} fromUserInput - Indica se la chiamata proviene da un'azione diretta dell'utente.
 */
function updateDeviceDescription(fromUserInput = false) {
    const model = document.getElementById('deviceModel').value;
    const descriptionEl = document.getElementById('deviceDescription');
    const configAndOutputContainer = document.getElementById('configAndOutputContainer');

    if (model && MODEL_SPECS[model]) {
        const specs = MODEL_SPECS[model];
        configAndOutputContainer.style.display = 'block';

        // Popola i campi di input/output solo se l'utente ha fatto una scelta
        if (fromUserInput) {
            populateInputConfigs(specs.inputs, specs.relays);
            populateRelayConfigs(specs.relays);
        }

        descriptionEl.innerHTML = `
            <strong>Scheda ${specs.friendly_name}</strong>
            <ul>
                <li><strong>Input disponibili:</strong> ${specs.inputs}</li>
                <li><strong>Output (Relè) disponibili:</strong> ${specs.relays}</li>
            </ul>
        `;
        descriptionEl.style.display = 'block';
    } else {
        // Se è selezionato "Seleziona il modello della scheda"
        descriptionEl.style.display = 'none';
        descriptionEl.innerHTML = ''; // Pulisce il contenuto se nessun modello è selezionato
        configAndOutputContainer.style.display = 'none';
    }
}

/**
 * Popola dinamicamente le righe di configurazione per gli input.
 * @param {number} inputCount - Il numero di righe di input da creare.
 * @param {number} relayCount - Il numero di relè disponibili per l'associazione.
 */
function populateInputConfigs(inputCount, relayCount) {
    const container = document.getElementById('inputConfigContainer');
    const template = document.getElementById('inputRowTemplate');
    container.innerHTML = '';

    for (let i = 1; i <= inputCount; i++) {
        const clone = template.content.cloneNode(true);
        clone.querySelector('.input-label').textContent = `Input ${i}`;
        
        clone.querySelector('.input-pin-input').id = `input_pin_${i}`;
        clone.querySelector('.input-name-input').id = `input_name_${i}`;

        // Popola il dropdown di associazione relè
        const assocSelect = clone.querySelector('.input-relay-assoc');
        assocSelect.id = `input_relay_assoc_${i}`;
        
        const noAssocOption = document.createElement('option');
        noAssocOption.value = "";
        noAssocOption.textContent = "Nessuna";
        assocSelect.appendChild(noAssocOption);

        for (let j = 1; j <= relayCount; j++) {
            assocSelect.add(new Option(`Relè ${j}`, j));
        }
        assocSelect.value = i <= relayCount ? i : ""; // Associazione di default (Input 1 -> Relè 1, etc.)

        container.appendChild(clone);
    }
}

/**
 * @param {number} count - Il numero di righe di relè da creare.
 */
function populateRelayConfigs(count) {
    const container = document.getElementById('relayConfigContainer');
    const template = document.getElementById('relayRowTemplate');
    container.innerHTML = '';

    for (let i = 1; i <= count; i++) {
        const clone = template.content.cloneNode(true);
        const relayRow = clone.querySelector('.relay-row');
        relayRow.id = `relay_row_${i}`;
        clone.querySelector('.relay-label').textContent = `Relè ${i}`;
        
        const select = clone.querySelector('.relay-type-select');
        select.id = `relay_type_${i}`;
        select.dataset.relayIndex = i;
        select.addEventListener('change', handleRelayTypeChange);

        clone.querySelector('.relay-pin-input').id = `relay_pin_${i}`;

        container.appendChild(clone);
    }
}

/**
 * Gestisce il cambio di tipo per un relè, mostrando opzioni extra se necessario.
 * @param {Event} event - L'evento di cambio.
 */
function handleRelayTypeChange(event) {
    const select = event.target;
    const relayIndex = parseInt(select.dataset.relayIndex, 10);
    const selectedType = select.value;
    const extraOptionsContainer = document.querySelector(`#relay_row_${relayIndex} .relay-extra-options`);
    extraOptionsContainer.innerHTML = '';

    const totalRelays = document.querySelectorAll('.relay-row').length;

    // Logica per "Copertura"
    if (selectedType === 'cover_open') {
        if (relayIndex < totalRelays) {
            const nextRelaySelect = document.getElementById(`relay_type_${relayIndex + 1}`);
            nextRelaySelect.value = 'cover_close';
            nextRelaySelect.disabled = true;
            SouthTechUI.showAlert(`Relè ${relayIndex + 1} è stato assegnato automaticamente alla chiusura della copertura.`, 'info');
        } else {
            SouthTechUI.showAlert('Non puoi impostare l\'ultimo relè come "Apertura Copertura".', 'warning');
            select.value = 'switch'; // Ripristina
        }
    } else {
        // Se il tipo precedente era 'cover_open', riabilita il successivo
        const previousValue = select.dataset.previousValue || '';
        if (previousValue === 'cover_open' && relayIndex < totalRelays) {
            const nextRelaySelect = document.getElementById(`relay_type_${relayIndex + 1}`);
            nextRelaySelect.disabled = false;
            nextRelaySelect.value = 'switch';
        }
    }

    // Logica per "Termostato"
    if (selectedType === 'thermostat') {
        const thermostatTemplate = document.getElementById('thermostatOptionsTemplate');
        const clone = thermostatTemplate.content.cloneNode(true);
        clone.querySelector('input').id = `thermostat_sensor_${relayIndex}`;
        extraOptionsContainer.appendChild(clone);
    }

    // Salva il valore corrente per il prossimo cambio
    select.dataset.previousValue = selectedType;
}

/**
 * Recupera l'elenco dei dispositivi già configurati.
 */
async function fetchExistingDevices() {
    SouthTechUI.showAlert('Recupero dispositivi esistenti...', 'info');
    try {
        const response = await communicateWithBackend('get_existing_devices');
        if (response.success) {
            const actionSelect = document.getElementById('deviceAction');
            
            if (response.devices.length > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = 'Modifica Esistente';
                response.devices.forEach(device => {
                    // Il valore del formato: edit_MODELLO_NUMERO
                    const option = new Option(device.friendly_name, `edit_${device.model}_${device.number}`);
                    optgroup.appendChild(option);
                });
                actionSelect.appendChild(optgroup);
            }
            
            SouthTechUI.showAlert('Dispositivi esistenti caricati.', 'success', 2000);
        } else {
            throw new Error(response.error || 'Errore sconosciuto');
        }
    } catch (error) {
        console.error('Errore nel recuperare i dispositivi esistenti:', error);
        SouthTechUI.showAlert(`Errore recupero dispositivi: ${error.message}`, 'error');
    }
}

/**
 * Gestisce il cambio di azione (Crea vs Modifica).
 */
async function handleDeviceActionChange() {
    const actionValue = document.getElementById('deviceAction').value;
    const modelSelect = document.getElementById('deviceModel');
    const numberSelect = document.getElementById('deviceNumber');

    if (actionValue === 'create_new') {
        // Modalità Creazione
        modelSelect.disabled = false;
        numberSelect.disabled = false;
        modelSelect.value = ''; // Resetta
        await fetchAvailableDeviceNumbers(); // Ricarica solo i numeri disponibili
        updateDeviceDescription(false); // Nasconde la configurazione
    } else {
        // Modalità Modifica
        const [action, model, number] = actionValue.split('_');
        
        modelSelect.value = model;
        modelSelect.disabled = true;
        
        let optionExists = Array.from(numberSelect.options).some(opt => opt.value === number);
        if (!optionExists) {
            numberSelect.add(new Option(number, number, false, true));
        }
        numberSelect.value = number;
        numberSelect.disabled = true;
        
        updateDeviceDescription(true); // Mostra la configurazione e popola i campi
    }
}

/**
 * Recupera l'elenco dei dispositivi già configurati.
 */
async function fetchExistingDevices() {
    SouthTechUI.showAlert('Recupero dispositivi esistenti...', 'info');
    try {
        const response = await communicateWithBackend('get_existing_devices');
        if (response.success) {
            const actionSelect = document.getElementById('deviceAction');
            
            if (response.devices.length > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = 'Modifica Esistente';
                response.devices.forEach(device => {
                    // Il valore del formato: edit_MODELLO_NUMERO
                    const option = new Option(device.friendly_name, `edit_${device.model}_${device.number}`);
                    optgroup.appendChild(option);
                });
                actionSelect.appendChild(optgroup);
            }
            
            SouthTechUI.showAlert('Dispositivi esistenti caricati.', 'success', 2000);
        } else {
            throw new Error(response.error || 'Errore sconosciuto');
        }
    } catch (error) {
        console.error('Errore nel recuperare i dispositivi esistenti:', error);
        SouthTechUI.showAlert(`Errore recupero dispositivi: ${error.message}`, 'error');
    }
}

/**
 * Gestisce il cambio di azione (Crea vs Modifica).
 */
async function handleDeviceActionChange() {
    const actionValue = document.getElementById('deviceAction').value;
    const modelSelect = document.getElementById('deviceModel');
    const numberSelect = document.getElementById('deviceNumber');

    if (actionValue === 'create_new') {
        // Modalità Creazione
        modelSelect.disabled = false;
        numberSelect.disabled = false;
        modelSelect.value = ''; // Resetta
        await fetchAvailableDeviceNumbers(); // Ricarica solo i numeri disponibili
        updateDeviceDescription(false); // Nasconde la configurazione
    } else {
        // Modalità Modifica
        const [action, model, number] = actionValue.split('_');
        
        modelSelect.value = model;
        modelSelect.disabled = true;
        
        let optionExists = Array.from(numberSelect.options).some(opt => opt.value === number);
        if (!optionExists) {
            numberSelect.add(new Option(number, number, false, true));
        }
        numberSelect.value = number;
        numberSelect.disabled = true;
        
        updateDeviceDescription(true); // Mostra la configurazione e popola i campi
    }
}

/**
 * Richiede al backend i numeri di dispositivo disponibili.
 */
async function fetchAvailableDeviceNumbers() {
    SouthTechUI.showAlert('Recupero numeri dispositivo disponibili...', 'info');
    try {
        const response = await communicateWithBackend('get_available_device_numbers');
        if (response.success) {
            const numberSelect = document.getElementById('deviceNumber');
            numberSelect.innerHTML = '';
            response.available_numbers.forEach(num => {
                const option = document.createElement('option');
                option.value = num;
                option.textContent = num;
                numberSelect.appendChild(option);
            });
            numberSelect.value = response.next_number;
            SouthTechUI.showAlert('Numeri dispositivo caricati.', 'success', 2000);
        } else {
            throw new Error(response.error || 'Errore sconosciuto');
        }
    } catch (error) {
        console.error('Errore nel recuperare i numeri di dispositivo:', error);
        SouthTechUI.showAlert(`Errore recupero numeri: ${error.message}`, 'error');
        document.getElementById('deviceNumber').innerHTML = '<option>Errore</option>';
    }
}

/**
 * Valida i pin GPIO inseriti per evitare duplicati e formati non validi.
 * @returns {{isValid: boolean, message?: string}} Oggetto con lo stato della validazione.
 */
function validatePins() {
    const pins = new Map(); // Usa una Map per memorizzare il pin e la sua origine (es. "Input 3")
    const errors = [];
    const model = document.getElementById('deviceModel').value;
    const specs = MODEL_SPECS[model];
    if (!specs) return { isValid: false, message: "Modello scheda non valido." };

    // Controlla gli input
    for (let i = 1; i <= specs.inputs; i++) {
        const pinInput = document.getElementById(`input_pin_${i}`);
        if (!pinInput) continue;
        const pin = pinInput.value.trim().toUpperCase();
        if (pin) {
            if (pins.has(pin)) {
                errors.push(`Pin duplicato ${pin} (usato da ${pins.get(pin)} e Input ${i})`);
            } else {
                pins.set(pin, `Input ${i}`);
            }
            if (!pin.startsWith('GPIO')) {
                 errors.push(`Pin non valido per Input ${i}: "${pin}". Dovrebbe iniziare con 'GPIO'.`);
            }
        }
    }

    // Controlla i relè
    for (let i = 1; i <= specs.relays; i++) {
        const pinInput = document.getElementById(`relay_pin_${i}`);
        if (!pinInput) continue;
        const pin = pinInput.value.trim().toUpperCase();
        if (pin) {
            if (pins.has(pin)) {
                errors.push(`Pin duplicato ${pin} (usato da ${pins.get(pin)} e Relè ${i})`);
            } else {
                pins.set(pin, `Relè ${i}`);
            }
             if (!pin.startsWith('GPIO')) {
                 errors.push(`Pin non valido per Relè ${i}: "${pin}". Dovrebbe iniziare con 'GPIO'.`);
            }
        }
    }

    if (errors.length > 0) return { isValid: false, message: "Errori di validazione:\n- " + errors.join('\n- ') };
    return { isValid: true };
}

/**
 * Genera il codice YAML basandosi sulla configurazione dell'interfaccia.
 */
function generateYaml() {
    const deviceNumber = document.getElementById('deviceNumber').value;
    const model = document.getElementById('deviceModel').value;
    const specs = MODEL_SPECS[model];

    if (!deviceNumber || deviceNumber === 'Errore') {
        SouthTechUI.showAlert('Numero dispositivo non valido. Impossibile generare YAML.', 'error');
        return;
    }
    if (!specs) {
        SouthTechUI.showAlert('Modello scheda non valido. Impossibile generare YAML.', 'error');
        return;
    }

    // Esegui la validazione dei pin prima di generare
    const validation = validatePins();
    if (!validation.isValid) {
        SouthTechUI.showAlert(validation.message, 'error', 8000);
        return;
    }

    const deviceName = `${model.toLowerCase()}_${deviceNumber}`;
    const friendlyName = `${specs.friendly_name} ${deviceNumber}`;

    const inputsYaml = Array.from({length: specs.inputs}, (_, i) => {
        const pin = document.getElementById(`input_pin_${i + 1}`).value.trim();
        const name = document.getElementById(`input_name_${i + 1}`).value.trim();
        if (pin && name) {
            return `  - platform: gpio\n    pin: ${pin}\n    name: "${name}"\n    id: input_${i + 1}`;
        } else if (pin || name) {
            return `  # Input ${i + 1} configurato parzialmente e ignorato.`;
        }
        return ``; // Non aggiungere nulla se vuoto
    }).filter(Boolean).join('\n');

    const relaysYaml = Array.from({length: specs.relays}, (_, i) => {
        const pin = document.getElementById(`relay_pin_${i + 1}`).value.trim();
        if (pin) {
            return `  - platform: gpio\n    pin: ${pin}\n    name: "\\${friendlyName} Relay ${i + 1}"\n    id: relay_${i + 1}`;
        }
        return ``; // Non aggiungere nulla se vuoto
    }).filter(Boolean).join('\n');

    const automationsYaml = Array.from({length: specs.inputs}, (_, i) => {
        const assocRelay = document.getElementById(`input_relay_assoc_${i + 1}`).value;
        const inputPin = document.getElementById(`input_pin_${i + 1}`).value.trim();
        if (assocRelay && inputPin) {
            return `  - alias: "Toggle Relay ${assocRelay} from Input ${i + 1}"\n    trigger:\n      - platform: state\n        entity_id: binary_sensor.input_${i + 1}\n        to: 'on'\n    action:\n      - service: switch.toggle\n        target:\n          entity_id: switch.relay_${assocRelay}`;
        }
        return '';
    }).filter(Boolean).join('\n');


    let yaml = `substitutions:
  device_name: ${deviceName}
  friendly_name: "${friendlyName}"

esphome:
  name: \\${device_name}
  friendly_name: \\${friendly_name}
  platform: ESP32
  board: esp32dev

api:
ota:
logger:
web_server:

wifi:
  # Inserisci qui le tue credenziali WiFi
  ssid: "Your_SSID"
  password: "Your_Password"

${inputsYaml ? 'binary_sensor:\n' + inputsYaml : '# Nessun input configurato'}

${relaysYaml ? 'switch:\n' + relaysYaml : '# Nessun relè configurato'}

${automationsYaml ? 'automation:\n' + automationsYaml : '# Nessuna automazione input-relè configurata'}
`;

    // Aggiunge le configurazioni specifiche per tipo di relè
    let covers = [];
    for (let i = 1; i <= specs.relays; i++) {
        const type = document.getElementById(`relay_type_${i}`).value;
        const relayId = `relay_${i}`;

        if (type === 'light') {
            yaml += `light:\n  - platform: switch\n    name: "\${friendly_name} Light ${i}"\n    switch_id: ${relayId}\n\n`;
        } else if (type === 'cover_open') {
            covers.push({ open_relay: relayId, close_relay: `relay_${i + 1}`, index: covers.length + 1 });
        } else if (type === 'thermostat') {
            const sensorId = document.getElementById(`thermostat_sensor_${i}`).value;
            if (sensorId) {
                yaml += `climate:\n  - platform: bang_bang\n    name: "\${friendly_name} Thermostat ${i}"\n    sensor: ${sensorId}\n    cool_action:\n      - switch.turn_on: ${relayId}\n    idle_action:\n      - switch.turn_off: ${relayId}\n\n`;
            } else {
                yaml += `# ATTENZIONE: Configurazione Termostato per Relè ${i} incompleta. Manca l'ID del sensore di temperatura.\n\n`;
            }
        }
    }

    // Aggiunge le configurazioni delle coperture
    if (covers.length > 0) {
        yaml += 'cover:\n';
        covers.forEach(cover => {
            yaml += `  - platform: template\n    name: "\${friendly_name} Cover ${cover.index}"\n    open_action:\n      - switch.turn_on: ${cover.open_relay}\n    close_action:\n      - switch.turn_on: ${cover.close_relay}\n    stop_action:\n      - switch.turn_off: ${cover.open_relay}\n      - switch.turn_off: ${cover.close_relay}\n\n`;
        });
    }

    document.getElementById('yamlCode').textContent = yaml;
    document.getElementById('yamlOutput').style.display = 'block';
    SouthTechUI.showAlert('YAML generato con successo!', 'success');
}

/**
 * Salva il codice YAML generato sul server.
 */
async function saveYaml() {
    const content = document.getElementById('yamlCode').textContent;
    const model = document.getElementById('deviceModel').value;
    const deviceNumber = document.getElementById('deviceNumber').value;

    if (content.includes('Clicca "Genera YAML"')) {
        SouthTechUI.showAlert('Per favore, genera prima il codice YAML.', 'warning');
        return;
    }

    const filename = `${model}_${deviceNumber}.yaml`;
    SouthTechUI.showAlert(`Salvataggio di ${filename} in corso...`, 'info');

    try {
        const response = await communicateWithBackend('save_esphome_device', { filename, content });
        if (response.success) {
            SouthTechUI.showAlert(response.message || 'File salvato con successo!', 'success');
        } else {
            throw new Error(response.error || 'Errore sconosciuto durante il salvataggio.');
        }
    } catch (error) {
        console.error('Errore salvataggio YAML:', error);
        SouthTechUI.showAlert(`Errore salvataggio: ${error.message}`, 'error');
    }
}

/**
 * Copia il contenuto YAML negli appunti.
 */
async function copyYaml() {
    const yamlContent = document.getElementById('yamlCode').textContent;
    try {
        await navigator.clipboard.writeText(yamlContent);
        SouthTechUI.showAlert('📋 Codice YAML copiato negli appunti!', 'success', 2000);
    } catch (err) {
        console.error('Errore durante la copia:', err);
        SouthTechUI.showAlert('❌ Errore durante la copia.', 'error');
    }
}

/**
 * Funzione centralizzata per comunicare con il backend tramite sensori.
 * @param {string} action - L'azione da eseguire nel backend.
 * @param {object} payload - I dati da inviare.
 * @returns {Promise<object>} - La risposta dal backend.
 */
async function communicateWithBackend(action, payload = {}) {
    const requestId = `device_config_${Date.now()}`;
    const requestSensor = 'sensor.southtech_device_config_request';
    const responseSensor = 'sensor.southtech_device_config_response';

    const requestPayload = {
        state: 'pending',
        attributes: { ...payload, action, request_id: requestId, browser_id: browserId }
    };

    // Invia la richiesta
    const setResponse = await fetch(`/api/states/${requestSensor}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${haToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload)
    });

    if (!setResponse.ok) throw new Error('Errore nell\'invio della richiesta al backend.');

    // Attende la risposta
    for (let i = 0; i < 15; i++) { // Timeout di 15 secondi
        await new Promise(resolve => setTimeout(resolve, 1000));
        const getResponse = await fetch(`/api/states/${responseSensor}`, {
            headers: { 'Authorization': `Bearer ${haToken}` }
        });
        if (getResponse.ok) {
            const responseState = await getResponse.json();
            if (responseState.attributes.request_id === requestId) {
                return responseState.attributes;
            }
        }
    }

    throw new Error('Timeout: nessuna risposta dal backend.');
}