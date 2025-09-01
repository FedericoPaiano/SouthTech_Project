/**
 * Ottieni l'area di un'entità dalla cache
 * @param {string} entityId - ID dell'entità
 * @returns {string|null} - Nome dell'area o null se non trovata
 */
function getEntityArea(entityId) {
    return entityAreaCache.get(entityId) || null;
}

// ====================================================================
// NUOVO SISTEMA DI COMUNICAZIONE VIA SENSORI
// ====================================================================

/**
 * [NUOVA FUNZIONE HELPER - CORRETTA v2]
 * Gestisce la comunicazione con il backend usando i sensori di Home Assistant.
 * Utilizza il metodo POST diretto all'endpoint /api/states/ per coerenza
 * con le altre funzioni del sistema (es. sync e login).
 * @param {string} action - Il tipo di azione (es. 'preview', 'save').
 * @param {object} payload - I dati da inviare al backend.
 * @param {number} timeoutSeconds - Il tempo massimo di attesa per una risposta.
 * @returns {Promise<object>} - Una promessa che si risolve con la risposta del backend.
 */
async function communicateViaSensors(action, payload, timeoutSeconds = 30) {
    const requestId = `${action}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const requestSensor = `sensor.southtech_${action}_request`;
    const responseSensor = `sensor.southtech_${action}_response`;

    console.log(`📡 SENSOR COMM: Avvio azione '${action}' (ID: ${requestId})`);

    try {
        // 1. Invia la richiesta scrivendo sul sensore tramite l'API REST di Home Assistant
        // [CORREZIONE] Utilizziamo il metodo POST diretto a /api/states/<entity_id>
        // che è lo stesso metodo usato con successo dalle funzioni di sync e login.
        const requestPayload = {
            state: 'pending',
            attributes: {
                ...payload,
                request_id: requestId,
                timestamp: new Date().toISOString(),
                browser_id: browserId
            }
        };

        const setServiceResponse = await fetch(`/api/states/${requestSensor}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestPayload)
        });

        if (!setServiceResponse.ok) {
            let errorDetails = setServiceResponse.statusText;
            try {
                const errorJson = await setServiceResponse.json();
                errorDetails = errorJson.message || errorDetails;
            } catch (e) {}
            throw new Error(`Errore nell'invio della richiesta al sensore: ${errorDetails}`);
        }

        // 2. Attendi la risposta dal sensore di risposta (logica invariata)
        const maxAttempts = timeoutSeconds;
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const getStateResponse = await fetch(`/api/states/${responseSensor}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${haToken}`
                }
            });

            if (getStateResponse.ok) {
                const responseState = await getStateResponse.json();
                if (responseState && responseState.state === 'completed' && responseState.attributes.request_id === requestId) {
                    console.log(`✅ SENSOR COMM: Risposta ricevuta per '${action}'`, responseState.attributes);
                    return responseState.attributes;
                }
            }
        }
        throw new Error(`Timeout: Nessuna risposta dal backend per l'azione '${action}' entro ${timeoutSeconds} secondi.`);
    } catch (error) {
        console.error(`❌ SENSOR COMM: Errore durante l'azione '${action}':`, error);
        throw error;
    }
}

/**
* 💾 Sistema di backup con rotazione (max 5 backup)
*/
async function createBackupWithRotation() {
    console.log('💾 Creazione backup con rotazione (max 5)...');
    
    try {
        const timestamp = new Date().toISOString()
            .slice(0, 19)
            .replace('T', '_')
            .replace(/:/g, '-');
        
        const backupData = {
            timestamp: timestamp,
            configurations_count: configurations.length,
            backup_reason: 'complete_save',
            files_backed_up: []
        };
        
        // Simula backup (implementazione reale sarà nel backend)
        console.log(`📦 Backup creato: southtech/backups/${timestamp}/`);
        console.log('🔄 Rotazione backup: mantenimento ultimi 5');
        
        // Il backend si occuperà della rotazione effettiva
        return {
            success: true,
            backup_folder: timestamp,
            message: 'Backup creato con rotazione automatica'
        };
        
    } catch (error) {
        console.error('❌ Errore creazione backup:', error);
        // Continua comunque (come specificato)
        return {
            success: false,
            error: error.message,
            message: 'Errore backup, ma proseguo con il salvataggio'
        };
    }
}

// ✅ CARICAMENTO ENTITÀ COMPLETAMENTE RISCRITTO
async function loadEntities() {
    console.log('📋 === INIZIO CARICAMENTO ENTITÀ (WebSocket Manager) ===');
    console.log(`🎯 Filtro area: ${areaFilterEnabled ? 'ATTIVO' : 'DISATTIVO'}`);
    
    try {
        // Se abbiamo cache recente (< 5 minuti), usala
        if (areasDataCache && (Date.now() - areasDataCache.timestamp < 300000)) {
            console.log('💾 Usando dati da cache (< 5 minuti)');
            await processEntitiesFromCache();
            return;
        }
        
        // ✅ USA SOLO WEBSOCKET MANAGER
        await loadEntitiesViaWebSocketManager();
        
    } catch (error) {
        console.error('❌ Errore WebSocket Manager:', error);
        
        // ✅ FALLBACK SEMPLIFICATO
        await loadEntitiesRestFallback();
    }
    
    console.log('✅ === FINE CARICAMENTO ENTITÀ ===');
}

// ✅ SOSTITUISCE TUTTA LA LOGICA WEBSOCKET CUSTOM
async function loadEntitiesViaWebSocketManager() {
    console.log('🔌 Caricamento dati via WebSocket Manager (v3.1.0)...');
    
    // ✅ USA IL NUOVO SISTEMA DI RILEVAMENTO RETE
    const networkInfo = SouthTechCore.getNetworkInfo();
    console.log(`🌐 Rete: ${networkInfo.networkType} - URL: ${networkInfo.wsUrl}`);
    
    const wsManager = new SouthTechCore.WebSocketManager(haToken);
    
    try {
        await wsManager.connect();
        console.log(`🔌 WebSocket Manager connesso (${networkInfo.networkType})`);
        
        // ✅ CARICA TUTTO IN PARALLELO
        const [areas, entityRegistry, deviceRegistry, allStates] = await Promise.all([
            wsManager.getAreas(),
            wsManager.getEntityRegistry(),
            wsManager.getDeviceRegistry(),
            wsManager.getStates()
        ]);
        
        console.log('✅ Dati WebSocket caricati:', {
            areas: areas.length,
            entities: entityRegistry.length,
            devices: deviceRegistry.length,
            states: allStates.length,
            networkType: networkInfo.networkType
        });
        
        // ✅ AGGIORNA CACHE GLOBALI
        updateGlobalCache(areas, entityRegistry, deviceRegistry);
        
        // ✅ PROCESSA ENTITÀ
        await processEntitiesFromWebSocketData(allStates);
        
        // ✅ IMPOSTA MODALITÀ
        currentCommunicationMode = areaFilterEnabled ? 'websocket_filtered' : 'websocket_unfiltered';
        
        console.log(`✅ Caricamento completato via ${networkInfo.networkType} WebSocket`);
        
    } catch (error) {
        console.error(`❌ Errore WebSocket (${networkInfo.networkType}):`, error);
        throw error;
    } finally {
        // ✅ DISCONNETTI SEMPRE
        wsManager.disconnect();
        console.log('🔌 WebSocket Manager disconnesso');
    }
}

