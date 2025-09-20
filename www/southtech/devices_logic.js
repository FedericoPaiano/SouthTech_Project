let haToken = null;
let browserId = null;
let selectedDeviceModel = null;

// Aggiungo una mappa per le specifiche dei modelli
const MODEL_SPECS = {
    'AION_A8R': { inputs: 8, relays: 8, friendly_name: 'AION Model: A8R' },
    'AION_A8SR': { inputs: 8, relays: 8, friendly_name: 'AION Model: A8SR' }
    // Aggiungere qui altri modelli
};

/**
 * Inizializza la pagina: recupera token, numeri di dispositivo e imposta i listener.
 */
async function initializePage() {
    haToken = sessionStorage.getItem('southtech_ha_token');
    browserId = sessionStorage.getItem('southtech_browser_id');
    setupEventListeners();
    await populateDeviceSelector();
}

/**
 * Imposta i listener per gli eventi della UI.
 */
function setupEventListeners() {
    // Listener per il modello, per aggiornare la UI quando si crea un nuovo dispositivo
    document.getElementById('deviceModel').addEventListener('change', handleDeviceSelectionChange);
}

/**
 * Popola il selettore dei dispositivi con opzioni per creare o modificare.
 */
async function populateDeviceSelector() {
    SouthTechUI.showAlert('Recupero dispositivi esistenti...', 'info');
    const modelSelect = document.getElementById('deviceModel');

    modelSelect.innerHTML = '<option value="" selected>Seleziona un dispositivo da modificare...</option>';

    try {
        // Recupera solo i dispositivi esistenti
        const devicesResponse = await communicateWithBackend('get_existing_devices');

        if (!devicesResponse.success) throw new Error(devicesResponse.error || 'Errore recupero dispositivi');

        const existingDevices = devicesResponse.devices || [];

        // --- Filtra solo i dispositivi A8R e A8SR ---
        console.log('Dispositivi trovati:', existingDevices);
        const validDevices = existingDevices.filter(device => {
            const modelLower = device.model.toLowerCase();
            console.log('Controllo modello:', device.model, 'lowercase:', modelLower);
            const isValid = modelLower.includes('a8') || modelLower.includes('a8s');
            console.log('È valido?', isValid);
            return isValid;
        });

        // --- Popola con i dispositivi esistenti ---
        console.log('Dispositivi validi dopo il filtro:', validDevices);
        if (validDevices.length > 0) {
            validDevices.forEach(device => {
                // Determina il modello corretto
                let displayModel = device.model;
                console.log('Elaborazione dispositivo:', device);
                if (device.model.toLowerCase().includes('a8s')) {
                    displayModel = 'AION_A8SR';
                } else if (device.model.toLowerCase().includes('a8')) {
                    displayModel = 'AION_A8R';
                }
                console.log('Modello finale:', displayModel);
                
                // Salva la configurazione del dispositivo per uso futuro
                device.displayModel = displayModel;
                window.deviceConfigurations = window.deviceConfigurations || {};
                console.log(`Salvando configurazione per ${displayModel}_${device.number}:`, device.configuration);
                window.deviceConfigurations[`${displayModel}_${device.number}`] = device.configuration;
                
                const option = new Option(
                    `${MODEL_SPECS[displayModel].friendly_name} #${device.number}`, 
                    `edit_${displayModel}_${device.number}`
                );
                modelSelect.appendChild(option);
            });
            SouthTechUI.showAlert(`${validDevices.length} dispositivi compatibili trovati.`, 'success', 2000);
        } else {
             SouthTechUI.showAlert('Nessun dispositivo A8R/A8SR trovato nella cartella esphome/hardware.', 'warning', 5000);
        }

    } catch (error) {
        console.error('Errore nel popolare il selettore dispositivi:', error);
        SouthTechUI.showAlert(`Errore caricamento: ${error.message}`, 'error');
    }
}

/**
 * Gestisce il cambio di selezione nel dropdown del dispositivo/modello.
 */
