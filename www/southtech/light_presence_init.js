// Configurazione API
let haAreasRegistry = [];
let haEntityRegistry = [];
let haDeviceRegistry = [];

// Variabili globali
let entities = { lights: [], binary_sensors: [], sensors: [] };
let configurations = [];
let configCounter = 0;
let isAuthenticated = false;
let isConnected = false;
let authToken = null;
let haToken = null;
let browserId = null;
let currentCommunicationMode = 'websocket_manager';
let entityAreaCache = new Map(); // Cache entity_id -> area_name
let areasDataCache = null; // Cache completa aree

// Variabili globali per salvataggio
let isSaving = false;

// 🎯 SISTEMA DI FILTRO CORRETTO
let areaFilterEnabled = true; // Filtro per aree (attivo di default)
let entityFilterEnabled = true; // Filtro per entità popolate (attivo di default)
let templateSensorsCache = null; // Cache per evitare ricaricamenti
let lastFilterCheck = null; // Timestamp ultimo controllo template

// 🏠 CACHE AREE - NUOVA VARIABILE
let entityAreasMap = new Map(); // Mappa entity_id -> area

// Inizializzazione
window.addEventListener('load', async () => {
    console.log('🚀 SouthTech Automatismo Luci avviato (v3.1.0)');
    console.log('🌐 Network Info:', SouthTechCore.getNetworkInfo());
    
    // ✅ STEP 1: CONTROLLO SESSIONE per pagine protette (versione inline)
    console.log('🛡️ Controllo sessione timeout per pagina protetta...');

    // Esegui controllo
    const sessionValid = await SouthTechSessionGuard.init();
    if (!sessionValid) {
        return; // Session Guard gestisce tutto automaticamente
    }
    
    // ✅ STEP 2: CONTROLLO ACCESSO AUTORIZZATO
    const accessGranted = await SouthTechCore.validateDirectPageAccess();
    if (!accessGranted) {
        console.log('🔐 Accesso negato - interruzione caricamento pagina');
        return;
    }
    
    // ✅ STEP 3: Continua con inizializzazione esistente
    console.log('✅ Sessione e accesso validi - continuazione inizializzazione...');
    await initializeAuthentication(); // ← Questa funzione ESISTE in light_presence
});

// Verifica autenticazione dalla sessione
async function initializeAuthentication() {
    authToken = sessionStorage.getItem('southtech_session_token');
    haToken = sessionStorage.getItem('southtech_ha_token');
    browserId = sessionStorage.getItem('southtech_browser_id');
    
    if (!authToken || !haToken) {
        console.log('❌ Token mancanti, reindirizzo al menu principale');
        showAuthError();
        return;
    }
    
    // ✅ CHIAMATA CORRETTA con namespace
    const tokenValid = await SouthTechCore.validateHAToken(haToken);
    if (!tokenValid) {
        console.log('❌ Token HA non valido, reindirizzo al menu principale');
        showAuthError();
        return;
    }
    
    console.log('✅ Autenticazione valida, inizializzo dashboard');
    isAuthenticated = true;
    showMainContent();
    await initializeDashboard();
}

function showAuthError() {
    document.getElementById('authError').style.display = 'block';
    document.getElementById('mainContent').style.display = 'none';
}

function showMainContent() {
    document.getElementById('authError').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
}

function redirectToMain() {
    window.location.href = 'index.html';
}

// ✅ INIZIALIZZAZIONE DASHBOARD CORRETTA (ORDINE FISSO)
async function initializeDashboard() {
    console.log('🔍 Inizializzazione dashboard automatismo luci...');
    SouthTechUI.updateConnectionStatus('Caricamento entità...', 'loading');

    // ✅ IMPORTANTE: Inizializza timeout system per questa pagina
    SouthTechTimeout.initialize();
    
    try {
        // 1. Mostra stato filtro
        showFilterStatus();
        
        // 2. ✅ PRIMA carica entità e aree
        await loadEntities();
        
        // 3. ✅ POI carica configurazioni (ora le aree ci sono!)
        console.log('📋 Caricamento configurazioni dopo le entità...');
        await syncConfigurations();
        
        // 4. Aggiorna interfaccia
        updateConfigurationsList();
        
        // 5. Mostra interfaccia
        document.getElementById('configurationsContainer').style.display = 'block';
        document.getElementById('connectionStatus').style.display = 'none';
        
        // 6. Messaggio finale
        let statusMessage = '';
        if (currentCommunicationMode === 'websocket_filtered' || currentCommunicationMode === 'websocket_unfiltered') {
            statusMessage = areaFilterEnabled ? 'CON filtro area (WebSocket Manager)' : 'SENZA filtro area (WebSocket Manager)';
        } else if (currentCommunicationMode === 'fallback_direct') {
            statusMessage = 'Modalità fallback (WebSocket Manager non disponibile)';
        } else {
            statusMessage = areaFilterEnabled ? 'CON filtro area' : 'SENZA filtro area';
        }
        SouthTechUI.showAlert(`Dashboard caricata: ${statusMessage}`, 'success');
        
        // 7. Inizializza submenu filtri dopo il caricamento
        setTimeout(() => {
            initializeFiltersSubmenu();
            setupSubmenuBehavior();
        }, 500);
        
    } catch (error) {
        console.error('Errore inizializzazione:', error);
        SouthTechUI.updateConnectionStatus('Caricamento entità...', 'loading');
        SouthTechUI.showAlert(`Errore inizializzazione: ${error.message}`, 'error');
    }
}