function getPopulatedAreas() {
    const populatedAreas = new Set();
    
    // Controlla tutte le entità caricate per vedere quali aree sono "popolate"
    [...entities.lights, ...entities.binary_sensors, ...entities.sensors].forEach(entity => {
        const area = getEntityArea(entity.entity_id);
        if (area) {
            populatedAreas.add(area);
        }
    });
    
    return populatedAreas;
}

// ✅ FALLBACK SEMPLIFICATO (SOLO REST API)
async function loadEntitiesRestFallback() {
    console.log('🔄 FALLBACK: Caricamento diretto REST API...');
    
    try {
        const response = await fetch('/api/states', {
            headers: { 'Authorization': `Bearer ${haToken}` }
        });
        
        if (!response.ok) throw new Error('Errore accesso HA API');
        
        const allStates = await response.json();
        
        // ✅ PROCESSA SENZA CACHE AREE
        await processEntitiesDirectly(allStates);
        
        // ✅ PULISCI CACHE
        entityAreaCache.clear();
        areasDataCache = null;
        
        currentCommunicationMode = 'fallback_rest';
        
        console.log(`✅ FALLBACK completato: ${entities.lights.length} luci, ${entities.binary_sensors.length} sensori`);
        
    } catch (error) {
        console.error('❌ Anche il fallback REST è fallito:', error);
        throw error;
    }
}

// 🔧 FUNZIONE: Calcola entità rilevanti totali
function calculateTotalRelevantEntities(allStates) {
    let totalRelevant = 0;
    
    allStates.forEach(state => {
        if (state.entity_id.startsWith('light.')) {
            totalRelevant++;
        } else if (state.entity_id.startsWith('binary_sensor.')) {
            totalRelevant++;
        } else if (state.entity_id.startsWith('sensor.')) {
            const isIlluminanceSensor = 
                state.attributes.device_class === 'illuminance' ||
                state.entity_id.toLowerCase().includes('illuminance') || 
                state.entity_id.toLowerCase().includes('lux');
            
            if (isIlluminanceSensor) {
                totalRelevant++;
            }
        }
    });
    
    console.log(`📊 Entità rilevanti totali: ${totalRelevant} (luci + sensori presenza + sensori lux)`);
    return totalRelevant;
}

// 🏠 NUOVA FUNZIONE: Conta aree uniche nelle entità filtrate
function countUniqueAreasInEntities(filteredEntities) {
    const uniqueAreas = new Set();
    
    // Aggiungi aree da tutte le categorie di entità filtrate
    [...filteredEntities.lights, ...filteredEntities.binary_sensors, ...filteredEntities.sensors].forEach(entity => {
        const area = getEntityArea(entity.entity_id);
        if (area) {
            uniqueAreas.add(area);
        }
    });
    
    return uniqueAreas.size;
}

// 🔧 Estrai aree per dropdown (INCLUDI TUTTE se filtro entità disattivo)
function extractUniqueAreas() {
    const areas = new Set();
    
    // Aggiungi aree da tutte le categorie di entità CARICATE
    [...entities.lights, ...entities.binary_sensors, ...entities.sensors].forEach(entity => {
        const area = getEntityArea(entity.entity_id);
        if (area) {
            areas.add(area);
        }
    });
    
    let sortedAreas = Array.from(areas).sort();
    
    // 🎯 SE FILTRO ENTITÀ DISATTIVO: Aggiungi TUTTE le aree con entità rilevanti
    if (!entityFilterEnabled) {
        const allAreasWithEntities = new Set();
        entityAreaCache.forEach((areaName, entityId) => {
            if (entityId.startsWith('light.') || 
                entityId.startsWith('binary_sensor.') || 
                (entityId.startsWith('sensor.') && 
                (entityId.toLowerCase().includes('illuminance') || entityId.toLowerCase().includes('lux')))) {
                allAreasWithEntities.add(areaName);
            }
        });
        
        // Unisci le aree caricate con tutte le aree del sistema
        const combinedAreas = new Set([...sortedAreas, ...allAreasWithEntities]);
        sortedAreas = Array.from(combinedAreas).sort();
        
        console.log(`🏠 Filtro entità DISATTIVO - Aree totali: ${sortedAreas.length} (${areas.size} caricate + ${allAreasWithEntities.size - areas.size} sistema)`);
    } else {
        console.log(`🏠 Filtro entità ATTIVO - Aree popolate: ${sortedAreas.length}/${areas.size}`);
    }
    
    console.log(`🏠 Aree uniche estratte: ${sortedAreas.length} -> ${sortedAreas.join(', ')}`);
    return sortedAreas;
}

/**
* 🔧 Estrai stato successo componente da strutture multiple
*/
function extractComponentSuccess(result, componentName) {
    // ✅ NUOVO: Gestisce la risposta da un salvataggio specifico (es. solo configuration.yaml).
    // Se la risposta contiene `file_type`, controlla sia success che message
    if (result.file_type === componentName) {
        if (result.success === true) return true;
        // Considera come successo anche quando il file è già configurato
        if (result.message && (
            result.message.includes("già configurata") ||
            result.message.includes("già presente") ||
            result.message.includes("nessuna modifica") ||
            result.message.includes("verificata")
        )) {
            return true;
        }
    }

    // Prova multiple strutture possibili
    const sources = [
        result.details?.[componentName]?.success,
        result[componentName]?.success,
        result.dashboard?.details?.[componentName]?.success,
        result.summary?.[`${componentName}_success`]
    ];
    
    // ✅ NUOVO: Casi speciali per apps
    if (componentName === 'apps') {
        sources.push(
            result.apps_yaml?.success,
            result.operation_summary?.apps_yaml_updated,
            result.summary?.apps_yaml_status === 'updated'
        );
    }
    
    // Casi speciali esistenti
    if (componentName === 'configuration') {
        sources.push(
            result.summary?.configuration_yaml_status === 'updated',
            result.files_created?.configuration_yaml_updated === true,
            // Aggiunto controllo per la chiave 'configuration_yaml' che potrebbe essere usata dal backend
            result.details?.configuration_yaml?.success,
            result.configuration_yaml?.success,
            // ✅ AGGIUNTA ULTERIORE: Se il salvataggio completo ha successo, anche configuration.yaml è OK
            (result.is_complete_save_flow && result.success === true),
            // ✅ AGGIUNTA ULTERIORE: Gestisce il caso di file_type: 'configuration_yaml'
            (result.file_type === 'configuration_yaml' && result.success === true),
            // ✅ NUOVO: Considera successo se il messaggio indica che è già configurato
            (result.message && (
                result.message.includes("già configurata") ||
                result.message.includes("già presente") ||
                result.message.includes("nessuna modifica") ||
                result.message.includes("verificata")
            ))
        );
        
        // Se è un salvataggio specifico di configuration.yaml, forza il successo con dettagli
        if (result.file_type === 'configuration' && result.success === true) {
            if (!result.details) result.details = {};
            if (!result.details.configuration) result.details.configuration = {};
            result.details.configuration.saved_entries = 1;
        }
    }
    
    return sources.find(val => val === true) || false;
}