async function handleDeviceSelectionChange() {
    const modelSelect = document.getElementById('deviceModel');
    const selectedValue = modelSelect.value;
    const deviceNumberContainer = document.getElementById('deviceNumberContainer');
    const header = document.querySelector('.config-section h5');
    selectedDeviceModel = null; // Reset

    if (!selectedValue) {
        deviceNumberContainer.style.display = 'none';
        updateDeviceDescription(null, false);
        if (header) header.innerHTML = '<i class="fas fa-edit"></i> Modifica Dispositivo';
        return;
    }

    // Il valore è sempre nel formato "edit_MODEL_NUMBER"
    // La riga seguente era errata perché non gestiva i modelli con underscore (es. AION_A8R)
    // const [mode, model, number] = selectedValue.split('_');
    const parts = selectedValue.split('_');
    const mode = parts[0]; // "edit"
    const number = parts[parts.length - 1]; // "01"
    const model = parts.slice(1, parts.length - 1).join('_'); // "AION_A8R"

    // --- Modalità MODIFICA ---
    selectedDeviceModel = model;
    if (header) header.innerHTML = `<i class="fas fa-edit"></i> Modifica Dispositivo ${model} (${number})`;
    
    deviceNumberContainer.innerHTML = `
        <label for="deviceNumber" class="form-label">Numero Dispositivo</label>
        <input type="text" id="deviceNumber" class="form-control" value="${number}" readonly style="background-color: #e9ecef;">
        <small class="form-text text-muted">Numero del dispositivo selezionato (non modificabile).</small>
    `;
    deviceNumberContainer.style.display = 'block';
    
    updateDeviceDescription(model, true);
    
    // Carica la configurazione salvata
    const deviceConfig = window.deviceConfigurations[`${model}_${number}`];
    if (deviceConfig) {
        console.log('Caricamento configurazione dispositivo completa:', deviceConfig);
        
        // Popola i relè con la configurazione salvata
        if (deviceConfig.relays) {
            deviceConfig.relays.forEach(relay => {
                const relayTypeSelect = document.getElementById(`relay_type_${relay.number}`);
                const relayNameInput = document.getElementById(`relay_name_${relay.number}`);
                
                if (relayTypeSelect) {
                    relayTypeSelect.value = relay.type;
                    // Trigger dell'evento change per gestire le opzioni aggiuntive
                    relayTypeSelect.dispatchEvent(new Event('change'));
                }
                
                if (relayNameInput && relay.name) {
                    relayNameInput.value = relay.name;
                }
            });
        }
        
        // Popola gli input con i dati di controllo luci
        if (deviceConfig.inputs && deviceConfig.inputs.length > 0) {
            console.log('✅ Configurazione input ricevuta dal backend:', deviceConfig.inputs);
            deviceConfig.inputs.forEach(input => {
                const nameInput = document.getElementById(`input_name_${input.number}`);
                const feedbackSelect = document.getElementById(`input_feedback_assoc_${input.number}`);
                
                if (nameInput) nameInput.value = input.name || '';
                
                // Determina quale dispositivo è associato a questo input di controllo
                if (feedbackSelect && input.feedback_for_relay) {
                    feedbackSelect.value = input.feedback_for_relay;
                    
                    // Aggiorna il testo dell'opzione in base al tipo di controllo
                    const option = feedbackSelect.querySelector(`option[value="${input.feedback_for_relay}"]`);
                    if (option) {
                        const controlType = input.control_type || 'unknown';
                        if (controlType === 'light') {
                            option.textContent = `Controlla Luce Relè ${input.feedback_for_relay}`;
                        } else if (controlType === 'cover_open') {
                            option.textContent = `Apertura Copertura Relè ${input.feedback_for_relay}`;
                        } else if (controlType === 'cover_close') {
                            option.textContent = `Chiusura Copertura Relè ${input.feedback_for_relay}`;
                        } else {
                            option.textContent = `Controllo ${controlType} Relè ${input.feedback_for_relay}`;
                        }
                    }
                }
            });
        } else {
            console.log('❌ Nessuna configurazione input ricevuta dal backend');
            console.log('💡 Questo indica che AppDaemon sta usando la vecchia versione del parser');
            console.log('🔄 Soluzione: Riavviare Home Assistant o AppDaemon');
            
            // Mostra un avviso all'utente
            SouthTechUI.showAlert('⚠️ Configurazione input non disponibile - Riavviare Home Assistant per caricare gli aggiornamenti', 'warning', 8000);
        }
        
        SouthTechUI.showAlert('Configurazione dispositivo caricata.', 'success');
    } else {
        SouthTechUI.showAlert('Nessuna configurazione trovata per questo dispositivo.', 'warning');
    }
}

