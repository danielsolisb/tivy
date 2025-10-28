// static/js/rule_editor.js

$(document).ready(function() {
    console.log("rule_editor.js cargado con filtro de estación y flujo corregido.");

    // --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
    const configElement = document.getElementById('editor-config');
    //const API_RULES_URL = configElement.dataset.apiRulesUrl;
    // Aseguramos que la URL base de la API de reglas siempre termine con una barra inclinada
    let baseUrl = configElement.dataset.apiRulesUrl;
    if (!baseUrl.endsWith('/')) {
        baseUrl += '/';
    }
    const API_RULES_URL = baseUrl;
    const API_STATIONS_URL = configElement.dataset.apiStationsUrl;
    const API_SENSORS_URL = configElement.dataset.apiSensorsUrl;
    const API_POLICIES_URL = configElement.dataset.apiPoliciesUrl;
    const CSRF_TOKEN = configElement.dataset.csrfToken;

    let currentRuleId = null;
    let selectedStationId = null;

    const container = document.getElementById("drawflow");
    const editor = new Drawflow(container);

    editor.start();
    editor.reroute = true;
    editor.editor_mode = 'edit';
    editor.zoom_max = 1.2;
    editor.zoom_min = 0.3;

    console.log("Editor de Drawflow iniciado con zoom y paneo habilitado.");

    // --- 2. DEFINICIÓN DE NODOS PERSONALIZADOS ---
    const availableNodes = {
        sensor: { name: 'Fuente: Sensor', content: `<div><strong>Fuente: Sensor</strong><hr><div class="main-content"><label>Seleccione un sensor:</label><select df-source_sensor class="api-select sensor-select"></select></div></div>`, inputs: 0, outputs: 1 },
        static_value: { name: 'Fuente: Valor Estático', content: `<div><strong>Fuente: Valor Estático</strong><hr><div class="main-content"><label>Valor numérico:</label><input type="number" df-static_value step="any" value="0"></div></div>`, inputs: 0, outputs: 1 },
        policy: { name: 'Fuente: Política de Alerta', content: `<div><strong>Fuente: Política de Alerta</strong><hr><div class="main-content"><label>Seleccione una política:</label><select df-linked_policy class="api-select policy-select" data-url="${API_POLICIES_URL}"></select></div></div>`, inputs: 0, outputs: 1 },
        operator: { name: 'Condición: Comparar', content: `<div><strong>Condición: Comparar</strong><hr><div class="main-content"><label>Operador:</label><select df-operator><option value=">">Mayor que (&gt;)</option><option value="<">Menor que (&lt;)</option><option value="==">Igual a (==)</option></select></div></div>`, inputs: 2, outputs: 1 },
        logical_op: { name: 'Lógica: Unir Condiciones', content: `<div><strong>Lógica: Unir Condiciones</strong><hr><div class="main-content"><select df-logical_operator><option value="AND">Y (AND)</option><option value="OR">O (OR)</option></select></div></div>`, inputs: 2, outputs: 1 },
        rule_output: { name: 'Acción: Generar Alerta', content: `<div><strong>Acción: Generar Alerta</strong><hr><div class="main-content"><label>Nombre de la Regla:</label><input type="text" df-name placeholder="Ej: Sobrecalentamiento"><label>Severidad:</label><select df-severity><option value="INFO">Informativo</option><option value="WARNING">Advertencia</option><option value="CRITICAL">Crítico</option></select></div></div>`, inputs: 1, outputs: 0 }
    };

    // --- 3. FUNCIONES AUXILIARES Y DE CARGA ---
    async function populateSelect(selectElement, valueToSelect = null) {
        let url = selectElement.dataset.url;

        if (selectElement.classList.contains('sensor-select')) {
            if (!selectedStationId) {
                selectElement.innerHTML = '<option value="">Primero seleccione una estación</option>';
                return;
            }
            url = `${API_SENSORS_URL}?station_id=${selectedStationId}`;
        }

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Network response was not ok for ${url}`);
            const data = await response.json();
            
            const currentSelectedValue = selectElement.value;
            selectElement.innerHTML = '<option value="">Seleccione...</option>';
            
            data.forEach(item => {
                const option = document.createElement('option');
                option.value = item.id;
                option.textContent = item.display_name || item.name || item.label;
                selectElement.appendChild(option);
            });

            // Re-seleccionar el valor si es posible
            if (valueToSelect) {
                selectElement.value = valueToSelect;
            } else {
                selectElement.value = currentSelectedValue;
            }

        } catch (error) { console.error(`Error cargando datos para select desde ${url}:`, error); }
    }

    editor.on('nodeCreated', function(nodeId) {
        const nodeElement = document.querySelector(`#node-${nodeId}`);
        const selects = nodeElement.querySelectorAll('.api-select');
        selects.forEach(select => populateSelect(select));
    });

    async function populateRulesDropdown() {
        try {
            const response = await fetch(API_RULES_URL);
            if (!response.ok) throw new Error('Failed to fetch rules');
            const rules = await response.json();
            const dropdown = document.getElementById('rules-dropdown');
            dropdown.innerHTML = '<option value="">--- Cargar Regla Existente ---</option>';
            rules.forEach(rule => {
                const option = document.createElement('option');
                option.value = rule.id;
                option.textContent = rule.name;
                dropdown.appendChild(option);
            });
        } catch (error) { console.error("Error al cargar la lista de reglas:", error); }
    }
    
    async function populateStationsDropdown() {
        try {
            const response = await fetch(API_STATIONS_URL);
            if (!response.ok) throw new Error('Failed to fetch stations');
            const stations = await response.json();
            const dropdown = document.getElementById('stations-dropdown');
            dropdown.innerHTML = '<option value="">--- Seleccione Estación ---</option>';
            stations.forEach(station => {
                const option = document.createElement('option');
                option.value = station.id;
                option.textContent = station.name;
                dropdown.appendChild(option);
            });
        } catch (error) { console.error("Error al cargar la lista de estaciones:", error); }
    }
    
    $('#stations-dropdown').on('change', function() {
        selectedStationId = $(this).val();
        console.log(`Estación seleccionada: ${selectedStationId}`);
        editor.clear();
        $('#rules-dropdown').val('');

        if (selectedStationId) {
            $('#rules-dropdown').prop('disabled', false);
            $('#btn-new-rule').prop('disabled', false);
             $.niftyNoty({
                type: 'info',
                icon : 'fa fa-info-circle',
                message : `Estación seleccionada: "${$(this).find("option:selected").text()}". Puede cargar o crear una regla.`,
                container : 'floating',
                timer : 4000
            });
        } else {
            $('#rules-dropdown').prop('disabled', true);
            $('#btn-new-rule').prop('disabled', true);
        }
    });
    
    $('#rules-dropdown').on('change', function() {
        const ruleId = $(this).val();
        if (ruleId) {
            loadRuleGraph(ruleId);
        }
    });

    function createNewRuleTemplate() {
        if (!selectedStationId) {
            alert("Por favor, seleccione una estación antes de crear una nueva regla.");
            return;
        }
        editor.clear();
        currentRuleId = null;
        $('#rules-dropdown').val('');
        $('#btn-delete-rule').prop('disabled', true);  //delete
        const sensorData = availableNodes.sensor;
        editor.addNode('sensor', sensorData.inputs, sensorData.outputs, 100, 200, 'sensor', {}, sensorData.content);
        const outputData = availableNodes.rule_output;
        editor.addNode('rule_output', outputData.inputs, outputData.outputs, 500, 200, 'rule_output', {}, outputData.content);
    }

    // --- 4. LÓGICA DE CARGA DE GRAFOS (Sin cambios en su lógica interna) ---
    // ... [La función loadRuleGraph y drawNodeAndChildren permanecen exactamente igual que en la versión anterior]
    async function loadRuleGraph(ruleId) {
    currentRuleId = ruleId;
    editor.clear();
    $('#btn-delete-rule').prop('disabled', false);
    console.log(`Pidiendo datos para la regla ID: ${ruleId}`);

    try {
        const response = await fetch(`${API_RULES_URL}${ruleId}/`);
        if (!response.ok) throw new Error(`Error en la API: ${response.statusText}`);
        const ruleData = await response.json();
        console.log("Datos de la regla recibidos:", ruleData);

        if (!ruleData.nodes || ruleData.nodes.length === 0) {
            console.warn("La regla no tiene nodos para dibujar.");
            createNewRuleTemplate();
            return;
        }

        const outputTemplate = availableNodes.rule_output;
        const outputDfId = editor.addNode('rule_output', outputTemplate.inputs, outputTemplate.outputs, 1500, 400, 'rule_output', {}, outputTemplate.content);

        const rootNode = ruleData.nodes[0];
        const { nodeId: finalNodeId } = await drawNodeAndChildren(rootNode, 1100, 400);

        if(finalNodeId) {
            editor.addConnection(finalNodeId, outputDfId, 'output_1', 'input_1');
        }

        setTimeout(() => {
            const outputElement = document.querySelector(`#node-${outputDfId}`);
            if (outputElement) {
                outputElement.querySelector('[df-name]').value = ruleData.name;
                outputElement.querySelector('[df-severity]').value = ruleData.severity;
                editor.updateNodeDataFromId(outputDfId, { name: ruleData.name, severity: ruleData.severity });
            }

            if (finalNodeId) {
                // --- CORRECCIÓN FINAL ---
                editor.zoom_reset(); // Usamos la función que sabemos que es segura.
                editor.zoom_out();
            }

            console.log("Grafo de la regla cargado y dibujado correctamente.");

        }, 500);

    } catch (error) {
        console.error("Error al cargar el grafo de la regla:", error);
        $('#btn-delete-rule').prop('disabled', true);
        currentRuleId = null; 
        alert("No se pudo cargar la regla seleccionada.");
    }
}
    
    async function drawNodeAndChildren(backendNode, x, y) {
    const HORIZONTAL_SPACING = 350;
    const VERTICAL_SPACING = 150;

    if (backendNode.node_type === 'OP') {
        const opTemplate = availableNodes.logical_op;
        const opDfId = editor.addNode('logical_op', opTemplate.inputs, opTemplate.outputs, x, y, 'logical_op', {}, opTemplate.content);

        setTimeout(() => {
            const opElement = document.querySelector(`#node-${opDfId}`);
            if (opElement) {
                opElement.querySelector('[df-logical_operator]').value = backendNode.logical_operator;
                // --- CORRECCIÓN AÑADIDA ---
                editor.updateNodeDataFromId(opDfId, { logical_operator: backendNode.logical_operator });
            }
        }, 200);

        let totalHeight = 0;
        let y_offset = y;

        if (backendNode.children && backendNode.children.length > 0) {
            const child1Result = await drawNodeAndChildren(backendNode.children[0], x - HORIZONTAL_SPACING, y_offset);
            editor.addConnection(child1Result.nodeId, opDfId, 'output_1', 'input_1');
            
            y_offset += child1Result.totalHeight / 2 + VERTICAL_SPACING / 2;
            
            const child2Result = await drawNodeAndChildren(backendNode.children[1], x - HORIZONTAL_SPACING, y_offset);
            editor.addConnection(child2Result.nodeId, opDfId, 'output_1', 'input_2');
            
            totalHeight = y_offset + child2Result.totalHeight / 2 - y;

            const centerY = (child1Result.y + child2Result.y) / 2;
            const node = editor.getNodeFromId(opDfId);
            node.pos_y = centerY;
            editor.updateNodeDataFromId(opDfId, { pos_y: centerY });
        }
        const finalNode = editor.getNodeFromId(opDfId);
        return { nodeId: opDfId, totalHeight: Math.max(totalHeight, VERTICAL_SPACING), y: finalNode.pos_y };
    }
    
    if (backendNode.node_type === 'COND' && backendNode.condition) {
        const condition = backendNode.condition;

        const opTemplate = availableNodes.operator;
        const opDfId = editor.addNode('operator', opTemplate.inputs, opTemplate.outputs, x, y, 'operator', {}, opTemplate.content);
        
        const sensorTemplate = availableNodes.sensor;
        const sensorDfId = editor.addNode('sensor', sensorTemplate.inputs, sensorTemplate.outputs, x - HORIZONTAL_SPACING, y - 75, 'sensor', {}, sensorTemplate.content);
        editor.addConnection(sensorDfId, opDfId, 'output_1', 'input_1');

        let thresholdDfId;
        if (condition.threshold_type === 'STATIC') {
            const staticValTemplate = availableNodes.static_value;
            thresholdDfId = editor.addNode('static_value', staticValTemplate.inputs, staticValTemplate.outputs, x - HORIZONTAL_SPACING, y + 75, 'static_value', {}, staticValTemplate.content);
        } else {
            const policyTemplate = availableNodes.policy;
            thresholdDfId = editor.addNode('policy', policyTemplate.inputs, policyTemplate.outputs, x - HORIZONTAL_SPACING, y + 75, 'policy', {}, policyTemplate.content);
        }
        editor.addConnection(thresholdDfId, opDfId, 'output_1', 'input_2');

        setTimeout(async () => {
            // --- BLOQUE DE CORRECCIÓN PRINCIPAL ---
            const sensorElement = document.querySelector(`#node-${sensorDfId}`);
            if (sensorElement) {
                await populateSelect(sensorElement.querySelector('[df-source_sensor]'), condition.source_sensor);
                // Forzamos la actualización de datos internos de Drawflow para el sensor
                editor.updateNodeDataFromId(sensorDfId, { source_sensor: condition.source_sensor });
            }

            const opElement = document.querySelector(`#node-${opDfId}`);
            if (opElement) {
                opElement.querySelector('[df-operator]').value = condition.operator;
                // Forzamos la actualización para el operador
                editor.updateNodeDataFromId(opDfId, { operator: condition.operator });
            }
            
            const thresholdElement = document.querySelector(`#node-${thresholdDfId}`);
            if (thresholdElement) {
                if(condition.threshold_type === 'STATIC') {
                     thresholdElement.querySelector('[df-static_value]').value = condition.threshold_config.value;
                     // Forzamos la actualización para el valor estático
                     editor.updateNodeDataFromId(thresholdDfId, { static_value: condition.threshold_config.value });
                } else {
                     await populateSelect(thresholdElement.querySelector('[df-linked_policy]'), condition.linked_policy);
                     // Forzamos la actualización para la política
                     editor.updateNodeDataFromId(thresholdDfId, { linked_policy: condition.linked_policy });
                }
            }
        }, 300);

        return { nodeId: opDfId, totalHeight: VERTICAL_SPACING, y: y };
    }
    
    return { nodeId: null, totalHeight: 0, y: y };
}

    // --- 5. NUEVA LÓGICA DE GUARDADO ---
    
    /**
     * Transforma el JSON de Drawflow en un formato anidado que la API puede entender.
     * @param {string} startNodeId - El ID del nodo final (el nodo de 'rule_output').
     * @param {object} allNodes - El objeto completo con todos los nodos del grafo de Drawflow.
     * @returns {object|null} - El nodo raíz de la regla en formato API, o null si hay error.
     */
   function transformDrawflowToAPI(startNodeId, allNodes) {
    const startNode = allNodes[startNodeId];
    if (!startNode || !startNode.inputs.input_1.connections.length > 0) {
        console.error("No hay nada conectado al nodo de salida de la regla.");
        return null;
    }

    const firstConnection = startNode.inputs.input_1.connections[0];
    const rootNodeId = firstConnection.node;

    function buildTree(nodeId) {
        const dfNode = allNodes[nodeId];
        const apiNode = {};

        if (dfNode.name === 'logical_op') {
            apiNode.node_type = 'OP';
            // --- CORRECCIÓN FINAL ---
            // Leemos el valor del operador lógico y lo añadimos al payload.
            apiNode.logical_operator = dfNode.data.logical_operator;
            apiNode.children = [];

            const input1 = dfNode.inputs.input_1.connections[0];
            const input2 = dfNode.inputs.input_2.connections[0];

            if (input1) apiNode.children.push(buildTree(input1.node));
            if (input2) apiNode.children.push(buildTree(input2.node));

        } else if (dfNode.name === 'operator') {
            apiNode.node_type = 'COND';

            const condition = {
                name: "Condición generada automáticamente",
                metric_to_evaluate: 'VALUE',
                operator: dfNode.data.operator,
            };

            const source1NodeId = dfNode.inputs.input_1.connections[0].node;
            const source2NodeId = dfNode.inputs.input_2.connections[0].node;

            const source1Node = allNodes[source1NodeId];
            const source2Node = allNodes[source2NodeId];

            const sensorNode = source1Node.name === 'sensor' ? source1Node : source2Node;
            const thresholdNode = source1Node.name !== 'sensor' ? source1Node : source2Node;

            condition.source_sensor = sensorNode.data.source_sensor;

            if(thresholdNode.name === 'static_value') {
                condition.threshold_type = 'STATIC';
                condition.threshold_config = { value: thresholdNode.data.static_value };
                condition.linked_policy = null;
            } else {
                condition.threshold_type = 'POLICY';
                condition.linked_policy = thresholdNode.data.linked_policy;
                condition.threshold_config = {};
            }
            apiNode.condition = condition;
        }
        return apiNode;
    }

    return buildTree(rootNodeId);
}
    /**
 * Orquesta el proceso de validación, transformación y envío de la regla a la API.
 */
async function saveRuleGraph() {
    console.log("Iniciando proceso de guardado...");
    
    if (!selectedStationId) {
        alert("Error: No se ha seleccionado una estación. Por favor, elija una de la lista.");
        return;
    }

    const exportData = editor.export();
    const nodes = exportData.drawflow.Home.data;
    
    let outputNodeId = null;
    let outputNodeData = null;

    // Encontrar el nodo de salida para obtener el nombre y la severidad.
    for (const id in nodes) {
        if (nodes[id].name === 'rule_output') {
            outputNodeId = id;
            outputNodeData = nodes[id].data;
            break;
        }
    }

    if (!outputNodeId || !outputNodeData.name) {
        alert("Error: La regla debe tener un nombre. Por favor, añádalo en el nodo 'Generar Alerta'.");
        return;
    }
    
    // Transformar el grafo a la estructura que espera la API
    const rootNode = transformDrawflowToAPI(outputNodeId, nodes);
    if (!rootNode) {
        alert("Error: La estructura de la regla es inválida. Asegúrese de que todos los nodos estén conectados correctamente.");
        return;
    }
    
    // Construir el payload final para la API
    const payload = {
        name: outputNodeData.name,
        description: '', //agregado
        // --- ¡ESTA ES LA LÍNEA QUE FALTABA! ---
        // Añadimos la severidad desde los datos del nodo de salida.
        severity: outputNodeData.severity,
        is_active: true,
        nodes_data: [rootNode] // La API espera una lista
    };

    console.log("Payload a enviar:", JSON.stringify(payload, null, 2));

    // Determinar si es una nueva regla (POST) o una actualización (PUT)
    const isUpdate = currentRuleId !== null;
    const url = isUpdate ? `${API_RULES_URL}${currentRuleId}/` : API_RULES_URL;
    const method = isUpdate ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json();
            // Mostramos el error específico que nos da el backend
            throw new Error(JSON.stringify(errorData));
        }

        const savedRule = await response.json();
        console.log("Respuesta de la API:", savedRule);

        $.niftyNoty({
            type: 'success',
            icon : 'fa fa-check',
            message : `Regla "${savedRule.name}" guardada con éxito.`,
            container : 'floating',
            timer : 5000
        });
        
        // Actualizar la lista de reglas y seleccionar la recién guardada/actualizada
        await populateRulesDropdown();
        $('#rules-dropdown').val(savedRule.id);
        currentRuleId = savedRule.id;

    } catch (error) {
        console.error("Error al guardar la regla:", error);
        alert("Ocurrió un error al guardar la regla. Revise la consola para más detalles.");
    }
}