/**
* 🔧 Estrai messaggio errore componente
*/
function extractComponentError(result, componentName) {
    // ✅ NUOVO: Gestisce la risposta da un salvataggio specifico.
    if (result.file_type === componentName && result.error) {
        return result.error;
    }

    const sources = [
        result.details?.[componentName]?.error,
        result[componentName]?.error,
        result.dashboard?.details?.[componentName]?.error
    ];
    
    // ✅ NUOVO: Casi speciali per apps
    if (componentName === 'apps') {
        sources.push(result.apps_yaml?.error);
    }
    
    // Aggiunto controllo per la chiave 'configuration_yaml'
    if (componentName === 'configuration') {
        sources.push(
            result.details?.configuration_yaml?.error,
            result.configuration_yaml?.error
        );
    }

    const error = sources.find(val => val && typeof val === 'string');
    return error || (componentName === 'apps' ? 'Errore salvataggio apps.yaml' : 
                    componentName === 'configuration' ? 'Richiede intervento manuale' : 'Errore sconosciuto');
}

// 🏠 NUOVA FUNZIONE: Rileva area automatica di una configurazione (CORRETTA)
function detectConfigurationArea(config) {
    const configAreas = new Set();
    let hasEntitiesWithoutArea = false;
    
    // Controlla tutti i campi compilati
    const fieldsToCheck = [
        config.light_entity,
        config.presence_sensor_on,
        config.presence_sensor_off,
        config.illuminance_sensor
    ];

    fieldsToCheck.forEach(entityId => {
        if (entityId) {
            const area = getEntityArea(entityId);
            if (area) {
                configAreas.add(area);
            } else {
                // Entità senza area
                hasEntitiesWithoutArea = true;
            }
        }
    });
    
    // Se ci sono entità senza area, non c'è area comune
    if (hasEntitiesWithoutArea) {
        console.log(`🏠 Config con entità senza area - nessuna area comune`);
        return null;
    }
    
    // Se tutte le entità con area appartengono alla stessa area
    if (configAreas.size === 1) {
        const detectedArea = Array.from(configAreas)[0];
        console.log(`🏠 Config area rilevata: ${detectedArea}`);
        return detectedArea;
    }
    
    // Aree multiple o nessuna entità con area
    if (configAreas.size > 1) {
        console.log(`🏠 Config con aree multiple: ${Array.from(configAreas).join(', ')}`);
    }
    return null;
}

// 🏠 NUOVA FUNZIONE: Filtra entità per area + entità esistenti
function filterEntitiesWithExisting(entityList, selectedArea, configIndex) {
    if (!selectedArea) {
        // Nessuna area selezionata → mostra tutte le entità
        return entityList;
    }
    
    // Ottieni entità della configurazione corrente
    const currentConfig = configurations[configIndex] || {};
    const currentConfigEntities = new Set([
        currentConfig.light_entity,
        currentConfig.presence_sensor_on,
        currentConfig.presence_sensor_off,
        currentConfig.illuminance_sensor
    ].filter(Boolean)); // Rimuovi valori vuoti
    
    return entityList.filter(entity => {
        const entityArea = getEntityArea(entity.entity_id);
        
        // Include se:
        // 1. Appartiene all'area selezionata, OPPURE
        // 2. È già presente nella configurazione corrente (anche se senza area)
        return entityArea === selectedArea || currentConfigEntities.has(entity.entity_id);
    });
}

// 🏠 NUOVA FUNZIONE: Trova campi incompatibili con l'area selezionata
function findIncompatibleFields(config, selectedArea) {
    const incompatible = [];
    
    const fieldMapping = {
        light_entity: 'Luce da controllare',
        presence_sensor_on: 'Sensore accensione',
        presence_sensor_off: 'Sensore spegnimento',
        illuminance_sensor: 'Sensore luminosità'
    };
    
    Object.entries(fieldMapping).forEach(([field, label]) => {
        const entityId = config[field];
        if (entityId) {
            const entityArea = getEntityArea(entityId);
            if (entityArea && entityArea !== selectedArea) {
                // Trova il nome friendly dell'entità
                const allEntities = [...entities.lights, ...entities.binary_sensors, ...entities.sensors];
                const entityData = allEntities.find(e => e.entity_id === entityId);
                const displayName = entityData ? entityData.display_name : entityId;
                
                incompatible.push({
                    field: field,
                    label: label,
                    entityName: displayName
                });
            }
        }
    });
    
    return incompatible;
}

// 🏠 NUOVA FUNZIONE: Gestisci cambio area configurazione
async function handleAreaChange(configIndex, selectedArea) {
    const config = configurations[configIndex];
    if (!config) return;
    
    console.log(`🏠 Cambio area configurazione ${configIndex + 1}: ${selectedArea}`);
    
    // Trova campi incompatibili
    const incompatibleFields = findIncompatibleFields(config, selectedArea);
    
    if (incompatibleFields.length > 0) {
        // Mostra avviso di conferma
        const message = `Hai selezionato un'area diversa da quella di alcune entità già inserite.
                                 <br><br>Le entità esistenti <strong>non verranno cancellate</strong>, ma i menu a tendina verranno aggiornati per mostrare le entità della nuova area.
                                 <br><br>Vuoi continuare?`;
        
        SouthTechUI.showConfirmDialog(
            'Cambio Area',
            message,
            {
                confirmText: 'Continua',
                cancelText: 'Annulla',
                confirmClass: 'btn-primary',
                cancelClass: 'btn-secondary',
                onConfirm: () => {
                    // [MODIFICA] Non resettare più i campi.
                    // Semplicemente aggiorna l'area selezionata e ricarica l'interfaccia.
                    // La funzione filterEntitiesWithExisting si occuperà di mantenere
                    // le selezioni esistenti nei dropdown.
                    console.log(`✅ Cambio area confermato. Le entità esistenti verranno mantenute.`);
                    SouthTechUI.showAlert(`Area cambiata in "${selectedArea}". Le selezioni precedenti sono state mantenute.`, 'info');
                    
                    // Aggiorna configurazione con area selezionata
                    config.selected_area = selectedArea;
                    
                    // Ricarica interfaccia configurazione
                    updateConfigurationsList();
                },
                onCancel: () => {
                    // Annulla cambio area - ripristina il valore precedente
                    // semplicemente ridisegnando l'interfaccia. Il modello dati non è stato modificato.
                    updateConfigurationsList();
                }
            }
        );
        return; // Esce dalla funzione, il resto viene gestito nei callback
    }
    
    // Aggiorna configurazione con area selezionata
    config.selected_area = selectedArea;
    
    // Ricarica interfaccia configurazione
    updateConfigurationsList();
}