function updateDeviceDescription(model, fromUserInput = false) {
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
                <li><strong>Input disponibili:</strong> ${specs.inputs} (controllo diretto luci)</li>
                <li><strong>Output (Relè) disponibili:</strong> ${specs.relays}</li>
                <li><strong>Logica Controllo:</strong> Ogni input controlla direttamente l'accensione/spegnimento di una luce specifica</li>
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
        
        const nameInput = clone.querySelector('.input-name-input');
        nameInput.id = `input_name_${i}`;
        nameInput.readOnly = true;
        nameInput.style.backgroundColor = '#e9ecef';

        // Popola il dropdown di associazione feedback luce
        const assocSelect = clone.querySelector('.input-relay-assoc');
        assocSelect.id = `input_feedback_assoc_${i}`;
        assocSelect.disabled = true;
        assocSelect.style.backgroundColor = '#e9ecef';
        
        const noAssocOption = document.createElement('option');
        noAssocOption.value = "";
        noAssocOption.textContent = "Nessun controllo";
        assocSelect.appendChild(noAssocOption);

        // Popola con tutti i relè - il testo sarà aggiornato quando si carica la configurazione
        for (let j = 1; j <= relayCount; j++) {
            assocSelect.add(new Option(`Controlla Relè ${j}`, j));
        }
        
        // Aggiungi opzioni per coperture (relè accoppiati)
        for (let j = 1; j < relayCount; j += 2) {
            const coverRelays = `${j}-${j + 1}`;
            assocSelect.add(new Option(`Copertura Relè ${coverRelays}`, coverRelays));
        }
        assocSelect.value = ""; // Nessuna associazione di default

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
        
        const nameInput = clone.querySelector('.relay-name-input');
        nameInput.id = `relay_name_${i}`;
        nameInput.readOnly = true;
        nameInput.style.backgroundColor = '#e9ecef';
        
        const select = clone.querySelector('.relay-type-select');
        select.id = `relay_type_${i}`;
        select.dataset.relayIndex = i;
        select.disabled = true;
        select.style.backgroundColor = '#e9ecef';
        select.addEventListener('change', handleRelayTypeChange);

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
    
    // Non c'è più il container per opzioni extra nel template semplificato
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

    // Logica per "Termostato" - Non più necessaria, configurazione gestita automaticamente

    // Salva il valore corrente per il prossimo cambio
    select.dataset.previousValue = selectedType;
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

    // Pin validation non più necessaria - gestita automaticamente dal parser

    // I pin dei relè sono ora gestiti automaticamente dal parser, non servono controlli

    if (errors.length > 0) return { isValid: false, message: "Errori di validazione:\n- " + errors.join('\n- ') };
    return { isValid: true };
}

/**
 * Genera il codice YAML basandosi sulla configurazione dell'interfaccia.
 */
function generateYaml() {
    const deviceNumber = document.getElementById('deviceNumber').value;
    const model = selectedDeviceModel;
    const specs = MODEL_SPECS[selectedDeviceModel];

    if (!deviceNumber || deviceNumber === 'Errore') {
        SouthTechUI.showAlert('Numero dispositivo non valido. Impossibile generare YAML.', 'error');
        return;
    }
    if (!specs) {
        SouthTechUI.showAlert('Modello scheda non valido. Impossibile generare YAML.', 'error');
        return;
    }

    // La validazione non è più necessaria - configurazione gestita automaticamente dal parser

    const deviceName = `${model.toLowerCase()}_${deviceNumber}`;
    const friendlyName = `${specs.friendly_name} ${deviceNumber}`;

    // La generazione YAML degli input è ora gestita direttamente dal file ESPHome esistente
    const inputsYaml = `# Input configuration is managed automatically from existing ESPHome file`;

    // I relè sono ora gestiti direttamente dal file YAML esistente - non generiamo più la sezione switch

    // Le automazioni input-dispositivo sono ora gestite dal file ESPHome esistente
    const automationsYaml = `# Input-device automation is managed automatically from existing ESPHome file`;


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

# Le configurazioni switch, light, cover e climate sono gestite dal file YAML esistente

${automationsYaml ? 'automation:\n' + automationsYaml : '# Nessuna automazione input-relè configurata'}
`;

    // Le configurazioni specifiche per tipo di relè (light, cover, climate) 
    // sono ora gestite direttamente dal file YAML esistente
    yaml += `\n# NOTA: Le configurazioni di luci, coperture e termostati sono già presenti nel file YAML esistente\n# e vengono gestite automaticamente dal sistema.\n`;

    document.getElementById('yamlCode').textContent = yaml;
    document.getElementById('yamlOutput').style.display = 'block';
    SouthTechUI.showAlert('YAML generato con successo!', 'success');
}

/**
 * Salva il codice YAML generato sul server.
 */
async function saveYaml() {
    const content = document.getElementById('yamlCode').textContent;
    const deviceNumber = document.getElementById('deviceNumber').value;
    const model = selectedDeviceModel;

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