/**
 * Funcion para borrado
 */
/**
 * Gestiona la eliminación de la regla actual.
 */
async function deleteRule() {
    if (!currentRuleId) {
        alert("No hay una regla cargada para eliminar.");
        return;
    }

    // Mensaje de confirmación
    const ruleNameToDelete = $('#rules-dropdown option:selected').text();
    if (!confirm(`¿Está seguro de que desea eliminar la regla "${ruleNameToDelete}"? Esta acción no se puede deshacer.`)) {
        return;
    }

    console.log(`Iniciando eliminación de la regla ID: ${currentRuleId}`);

    try {
        const response = await fetch(`${API_RULES_URL}${currentRuleId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': CSRF_TOKEN
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(JSON.stringify(errorData));
        }

        $.niftyNoty({
            type: 'success',
            icon : 'fa fa-check',
            message : `Regla "${ruleNameToDelete}" eliminada con éxito.`,
            container : 'floating',
            timer : 5000
        });

        // Limpiar y actualizar la UI
        editor.clear();
        currentRuleId = null;
        $('#rules-dropdown').val('');
        $('#btn-delete-rule').prop('disabled', true);
        await populateRulesDropdown();

    } catch (error) {
        console.error("Error al eliminar la regla:", error);
        alert("Ocurrió un error al eliminar la regla. Revise la consola para más detalles.");
    }
}

    // --- 6. EVENTOS DE UI Y ARRANQUE ---
    $('#btn-new-rule').on('click', createNewRuleTemplate);
    $('#btn-save-rule').on('click', saveRuleGraph); // ¡Funcionalidad activada!
    $('#btn-delete-rule').on('click', deleteRule); //delete
    $('#zoom-in-btn').on('click', () => editor.zoom_in());
    $('#zoom-out-btn').on('click', () => editor.zoom_out());
    $('#zoom-reset-btn').on('click', () => editor.zoom_reset());

    window.addEventListener("click", function() {
        const menu = document.getElementById("context-menu");
        if (menu && menu.style.display === "block") {
            menu.style.display = "none";
        }
    });

    editor.on('contextmenu', function (event) {
        event.preventDefault();
        const menu = document.getElementById("context-menu");
        menu.style.display = "block";
        menu.style.left = event.clientX + 'px';
        menu.style.top = event.clientY + 'px';
        menu.innerHTML = '';
        Object.entries(availableNodes).forEach(([key, nodeInfo]) => {
            const menuItem = document.createElement('a');
            menuItem.href = '#';
            menuItem.textContent = nodeInfo.name;
            menuItem.addEventListener('click', function(e) {
                e.preventDefault();
                const pos_x = (event.clientX * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom))) - (editor.precanvas.getBoundingClientRect().x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)));
                const pos_y = (event.clientY * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom))) - (editor.precanvas.getBoundingClientRect().y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)));
                editor.addNode(key, nodeInfo.inputs, nodeInfo.outputs, pos_x, pos_y, key, {}, nodeInfo.content);
            });
            menu.appendChild(menuItem);
        });
    });

    // --- FUNCIÓN DE INICIALIZACIÓN SECUENCIAL ---
    async function initializeApp() {
        // Deshabilitar controles hasta que se seleccione una estación
        $('#rules-dropdown').prop('disabled', true);
        $('#btn-new-rule').prop('disabled', true);

        // Paso 1: Cargar estaciones y esperar a que termine.
        await populateStationsDropdown();
        console.log("Dropdown de estaciones cargado.");

        // Paso 2: Cargar reglas (opcional, pero las deja listas)
        await populateRulesDropdown();
        console.log("Dropdown de reglas cargado.");

        console.log("Inicialización completada.");
    }

    // --- INICIO DE LA APLICACIÓN ---
    initializeApp();
});

// este archivo funciona