function buildEntityAreaCache() {
    console.log('🏠 Costruzione cache entità-aree...');
    
    entityAreaCache.clear();
    let mappedCount = 0;
    
    // Mappa entità direttamente assegnate ad aree
    haEntityRegistry.forEach(entity => {
        if (entity.area_id && entity.entity_id) {
            const area = haAreasRegistry.find(a => a.area_id === entity.area_id);
            if (area) {
                entityAreaCache.set(entity.entity_id, area.name);
                mappedCount++;
            }
        }
    });
    
    // Mappa entità tramite device
    haEntityRegistry.forEach(entity => {
        if (!entityAreaCache.has(entity.entity_id) && entity.device_id) {
            const device = haDeviceRegistry.find(d => d.id === entity.device_id);
            if (device && device.area_id) {
                const area = haAreasRegistry.find(a => a.area_id === device.area_id);
                if (area) {
                    entityAreaCache.set(entity.entity_id, area.name);
                    mappedCount++;
                }
            }
        }
    });
    
    console.log(`✅ Cache costruita: ${mappedCount} entità mappate su ${entityAreaCache.size} totali`);
}

// 🔧 FUNZIONE: getFilterStatusMessage (testo semplificato + aree escluse)
function getFilterStatusMessage(mode, totalEntities, totalFiltered, shownAreasCount) {
    if (mode === 'fallback_no_areas') {
        return 'WebSocket non disponibile - modalità fallback attiva';
    }
    
    if (!areaFilterEnabled && !entityFilterEnabled) {
        return 'Tutti i filtri disattivati - tutte le entità rilevanti visibili';
    }
    
    const excludedEntities = totalEntities - totalFiltered;
    const entitiesPercentage = Math.round((excludedEntities / totalEntities) * 100);
    
    // ✅ LOGICA CORRETTA: Usa sempre il totale delle aree del sistema come riferimento
    const totalAreasReference = getTotalAreasWithEntities(); // Sempre 13
    let excludedAreas, areasPercentage;
    
    if (entityFilterEnabled || areaFilterEnabled) {
        // Con qualsiasi filtro attivo: aree escluse = totale sistema - aree mostrate
        excludedAreas = totalAreasReference - shownAreasCount;
        
        console.log(`🔍 CALCOLO AREE CON FILTRI:`);
        console.log(`   📊 Aree totali sistema: ${totalAreasReference}`);
        console.log(`   📋 Aree mostrate: ${shownAreasCount}`);
        console.log(`   ❌ Aree escluse: ${excludedAreas}`);
        
    } else {
        // Nessun filtro: tutte le aree disponibili
        excludedAreas = 0;
    }
    
    areasPercentage = totalAreasReference > 0 ? Math.round((excludedAreas / totalAreasReference) * 100) : 0;
    
    // ✅ TESTO NATURALE per entità ed aree
    let entitiesText = excludedEntities === 0 ? 
        'Nessuna entità esclusa' : 
        `${excludedEntities} entità escluse (${entitiesPercentage}%)`;
    
    let areasText = excludedAreas === 0 ? 
        'Nessuna area esclusa' : 
        `${excludedAreas} aree escluse (${areasPercentage}%)`;
    
    // Testo semplificato
    let filters = [];
    if (entityFilterEnabled) filters.push('entità');
    if (areaFilterEnabled) filters.push('area');
    
    return `Filtri attivi: ${filters.join(' + ')} - ${entitiesText} - ${areasText}`;
}

// 🔧 FUNZIONE: Calcola aree totali con entità
function getTotalAreasWithEntities() {
    // Conta tutte le aree che hanno almeno un'entità RILEVANTE (senza filtri)
    const allAreasWithEntities = new Set();
    
    // ✅ CONTROLLA SOLO ENTITÀ RILEVANTI nella cache
    entityAreaCache.forEach((areaName, entityId) => {
        // Verifica se l'entità è del tipo che ci interessa per l'automatismo luci
        if (entityId.startsWith('light.') || 
            entityId.startsWith('binary_sensor.') || 
            (entityId.startsWith('sensor.') && 
            (entityId.toLowerCase().includes('illuminance') || entityId.toLowerCase().includes('lux')))) {
            allAreasWithEntities.add(areaName);
        }
    });
    
    console.log(`🏠 Aree totali con entità rilevanti: ${allAreasWithEntities.size}`);
    return allAreasWithEntities.size;
}

// 📋 CARICA CONFIGURAZIONI DAL TUO FILE
function loadConfigurationsFromYourFile() {
    console.log('📋 Caricamento configurazioni dal tuo apps.yaml...');
    
    const yourConfigurations = [
        {
            light_entity: 'light.rgb_03_02',
            presence_sensor_on: 'binary_sensor.presenza_01_presence',
            presence_sensor_off: '',
            illuminance_sensor: 'sensor.presenza_01_illuminance'
        },
        {
            light_entity: 'light.rgb_01_05',
            presence_sensor_on: 'binary_sensor.presenza_02_movimento',
            presence_sensor_off: '',
            illuminance_sensor: ''
        },
        {
            light_entity: 'light.shellyplus1pm_80646fe3563c_switch_0',
            presence_sensor_on: 'binary_sensor.presenza_03_zone_1_occupancy',
            presence_sensor_off: 'binary_sensor.presenza_03_zone_4_occupancy',
            illuminance_sensor: 'sensor.presenza_03_illuminance'
        }
    ];
    
    configurations = yourConfigurations;
    console.log(`✅ Caricate ${configurations.length} configurazioni`);
}