/**
* Crea nome di visualizzazione per un'entità INCLUDENDO L'AREA
* Combina entity_id, friendly_name e area per un display completo e leggibile
* 
* @param {string} entityId - ID dell'entità (es: "light.rgb_01_05")
* @param {string} friendlyName - Nome friendly dall'attributo HA (es: "Luce RGB Soggiorno")
* @returns {string} - Nome di visualizzazione con area (es: "Luce RGB Soggiorno (Soggiorno)")
*/
function createEntityDisplayName(entityId, friendlyName) {
    let baseName;
    
    if (friendlyName && friendlyName !== entityId) {
        baseName = friendlyName;
    } else {
        baseName = entityId.split('.')[1].replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    const entityArea = getEntityArea(entityId);
    
    return entityArea ? `${baseName} (${entityArea})` : `${baseName} (Area non assegnata)`;
}

function setupSubmenuBehavior() {
    // CSS per submenu dropdown
    const submenuCSS = `
        <style id="submenu-styles">
        .dropdown-submenu {
            position: relative;
        }
        
        .dropdown-submenu .submenu {
            position: absolute;
            top: 0;
            left: 100%;
            margin-top: -1px;
            min-width: 200px;
            display: none;
        }
        
        .dropdown-submenu:hover .submenu {
            display: block;
        }
        
        .dropdown-submenu .dropdown-toggle::after {
            display: inline-block;
            margin-left: 0.255em;
            vertical-align: 0.255em;
            content: "";
            border-top: 0.3em solid transparent;
            border-right: 0;
            border-bottom: 0.3em solid transparent;
            border-left: 0.3em solid;
        }
        </style>
    `;
    
    // Aggiungi CSS se non esiste
    if (!document.getElementById('submenu-styles')) {
        document.head.insertAdjacentHTML('beforeend', submenuCSS);
    }
    
    // Gestisci click su submenu
    const submenu = document.querySelector('.dropdown-submenu .submenu');
    if (submenu) {
        submenu.addEventListener('click', function(e) {
            e.stopPropagation(); // Impedisce chiusura del menu principale
        });
    }
}

// 🔧 FUNZIONE: forceInterfaceUpdate (conteggio corretto)
function forceInterfaceUpdate() {
    console.log('🔄 Aggiornamento forzato interfaccia...');
    
    setTimeout(() => {
        updateConfigurationsList();
        
        if (entities && entities.lights) {
            // ✅ CALCOLA ENTITÀ RILEVANTI ATTUALI invece di hardcode 1801
            const currentRelevantTotal = entities.lights.length + entities.binary_sensors.length + entities.sensors.length;
            
            // Per forceInterfaceUpdate, usiamo il totale delle entità attualmente caricate
            // che rappresenta il nostro universo di entità rilevanti
            let mode;
            if (currentCommunicationMode === 'fallback_direct') {
                mode = 'fallback_no_areas';
            } else if (areaFilterEnabled) {
                mode = 'active_with_websocket';
            } else {
                mode = 'disabled_with_websocket';
            }
            
            // ✅ USA IL TOTALE CORRETTO: se i filtri sono attivi, le entità mostrate 
            // sono un subset del totale possibile, quindi usiamo un totale stimato
            let estimatedTotal = currentRelevantTotal;
            if (areaFilterEnabled && currentCommunicationMode !== 'fallback_direct') {
                // Se il filtro area è attivo, stima il totale basandoti sul rapporto
                // Questo è approssimativo ma più accurato di 1801
                estimatedTotal = Math.round(currentRelevantTotal * 1.5); // Stima conservativa
            }
            
            updateFilterStatusDisplay(mode, estimatedTotal, entities);
        }
    }, 100);
}

// 🏠 Estrai tutte le aree uniche dalle entità caricate
async function toggleAreaFilter() {
    areaFilterEnabled = !areaFilterEnabled;
    console.log(`🎯 Filtro Area: ${areaFilterEnabled ? 'ATTIVATO' : 'DISATTIVATO'}`);
    
    // Aggiorna toggle nel submenu
    const areaToggle = document.getElementById('areaFilterToggle');
    if (areaToggle) areaToggle.checked = areaFilterEnabled;
    
    await applyFiltersImmediate();
}

async function toggleEntityFilter() {
    entityFilterEnabled = !entityFilterEnabled;
    console.log(`🏠 Filtro Entità: ${entityFilterEnabled ? 'ATTIVATO' : 'DISATTIVATO'}`);
    
    // Aggiorna toggle nel submenu
    const entityToggle = document.getElementById('entityFilterToggle');
    if (entityToggle) entityToggle.checked = entityFilterEnabled;
    
    await applyFiltersImmediate();
}

// 🔧 FUNZIONI TOGGLE: aggiorna alert con ordine invertito
async function applyFiltersImmediate() {
    SouthTechUI.showAlert('🔄 Aggiornamento filtri in corso...', 'info', 2000);
    
    try {
        await loadEntities();
        updateConfigurationsList();
        forceInterfaceUpdate();
        
        // Ordine invertito: Entità prima, Area dopo (invariato)
        const entityStatus = entityFilterEnabled ? 'Entità ✅' : 'Entità ❌';
        const areaStatus = areaFilterEnabled ? 'Area ✅' : 'Area ❌';
        SouthTechUI.showAlert(`✅ Filtri aggiornati: ${entityStatus} | ${areaStatus}`, 'success');
        
    } catch (error) {
        console.error('Errore applicazione filtri:', error);
        SouthTechUI.showAlert(`Errore applicazione filtri: ${error.message}`, 'error');
    }
}

// 🔧 FUNZIONE: initializeFiltersSubmenu (COMPLETA CON POSIZIONE CORRETTA)
function initializeFiltersSubmenu() {
    // Trova il menu dropdown e aggiungi il submenu
    const menuDropdown = document.querySelector('.dropdown-menu');
    if (!menuDropdown) {
        console.warn('⚠️ Menu dropdown non trovato');
        return;
    }
    
    // Trova la voce filtri esistente e sostituiscila
    const existingFilterItem = document.getElementById('filterMenuToggle');
    if (existingFilterItem) {
        existingFilterItem.parentElement.remove();
    }
    
    // ✅ SUBMENU CON STYLING MIGLIORATO - Toggle più grandi e allineamento perfetto
    const submenuHTML = `
        <li class="dropdown-submenu">
            <a class="dropdown-item dropdown-toggle" href="#" id="filtersSubmenuToggle">
                <i class="fas fa-filter"></i> Filtri
            </a>
            <ul class="dropdown-menu submenu">
                <!-- ✅ TOGGLE ENTITÀ - MARGINI BILANCIATI FINALI -->
                <li style="padding: 0 !important; margin: 0 !important;">
                    <div class="form-check form-switch" style="display: flex; align-items: center; gap: 8px; margin: 0; padding: 10px 18px;">
                        <input class="form-check-input" type="checkbox" id="entityFilterToggle" 
                              ${entityFilterEnabled ? 'checked' : ''} onchange="toggleEntityFilter()" 
                              style="margin: 0; width: 40px; height: 20px; transform: scale(1.2); flex-shrink: 0;">
                        <i class="fas fa-microchip" style="width: 16px; text-align: center; color: #495057; flex-shrink: 0;"></i>
                        <label class="form-check-label" for="entityFilterToggle" 
                              style="margin: 0; cursor: pointer; font-size: 15px; font-weight: 500; white-space: nowrap;">
                            Filtra per Entità
                        </label>
                    </div>
                </li>
                
                <!-- ✅ TOGGLE AREA - MARGINI BILANCIATI FINALI -->
                <li style="padding: 0 !important; margin: 0 !important;">
                    <div class="form-check form-switch" style="display: flex; align-items: center; gap: 8px; margin: 0; padding: 10px 18px;">
                        <input class="form-check-input" type="checkbox" id="areaFilterToggle" 
                              ${areaFilterEnabled ? 'checked' : ''} onchange="toggleAreaFilter()"
                              style="margin: 0; width: 40px; height: 20px; transform: scale(1.2); flex-shrink: 0;">
                        <i class="fas fa-home" style="width: 16px; text-align: center; color: #495057; flex-shrink: 0;"></i>
                        <label class="form-check-label" for="areaFilterToggle" 
                              style="margin: 0; cursor: pointer; font-size: 15px; font-weight: 500; white-space: nowrap;">
                            Filtra per Area
                        </label>
                    </div>
                </li>
            </ul>
        </li>
    `;
    
    // 🎯 POSIZIONAMENTO CORRETTO: Subito dopo Menu Principale con divider sopra
    let menuPrincipaleItem = menuDropdown.querySelector('a[onclick="SouthTechCore.goToMainMenu()"]') ||
                            menuDropdown.querySelector('a[onclick="goToMainMenu()"]');
    
    if (menuPrincipaleItem) {
        console.log('✅ Trovato Menu Principale, inserisco Filtri con divider sopra...');
        
        const menuPrincipaleParent = menuPrincipaleItem.parentElement;
        const nextElement = menuPrincipaleParent.nextElementSibling;
        
        // Controlla se c'è già un divider dopo Menu Principale
        if (nextElement && nextElement.classList.contains('dropdown-divider')) {
            // C'è già un divider, inserisci i Filtri dopo
            nextElement.insertAdjacentHTML('afterend', submenuHTML);
            console.log('✅ Filtri inseriti dopo divider esistente');
        } else {
            // Non c'è divider, crealo e poi aggiungi i Filtri
            const dividerAndFilters = '<li><hr class="dropdown-divider"></li>' + submenuHTML;
            menuPrincipaleParent.insertAdjacentHTML('afterend', dividerAndFilters);
            console.log('✅ Creato divider e inseriti Filtri dopo Menu Principale');
        }
        
        // 🗑️ RIMUOVI TUTTI i divider dopo Filtri fino a Ricarica Configurazioni
        setTimeout(() => {
            const filtersSubmenu = document.querySelector('.dropdown-submenu');
            if (filtersSubmenu) {
                let currentElement = filtersSubmenu.nextElementSibling;
                
                // Rimuovi tutti i divider consecutivi dopo i Filtri
                while (currentElement) {
                    if (currentElement.classList.contains('dropdown-divider')) {
                        const elementToRemove = currentElement;
                        currentElement = currentElement.nextElementSibling;
                        elementToRemove.remove();
                        console.log('🗑️ Rimosso divider dopo Filtri');
                    } else {
                        // Se trovi un elemento che non è divider, fermati
                        break;
                    }
                }
                
                // Controlla anche se "Ricarica Configurazioni" ha un divider prima
                const ricaricaItem = menuDropdown.querySelector('a[onclick*="syncConfigurations"]');
                if (ricaricaItem) {
                    const ricaricaParent = ricaricaItem.parentElement;
                    const prevElement = ricaricaParent.previousElementSibling;
                    if (prevElement && prevElement.classList.contains('dropdown-divider')) {
                        prevElement.remove();
                        console.log('🗑️ Rimosso divider prima di Ricarica Configurazioni');
                    }
                }
            }
        }, 100);
        
    } else {
        // Fallback: inserisci all'inizio con divider
        console.warn('⚠️ Menu Principale non trovato, inserisco all\'inizio');
        const dividerAndFilters = '<li><hr class="dropdown-divider"></li>' + submenuHTML;
        menuDropdown.insertAdjacentHTML('afterbegin', dividerAndFilters);
    }
}

// 🎯 AGGIORNA ICONA MENU FILTRO
function updateFilterMenuIcon() {
    const menuItem = document.getElementById('filterMenuToggle');
    if (menuItem) {
        const icon = areaFilterEnabled ? 'fa-filter' : 'fa-filter-slash';
        const text = areaFilterEnabled ? 'Disattiva Filtro Area' : 'Attiva Filtro Area';
        menuItem.innerHTML = `<i class="fas ${icon}"></i> ${text}`;
    }
}

// 📊 MOSTRA STATO FILTRO (VERSIONE SICURA)
function showFilterStatus() {
    const systemFilterStatusDiv = document.getElementById('systemFilterStatus');
    if (systemFilterStatusDiv) {
        systemFilterStatusDiv.style.display = 'block';
        console.log('✅ Pannello sistema e filtro attivato');
    } else {
        console.warn('⚠️ Elemento systemFilterStatus non trovato');
    }
}

// 📊 AGGIORNA DISPLAY STATO FILTRO (LAYOUT A 3 COLONNE)
function updateFilterStatusDisplay(mode, totalEntities, filteredEntities) {
    const systemFilterStatusDiv = document.getElementById('systemFilterStatus');
    
    if (!systemFilterStatusDiv) {
        console.warn('⚠️ Elemento systemFilterStatus non trovato, skip aggiornamento');
        return;
    }
    
    console.log(`📊 Aggiornamento display filtri - Modalità: ${mode}`);
    console.log(`🎯 Area: ${areaFilterEnabled}, Entità: ${entityFilterEnabled}`);
    
    const totalFiltered = filteredEntities.lights.length + filteredEntities.binary_sensors.length + filteredEntities.sensors.length;
    
    // ✅ USA IL CONTEGGIO TOTALE DELLE AREE (non solo quelle caricate)
    const totalAreasCount = getTotalAreasWithEntities();
    
    systemFilterStatusDiv.style.display = 'block';
    
    // Contenuto filtri
    let filterAreaContent = '';
    let cssClass = '';
    
    if (mode === 'fallback_no_areas') {
        cssClass = 'filter-status disabled';
        filterAreaContent = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Modalità Fallback</strong>
            <span class="badge bg-warning ms-2">No Areas</span>
        `;
    } else {
        if (areaFilterEnabled || entityFilterEnabled) {
            cssClass = 'filter-status';
        } else {
            cssClass = 'filter-status disabled';
        }
        
        let filterText = 'Filtri: ';
        if (entityFilterEnabled && areaFilterEnabled) {
            filterText += 'Entità ✅ | Area ✅';
        } else if (entityFilterEnabled && !areaFilterEnabled) {
            filterText += 'Entità ✅ | Area ❌';
        } else if (!entityFilterEnabled && areaFilterEnabled) {
            filterText += 'Entità ❌ | Area ✅';
        } else {
            filterText = 'Filtri: DISATTIVATI';
        }
        
        filterAreaContent = `
            <i class="fas fa-filter me-2"></i>
            <strong>${filterText}</strong>
            <span class="badge bg-success ms-2">WebSocket</span>
        `;
    }
    
    systemFilterStatusDiv.className = cssClass;
    
    let areasText = (mode === 'fallback_no_areas') ? 'N/A' : totalAreasCount.toString();
    
    // Layout aggiornato
    systemFilterStatusDiv.innerHTML = `
        <div style="display: flex; align-items: stretch; min-height: 60px;">
            <div style="width: 25%; display: flex; align-items: center; justify-content: center; border-right: 1px solid rgba(0,0,0,0.1);">
                <div style="text-align: center;">
                    <div>
                        <i class="fas fa-check-circle text-success me-2"></i>
                        <strong>Sistema Connesso</strong>
                        <span class="badge bg-primary ms-2">API</span>
                    </div>
                </div>
            </div>
            
            <div style="width: 50%; display: flex; flex-direction: column; justify-content: space-between; padding: 8px 15px;">
                <div style="display: flex; align-items: center; justify-content: center;">
                    ${filterAreaContent}
                </div>
                
                <div style="text-align: center; font-size: 14px; color: #333;">
                    <strong>Luci:</strong> ${filteredEntities.lights.length} • <strong>Sensori presenza:</strong> ${filteredEntities.binary_sensors.length} • <strong>Sensori luminosità:</strong> ${filteredEntities.sensors.length}
                </div>
            </div>
            
            <div style="width: 25%; display: flex; flex-direction: column; justify-content: space-between; padding: 8px 0; border-left: 1px solid rgba(0,0,0,0.1);">
                <div style="display: flex; align-items: center; height: 50%;">
                    <div style="width: 100%; padding-left: 15px; display: flex; align-items: center;">
                        <i class="fas fa-microchip me-2" style="width: 16px;"></i>
                        <span style="font-weight: bold; width: 55px;">Entità:</span>
                        <span style="font-weight: bold; color: #2c3e50; text-align: right; width: 30px;">${totalFiltered}</span>
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; height: 50%;">
                    <div style="width: 100%; padding-left: 15px; display: flex; align-items: center;">
                        <i class="fas fa-home me-2" style="width: 16px;"></i>
                        <span style="font-weight: bold; width: 55px;">Aree:</span>
                        <span style="font-weight: bold; color: #2c3e50; text-align: right; width: 30px;">${areasText}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; font-size: 12px; color: #333; margin-top: 5px; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 5px;">
            ${getFilterStatusMessage(mode, totalEntities, totalFiltered, extractUniqueAreas().length)}
        </div>
    `;
    
    console.log(`✅ Display aggiornato: Area ${areaFilterEnabled ? 'ON' : 'OFF'}, Entità ${entityFilterEnabled ? 'ON' : 'OFF'}`);
}

// 📋 AGGIORNA LISTA CONFIGURAZIONI - AGGIORNATA CON DISPLAY_NAME
function updateConfigurationsList() {
    const container = document.getElementById('configsList');
    container.innerHTML = '';
    
    if (configurations.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info text-center">
                <i class="fas fa-info-circle me-2"></i>
                Nessuna configurazione presente. Clicca il pulsante + per aggiungerne una.
            </div>
        `;
        return;
    }
    
    configurations.forEach((config, index) => {
        const configElement = createConfigurationElement(config, index);
        container.appendChild(configElement);
    });
}

// 🔨 CREA ELEMENTO CONFIGURAZIONE - AGGIORNATO CON CAMPO AREA
function createConfigurationElement(config, index) {
    const div = document.createElement('div');
    div.className = 'config-section fade-in';
    
    // Rileva area automatica della configurazione
    const detectedArea = detectConfigurationArea(config);
    // FIX: Rispetta la selezione esplicita dell'utente (anche se vuota), altrimenti usa l'area rilevata.
    const selectedArea = (config.selected_area !== undefined && config.selected_area !== null) 
                         ? config.selected_area 
                         : (detectedArea || '');
    
    // Ottieni lista aree disponibili
    const availableAreas = extractUniqueAreas();
    
    // Filtra entità per area selezionata + mantieni entità già configurate
    const filteredLights = filterEntitiesWithExisting(entities.lights, selectedArea, index);
    const filteredBinarySensors = filterEntitiesWithExisting(entities.binary_sensors, selectedArea, index);
    const filteredSensors = filterEntitiesWithExisting(entities.sensors, selectedArea, index);
    
    div.innerHTML = `
        <div class="config-header">
            <h5 class="mb-0">
                <i class="fas fa-lightbulb me-2"></i>
                Configurazione ${index + 1}
            </h5>
            <button class="remove-button" onclick="removeConfiguration(${index})" title="Rimuovi configurazione">
                <i class="fas fa-trash"></i>
            </button>
        </div>
        
        <!-- 🏠 CAMPO AREA NUOVO -->
        <div class="row mb-3">
            <div class="col-12">
                <label class="form-label">
                    <i class="fas fa-home me-1"></i> Area
                </label>
                <select class="form-select" id="areaSelect_${index}" onchange="handleAreaChange(${index}, this.value)">
                    <option value="">Seleziona area</option>
                    ${availableAreas.map(area => 
                        `<option value="${area}" ${selectedArea === area ? 'selected' : ''}>
                            ${area}
                        </option>`
                    ).join('')}
                </select>
                ${selectedArea && !detectedArea ? '<small class="text-info">Area selezionata manualmente</small>' : ''}
                ${detectedArea ? '<small class="text-success">Area rilevata automaticamente</small>' : ''}
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6 mb-3">
                <label class="form-label">
                    <i class="fas fa-lightbulb me-1"></i> Luce da controllare
                </label>
                <select class="form-select" onchange="updateConfiguration(${index}, 'light_entity', this.value)">
                    <option value="">Seleziona una luce...</option>
                    ${filteredLights.map(light => 
                        `<option value="${light.entity_id}" ${config.light_entity === light.entity_id ? 'selected' : ''}>
                            ${light.display_name}
                        </option>`
                    ).join('')}
                </select>
                ${selectedArea && filteredLights.length === 0 ? '<small class="text-danger">Nessuna luce disponibile per questa area</small>' : ''}
            </div>
            
            <div class="col-md-6 mb-3">
                <label class="form-label">
                    <i class="fas fa-walking me-1"></i> Sensore accensione
                </label>
                <select class="form-select" onchange="updateConfiguration(${index}, 'presence_sensor_on', this.value)">
                    <option value="">Seleziona sensore presenza...</option>
                    ${filteredBinarySensors.map(sensor => 
                        `<option value="${sensor.entity_id}" ${config.presence_sensor_on === sensor.entity_id ? 'selected' : ''}>
                            ${sensor.display_name}
                        </option>`
                    ).join('')}
                </select>
                ${selectedArea && filteredBinarySensors.length === 0 ? '<small class="text-danger">Nessun sensore presenza disponibile per questa area</small>' : ''}
            </div>
            
            <div class="col-md-6 mb-3">
                <label class="form-label">
                    <i class="fas fa-power-off me-1"></i> Sensore spegnimento (opzionale)
                </label>
                <select class="form-select" onchange="updateConfiguration(${index}, 'presence_sensor_off', this.value)">
                    <option value="">Seleziona sensore spegnimento...</option>
                    ${filteredBinarySensors.map(sensor => 
                        `<option value="${sensor.entity_id}" ${config.presence_sensor_off === sensor.entity_id ? 'selected' : ''}>
                            ${sensor.display_name}
                        </option>`
                    ).join('')}
                </select>
                ${selectedArea && filteredBinarySensors.length === 0 ? '<small class="text-warning">Nessun sensore spegnimento disponibile per questa area</small>' : ''}
            </div>
            
            <div class="col-md-6 mb-3">
                <label class="form-label">
                    <i class="fas fa-sun me-1"></i> Sensore luminosità (opzionale)
                </label>
                <select class="form-select" onchange="updateConfiguration(${index}, 'illuminance_sensor', this.value)">
                    <option value="">Nessun sensore luminosità</option>
                    ${filteredSensors.map(sensor => 
                        `<option value="${sensor.entity_id}" ${config.illuminance_sensor === sensor.entity_id ? 'selected' : ''}>
                            ${sensor.display_name}
                        </option>`
                    ).join('')}
                </select>
                ${selectedArea && filteredSensors.length === 0 ? '<small class="text-warning">Nessun sensore luminosità disponibile per questa area</small>' : ''}
            </div>
        </div>
        
        <div class="mt-3 p-3 bg-light rounded">
            <h6><i class="fas fa-info-circle me-2"></i>Riepilogo Configurazione:</h6>
            <div class="small text-muted">
                ${selectedArea ? `<i class="fas fa-home me-1"></i> Area: ${selectedArea}` : '<i class="fas fa-home me-1"></i> Area: Non specificata'}<br>
                ${config.light_entity ? `✅ Luce: ${entities.lights.find(l => l.entity_id === config.light_entity)?.display_name || config.light_entity}` : '❌ Luce non selezionata'}<br>
                ${config.presence_sensor_on ? `✅ Accensione: ${entities.binary_sensors.find(s => s.entity_id === config.presence_sensor_on)?.display_name || config.presence_sensor_on}` : '❌ Sensore accensione non selezionato'}<br>
                ${config.presence_sensor_off ? `✅ Spegnimento: ${entities.binary_sensors.find(s => s.entity_id === config.presence_sensor_off)?.display_name || config.presence_sensor_off}` : '❌ Sensore spegnimento non selezionato'}<br>
                ${config.illuminance_sensor ? `✅ Luminosità: ${entities.sensors.find(s => s.entity_id === config.illuminance_sensor)?.display_name || config.illuminance_sensor}` : 'ℹ️ Nessun controllo luminosità'}
            </div>
        </div>
    `;
    
    return div;
}

// ➕ AGGIUNGI CONFIGURAZIONE - AGGIORNATO PER SUPPORTARE AREE
function addConfiguration() {
    configurations.push({
        light_entity: '',
        presence_sensor_on: '',
        presence_sensor_off: '',
        illuminance_sensor: '',
        selected_area: '' // Nuovo campo per area selezionata manualmente
    });
    
    updateConfigurationsList();
    SouthTechUI.showAlert('Nuova configurazione aggiunta', 'success');
    
    // Scroll verso la nuova configurazione
    setTimeout(() => {
        const newConfig = document.querySelector('.config-section:last-child');
        if (newConfig) {
            newConfig.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 100);
}

// ❌ RIMUOVI CONFIGURAZIONE
function removeConfiguration(index) {
    SouthTechUI.showConfirmDialog(
        'Rimuovi Configurazione',
        `Sei sicuro di voler rimuovere la configurazione ${index + 1}? Questa azione non può essere annullata.`,
        {
            confirmText: 'Rimuovi',
            cancelText: 'Annulla',
            confirmClass: 'btn-danger',
            cancelClass: 'btn-secondary',
            onConfirm: () => {
                configurations.splice(index, 1);
                updateConfigurationsList();
                SouthTechUI.showAlert('Configurazione rimossa', 'info');
            },
            onCancel: () => {
                // Nessuna azione necessaria
            }
        }
    );
}

// 🔄 AGGIORNA CONFIGURAZIONE - AGGIORNATO PER GESTIRE CAMBIO AREA
function updateConfiguration(index, field, value) {
    if (configurations[index]) {
        configurations[index][field] = value;
        console.log(`Aggiornata configurazione ${index}:`, field, '=', value);
        
        // Se ho cambiato un'entità, aggiorna l'area automatica
        if (['light_entity', 'presence_sensor_on', 'presence_sensor_off', 'illuminance_sensor'].includes(field)) {
            const config = configurations[index];
            const detectedArea = detectConfigurationArea(config);
            
            // Se c'è un'area rilevata automaticamente e non c'è area selezionata manualmente
            if (detectedArea && !config.selected_area) {
                const areaSelect = document.querySelector(`#areaSelect_${index}`);
                if (areaSelect) {
                    areaSelect.value = detectedArea;
                }
            }
            
            // Se l'area selezionata manualmente non è compatibile, resettala
            if (config.selected_area) {
                const entityArea = getEntityArea(value);
                if (entityArea && entityArea !== config.selected_area) {
                    // L'entità appartiene a un'area diversa da quella selezionata
                    console.log(`⚠️ Entità ${value} (${entityArea}) non compatibile con area selezionata ${config.selected_area}`);
                }
            }
        }
        
        // Aggiorna interfaccia
        setTimeout(() => {
            updateConfigurationsList();
            updateGenerateButtonState();
        }, 100);
    }
}

// 🎯 AGGIORNA STATO PULSANTE GENERA YAML
function updateGenerateButtonState() {
    const generateButton = document.querySelector('button[onclick="generateYAMLAndDashboard()"]');
    if (!generateButton) {
        // Se il pulsante non è visibile (es. dopo aver generato l'anteprima), non fare nulla.
        return;
    }

    const hasErrors = !validateConfigurationSilent();
    
    if (hasErrors) {
        generateButton.disabled = true;
        generateButton.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Correggi errori per generare';
        generateButton.classList.remove('btn-success');
        generateButton.classList.add('btn-warning');
    } else {
        generateButton.disabled = false;
        generateButton.innerHTML = '<i class="fas fa-magic"></i> Genera Apps.yaml + Dashboard + Templates';
        generateButton.classList.remove('btn-warning');
        generateButton.classList.add('btn-success');
    }
}

// 🔍 VALIDAZIONE SILENZIOSA
function validateConfigurationSilent() {
    let errors = [];
    
    configurations.forEach((config, index) => {
        if (!config.light_entity) errors.push(`Config ${index + 1}: No light`);
        if (!config.presence_sensor_on) errors.push(`Config ${index + 1}: No sensor`);
    });
    
    return errors.length === 0;
}

// ✅ VALIDAZIONE CONFIGURAZIONE
/**
* 🎯 FUNZIONE DI VALIDAZIONE MODIFICATA
* @param {boolean} showWarnings - Se true, mostra anche gli avvisi per i campi opzionali.
* @returns {boolean} - True se non ci sono errori critici.
*/
function validateConfiguration(showWarnings = true) {
    let errors = [];
    let warnings = [];

    configurations.forEach((config, index) => {
        const num = index + 1;
        
        // Errori obbligatori
        if (!config.light_entity) {
            errors.push(`Configurazione ${num}: Luce non selezionata`);
        }
        if (!config.presence_sensor_on) {
            errors.push(`Configurazione ${num}: Sensore accensione non selezionato`);
        }
        
        // Avvisi opzionali (solo se showWarnings è true)
        if (showWarnings) {
            if (!config.presence_sensor_off) {
                warnings.push(`Configurazione ${num}: Nessun sensore spegnimento configurato`);
            }
            if (!config.illuminance_sensor) {
                warnings.push(`Configurazione ${num}: Nessun controllo luminosità configurato`);
            }
        }
        
        // Controllo duplicati
        if (config.light_entity) {
            const duplicates = configurations.filter((c, i) => 
                i !== index && c.light_entity === config.light_entity
            );
            if (duplicates.length > 0) {
                errors.push(`Configurazione ${num}: Luce già configurata in un'altra regola`);
            }
        }
    });
    
    // Mostra risultati solo se ci sono errori o (se richiesti) avvisi
    if (errors.length > 0 || (showWarnings && warnings.length > 0)) {
        let message = '';
        if (errors.length > 0) {
            message += `❌ ERRORI:\n${errors.join('\n')}\n\n`;
        }
        if (showWarnings && warnings.length > 0) {
            message += `⚠️ AVVISI:\n${warnings.join('\n')}\n\n`;
        }
        const alertType = errors.length > 0 ? 'error' : 'warning';
        SouthTechUI.showAlert(message, alertType);
    }
    
    return errors.length === 0;
}

/**
* 🏗️ Crea HTML del modal dei risultati
*/
function createResultsModalHTML(result, configCount, totalSensors, configYamlSuccess) {
    const dashboardUrl = configYamlSuccess ? '/lovelace/light-presence' : '#';
    const headerClass = configYamlSuccess ? 'bg-success' : 'bg-warning';
    const headerIcon = configYamlSuccess ? 'fas fa-check-circle' : 'fas fa-exclamation-triangle';
    const headerTitle = configYamlSuccess ? 'Configurazione Completa Salvata' : 'Configurazione Parzialmente Salvata';
    
    return `
        <div class="modal-dialog modal-xl">
            <div class="modal-content" style="border-radius: 20px;">
                <div class="modal-header ${headerClass} text-white" style="border-radius: 20px 20px 0 0;">
                    <h5 class="modal-title">
                        <i class="${headerIcon} me-2"></i>${headerTitle}
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="padding: 30px;">
                    ${createStatusSummaryHTML(result, configYamlSuccess)}
                    ${createFilesStatusHTML(result, configCount, totalSensors)}
                    ${createInstructionsHTML(configYamlSuccess)}
                    ${createTechnicalDetailsHTML(result)}
                </div>
                <div class="modal-footer">
                    ${configYamlSuccess ? 
                        `<button type="button" class="btn btn-primary" onclick="window.open('${dashboardUrl}', '_blank')">
                            <i class="fas fa-external-link-alt me-2"></i>Apri Dashboard
                        </button>` : 
                        `<button type="button" class="btn btn-warning" onclick="showConfigYamlManualInstructions()">
                            <i class="fas fa-wrench me-2"></i>Istruzioni Manuali
                        </button>`
                    }
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times me-2"></i>Chiudi
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
* 📊 Crea riepilogo stato
*/
function createStatusSummaryHTML(result, configYamlSuccess) {
    const alertClass = configYamlSuccess ? 'alert-success' : 'alert-warning';
    const icon = configYamlSuccess ? 'fas fa-magic fa-3x mb-3' : 'fas fa-exclamation-triangle fa-3x mb-3';
    const title = configYamlSuccess ? 'Operazione Completata con Successo!' : 'Operazione Parzialmente Completata';
    const subtitle = configYamlSuccess ? 
        'Tutti i file sono stati generati e salvati correttamente.' :
        'File generati con successo, ma configuration.yaml richiede intervento manuale.';
    
    return `
        <div class="alert ${alertClass} text-center">
            <i class="${icon}"></i>
            <h4>${title}</h4>
            <p>${subtitle}</p>
        </div>
    `;
}

/**
* 📁 Crea stato dei file
*/
function createFilesStatusHTML(result, configCount, totalSensors) {
    const templatesSuccess = result.details?.templates?.success || false;
    const dashboardSuccess = result.details?.dashboard?.success || false;
    const configSuccess = result.details?.configuration?.success || false;
    
    return `
        <div class="row">
            <div class="col-md-4 text-center mb-3">
                <div class="card border-${templatesSuccess ? 'success' : 'danger'}">
                    <div class="card-body">
                        <i class="fas fa-puzzle-piece fa-2x ${templatesSuccess ? 'text-success' : 'text-danger'} mb-2"></i>
                        <h6>Templates.yaml</h6>
                        <span class="badge bg-${templatesSuccess ? 'success' : 'danger'}">${templatesSuccess ? `${totalSensors} sensori` : 'Errore'}</span>
                        ${!templatesSuccess ? `<div class="small text-danger mt-1">${result.details?.templates?.error || 'Errore sconosciuto'}</div>` : ''}
                    </div>
                </div>
            </div>
            <div class="col-md-4 text-center mb-3">
                <div class="card border-${dashboardSuccess ? 'info' : 'danger'}">
                    <div class="card-body">
                        <i class="fas fa-tachometer-alt fa-2x ${dashboardSuccess ? 'text-info' : 'text-danger'} mb-2"></i>
                        <h6>Dashboard</h6>
                        <span class="badge bg-${dashboardSuccess ? 'info' : 'danger'}">${dashboardSuccess ? `${configCount} pannelli` : 'Errore'}</span>
                        ${!dashboardSuccess ? `<div class="small text-danger mt-1">${result.details?.dashboard?.error || 'Errore sconosciuto'}</div>` : ''}
                    </div>
                </div>
            </div>
            <div class="col-md-4 text-center mb-3">
                <div class="card border-${configSuccess ? 'primary' : 'warning'}">
                    <div class="card-body">
                        <i class="fas fa-cog fa-2x ${configSuccess ? 'text-primary' : 'text-warning'} mb-2"></i>
                        <h6>Configuration.yaml</h6>
                        <span class="badge bg-${configSuccess ? 'primary' : 'warning'}">${configSuccess ? 'Aggiornato' : 'Manuale'}</span>
                        ${!configSuccess ? `<div class="small text-warning mt-1">${result.details?.configuration?.error || 'Richiede intervento manuale'}</div>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
* 📋 Crea istruzioni
*/
function createInstructionsHTML(configYamlSuccess) {
    if (configYamlSuccess) {
        return `
            <div class="alert alert-info">
                <h6><i class="fas fa-lightbulb me-2"></i>Prossimi Passi:</h6>
                <ol class="mb-0">
                    <li><strong>Riavvia AppDaemon</strong> per caricare la nuova configurazione apps.yaml</li>
                    <li><strong>Riavvia Home Assistant</strong> per attivare template sensors e dashboard</li>
                    <li><strong>Accedi alla dashboard</strong> dal menu Lovelace → "Configurazione Luci Automatiche"</li>
                    <li><strong>Configura i parametri</strong> di ogni luce tramite i pannelli dedicati</li>
                </ol>
            </div>
        `;
    } else {
        return `
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle me-2"></i>Azione Richiesta per Configuration.yaml:</h6>
                <p class="mb-2">Il file configuration.yaml non è stato aggiornato automaticamente. Per accedere alla dashboard:</p>
                <ol class="mb-0">
                    <li><strong>Aggiungi manualmente</strong> la configurazione dashboard (vedi istruzioni)</li>
                    <li><strong>Riavvia Home Assistant</strong> dopo aver modificato configuration.yaml</li>
                    <li><strong>Riavvia AppDaemon</strong> per la configurazione apps.yaml</li>
                </ol>
            </div>
        `;
    }
}

/**
* 🔧 Crea dettagli tecnici
*/
function createTechnicalDetailsHTML(result) {
    if (!result.details) return '';
    
    return `
        <div class="mt-3">
            <h6>Dettagli Tecnici:</h6>
            <div class="small">
                <strong>Backup creati:</strong> ${result.backup_created ? 'Sì' : 'No'}<br>
                <strong>Metodo:</strong> ${result.method || 'sensor_optimized'}<br>
                <strong>Operazioni riuscite:</strong> ${result.summary?.successful_operations || 'N/A'}/${result.summary?.total_operations || 'N/A'}<br>
                <strong>Timestamp:</strong> ${result.timestamp ? new Date(result.timestamp).toLocaleString() : 'N/A'}
            </div>
        </div>
    `;
}

/**
* 🎨 Crea modal universale
*/
function createUniversalModalHTML(result, states) {
    const { templatesSuccess, dashboardSuccess, configSuccess, 
            templatesError, dashboardError, configError,
            configCount, totalSensors } = states;

    const isCompleteSave = states.method === 'sensor_complete' || states.method === 'complete_sensor';
    const isSpecificSave = !!states.fileType && !isCompleteSave;

    let overallSuccess;
    if (isSpecificSave) {
        // Per un salvataggio specifico, il successo generale è semplicemente il successo di quella operazione.
        overallSuccess = result.success;
    } else {
        // Per un salvataggio completo, consideriamolo un successo se almeno 3 componenti su 4 sono andati a buon fine.
        const successCount = [states.appsSuccess, states.templatesSuccess, states.configSuccess, states.dashboardSuccess].filter(Boolean).length;
        overallSuccess = successCount >= 3;
    }

    const headerClass = overallSuccess ? 'bg-success' : 'bg-warning';
    const headerIcon = overallSuccess ? 'fas fa-check-circle' : 'fas fa-exclamation-triangle';
    const headerTitle = overallSuccess ? 'Operazione Completata' : 'Attenzione Richiesta';
    
    return `
        <div class="modal-dialog modal-xl">
            <div class="modal-content" style="border-radius: 20px;">
                <div class="modal-header ${headerClass} text-white" style="border-radius: 20px 20px 0 0;">
                    <h5 class="modal-title">
                        <i class="${headerIcon} me-2"></i>${headerTitle}
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="padding: 30px;">
                    
                    ${createUniversalStatusSummary(result, states)}
                    ${createUniversalFilesStatus(states)}
                    ${createUniversalInstructions(configSuccess)}
                    ${createUniversalTechnicalDetails(result)}
                    
                </div>
                <div class="modal-footer">
                    ${(() => {
                        // Caso 1: Fallimento specifico di configuration.yaml
                        if (configSuccess === false) {
                            return `<button type="button" class="btn btn-warning" onclick="showConfigYamlManualInstructions()" style="height: 48px;">
                                        <i class="fas fa-wrench me-2"></i>Istruzioni Manuali
                                    </button>`;
                        }
                        // Caso 2: Successo generale (completo o specifico)
                        if (overallSuccess) {
                             return `<button type="button" class="btn btn-primary" onclick="window.open('/lovelace/light-presence', '_blank')" style="height: 48px;">
                                        <i class="fas fa-external-link-alt me-2"></i>Apri Dashboard
                                    </button>`;
                        }
                        // Altrimenti, non mostrare nulla
                        return '';
                    })()}
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" style="height: 48px;">
                        <i class="fas fa-times me-2"></i>Chiudi
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
* 📊 Status componenti universale - 4 COMPONENTI
*/
function createUniversalFilesStatus(states) {
    const { fileType, configCount, totalSensors, method } = states;
    const isCompleteSave = method === 'sensor_complete' || method === 'complete_sensor';
    // Un salvataggio è specifico SOLO se ha un file_type E NON è un salvataggio completo.
    const isSpecificSave = !!fileType && !isCompleteSave;

    const components = [
        { name: 'apps', title: 'Apps.yaml', icon: 'fas fa-cog text-primary', countText: `${configCount} config` },
        { name: 'templates', title: 'Templates.yaml', icon: 'fas fa-puzzle-piece text-success', countText: `${totalSensors} sensori` },
        { name: 'configuration', title: 'Configuration.yaml', icon: 'fas fa-file-code text-warning', countText: '1 voce' },
        { name: 'dashboard', title: 'Dashboard', icon: 'fas fa-tachometer-alt text-info', countText: `${configCount} pannelli` }
    ];

    const createCard = (comp) => {
        const successKey = `${comp.name}Success`;
        const errorKey = `${comp.name}Error`;

        // FIX: Handle inconsistency between 'configuration' and 'configuration_yaml'
        const isThisComponent = (fileType === comp.name) || (comp.name === 'configuration' && fileType === 'configuration_yaml');

        // Se è un salvataggio specifico, solo il componente corrispondente ha uno stato. Gli altri sono null.
        // Altrimenti (salvataggio completo), tutti i componenti hanno il loro stato.
        // ✅ NUOVO: Logica migliorata per determinare il successo
        let success = null; // Inizializza come null per default
        
        if (isSpecificSave) {
            if (isThisComponent) {
                // Se è il componente che stiamo salvando specificamente
                success = states.success === true || states[successKey] === true;
                // Controlla anche i dettagli specifici
                if (states.details && states.details[comp.name] && states.details[comp.name].success) {
                    success = true;
                }
            } else {
                // Se NON è il componente che stiamo salvando specificamente
                success = null; // Imposta come "Non salvato"
            }
        } else {
            // Per salvataggio completo
            success = states[successKey] === true;
        }

        // Gestione speciale per configuration.yaml (sia per salvataggio specifico che completo)
        if (comp.name === 'configuration') {
            if (states.configSuccess === true || states.configurationSuccess === true || 
                (states.details && states.details.configuration && states.details.configuration.success) ||
                (states.previews && states.previews.configuration)) {
                success = true;
            }
        }

        const errorText = isSpecificSave ? (isThisComponent ? states[errorKey] : '') : states[errorKey];
        let cardClass, badgeClass, badgeText, errorHtml;

        if (success === true) {
            cardClass = 'border-success';
            badgeClass = 'bg-success';
            badgeText = comp.countText;
            errorHtml = '';
        } else if (success === false) {
            cardClass = 'border-danger';
            badgeClass = 'bg-danger';
            badgeText = 'Errore';
            errorHtml = `<div class="small text-danger mt-2" style="max-height: 60px; overflow-y: auto;">${(errorText || '').substring(0, 100)}</div>`;
        } else { // success is null (Not Applicable)
            cardClass = 'border-secondary opacity-50';
            badgeClass = 'bg-secondary';
            badgeText = 'Non salvato';
            errorHtml = '';
        }

        return `
            <div class="col-md-3 text-center mb-3">
                <div class="card ${cardClass}">
                    <div class="card-body">
                        <i class="${comp.icon} fa-2x mb-2"></i>
                        <h6>${comp.title}</h6>
                        <span class="badge ${badgeClass}">${badgeText}</span>
                        ${errorHtml}
                    </div>
                </div>
            </div>
        `;
    };

    return `<div class="row">${components.map(createCard).join('')}</div>`;
}

function createUniversalStatusSummary(result, states) {
    const isCompleteSave = result.method === 'sensor_complete' || result.method === 'complete_sensor';
    const isSpecificSave = !!result.file_type;

    if (isSpecificSave && !isCompleteSave) {
        // Single file save view
        const success = result.success;
        const fileType = result.file_type;
        const alertClass = success ? 'alert-success' : 'alert-danger';
        const icon = success ? 'fas fa-check-circle' : 'fas fa-times-circle';
        const friendlyName = fileType.charAt(0).toUpperCase() + fileType.slice(1);
        const title = success ? `Salvataggio ${friendlyName}.yaml Riuscito` : `Salvataggio ${friendlyName}.yaml Fallito`;
        const message = success ? `Il file è stato aggiornato correttamente sul server.` : `Si è verificato un errore: ${result.error || 'Dettaglio non disponibile'}`;

        return `
            <div class="alert ${alertClass} text-center">
                <i class="${icon} fa-3x mb-3"></i>
                <h4>${title}</h4>
                <p>${message}</p>
            </div>
        `;
    }

    // Complete save view (or fallback if logic is ambiguous)
    const { appsSuccess, templatesSuccess, configSuccess, dashboardSuccess } = states;
    const successCount = [states.appsSuccess, states.templatesSuccess, states.configSuccess, states.dashboardSuccess].filter(Boolean).length;
    const alertClass = successCount >= 3 ? 'alert-success' : (successCount >= 2 ? 'alert-warning' : 'alert-danger');
    const icon = successCount >= 3 ? 'fas fa-check-circle' : (successCount >= 2 ? 'fas fa-exclamation-triangle' : 'fas fa-times-circle');
    
    return `
        <div class="alert ${alertClass} text-center">
            <i class="${icon} fa-3x mb-3"></i>
            <h4>${successCount >= 3 ? 'Operazione Riuscita' : (successCount >= 2 ? 'Successo Parziale' : 'Operazione Fallita')}</h4>
            <p>${successCount}/4 componenti principali generati con successo.</p>
        </div>
    `;
}

function createUniversalInstructions(configSuccess) {
    // Mostra le istruzioni di successo solo se configSuccess è esplicitamente true.
    if (configSuccess === true) {
        return `
            <div class="alert alert-info">
                <h6><i class="fas fa-lightbulb me-2"></i>Prossimi Passi:</h6>
                <ol class="mb-0">
                    <li><strong>Riavvia AppDaemon</strong> per caricare la nuova configurazione apps.yaml.</li>
                    <li><strong>Riavvia Home Assistant</strong> per attivare i template sensors e la nuova dashboard.</li>
                    <li>Accedi alla dashboard dal menu Lovelace → "SouthTech - Light Presence Monitor".</li>
                </ol>
            </div>
        `;
    } 
    // Mostra le istruzioni di fallimento solo se configSuccess è esplicitamente false.
    else if (configSuccess === false) {
        const manualConfigCode = `
lovelace:
  dashboards:
    light-presence:
      mode: yaml
      title: SouthTech - Light Presence Monitor
      icon: mdi:lightbulb-on
      filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml
      show_in_sidebar: true`;

        return `
            <div class="alert alert-warning">
                <h6><i class="fas fa-wrench me-2"></i>Azione Manuale Richiesta per <code>configuration.yaml</code></h6>
                <p>L'aggiornamento automatico è fallito, probabilmente perché la sezione <code>lovelace: dashboards:</code> non è stata trovata.</p>
                <p><strong>Copia e incolla il seguente blocco nel tuo file <code>configuration.yaml</code>:</strong></p>
                <pre style="background-color: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px;"><code>${manualConfigCode.trim()}</code></pre>
                <p class="mt-3">Dopo aver salvato la modifica, <strong>riavvia Home Assistant</strong>.</p>
            </div>
        `;
    }
    // Se configSuccess è null o undefined (cioè non era parte del salvataggio), non mostrare nulla.
    return '';
}

function createUniversalTechnicalDetails(result) {
    return `
        <div class="mt-3">
            <h6>Dettagli Operazione:</h6>
            <div class="small">
                <strong>Metodo:</strong> ${result.method || result.communication_method || 'unknown'}<br>
                <strong>Timestamp:</strong> ${result.timestamp ? new Date(result.timestamp).toLocaleString() : new Date().toLocaleString()}<br>
                <strong>Durata:</strong> ${result.operation_duration || 'N/A'} secondi
            </div>
        </div>
    `;
}

/**
* ✅ [NUOVO] Estrae lo stato di successo di un componente dalla risposta del backend.
* Gestisce l'incoerenza di denominazione per 'configuration.yaml'.
* @param {object} result - L'oggetto risultato del backend.
* @param {string} componentName - Il nome del componente ('apps', 'templates', 'configuration', 'dashboard').
* @returns {boolean|null} - true/false se lo stato è trovato, altrimenti null.
*/
function extractComponentSuccess(result, componentName) {
    if (!result || !result.details) return null;

    // Gestisce l'incoerenza: il backend potrebbe restituire 'configuration_yaml'
    const key = (componentName === 'configuration') ? 'configuration_yaml' : componentName;
    
    const detail = result.details[key] || result.details[componentName];

    if (detail && typeof detail.success === 'boolean') {
        return detail.success;
    }

    return null; // Ritorna null se non trovato, per indicare "Non salvato"
}

/**
* ✅ [NUOVO] Estrae il messaggio di errore di un componente dalla risposta del backend.
* Gestisce l'incoerenza di denominazione per 'configuration.yaml'.
* @param {object} result - L'oggetto risultato del backend.
* @param {string} componentName - Il nome del componente.
* @returns {string} - Il messaggio di errore o una stringa vuota.
*/
function extractComponentError(result, componentName) {
    if (!result || !result.details) return '';

    // Gestisce l'incoerenza: il backend potrebbe restituire 'configuration_yaml'
    const key = (componentName === 'configuration') ? 'configuration_yaml' : componentName;

    const detail = result.details[key] || result.details[componentName];

    if (detail && detail.error) {
        return detail.error;
    }

    return '';
}

/**
* ✅ [NUOVO] Mostra modal con i risultati del salvataggio completo/specifico.
* @param {object} result - L'oggetto risultato restituito dal backend.
*/
function showSaveResultsModal(result) {
    console.log('📊 Mostrando risultati salvataggio:', result);

    const isCompleteSave = result.method === 'sensor_complete' || result.method === 'complete_sensor';
    const isSpecificSave = !!result.file_type && !isCompleteSave;

    if (isSpecificSave) {
        const isConfigurationSave = result.file_type === 'configuration' || result.file_type === 'configuration_yaml';
        const isConfigurationMessage = result.message?.includes('lovelace: dashboards:') || 
                                     result.message?.includes('Azione Manuale Richiesta per configuration.yaml');

        if (!isConfigurationSave && isConfigurationMessage) {
            // Se non stiamo salvando configuration.yaml ma riceviamo il suo messaggio di errore, lo ignoriamo
            result.message = 'Operazione completata';
            if (result.details?.configuration?.error) {
                delete result.details.configuration.error;
            }
            if (result.manualActionRequired) {
                result.manualActionRequired = false;
                result.manualActionMessage = '';
            }
            // Assicuriamoci che non ci siano altri riferimenti a configuration.yaml
            if (result.details?.configuration_yaml?.error) {
                delete result.details.configuration_yaml.error;
            }
        }
    }

    let states = {
        isCompleteSaveFlow: result.is_complete_save_flow || false,
        fileType: result.file_type || null,
        method: result.method || null,
        configCount: configurations.length,
        totalSensors: configurations.length * 4 + 1,
        // Inizializza tutto a null/vuoto
        appsSuccess: null, templatesSuccess: null, configSuccess: null, dashboardSuccess: null,
        appsError: '', templatesError: '', configError: '', dashboardError: ''
    };

    if (isSpecificSave) {
        // Gestisce la struttura della risposta per il salvataggio di un singolo file
        let fileType = result.file_type;
        // Gestisce l'incoerenza del backend tra 'configuration' e 'configuration_yaml'
        if (fileType === 'configuration_yaml') {
            fileType = 'configuration';
        }

        const successKey = `${fileType}Success`;
        const errorKey = `${fileType}Error`;

        // ✅ NUOVO: Gestione migliorata per file già configurati
        const isAlreadyConfigured = result.message && (
            result.message.includes("già configurata") ||
            result.message.includes("già presente") ||
            result.message.includes("nessuna modifica") ||
            result.message.includes("verificata")
        );

        if (states.hasOwnProperty(successKey)) {
            // Imposta lo stato di successo per il componente specifico
            states[successKey] = result.success;
            states[errorKey] = '';
            
            // ✅ NUOVO: Aggiungi dettagli per ogni tipo di file
            if (!states.details) states.details = {};
            states.details[fileType] = {
                success: true,
                saved_entries: 1,
                message: result.message || "File salvato correttamente"
            };
        }

        // ✅ NUOVO: Gestione specifica per configuration.yaml
        if (fileType === 'configuration') {
            states.configSuccess = true;
            states.configurationSuccess = true; // Aggiungi anche questo stato
            if (!states.details) states.details = {};
            states.details.configuration = {
                success: true,
                saved_entries: 1,
                message: "File configurato correttamente"
            };
            // Forza questi stati specifici per configuration.yaml
            states.success = true;
            states.operation = "saved";
        }
    } else {
        // Gestisce la struttura della risposta per il salvataggio completo
        states.appsSuccess = extractComponentSuccess(result, 'apps');
        states.templatesSuccess = extractComponentSuccess(result, 'templates');
        states.configSuccess = extractComponentSuccess(result, 'configuration');
        states.dashboardSuccess = extractComponentSuccess(result, 'dashboard');
        
        // ✅ CONTROLLO DI SICUREZZA MIGLIORATO:
        if (result.success && result.message && (
            result.message.includes("4/4 componenti") ||
            result.message.includes("già configurata") ||
            result.message.includes("nessuna modifica")
        )) {
            // Forza tutto a true se è un successo completo
            states.appsSuccess = true;
            states.templatesSuccess = true;
            states.configSuccess = true;
            states.dashboardSuccess = true;
            console.log("✅ Successo completo confermato dal messaggio del backend");
        }
        
        states.appsError = extractComponentError(result, 'apps');
        states.templatesError = extractComponentError(result, 'templates');
        states.configError = extractComponentError(result, 'configuration');
        states.dashboardError = extractComponentError(result, 'dashboard');
    }

    // Crea il contenuto HTML del modal
    const modalHTML = createUniversalModalHTML(result, states);

    // Rimuovi modal esistenti per evitare sovrapposizioni
    const existingModal = document.getElementById('saveResultsModal');
    if (existingModal) {
        existingModal.remove();
    }

    const modalContainer = document.createElement('div');
    modalContainer.id = 'saveResultsModal';
    modalContainer.className = 'modal fade';
    modalContainer.setAttribute('tabindex', '-1');
    modalContainer.innerHTML = modalHTML;
    document.body.appendChild(modalContainer);

    const bootstrapModal = new bootstrap.Modal(modalContainer);
    bootstrapModal.show();

    modalContainer.addEventListener('hidden.bs.modal', () => {
        modalContainer.remove();
    });
}

function showUniversalDebugInfo() {
    console.log('🐛 UNIVERSAL DEBUG - Mostra informazioni debug complete');
    alert('Controlla la console del browser (F12) per i dettagli tecnici completi.');
}

// 📝 GENERA YAML
function generateYAML() {
    console.log('🔄 Redirezione a generazione completa...');
    generateYAMLAndDashboard();
}

// 📋 COPIA YAML
async function copyAppsYAML() {
    try {
        const yamlContent = document.getElementById('yamlCode').textContent;
        await navigator.clipboard.writeText(yamlContent);
        SouthTechUI.showAlert('📋 Apps.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Apps.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Apps.yaml', 'error');
    }
}

// Mantieni la compatibilità con la funzione esistente
async function copyYAML() {
    await copyAppsYAML();
}

async function copyDashboardYAML() {
    try {
        const dashboardContent = document.getElementById('dashboardYamlCode').textContent;
        await navigator.clipboard.writeText(dashboardContent);
        SouthTechUI.showAlert('📋 Dashboard.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Dashboard.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Dashboard.yaml', 'error');
    }
}

async function copyConfigurationYAML() {
    try {
        const configContent = document.getElementById('configurationYamlCode').textContent;
        await navigator.clipboard.writeText(configContent);
        SouthTechUI.showAlert('📋 Configuration.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Configuration.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Configuration.yaml', 'error');
    }
}

/**
* 📁 Funzioni di download per ogni file YAML
*/
function downloadDashboardYAML() {
    const dashboardContent = document.getElementById('dashboardYamlCode').textContent;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `ui-lovelace-light-presence_${timestamp}.yaml`;
    
    const blob = new Blob([dashboardContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    SouthTechUI.showAlert(`📁 File scaricato: ${filename}`, 'success');
}

function downloadTemplatesYAML() {
    const templatesContent = document.getElementById('templatesYamlCode').textContent;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `templates_${timestamp}.yaml`;
    
    const blob = new Blob([templatesContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    SouthTechUI.showAlert(`📁 File scaricato: ${filename}`, 'success');
}

function downloadConfigurationYAML() {
    const configContent = document.getElementById('configurationYamlCode').textContent;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `configuration_entry_${timestamp}.yaml`;
    
    const blob = new Blob([configContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    SouthTechUI.showAlert(`📁 File scaricato: ${filename}`, 'success');
}

function downloadAppsYAML() {
    const appsContent = document.getElementById('yamlCode').textContent;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `apps_${timestamp}.yaml`;
    
    const blob = new Blob([appsContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    SouthTechUI.showAlert(`📁 File scaricato: ${filename}`, 'success');
}

/**
* 📋 Funzioni di copia per ogni file YAML
*/
async function copyAppsYAML() {
    try {
        const yamlContent = document.getElementById('yamlCode').textContent;
        await navigator.clipboard.writeText(yamlContent);
        SouthTechUI.showAlert('📋 Apps.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Apps.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Apps.yaml', 'error');
    }
}

async function copyDashboardYAML() {
    try {
        const dashboardContent = document.getElementById('dashboardYamlCode').textContent;
        await navigator.clipboard.writeText(dashboardContent);
        SouthTechUI.showAlert('📋 Dashboard.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Dashboard.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Dashboard.yaml', 'error');
    }
}

async function copyTemplatesYAML() {
    try {
        const templatesContent = document.getElementById('templatesYamlCode').textContent;
        await navigator.clipboard.writeText(templatesContent);
        SouthTechUI.showAlert('📋 Templates.yaml copiato negli appunti!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia Templates.yaml:', error);
        SouthTechUI.showAlert('❌ Errore copia Templates.yaml', 'error');
    }
}

// Mantieni la compatibilità con le funzioni esistenti
async function saveConfiguration() {
    console.log('🔄 Redirezione a salvataggio completo...');
    await saveCompleteConfiguration();
}

// ✅ NUOVA FUNZIONE: Mostra popup di conferma salvataggio
function showSaveConfirmation() {
    // Genera anteprima della configurazione
    const yamlContent = generateYAMLContent();
    const configCount = configurations.length;
    const yamlSize = yamlContent.length;
    const yamlLines = yamlContent.split('\n').length;
    
    // Crea modal di conferma con lo stile di index.html
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'saveConfirmationModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content" style="border-radius: 20px; border: none;">
                <div class="modal-header" style="background: linear-gradient(135deg, var(--secondary-color) 0%, var(--primary-color) 100%); color: white; border-radius: 20px 20px 0 0;">
                    <h5 class="modal-title" style="font-weight: bold;">
                        <i class="fas fa-save me-2"></i>Conferma Salvataggio Configurazione
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="padding: 30px;">
                    <div style="text-align: center; margin-bottom: 25px;">
                        <div style="font-size: 3rem; color: var(--secondary-color); margin-bottom: 15px;">
                            <i class="fas fa-file-code"></i>
                        </div>
                        <h4 style="color: var(--primary-color); font-weight: bold;">Salvataggio in apps.yaml</h4>
                        <p class="text-muted">Stai per salvare la configurazione dell'automatismo luci</p>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div style="background: #f8f9fa; border-left: 4px solid var(--secondary-color); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <h6 style="color: var(--primary-color); font-weight: bold; margin-bottom: 15px;">
                                    <i class="fas fa-info-circle me-2"></i>Dettagli Configurazione
                                </h6>
                                <div style="font-size: 0.95rem;">
                                    <div class="mb-2">
                                        <strong>📊 Configurazioni:</strong> <span class="badge bg-primary">${configCount}</span>
                                    </div>
                                    <div class="mb-2">
                                        <strong>📏 Dimensione YAML:</strong> <span class="badge bg-info">${yamlSize} caratteri</span>
                                    </div>
                                    <div class="mb-2">
                                        <strong>📄 Righe di codice:</strong> <span class="badge bg-success">${yamlLines}</span>
                                    </div>
                                    <div>
                                        <strong>💾 File destinazione:</strong><br>
                                        <code style="font-size: 0.85rem;">/config/appdaemon/apps/apps.yaml</code>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div style="background: #e8f5e8; border-left: 4px solid var(--success-color); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <h6 style="color: var(--success-color); font-weight: bold; margin-bottom: 15px;">
                                    <i class="fas fa-shield-alt me-2"></i>Operazioni di Sicurezza
                                </h6>
                                <div style="font-size: 0.9rem;">
                                    <div class="mb-2">
                                        <i class="fas fa-check text-success me-2"></i>Backup automatico del file esistente
                                    </div>
                                    <div class="mb-2">
                                        <i class="fas fa-check text-success me-2"></i>Validazione YAML prima della scrittura
                                    </div>
                                    <div class="mb-2">
                                        <i class="fas fa-check text-success me-2"></i>Verifica integrità file salvato
                                    </div>
                                    <div>
                                        <i class="fas fa-check text-success me-2"></i>Preservazione configurazioni esistenti
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: center;">
                            <i class="fas fa-exclamation-triangle text-warning me-3" style="font-size: 1.5rem;"></i>
                            <div>
                                <strong>Importante:</strong> Il salvataggio sostituirà la sezione "CONTROLLO LUCI AUTOMATICHE" 
                                nel file apps.yaml. Le altre configurazioni rimarranno invariate.
                            </div>
                        </div>
                    </div>
                    
                    <div style="text-align: center; color: #6c757d;">
                        <small>
                            <i class="fas fa-clock me-1"></i>
                            Il processo di salvataggio richiede solitamente 2-5 secondi
                        </small>
                    </div>
                </div>
                <div class="modal-footer" style="border: none; padding: 20px 30px 30px;">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" style="border-radius: 10px; padding: 12px 25px; font-weight: 600;">
                        <i class="fas fa-times me-2"></i>Annulla
                    </button>
                    <button type="button" class="btn btn-success" onclick="proceedWithSave()" style="background: linear-gradient(135deg, var(--success-color) 0%, #229954 100%); border: none; border-radius: 10px; padding: 12px 25px; font-weight: 600; font-size: 1.1rem;">
                        <i class="fas fa-save me-2"></i>Conferma e Salva
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    // Rimuovi modal quando chiuso
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

// ✅ NUOVA FUNZIONE: Procede con il salvataggio dopo conferma
async function proceedWithSave() {
    // Chiudi il modal di conferma
    const modal = bootstrap.Modal.getInstance(document.getElementById('saveConfirmationModal'));
    modal.hide();
    
    // Avvia il processo di salvataggio effettivo
    await executeActualSave();
}

// 📖 STEP 3: Mostra istruzioni salvataggio manuale
function showManualSaveInstructions() {
    const yamlContent = generateYAMLContent();
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'manualSaveModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header bg-warning text-dark">
                    <h5 class="modal-title">
                        <i class="fas fa-hand-paper me-2"></i>
                        Salvataggio Manuale Richiesto
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>Tutti i metodi automatici di salvataggio sono falliti.</strong>
                        Segui questi passaggi per salvare manualmente la configurazione:
                    </div>
                    
                    <div class="row">
                        <div class="col-md-5">
                            <h6><i class="fas fa-list-ol me-2"></i>Passaggi da seguire:</h6>
                            <ol class="list-group list-group-numbered">
                                <li class="list-group-item d-flex align-items-start">
                                    <div class="ms-2">
                                        <strong>Copia il codice YAML</strong><br>
                                        <small class="text-muted">Usa il pulsante "Copia" nella sezione a destra</small>
                                    </div>
                                </li>
                                <li class="list-group-item d-flex align-items-start">
                                    <div class="ms-2">
                                        <strong>Accedi al file apps.yaml</strong><br>
                                        <small class="text-muted">Percorso: <code>/config/appdaemon/apps/apps.yaml</code></small>
                                    </div>
                                </li>
                                <li class="list-group-item d-flex align-items-start">
                                    <div class="ms-2">
                                        <strong>Trova la sezione esistente</strong><br>
                                        <small class="text-muted">Cerca tra:<br>
                                        <code># START CONTROLLO LUCI AUTOMATICHE</code><br>
                                        <code># END CONTROLLO LUCI AUTOMATICHE</code></small>
                                    </div>
                                </li>
                                <li class="list-group-item d-flex align-items-start">
                                    <div class="ms-2">
                                        <strong>Sostituisci o aggiungi</strong><br>
                                        <small class="text-muted">Se la sezione esiste, sostituiscila completamente. Altrimenti aggiungi alla fine del file.</small>
                                    </div>
                                </li>
                                <li class="list-group-item d-flex align-items-start">
                                    <div class="ms-2">
                                        <strong>Salva e riavvia</strong><br>
                                        <small class="text-muted">Salva il file e riavvia AppDaemon dal menu Supervisor</small>
                                    </div>
                                </li>
                            </ol>
                            
                            <div class="alert alert-info mt-3">
                                <i class="fas fa-lightbulb me-2"></i>
                                <strong>Suggerimento:</strong> Fai sempre un backup del file prima di modificarlo!
                            </div>
                            
                            <div class="alert alert-secondary mt-2">
                                <i class="fas fa-info-circle me-2"></i>
                                <strong>Configurazioni salvate:</strong> ${configurations.length}<br>
                                <strong>Dimensione YAML:</strong> ${yamlContent.length} caratteri
                            </div>
                        </div>
                        
                        <div class="col-md-7">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6><i class="fas fa-code me-2"></i>Codice YAML da copiare:</h6>
                                <button type="button" class="btn btn-outline-primary btn-sm" onclick="copyManualYAML()">
                                    <i class="fas fa-copy me-1"></i>Copia
                                </button>
                            </div>
                            
                            <div style="position: relative;">
                                <textarea id="manualYamlContent" class="form-control" rows="22" readonly 
                                        style="font-family: 'Courier New', monospace; font-size: 11px; background-color: #f8f9fa; border: 2px solid #dee2e6;">${yamlContent}</textarea>
                                
                                <div class="position-absolute" style="bottom: 5px; right: 5px; background: rgba(255,255,255,0.9); padding: 2px 6px; border-radius: 3px; font-size: 10px; color: #666;">
                                    ${yamlContent.split('\n').length} righe
                                </div>
                            </div>
                            
                            <div class="mt-2">
                                <small class="text-muted">
                                    <i class="fas fa-shield-alt me-1"></i>
                                    Il codice è stato validato ed è pronto per l'uso
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-primary" onclick="copyManualYAML()">
                        <i class="fas fa-copy me-2"></i>Copia YAML
                    </button>
                    <button type="button" class="btn btn-outline-secondary" onclick="downloadYAML()">
                        <i class="fas fa-download me-2"></i>Scarica File
                    </button>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times me-2"></i>Chiudi
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    // Rimuovi modal quando chiuso
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

// 📋 Copia YAML manuale
function copyManualYAML() {
    const textarea = document.getElementById('manualYamlContent');
    if (textarea) {
        textarea.select();
        textarea.setSelectionRange(0, 99999); // Per dispositivi mobile
        
        try {
            // Prova il nuovo API navigator.clipboard
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(textarea.value).then(() => {
                    showCopySuccess();
                }).catch(() => {
                    // Fallback al metodo legacy
                    legacyCopy(textarea);
                });
            } else {
                // Fallback diretto
                legacyCopy(textarea);
            }
            
        } catch (error) {
            console.error('Errore copia:', error);
            SouthTechUI.showAlert('❌ Errore durante la copia. Seleziona tutto il testo e copia manualmente (Ctrl+C)', 'error');
        }
    }
}

/**
* 📋 [NUOVO] Mostra istruzioni per aggiornamento manuale di configuration.yaml
*/
function showConfigYamlManualInstructions() {
    const manualConfigCode = `
lovelace:
  dashboards:
    light-presence:
      mode: yaml
      title: SouthTech - Light Presence Monitor
      icon: mdi:lightbulb-on
      filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml
      show_in_sidebar: true`.trim();

    const modalHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-warning text-dark">
                    <h5 class="modal-title">
                        <i class="fas fa-wrench me-2"></i>Istruzioni Manuali per Configuration.yaml
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p>L'aggiornamento automatico del file <strong>configuration.yaml</strong> è fallito.</p>
                    <p>Per abilitare la dashboard, copia e incolla il seguente blocco di codice nel tuo file <code>configuration.yaml</code>, solitamente alla fine del file.</p>
                    <pre style="background-color: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px;"><code>${manualConfigCode}</code></pre>
                    <p class="mt-3">Dopo aver salvato la modifica, <strong>riavvia Home Assistant</strong> per applicare le modifiche.</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-primary" onclick="copyConfigYamlContent()">
                        <i class="fas fa-copy me-2"></i>Copia Codice
                    </button>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times me-2"></i>Chiudi
                    </button>
                </div>
            </div>
        </div>
    `;

    // Rimuovi modal esistenti
    const existingModal = document.getElementById('manualConfigYamlModal');
    if (existingModal) {
        existingModal.remove();
    }

    const modalContainer = document.createElement('div');
    modalContainer.id = 'manualConfigYamlModal';
    modalContainer.className = 'modal fade';
    modalContainer.setAttribute('tabindex', '-1');
    modalContainer.innerHTML = modalHTML;
    document.body.appendChild(modalContainer);

    const bootstrapModal = new bootstrap.Modal(modalContainer);
    bootstrapModal.show();

    modalContainer.addEventListener('hidden.bs.modal', () => {
        modalContainer.remove();
    });
}

/**
* 📋 Copia contenuto configuration.yaml
*/
async function copyConfigYamlContent() {
    const content = `
lovelace:
  dashboards:
    light-presence:
      mode: yaml
      title: SouthTech - Light Presence Monitor
      icon: mdi:lightbulb-on
      filename: www/southtech/dashboards/ui-lovelace-light-presence.yaml
      show_in_sidebar: true
`.trim();
    
    try {
        await navigator.clipboard.writeText(content);
        SouthTechUI.showAlert('📋 Configurazione lovelace copiata!', 'success', 3000);
    } catch (error) {
        console.error('Errore copia:', error);
        SouthTechUI.showAlert('❌ Errore durante la copia', 'error');
    }
}

// Copia legacy (fallback)
function legacyCopy(textarea) {
    try {
        document.execCommand('copy');
        showCopySuccess();
    } catch (error) {
        SouthTechUI.showAlert('❌ Copia automatica non disponibile. Seleziona tutto il testo e usa Ctrl+C', 'warning');
    }
}

// Mostra successo copia
function showCopySuccess() {
    SouthTechUI.showAlert('✅ YAML copiato negli appunti!', 'success');
    
    // Evidenzia visivamente la copia
    const textarea = document.getElementById('manualYamlContent');
    if (textarea) {
        textarea.style.backgroundColor = '#d4edda';
        textarea.style.borderColor = '#28a745';
        setTimeout(() => {
            textarea.style.backgroundColor = '#f8f9fa';
            textarea.style.borderColor = '#dee2e6';
        }, 1500);
    }
}

// 📁 Scarica YAML come file
function downloadYAML() {
    const yamlContent = generateYAMLContent();
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `southtech_light_config_${timestamp}.yaml`;
    
    const blob = new Blob([yamlContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    SouthTechUI.showAlert(`📁 File scaricato: ${filename}`, 'success');
}

// ====================================================================
// 🆕 FUNZIONI JAVASCRIPT AGGIORNATE
// ====================================================================

/**
 * [NUOVA] Richiede e visualizza le anteprime di tutti i file YAML dal backend.
 * Utilizza il sistema di comunicazione via sensori.
 */
async function requestAndDisplayPreviews() {
    console.log('✨ Richiesta anteprima configurazione via sensori...');

    // Per l'anteprima mostriamo sia errori che avvisi
    if (!validateConfiguration(true)) {
        SouthTechUI.showAlert('❌ Correggi gli errori nelle configurazioni prima di generare l\'anteprima', 'error');
        return;
    }

    SouthTechUI.showAlert('🔄 Generazione anteprima in corso dal backend (via sensori)...', 'info', 4000);
    const yamlOutputElement = document.getElementById('yamlOutput');
    if (yamlOutputElement) {
        yamlOutputElement.style.display = 'block';
        document.getElementById('yamlCode').textContent = 'Caricamento...';
        document.getElementById('templatesYamlCode').textContent = 'Caricamento...';
        document.getElementById('configurationYamlCode').textContent = 'Caricamento...';
        document.getElementById('dashboardYamlCode').textContent = 'Caricamento...';
    }

    try {
        const response = await communicateViaSensors('save', { 
            configurations: configurations, 
            action: 'preview' 
        }, 20);

        if (response.success && response.previews) {
            await populateAllTabs(response.previews);
            yamlOutputElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            SouthTechUI.showAlert('✅ Anteprima generata con successo!', 'success');
        } else {
            throw new Error(response.error || 'Risposta non valida dal backend.');
        }
    } catch (error) {
        console.error('❌ Errore durante la richiesta di anteprima:', error);
        SouthTechUI.showAlert(`❌ Errore anteprima: ${error.message}`, 'error', 8000);
        if (yamlOutputElement) {
            document.getElementById('yamlCode').textContent = `Errore durante la generazione dell'anteprima.`;
            document.getElementById('templatesYamlCode').textContent = `Errore.`;
            document.getElementById('configurationYamlCode').textContent = `Errore.`;
            document.getElementById('dashboardYamlCode').textContent = `Errore.`;
        }
    }
}

/**
 * [MODIFICATA] - Ora non genera più nulla, ma chiama la nuova funzione
 * per richiedere l'anteprima al backend.
 */
async function generateYAMLAndDashboard() {
    await requestAndDisplayPreviews();
}

/**
* 🎨 Popola il tab Dashboard Preview (mantiene implementazione precedente migliorata)
*/
async function populateDashboardPreview() {
    console.log('🎨 Popolamento dashboard preview...');
    
    try {
        const dashboardInfo = document.getElementById('dashboardInfo');
        if (!dashboardInfo) {
            console.warn('⚠️ Elemento dashboardInfo non trovato');
            return;
        }
        
        let content = '';
        
        // Header con statistiche immediate
        const totalFiles = configurations.length + 1;
        const totalSensors = configurations.length * 4;
        
        content += `<div class="row text-center mb-4">`;
        content += `<div class="col-md-3">`;
        content += `<div class="card border-primary">`;
        content += `<div class="card-body p-2">`;
        content += `<h4 class="text-primary mb-1">${totalFiles}</h4>`;
        content += `<small>File Dashboard</small>`;
        content += `</div></div></div>`;
        
        content += `<div class="col-md-3">`;
        content += `<div class="card border-success">`;
        content += `<div class="card-body p-2">`;
        content += `<h4 class="text-success mb-1">${configurations.length}</h4>`;
        content += `<small>Luci Configurate</small>`;
        content += `</div></div></div>`;
        
        content += `<div class="col-md-3">`;
        content += `<div class="card border-warning">`;
        content += `<div class="card-body p-2">`;
        content += `<h4 class="text-warning mb-1">${totalSensors}</h4>`;
        content += `<small>Template Sensors</small>`;
        content += `</div></div></div>`;
        
        content += `<div class="col-md-3">`;
        content += `<div class="card border-info">`;
        content += `<div class="card-body p-2">`;
        content += `<h4 class="text-info mb-1">3</h4>`;
        content += `<small>File YAML</small>`;
        content += `</div></div></div>`;
        content += `</div>`;
        
        // Anteprima rapida di ogni luce
        content += '<h6><i class="fas fa-lightbulb me-2 text-primary"></i>Pannelli Dashboard Generati:</h6>';
        content += '<div class="row">';
        
        configurations.forEach((config, index) => {
            if (!config.light_entity) return;
            
            const baseId = config.light_entity.replace('light.', '');
            const displayName = baseId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const hasIlluminance = !!config.illuminance_sensor;
            const hasPresenceOff = !!config.presence_sensor_off;
            
            content += '<div class="col-md-6 mb-2">';
            content += '<div class="card border-light">';
            content += '<div class="card-body p-2">';
            content += `<h6 class="mb-1"><i class="fas fa-lightbulb me-1 text-warning"></i> ${displayName}</h6>`;
            content += '<div class="small text-muted">';
            content += `<strong>File:</strong> <code>${baseId}.yaml</code><br>`;
            content += `<strong>Path:</strong> <code>/lovelace/light-presence#opzioni_${baseId}</code>`;
            content += '</div>';
            content += '<div class="mt-1">';
            content += `<span class="badge bg-${hasIlluminance ? 'success' : 'secondary'} me-1">`;
            content += `${hasIlluminance ? '📊 Grafico' : '📝 Placeholder'}`;
            content += '</span>';
            content += `<span class="badge bg-${hasPresenceOff ? 'info' : 'secondary'}">`;
            content += `${hasPresenceOff ? '🔄 Doppio sensore' : '📍 Singolo sensore'}`;
            content += '</span>';
            content += '</div>';
            content += '</div>';
            content += '</div>';
            content += '</div>';
        });
        
        content += '</div>';
        
        // Istruzioni accesso
        content += '<div class="alert alert-success mt-3">';
        content += '<h6><i class="fas fa-rocket me-2"></i>Come Accedere alla Dashboard:</h6>';
        content += '<ol class="mb-0">';
        content += '<li><strong>Salva la configurazione</strong> con il pulsante "Salva Configurazione Completa"</li>';
        content += '<li><strong>Riavvia Home Assistant</strong> per attivare templates e dashboard</li>';
        content += '<li><strong>Vai al menu Lovelace</strong> → "Configurazione Luci Automatiche"</li>';
        content += '<li><strong>Seleziona la luce</strong> che vuoi configurare dal menu laterale</li>';
        content += '</ol>';
        content += '</div>';
        
        dashboardInfo.innerHTML = content;
        console.log('✅ Dashboard preview popolato con successo');
        
    } catch (error) {
        console.error('❌ Errore popolamento dashboard preview:', error);
        const dashboardInfo = document.getElementById('dashboardInfo');
        if (dashboardInfo) {
            dashboardInfo.innerHTML = `<div class="alert alert-danger">Errore generazione preview: ${error.message}</div>`;
        }
    }
}

/**
        * 🧩 Popola informazioni Templates con grafica migliorata
        */
        function populateTemplatesInfo() {
            const templatesInfo = document.getElementById('templatesInfo');
            if (!templatesInfo) {
                console.warn('⚠️ Elemento templatesInfo non trovato');
                return;
            }
            
            let content = '';
            
            // Header con statistiche immediate
            const totalSensors = configurations.length * 4;
            
            content += `<div class="row text-center mb-4">`;
            content += `<div class="col-md-3">`;
            content += `<div class="card border-primary">`;
            content += `<div class="card-body p-2">`;
            content += `<h4 class="text-primary mb-1">${totalSensors}</h4>`;
            content += `<small>Template Sensors</small>`;
            content += `</div></div></div>`;
            
            content += `<div class="col-md-3">`;
            content += `<div class="card border-success">`;
            content += `<div class="card-body p-2">`;
            content += `<h4 class="text-success mb-1">${configurations.length}</h4>`;
            content += `<small>Luci Configurate</small>`;
            content += `</div></div></div>`;
            
            content += `<div class="col-md-3">`;
            content += `<div class="card border-warning">`;
            content += `<div class="card-body p-2">`;
            content += `<h4 class="text-warning mb-1">4</h4>`;
            content += `<small>Sensori per Luce</small>`;
            content += `</div></div></div>`;
            
            content += `<div class="col-md-3">`;
            content += `<div class="card border-info">`;
            content += `<div class="card-body p-2">`;
            content += `<h4 class="text-info mb-1">1</h4>`;
            content += `<small>File Templates</small>`;
            content += `</div></div></div>`;
            content += `</div>`;
            
            content += '<h6><i class="fas fa-puzzle-piece me-2"></i>Template Sensors Generati per Luce:</h6>';
            content += '<div class="row">';
            
            configurations.forEach((config, index) => {
                if (!config.light_entity) return;
                
                const baseId = config.light_entity.replace('light.', '');
                const friendlyName = config.light_entity.replace('light.', '').replace(/_/g, ' ').split(' ').map(word => 
                    word.charAt(0).toUpperCase() + word.slice(1)
                ).join(' ');
                
                content += '<div class="col-md-6 mb-3">';
                content += '<div class="card border-light">';
                content += '<div class="card-header bg-light">';
                content += `<i class="fas fa-lightbulb me-2 text-warning"></i><strong>${friendlyName}</strong>`;
                content += '</div>';
                content += '<div class="card-body p-3">';
                
                const sensors = [
                    { name: 'Presenza + Luce', id: `presenza_luce_${baseId}`, color: 'warning', icon: 'fas fa-user-check', desc: 'Persona presente E luce accesa' },
                    { name: 'Solo Presenza', id: `solo_presenza_${baseId}`, color: 'success', icon: 'fas fa-user', desc: 'Persona presente MA luce spenta' },
                    { name: 'Solo Luce', id: `solo_luce_${baseId}`, color: 'info', icon: 'fas fa-lightbulb', desc: 'Luce accesa MA persona assente' },
                    { name: 'Vuoto', id: `vuoto_${baseId}`, color: 'secondary', icon: 'fas fa-bed', desc: 'Persona assente E luce spenta' }
                ];
                
                sensors.forEach(sensor => {
                    content += `<div class="d-flex justify-content-between align-items-center mb-2 p-2" style="background-color: #f8f9fa; border-radius: 8px;">`;
                    content += `<div>`;
                    content += `<i class="${sensor.icon} me-2 text-${sensor.color}"></i>`;
                    content += `<strong>${sensor.name}</strong>`;
                    content += `<br><small class="text-muted">${sensor.desc}</small>`;
                    content += `</div>`;
                    content += `<div class="text-end">`;
                    content += `<div class="badge bg-${sensor.color}">sensor.${sensor.id}</div>`;
                    content += `</div>`;
                    content += `</div>`;
                });
                
                content += '</div>';
                content += '</div>';
                content += '</div>';
            });
            
            content += '</div>';
            
            // Informazioni tecniche
            content += '<div class="alert alert-info mt-3">';
            content += '<h6><i class="fas fa-info-circle me-2"></i>Come Funzionano i Template Sensors:</h6>';
            content += '<ul class="mb-0">';
            content += '<li><strong>Presenza + Luce:</strong> Indica quando qualcuno è presente E la luce è accesa (stato ideale)</li>';
            content += '<li><strong>Solo Presenza:</strong> Indica quando qualcuno è presente MA la luce è spenta (potenziale accensione)</li>';
            content += '<li><strong>Solo Luce:</strong> Indica quando la luce è accesa MA nessuno è presente (potenziale spegnimento)</li>';
            content += '<li><strong>Vuoto:</strong> Indica quando nessuno è presente E la luce è spenta (stato di riposo)</li>';
            content += '</ul>';
            content += '</div>';
            
            content += '<div class="alert alert-warning">';
            content += '<i class="fas fa-exclamation-triangle me-2"></i>';
            content += '<strong>Importante:</strong> I template sensors saranno salvati in <code>templates.yaml</code> ';
            content += 'e saranno automaticamente disponibili dopo il riavvio di Home Assistant.';
            content += '</div>';
            
            templatesInfo.innerHTML = content;
        }

/**
* 🎨 Popola tutti i 4 tab con i contenuti generati
*/
async function populateAllTabs(previews) {
    console.log('🎨 Popolamento tab con anteprime dal backend...');
    
    try {
        // 1. Tab Apps.yaml
        const yamlCodeElement = document.getElementById('yamlCode');
        const yamlStatsElement = document.getElementById('yamlStats');
        if (yamlCodeElement && yamlStatsElement) {
            const content = previews.apps_yaml || '';
            yamlCodeElement.textContent = content;
            
            const lines = content.split('\n').length;
            const size = (content.length / 1024).toFixed(1);
            const configCount = configurations.length;
            
            yamlStatsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    ⚙️ <strong>${configCount}</strong> configurazioni
                </div>
            `;
        }
        
        // 2. Tab Dashboard.yaml  
        const dashboardYamlElement = document.getElementById('dashboardYamlCode');
        const dashboardStatsElement = document.getElementById('dashboardYamlStats');
        if (dashboardYamlElement && dashboardStatsElement) {
            const content = previews.dashboard_yaml || '';
            dashboardYamlElement.textContent = content;

            const lines = content.split('\n').length;
            const size = (content.length / 1024).toFixed(1);
            const views = configurations.length + 1; // +1 per il riepilogo

            dashboardStatsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    🎨 <strong>${views}</strong> viste (1 riepilogo + ${configurations.length} luci)
                </div>
            `;
        }
        
        // 3. Tab Templates.yaml
        const templatesYamlElement = document.getElementById('templatesYamlCode');
        const templatesStatsElement = document.getElementById('templatesYamlStats');
        if (templatesYamlElement && templatesStatsElement) {
            const content = previews.templates_yaml || '';
            templatesYamlElement.textContent = content;

            const lines = content.split('\n').length;
            const size = (content.length / 1024).toFixed(1);
            const sensors = configurations.length * 4 + 1; // 4 per luce + 1 placeholder

            templatesStatsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    🧩 <strong>${sensors}</strong> sensori template
                </div>
            `;
        }
        
        // 4. Configuration.yaml
        const configurationYamlElement = document.getElementById('configurationYamlCode');
        const configurationStatsElement = document.getElementById('configurationYamlStats');
        if (configurationYamlElement && configurationStatsElement) {
            const content = previews.configuration_yaml || '';
            configurationYamlElement.textContent = content;

            const lines = content.split('\n').length;
            const size = (content.length / 1024).toFixed(1);

            configurationStatsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    ⚙️ <strong>1</strong> voce dashboard
                </div>
            `;
        }
        
        // 5. Tab Preview Dashboard (logica invariata, è solo HTML)
        await populateDashboardPreview();
        
        console.log('✅ Tutti i tab popolati con successo');
        
    } catch (error) {
        console.error('❌ Errore popolamento tab:', error);
        throw error; // Propaga l'errore alla funzione chiamante
    }
}

/**
* 🎨 Popola il tab Dashboard.yaml
*/
async function populateDashboardYamlTab(dashboardContent) {
    console.log('🎨 Popolamento tab Dashboard.yaml...');
    
    try {
        // Popola il contenuto YAML
        const yamlElement = document.getElementById('dashboardYamlCode');
        if (yamlElement) {
            yamlElement.textContent = dashboardContent;
        } else {
            console.warn('⚠️ Elemento dashboardYamlCode non trovato');
            return;
        }
        
        // Aggiorna statistiche
        const statsElement = document.getElementById('dashboardYamlStats');
        if (statsElement) {
            const lines = dashboardContent.split('\n').length;
            const size = (dashboardContent.length / 1024).toFixed(1);
            const views = configurations.length;
            
            statsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    🎨 <strong>${views}</strong> views
                </div>
            `;
        }
        
        console.log('✅ Tab Dashboard.yaml popolato');
        
    } catch (error) {
        console.error('❌ Errore popolamento tab Dashboard.yaml:', error);
    }
}

/**
* 🧩 Popola il tab Templates.yaml
*/
async function populateTemplatesYamlTab(templatesContent) {
    console.log('🧩 Popolamento tab Templates.yaml...');
    
    try {
        // Popola il contenuto YAML
        const yamlElement = document.getElementById('templatesYamlCode');
        if (yamlElement) {
            yamlElement.textContent = templatesContent;
        } else {
            console.warn('⚠️ Elemento templatesYamlCode non trovato');
            return;
        }
        
        // Aggiorna statistiche
        const statsElement = document.getElementById('templatesYamlStats');
        if (statsElement) {
            const lines = templatesContent.split('\n').length;
            const size = (templatesContent.length / 1024).toFixed(1);
            const sensors = configurations.length * 4 + 1; // +1 per placeholder
            
            statsElement.innerHTML = `
                <div class="small text-muted mt-2">
                    📄 <strong>${lines}</strong> righe • 
                    💾 <strong>${size} KB</strong> • 
                    🧩 <strong>${sensors}</strong> sensori
                </div>
            `;
        }
        
        console.log('✅ Tab Templates.yaml popolato');
        
    } catch (error) {
        console.error('❌ Errore popolamento tab Templates.yaml:', error);
    }
}

/**
* ✅ [NUOVO] Mostra popup di conferma per salvataggio di un file specifico.
* @param {string} fileType - Il tipo di file da salvare ('apps', 'templates', 'dashboard', 'configuration').
*/
function showSpecificSaveConfirmation(fileType) {
    if (!fileType) {
        SouthTechUI.showAlert('Errore: Tipo di file non specificato per il salvataggio.', 'error');
        return;
    }

    // Per i salvataggi specifici controlliamo solo gli errori, non gli avvisi
    if (!validateConfiguration(false)) {
        SouthTechUI.showAlert('❌ Correggi gli errori nelle configurazioni prima di salvare', 'error');
        return;
    }

    const friendlyNames = {
        apps: 'Apps.yaml',
        templates: 'Templates.yaml',
        dashboard: 'Dashboard.yaml',
        configuration: 'Configuration.yaml'
    };

    const friendlyName = friendlyNames[fileType] || fileType;
    const iconClasses = {
        apps: 'fas fa-cog text-primary',
        templates: 'fas fa-puzzle-piece text-success',
        dashboard: 'fas fa-file-code text-info',
        configuration: 'fas fa-file-alt text-warning'
    };
    const icon = iconClasses[fileType] || 'fas fa-file-alt';

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'specificSaveConfirmationModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content" style="border-radius: 20px; border: none;">
                <div class="modal-header" style="background: linear-gradient(135deg, var(--secondary-color) 0%, var(--primary-color) 100%); color: white; border-radius: 20px 20px 0 0;">
                    <h5 class="modal-title" style="font-weight: bold;">
                        <i class="fas fa-file-upload me-2"></i>Conferma Salvataggio Specifico
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="padding: 30px;">
                    <div class="text-center mb-4">
                        <i class="${icon}" style="font-size: 3rem;"></i>
                        <h4 class="mt-3" style="color: var(--primary-color); font-weight: bold;">Salvataggio di ${friendlyName}</h4>
                        <p class="text-muted">Stai per salvare <strong>solo</strong> il file <code>${friendlyName}</code> sul server.</p>
                    </div>
                    
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>Importante:</strong> Questa operazione sovrascriverà il file esistente sul server. Sarà creato un backup automatico. Le altre configurazioni non verranno modificate.
                    </div>
                </div>
                <div class="modal-footer" style="border: none; padding: 20px 30px 30px;">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Annulla</button>
                    <button type="button" class="btn btn-info" onclick="executeSpecificSave('${fileType}')">
                        <i class="fas fa-save me-2"></i>Conferma e Salva ${friendlyName}
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

/**
* 💾 FUNZIONE DI SALVATAGGIO
* Utilizza la funzione di validazione corretta.
*/
async function saveCompleteConfiguration() {
    console.log('💾 Avvio salvataggio configurazione completa...');
    
    if (isSaving) {
        SouthTechUI.showAlert('⚠️ Salvataggio già in corso, attendere...', 'warning');
        return;
    }
    
    // Per il salvataggio completo mostriamo sia errori che avvisi
    if (!validateConfiguration(true)) {
        SouthTechUI.showAlert('❌ Correggi gli errori nelle configurazioni prima di salvare', 'error');
        return;
    }
    
    // Mostra il modale di conferma prima di procedere
    showCompleteSaveConfirmation();
}

/**
* ✅ Procede con il salvataggio dopo la conferma dell'utente.
*/
async function proceedWithCompleteSave() {
    // Chiudi il modal di conferma
    const modal = bootstrap.Modal.getInstance(document.getElementById('completeSaveConfirmationModal'));
    if (modal) {
        modal.hide();
    }
    
    // Avvia il processo di salvataggio effettivo
    await executeCompleteSave();
}

/**
* ✅ Mostra popup di conferma per salvataggio completo - 4 COMPONENTI
*/
function showCompleteSaveConfirmation() {
    // Legge il contenuto dall'elemento dell'interfaccia,
    // che è stato popolato dalla chiamata di anteprima al backend.
    const yamlContent = document.getElementById('yamlCode').textContent;
    
    if (!yamlContent || yamlContent === 'Caricamento...') {
        SouthTechUI.showAlert('Errore: Contenuto YAML di anteprima non disponibile. Prova a rigenerare.', 'error');
        return;
    }

    const configCount = configurations.length;
    const totalSensors = configCount * 4 + 1; // +1 per il placeholder
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'completeSaveConfirmationModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content" style="border-radius: 20px; border: none;">
                <div class="modal-header" style="background: linear-gradient(135deg, var(--secondary-color) 0%, var(--primary-color) 100%); color: white; border-radius: 20px 20px 0 0;">
                    <h5 class="modal-title" style="font-weight: bold;">
                        <i class="fas fa-magic me-2"></i>Conferma Salvataggio Configurazione Completa
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="padding: 30px;">
                    <h4 style="color: var(--primary-color); font-weight: bold; text-align: center;">Stai per salvare la configurazione completa.</h4>
                    <p class="text-muted text-center">Questo aggiornerà tutti i file necessari sul server.</p>
                    
                    <div class="row mt-4">
                        <div class="col-md-3">
                            <div class="card text-center h-100">
                                <div class="card-body">
                                    <i class="fas fa-cog fa-2x text-primary mb-2"></i>
                                    <h6>Apps.yaml</h6>
                                    <span class="badge bg-primary">${configCount} configurazioni</span>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center h-100">
                                <div class="card-body">
                                    <i class="fas fa-puzzle-piece fa-2x text-success mb-2"></i>
                                    <h6>Templates.yaml</h6>
                                    <span class="badge bg-success">${totalSensors} sensori</span>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center h-100">
                                <div class="card-body">
                                    <i class="fas fa-file-alt fa-2x text-warning mb-2"></i>
                                    <h6>Configuration.yaml</h6>
                                    <span class="badge bg-warning">1 voce</span>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center h-100">
                                <div class="card-body">
                                    <i class="fas fa-tachometer-alt fa-2x text-info mb-2"></i>
                                    <h6>Dashboard & Lovelace</h6>
                                    <span class="badge bg-info">${configCount + 1} viste</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="alert alert-warning mt-4">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>Importante:</strong> Sarà creato un backup automatico prima di applicare le modifiche.
                    </div>
                </div>
                <div class="modal-footer" style="border: none; padding: 20px 30px 30px;">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Annulla</button>
                    <button type="button" class="btn btn-success" onclick="proceedWithCompleteSave()">
                        <i class="fas fa-save me-2"></i>Conferma e Salva Tutto
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}