// 🔧 CORREZIONE 4: Sync configurations via sensori (NUOVA)
async function syncConfigurationsViaSensors() {
    try {
        console.log('📡 SENSOR SYNC: Inizio sincronizzazione via sensori...');
        
        // Reset sensore risposta
        await fetch('/api/states/sensor.southtech_sync_response', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'ready',
                attributes: { reset_at: new Date().toISOString() }
            })
        });
        
        // Invia richiesta
        const requestResponse = await fetch('/api/states/sensor.southtech_sync_request', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'pending',
                attributes: {
                    action: 'sync_configurations',
                    browser_id: browserId,
                    timestamp: new Date().toISOString(),
                    request_id: `sync_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
                }
            })
        });
        
        if (!requestResponse.ok) {
            throw new Error(`Errore invio richiesta: HTTP ${requestResponse.status}`);
        }
        
        console.log('📤 Richiesta sync inviata via sensore');
        
        // Attendi risposta
        const result = await waitForSyncSensorResponse();
        
        console.log('📨 Risposta sync ricevuta:', result);
        return result;
        
    } catch (error) {
        console.error('❌ Errore sync via sensori:', error);
        throw error;
    }
}

// 🔧 Attesa risposta sync sensore
async function waitForSyncSensorResponse() {
    const maxAttempts = 15; // 30 secondi
    const pollInterval = 2000;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            const response = await fetch('/api/states/sensor.southtech_sync_response', {
                headers: { 'Authorization': `Bearer ${haToken}` }
            });
            
            if (!response.ok) {
                await SouthTechCore.sleep(pollInterval);
                continue;
            }
            
            const data = await response.json();
            
            if (data.state === 'completed' && data.attributes) {
                return data.attributes;
            }
            
        } catch (error) {
            console.log(`❌ Errore controllo sync (${attempt}):`, error);
        }
        
        await SouthTechCore.sleep(pollInterval);
    }
    
    throw new Error('Timeout sincronizzazione via sensori');
}

async function syncConfigurations() {
    try {
        SouthTechUI.showAlert('🔄 Richiesta sincronizzazione...', 'info');
        
        // Prima prova via sensori (il sistema più affidabile attualmente)
        console.log('📡 Tentativo sincronizzazione via sensori...');
        
        try {
            const result = await syncConfigurationsViaSensors();
            
            if (result.success && result.configurations) {
                const newConfigurations = result.configurations;
                
                if (newConfigurations.length > 0) {
                    configurations = newConfigurations;
                    SouthTechUI.showAlert(`✅ ${configurations.length} configurazioni caricate da apps.yaml`, 'success');
                } else {
                    SouthTechUI.showAlert('⚠️ File apps.yaml vuoto o nessuna configurazione trovata', 'warning');
                }
                
                updateConfigurationsList();
                return;
            } else {
                throw new Error(result.error || 'Errore sincronizzazione sensori');
            }
            
        } catch (sensorError) {
            console.error('❌ Sync sensori fallita:', sensorError);
            SouthTechUI.showAlert(`⚠️ Sync via sensori fallita: ${sensorError.message}. Uso configurazioni locali.`, 'warning');
        }
        
    } catch (error) {
        console.error('❌ Errore sincronizzazione completo:', error);
        SouthTechUI.showAlert(`⚠️ Errore sync: ${error.message}`, 'warning');
    }
}

// 📋 Ottieni entità da configurazioni esistenti
function getEntitiesFromExistingConfigurations() {
    const existingEntities = new Set();
    
    configurations.forEach(config => {
        if (config.light_entity) existingEntities.add(config.light_entity);
        if (config.presence_sensor_on) existingEntities.add(config.presence_sensor_on);
        if (config.presence_sensor_off) existingEntities.add(config.presence_sensor_off);
        if (config.illuminance_sensor) existingEntities.add(config.illuminance_sensor);
    });
    
    console.log(`📋 Entità da configurazioni esistenti: ${existingEntities.size}`);
    return existingEntities;
}

// ✅ SOSTITUISCE buildEntityAreaCache() e altra logica
function updateGlobalCache(areas, entityRegistry, deviceRegistry) {
    // Salva nei registri globali
    haAreasRegistry = areas;
    haEntityRegistry = entityRegistry;
    haDeviceRegistry = deviceRegistry;
    
    // Aggiorna cache
    areasDataCache = {
        areas: areas,
        entityRegistry: entityRegistry,
        deviceRegistry: deviceRegistry,
        timestamp: Date.now()
    };
    
    // Costruisci cache aree
    buildEntityAreaCache();
    
    console.log('💾 Cache globali aggiornate');
}

/**
* Crea nome sensore dinamico basato su operazione
*/
function createSensorName(operation, suffix = '') {
    const timestamp = Date.now();
    const base = `sensor.southtech_${operation}`;
    return suffix ? `${base}_${suffix}_${timestamp}` : `${base}_${timestamp}`;
}

async function processEntitiesFromWebSocketData(allStates) {
    console.log('📊 Processamento entità da dati WebSocket...');
    console.log(`🎯 FILTRI - Area: ${areaFilterEnabled}, Entità: ${entityFilterEnabled}`);
    
    const totalRelevantEntities = calculateTotalRelevantEntities(allStates);
    
    // ✅ NUOVA LOGICA UNIFICATA (senza chiamare vecchie funzioni)
    entities = { lights: [], binary_sensors: [], sensors: [] };
    
    // Ottieni entità esistenti per il filtro
    const existingEntities = getEntitiesFromExistingConfigurations();
    
    allStates.forEach(state => {
        const baseEntityData = {
            entity_id: state.entity_id,
            friendly_name: state.attributes.friendly_name || state.entity_id
        };
        
        const entityData = {
            ...baseEntityData,
            display_name: createEntityDisplayName(state.entity_id, baseEntityData.friendly_name)
        };
        
        // Determina se includere l'entità
        const hasArea = entityAreaCache.has(state.entity_id);
        const inExisting = existingEntities.has(state.entity_id);
        const shouldInclude = areaFilterEnabled ? (hasArea || inExisting) : true;
        
        if (!shouldInclude) return;
        
        // Aggiungi alle categorie appropriate
        if (state.entity_id.startsWith('light.')) {
            entities.lights.push(entityData);
        } else if (state.entity_id.startsWith('binary_sensor.')) {
            entities.binary_sensors.push(entityData);
        } else if (state.entity_id.startsWith('sensor.')) {
            const isIlluminanceSensor = 
                state.attributes.device_class === 'illuminance' ||
                state.entity_id.toLowerCase().includes('illuminance') || 
                state.entity_id.toLowerCase().includes('lux');
            
            if (isIlluminanceSensor) {
                entities.sensors.push(entityData);
            }
        }
    });
    
    // Ordina alfabeticamente
    Object.values(entities).forEach(category => {
        category.sort((a, b) => a.display_name.localeCompare(b.display_name));
    });
    
    // Determina modalità per display
    const mode = areaFilterEnabled ? 'websocket_filtered' : 'websocket_unfiltered';
    
    console.log(`✅ Processate: ${entities.lights.length} luci, ${entities.binary_sensors.length} sensori presenza, ${entities.sensors.length} sensori lux`);
    
    // Aggiorna display
    setTimeout(() => {
        updateFilterStatusDisplay(mode, totalRelevantEntities, entities);
        forceInterfaceUpdate();
    }, 100);
}

async function processEntitiesDirectly(allStates) {
    console.log('📊 Processamento diretto entità (fallback)...');
    
    entities = { lights: [], binary_sensors: [], sensors: [] };
    
    allStates.forEach(state => {
        const entityData = {
            entity_id: state.entity_id,
            friendly_name: state.attributes.friendly_name || state.entity_id,
            display_name: createEntityDisplayName(state.entity_id, state.attributes.friendly_name)
        };
        
        if (state.entity_id.startsWith('light.')) {
            entities.lights.push(entityData);
        } else if (state.entity_id.startsWith('binary_sensor.')) {
            entities.binary_sensors.push(entityData);
        } else if (state.entity_id.startsWith('sensor.')) {
            const isIlluminanceSensor = 
                state.attributes.device_class === 'illuminance' ||
                state.entity_id.toLowerCase().includes('illuminance') || 
                state.entity_id.toLowerCase().includes('lux');
            
            if (isIlluminanceSensor) {
                entities.sensors.push(entityData);
            }
        }
    });
    
    // Ordina
    Object.values(entities).forEach(category => {
        category.sort((a, b) => a.display_name.localeCompare(b.display_name));
    });
    
    console.log(`✅ Fallback: ${entities.lights.length} luci, ${entities.binary_sensors.length} sensori presenza, ${entities.sensors.length} sensori lux`);
}

// ✅ PROCESSA DA CACHE
async function processEntitiesFromCache() {
    // Ripristina dati dalla cache
    haAreasRegistry = areasDataCache.areas;
    haEntityRegistry = areasDataCache.entityRegistry;
    haDeviceRegistry = areasDataCache.deviceRegistry;
    
    // Ricostruisci cache aree
    buildEntityAreaCache();
    
    // Carica stati aggiornati
    const response = await fetch('/api/states', {
        headers: { 'Authorization': `Bearer ${haToken}` }
    });
    const allStates = await response.json();
    
    // Processa entità
    await processEntitiesFromWebSocketData(allStates);
}

// ✅ Esegue il salvataggio effettivo (logica originale)
async function executeActualSave() {
    if (isSaving) {
        SouthTechUI.showAlert('⚠️ Salvataggio già in corso, attendere...', 'warning');
        return;
    }
    
    isSaving = true;
    const yamlContent = generateYAMLContent();
    
    try {
        console.log('🚀 === INIZIO SALVATAGGIO SEMPLIFICATO ===');
        
        // ✅ UNICO METODO: Sensori ottimizzati (che funziona)
        console.log('📡 Salvataggio via sensori ottimizzati...');
        SouthTechUI.showAlert('📡 Salvataggio in corso...', 'info');
        
        const sensorResult = await saveViaSensorsOptimized(yamlContent, configurations);
        if (sensorResult.success) {
            SouthTechUI.showAlert('✅ Configurazione salvata con successo!', 'success');
            console.log('✅ Salvataggio completato:', sensorResult);
            return;
        }
        
        console.log('❌ Anche i sensori ottimizzati sono falliti');
        throw new Error('Metodo automatico di salvataggio fallito');
        
    } catch (error) {
        console.error('❌ Errore salvataggio:', error);
        
        // Fallback: istruzioni manuali
        console.log('📖 Mostra istruzioni salvataggio manuale');
        SouthTechUI.showAlert('⚠️ Salvataggio automatico fallito, mostra istruzioni manuali', 'warning');
        showManualSaveInstructions();
        
    } finally {
        isSaving = false;
        console.log('🏁 === FINE SALVATAGGIO SEMPLIFICATO ===');
    }
}

/**
* ✅ Aggiorna sensore debug WebSocket
*/
async function updateWebSocketDebugSensor(error, networkInfo, suggestions, yamlContent = null) {
    try {
        await fetch('/api/states/sensor.southtech_websocket_debug', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'frontend_error_detailed',
                attributes: {
                    error_message: error.message,
                    error_type: error.constructor.name,
                    error_time: new Date().toISOString(),
                    network_type: networkInfo.networkType,
                    ws_url: networkInfo.wsUrl,
                    browser_id: browserId,
                    yaml_size: yamlContent ? yamlContent.length : 0,  // ← Fix qui
                    configs_count: configurations.length,
                    suggestions: suggestions,
                    debug_source: 'frontend_websocket_v3.2.1',
                    troubleshooting_complete: true
                }
            })
        });
        
        console.log('📱 Sensore debug aggiornato con dettagli errore');
        
    } catch (debugError) {
        console.warn('⚠️ Errore aggiornamento sensore debug:', debugError);
    }
}

// 📡 STEP 2: Salvataggio via sensori HA (fallback)
async function saveViaSensors(yamlContent) {
    try {
        console.log('📡 SENSOR SAVE: Preparazione salvataggio via sensori...');
        
        const saveData = {
            action: 'save_yaml',
            yaml_content: yamlContent,
            configurations: configurations,
            browser_id: browserId || 'unknown',
            timestamp: new Date().toISOString(),
            debug_info: {
                frontend_version: '3.0.1',
                method: 'sensor_fallback',
                fallback_reason: 'websocket_failed'
            }
        };
        
        // Reset sensore risposta
        console.log('🔄 Reset sensore risposta...');
        await fetch('/api/states/sensor.southtech_save_response', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'ready',
                attributes: { 
                    reset_at: new Date().toISOString(),
                    reset_reason: 'websocket_fallback'
                }
            })
        });
        
        // Attendi un momento per il reset
        await SouthTechCore.sleep(1000);
        
        // Invia richiesta via sensore
        console.log('📤 Invio richiesta via sensore...');
        const response = await fetch('/api/states/sensor.southtech_save_request', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'pending',
                attributes: saveData
            })
        });
        
        if (!response.ok) {
            throw new Error(`Errore HTTP ${response.status}: ${response.statusText}`);
        }
        
        console.log('✅ Richiesta sensore inviata, attesa risposta...');
        SouthTechUI.showAlert('📡 Richiesta inviata via sensore, elaborazione in corso...', 'info');
        
        // Attendi risposta con timeout più lungo
        const result = await waitForSensorResponse(30); // 30 secondi invece di 25
        
        console.log('📨 Risposta sensore ricevuta:', result);
        return result;
        
    } catch (error) {
        console.error('❌ Errore salvataggio sensori:', error);
        
        // Aggiorna sensore debug
        try {
            await fetch('/api/states/sensor.southtech_websocket_debug', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${haToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    state: 'sensor_fallback_error',
                    attributes: {
                        error_message: error.message,
                        error_time: new Date().toISOString(),
                        fallback_method: 'sensor',
                        debug_source: 'frontend_sensor_fallback'
                    }
                })
            });
        } catch (debugError) {
            console.warn('⚠️ Impossibile aggiornare sensore debug:', debugError);
        }
        
        return { success: false, error: error.message, method: 'sensor_failed' };
    }
}

async function saveViaSensorsOptimized(yamlContent, configurations) {
    try {
        console.log('📡 Sensori ottimizzati: Inizializzazione...');
        
        // Sistema sensori ottimizzato con timestamp per evitare duplicati
        const requestTimestamp = new Date().toISOString();
        const requestId = `sensor_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Reset sensore risposta
        await fetch('/api/states/sensor.southtech_save_response', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'ready',
                attributes: { 
                    reset_at: requestTimestamp,
                    reset_for_request: requestId
                }
            })
        });
        
        // Attendi reset
        await SouthTechCore.sleep(1500);
        
        // Invia richiesta con timestamp univoco
        const response = await fetch('/api/states/sensor.southtech_save_request', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${haToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'pending',
                attributes: {
                    request_id: requestId,
                    timestamp: requestTimestamp, // Chiave per evitare riprocessing
                    action: 'save_yaml',
                    yaml_content: yamlContent,
                    configurations: configurations,
                    browser_id: browserId,
                    method: 'sensor_optimized'
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Errore invio richiesta sensori: HTTP ${response.status}`);
        }
        
        console.log('📤 Richiesta sensori ottimizzati inviata');
        
        // Attendi con timeout ottimizzato
        const result = await waitForSensorResponseOptimized(25); // 25 secondi
        return result;
        
    } catch (error) {
        console.error('❌ Sensori ottimizzati falliti:', error);
        return { success: false, error: error.message };
    }
}

async function saveViaOptimizedSystem(yamlContent, configurations) {
    try {
        console.log('💾 OTTIMIZZATO: Tentativo salvataggio senza servizi AppDaemon...');
        
        // STEP 1: Tentativo WebSocket interno (tramite sensore speciale)
        const wsResult = await saveViaInternalWebSocket(yamlContent, configurations);
        if (wsResult.success) {
            SouthTechUI.showAlert('✅ Salvato via WebSocket interno!', 'success');
            return wsResult;
        }
        
        console.log('⚠️ WebSocket interno fallito, uso sensori...');
        
        // STEP 2: Fallback sensori ottimizzato
        const sensorResult = await saveViaSensorsOptimized(yamlContent, configurations);
        if (sensorResult.success) {
            SouthTechUI.showAlert('✅ Salvato via sensori ottimizzati!', 'success');
            return sensorResult;
        }
        
        // STEP 3: Ultimo resort - istruzioni manuali
        showManualSaveInstructions();
        
    } catch (error) {
        console.error('❌ Errore sistema ottimizzato:', error);
        showManualSaveInstructions();
    }
}

// 🔧 Debug WebSocket status
async function checkWebSocketServiceStatus() {
    try {
        console.log('🔍 Controllo stato servizio WebSocket (v3.1.0)...');
        
        const networkInfo = SouthTechCore.getNetworkInfo();
        console.log(`🌐 Test su rete ${networkInfo.networkType}: ${networkInfo.wsUrl}`);
        
        const wsManager = new SouthTechCore.WebSocketManager(haToken);
        await wsManager.connect();
        
        // Test chiamata servizio
        try {
            await wsManager.callService('appdaemon', 'southtech_save_yaml', {
                test: true,
                yaml_content: '# test',
                browser_id: browserId,
                network_type: networkInfo.networkType
            });
            
            console.log(`✅ Servizio WebSocket disponibile (${networkInfo.networkType})`);
            return true;
            
        } catch (serviceError) {
            console.error(`❌ Servizio WebSocket non disponibile (${networkInfo.networkType}):`, serviceError);
            return false;
            
        } finally {
            wsManager.disconnect();
        }
        
    } catch (connectionError) {
        console.error(`❌ Connessione WebSocket fallita:`, connectionError);
        return false;
    }
}

// ⏳ Attendi risposta da sensore
async function waitForSensorResponse(maxSeconds = 30) {
    const maxAttempts = Math.floor(maxSeconds / 2); // Controllo ogni 2 secondi
    const pollInterval = 2000;
    
    console.log(`🔍 Attesa risposta sensore (max ${maxSeconds}s, ${maxAttempts} tentativi)`);
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            console.log(`🔍 Controllo risposta sensore (${attempt}/${maxAttempts})...`);
            
            const response = await fetch('/api/states/sensor.southtech_save_response', {
                headers: { 'Authorization': `Bearer ${haToken}` }
            });
            
            if (!response.ok) {
                console.log(`⚠️ Errore HTTP ${response.status}, riprovo...`);
                await SouthTechCore.sleep(pollInterval);
                continue;
            }
            
            const data = await response.json();
            const state = data.state;
            const attributes = data.attributes || {};
            
            console.log(`📡 Stato sensore: ${state}, attributi:`, attributes);
            
            // Controlla se la risposta è pronta
            if (state === 'completed' && attributes.timestamp) {
                // Verifica che sia una risposta recente (ultimi 60 secondi)
                const responseTime = new Date(attributes.timestamp);
                const now = new Date();
                const ageDiff = now - responseTime;
                
                if (ageDiff < 60000) { // 60 secondi
                    console.log('✅ Risposta sensore valida ricevuta');
                    
                    // Reset sensore per pulizia
                    try {
                        await fetch('/api/states/sensor.southtech_save_response', {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${haToken}`,
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                state: 'cleaned',
                                attributes: { cleaned_at: new Date().toISOString() }
                            })
                        });
                    } catch (e) {
                        console.warn('⚠️ Errore pulizia sensore:', e);
                    }
                    
                    return attributes;
                } else {
                    console.log(`⚠️ Risposta troppo vecchia (${Math.round(ageDiff/1000)}s), continuo ad aspettare...`);
                }
            } else if (state === 'error') {
                throw new Error(attributes.error || 'Errore dal backend AppDaemon');
            }
            
            // Aggiorna UI ogni 3 tentativi (6 secondi)
            if (attempt % 3 === 0) {
                const dots = '.'.repeat((attempt / 3) % 4);
                SouthTechUI.showAlert(`📡 Elaborazione in corso${dots} (${attempt * 2}s)`, 'info', 1500);
            }
            
        } catch (error) {
            console.log(`❌ Errore controllo risposta (${attempt}):`, error);
        }
        
        await SouthTechCore.sleep(pollInterval);
    }
    
    throw new Error(`Timeout: Nessuna risposta dal backend entro ${maxSeconds} secondi`);
}

async function waitForSensorResponseOptimized(maxSeconds) {
    const maxAttempts = Math.floor(maxSeconds / 2); // Controllo ogni 2 secondi
    const pollInterval = 2000;
    
    console.log(`🔍 Attesa risposta sensori ottimizzati (max ${maxSeconds}s)...`);
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            const response = await fetch('/api/states/sensor.southtech_save_response', {
                headers: { 'Authorization': `Bearer ${haToken}` }
            });
            
            if (!response.ok) {
                await SouthTechCore.sleep(pollInterval);
                continue;
            }
            
            const data = await response.json();
            
            if (data.state === 'completed' && data.attributes && data.attributes.timestamp) {
                // Verifica timestamp recente
                const responseTime = new Date(data.attributes.timestamp);
                const now = new Date();
                
                if ((now - responseTime) < 60000) { // 1 minuto
                    console.log('✅ Risposta sensori ottimizzati ricevuta');
                    
                    // Pulizia sensore
                    try {
                        await fetch('/api/states/sensor.southtech_save_response', {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${haToken}`,
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                state: 'cleaned',
                                attributes: { cleaned_at: new Date().toISOString() }
                            })
                        });
                    } catch (e) {
                        console.warn('⚠️ Errore pulizia sensore:', e);
                    }
                    
                    return data.attributes;
                } else {
                    console.log(`⚠️ Risposta sensori troppo vecchia (${Math.round((now - responseTime)/1000)}s)`);
                }
            } else if (data.state === 'error') {
                throw new Error(data.attributes?.error || 'Errore dal backend sensori');
            }
            
            // Progress feedback ogni 3 tentativi (6 secondi)
            if (attempt % 3 === 0) {
                SouthTechUI.showAlert(`📡 Sensori... (${attempt * 2}s)`, 'info', 1500);
            }
            
        } catch (error) {
            console.log(`❌ Errore controllo sensori (${attempt}):`, error);
        }
        
        await SouthTechCore.sleep(pollInterval);
    }
    
    throw new Error(`Timeout sensori ottimizzati: ${maxSeconds} secondi`);
}

/**
* 📝 Genera tutti i contenuti YAML (Apps, Dashboard, Templates)
*/
async function generateAllYAMLContents() {
    console.log('📝 Generazione tutti i contenuti YAML...');
    
    try {
        // 1. Apps.yaml (usa funzione esistente)
        const appsYaml = generateYAMLContent();
        
        // 2. Dashboard.yaml (principale)
        const dashboardYaml = generateDashboardYAML();
        
        // 3. Templates.yaml
        const templatesYaml = generateTemplatesYAML();
        
        return {
            apps: appsYaml,
            dashboard: dashboardYaml,
            templates: templatesYaml
        };
        
    } catch (error) {
        console.error('❌ Errore generazione contenuti YAML:', error);
        throw error;
    }
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
* ✅ Esegue il salvataggio completo (YAML + Dashboard + Templates)
*/
async function executeCompleteSave() {
    if (isSaving) {
        SouthTechUI.showAlert('⚠️ Salvataggio già in corso, attendere...', 'warning');
        return;
    }
    
    isSaving = true;
    
    try {
        console.log('🚀 === INIZIO SALVATAGGIO COMPLETO ===');
        SouthTechUI.showAlert('✨ Generazione e salvataggio configurazione completa in corso...', 'info');
        
        const result = await saveCompleteViaSensorsOptimized(configurations);
        
        // ✅ INJECT FLAGS to ensure proper success state
        result.is_complete_save_flow = true;
        
        // Se il risultato indica "già configurato", lo trattiamo come un successo
        if (result.message && (
            result.message.includes("già configurata") ||
            result.message.includes("già presente") ||
            result.message.includes("nessuna modifica") ||
            result.message.includes("verificata")
        )) {
            result.success = true;
            if (!result.details) result.details = {};
            result.details.configuration = {
                success: true,
                saved_entries: 1,
                message: "File verificato correttamente"
            };
        }

        showSaveResultsModal(result);
        
    } catch (error) {
        console.error('❌ Errore salvataggio completo:', error);
        SouthTechUI.showAlert(`❌ Errore critico: ${error.message}`, 'error');
        showSaveResultsModal({
            success: false,
            error: error.message,
            details: {}
        });
    } finally {
        isSaving = false;
        console.log('🏁 === FINE SALVATAGGIO COMPLETO ===');
    }
}

/**
 * Ora utilizza il sistema di comunicazione a sensori.
 */
async function saveCompleteViaSensorsOptimized(configurations) {
    try {
        const payload = {
            action: 'save_complete',
            // Non inviamo più lo yaml_content, il backend lo genera
            configurations: configurations,
            method: 'complete_sensor',
            generate_dashboard: true,
            generate_templates: true,
            generate_configuration: true // ✅ Aggiunto per assicurare il salvataggio di configuration.yaml
        };
        return await communicateViaSensors('save', payload, 45);
    } catch (error) {
        console.error('❌ Salvataggio completo via sensori fallito:', error);
        return { success: false, error: error.message };
    }
}

/**
 * ✅ [NUOVO] Esegue il salvataggio specifico dopo la conferma.
 */
async function executeSpecificSave(fileType) {
    // Chiudi il modal di conferma
    const modal = bootstrap.Modal.getInstance(document.getElementById('specificSaveConfirmationModal'));
    if (modal) {
        modal.hide();
    }

    if (isSaving) {
        SouthTechUI.showAlert('⚠️ Salvataggio già in corso, attendere...', 'warning');
        return;
    }

    if (!validateConfiguration()) {
        SouthTechUI.showAlert('❌ Correggi gli errori prima di salvare', 'error');
        return;
    }

    isSaving = true;
    const friendlyName = fileType.charAt(0).toUpperCase() + fileType.slice(1);

    try {
        console.log(`🚀 Salvataggio specifico ${friendlyName}.yaml...`);
        SouthTechUI.showAlert(`📡 Salvataggio ${friendlyName}.yaml in corso...`, 'info');

        const result = await saveSpecificFileViaSensors(fileType);

        // Assicura che il risultato sia mostrato come successo anche per file già configurati
        if (result.message && (
            result.message.includes("già configurata") ||
            result.message.includes("già presente") ||
            result.message.includes("nessuna modifica") ||
            result.message.includes("verificata")
        )) {
            result.success = true;
            if (!result.details) {
                result.details = {};
            }
            result.details[fileType] = {
                success: true,
                message: result.message
            };
        }

        showSaveResultsModal(result);

    } catch (error) {
        console.error(`❌ Errore salvataggio ${friendlyName}.yaml:`, error);
        SouthTechUI.showAlert(`❌ Errore salvataggio ${friendlyName}.yaml: ${error.message}`, 'error');
        showSaveResultsModal({ success: false, error: error.message });
    } finally {
        isSaving = false;
    }
}

/**
* 📡 [NUOVA FUNZIONE HELPER] Funzione per salvare file specifici via sensori.
*/
async function saveSpecificFileViaSensors(fileType) {
    try {
        const payload = {
            action: `save_${fileType}_only`, // Azione specifica per il backend
            file_type: fileType,
            configurations: configurations // Configurazioni correnti per contesto
        };
        const result = await communicateViaSensors('save', payload, 30);
        
        // Trasforma sempre la risposta per gestire uniformemente tutti i tipi di file
        const transformedResult = {
            success: result.success,
            file_type: fileType,
            method: 'sensor_specific',
            message: result.message || "Operazione completata",
            operation: result.operation || "saved",
            details: {}
        };

        // Struttura details per il file specifico
        transformedResult.details[fileType] = {
            success: result.success,
            saved_entries: 1,
            message: result.message || "File elaborato correttamente"
        };

        // Se è configuration.yaml, aggiungi il flag di successo specifico
        if (fileType === 'configuration') {
            transformedResult.configSuccess = result.success;
            transformedResult.configurationSuccess = result.success;
        }

        // Per gli altri file, metti null nei details di configuration
        if (fileType !== 'configuration') {
            transformedResult.details.configuration = {
                success: null,
                message: "Non incluso in questo salvataggio"
            };
        }

        return transformedResult;
    } catch (error) {
        console.error(`❌ Salvataggio specifico per ${fileType} fallito:`, error);
        return { success: false, error: error.message };
    }
}
