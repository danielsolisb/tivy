// static/js/monitor_tecnico.js
(function(){
  "use strict";

  // ============================
  // CONFIG & STATE
  // ============================
  const CFG = window.MONTEC_CONFIG || {};
  const API_SENSORS = CFG?.apis?.sensors || "";
  const API_HISTORY = CFG?.apis?.history || "";
  const MQTT_HOST = CFG?.mqtt?.host || "localhost";
  const MQTT_PORT = Number(CFG?.mqtt?.port || 8081);

  const AXIS_STEP = 26;   // separación entre ejes Y
  const MAX_SENSORS = 10; // límite práctico que acordamos
  let GRID_LEFT = 0;   // margen efectivo a la izquierda del grid (se setea en buildChart)

  const Y_POINTER_FONT = 8;        // ⬅️ tamaño del número (sube/baja aquí)
  const Y_POINTER_BG_ALPHA = 0.75;  // ⬅️ opacidad del fondo (0..1). Prueba 0.6–0.85

  let mqttClient = null;
  let currentStationId = null;
  let currentStationName = "";
  let isLiveMode = true;

  let highlightedId = null; 

  let sensors = [];               // [{id,name,unit,site,color,min_value,max_value,topic}]
  let sensorById = {};            // id -> sensor
  let sensorIdxById = {};         // id -> index (orden por site)
  let seriesBuffers = {};         // id -> [ [Date, value], ... ]
  let lastValue = {};             // id -> último valor

  let chart = null;
  let currentRange = "5m";        // default

  

  const timescaleMs = (r) => {
    switch(r){
      case "5m":  return 5 * 60 * 1000;
      case "30m": return 30 * 60 * 1000;
      case "1h":  return 60 * 60 * 1000;
      case "3h":  return 3 * 60 * 60 * 1000;
      case "6h":  return 6 * 60 * 60 * 1000;
      case "12h": return 12 * 60 * 60 * 1000;
      default:    return 5 * 60 * 1000;
    }
  };

  document.addEventListener("DOMContentLoaded", init);

  // ============================
  // INIT
  // ============================
  function init(){
    // chips
    initRangeChips();

    // botones
    const btnLoad = document.getElementById("load-sensors-btn");
    btnLoad?.addEventListener("click", onLoadSensors);

    const backLive = document.getElementById("back-to-live");
    backLive?.addEventListener("click", () => backToLive(true));

    // instanciar chart
    chart = echarts.init(document.getElementById("multiscale-chart"));

    // ESC => quitar resaltado
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') resetHighlight(); });

    // Click en el fondo del panel derecho => quitar resaltado
    const panelBg = document.getElementById('values-panel-tech');
    panelBg?.addEventListener('click', (e) => { if (e.target === panelBg) resetHighlight(); });


    // resize
    window.addEventListener("resize", () => chart?.resize());
  }

  // ============================
  // UI handlers
  // ============================
  function onLoadSensors(){
  const sel = document.getElementById("station-select");
  currentStationId = parseInt(sel?.value || "", 10);
  currentStationName = sel?.selectedOptions?.[0]?.dataset?.name || "";

  if(!currentStationId){
    alert("Selecciona una estación.");
    return;
  }

  // reset state
  sensors = [];
  sensorById = {};
  sensorIdxById = {};
  seriesBuffers = {};
  lastValue = {};

  // 1) cargar sensores + conexión de estación (host/port)
  fetchSensors(currentStationId)
    .then(payload => {
      // payload: { stationConn, list }
      const list = (payload?.list || []).slice(0, MAX_SENSORS);
      sensors = list;

      // mapear
      sensors.forEach((s, idx) => {
        sensorById[s.id] = s;
        sensorIdxById[s.id] = idx;
        seriesBuffers[s.id] = [];
        lastValue[s.id] = null;
      });

      // guardo la conexión para usarla en MQTT
      sensors._conn = payload?.stationConn || null;

      buildChart(sensors);
      renderRightPanel();

      // 2) histórico del rango actual
      return fetchHistory(currentStationId, currentRange);
    })
    .then(historyData => {
      // 3) aplicar histórico y suscribir MQTT por IP/puerto y topic EXACTO
      applyHistory(historyData);
      subscribeStation(sensors._conn);

      setTimeout(()=>chart.resize(),0);
    })
    .catch(err => {
      console.error("onLoadSensors error:", err);
      alert("Error cargando sensores/histórico.");
    });
}


  function initRangeChips(){
    const chips = document.querySelectorAll(".range-chips .chip");
    chips.forEach(ch => {
      ch.addEventListener("click", () => {
        chips.forEach(x => x.classList.remove("active"));
        ch.classList.add("active");
        currentRange = ch.dataset.range;
        if(currentStationId){
          // pedir histórico para nuevo rango
          fetchHistory(currentStationId, currentRange)
            .then(historyData => {
              applyHistory(historyData);
              backToLive(true); // volver a vivo tras cambiar rango
            })
            .catch(console.error);
        }
      });
    });
    // seleccionar 5m por defecto
    const def = Array.from(chips).find(x => x.dataset.range === "5m");
    def && def.classList.add("active");
  }

  function setLiveUI(on){
    isLiveMode = !!on;
    const node = document.getElementById("live-indicator");
    const back = document.getElementById("back-to-live");
    if(node){
      node.classList.remove("on","off");
      node.classList.add(on ? "on" : "off");
      node.textContent = on ? "En vivo" : "Pausado";
    }
    if(back){
      back.style.display = on ? "none" : "inline-block";
    }
  }

  function backToLive(forceToEnd){
    if(!chart) return;
    const opt = chart.getOption();
    if(!opt || !opt.dataZoom || !opt.dataZoom.length) return;
    // mover el slider a 100% para seguir en vivo
    // usamos el primer dataZoom slider que apliquemos
    const dzIndex = opt.dataZoom.findIndex(z => z.type === 'slider');
    if(dzIndex >= 0){
      opt.dataZoom[dzIndex].end = 100;
      chart.setOption({ dataZoom: opt.dataZoom });
    }
    setLiveUI(true);
  }

  // ============================
  // FETCH
  // ============================
 async function fetchSensors(stationId){
  const url = API_SENSORS.replace("{station_id}", String(stationId));
  const res = await fetch(url, { credentials: 'same-origin' });
  if(!res.ok) throw new Error("fetchSensors failed");
  const json = await res.json();

  const stationConn = {
    host:  json?.station?.mqtt_host ?? json?.station?.ip ?? null,
    port:  Number(json?.station?.mqtt_port ?? json?.station?.port ?? 8081),
    useSSL: true  // ← opcional; ya no se usa, pero mejor dejarlo coherente
  };

  const list = Array.isArray(json?.sensors) ? json.sensors : [];
  list.sort((a,b) => {
    const sa = (a.site ?? 999999), sb = (b.site ?? 999999);
    if(sa !== sb) return sa - sb;
    return (a.id ?? 0) - (b.id ?? 0);
  });

  const normalized = list.map(s => ({
    ...s,
    mqtt_topic: s.mqtt_topic ?? s.topic ?? null
  }));

  return { stationConn, list: normalized };
}


  async function fetchHistory(stationId, range){
    const url = API_HISTORY.replace("{station_id}", String(stationId)) + `?timescale=${encodeURIComponent(range)}`;
    const res = await fetch(url, { credentials: 'same-origin' });
    if(!res.ok) throw new Error("fetchHistory failed");
    return await res.json(); // { sensorId: [ [iso,value], ... ], ... }
  }

  // ============================
  // CHART
  // ============================
function buildChart(sensors){
  if(!chart) return;

  const pointerLabelStyle = {
    show: true,
    fontSize: 10,
    padding: [2, 4, 2, 4],
    backgroundColor: 'rgba(0,0,0,0.65)',
    color: '#fff',
    borderRadius: 3,
    shadowBlur: 0
  };

  const xAxis = [{
    type: 'time',
    axisLabel: { formatter: ts => timeLabel(ts), fontSize: 11, color: '#6b7280' },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisPointer: { label: pointerLabelStyle }
  }];

  const yAxis = [];
  const series = [];
  const colors = sensors.map(s => s.color || '#3b82f6');

  sensors.forEach((s, i) => {
    const axisIndex = i;
    const offset = i * AXIS_STEP;

    yAxis.push({
      type: 'value',
      position: 'left',
      offset,
      axisLine: { lineStyle: { color: s.color || '#3b82f6', width: 2 } },
      axisTick: { show: false },
      axisLabel: {
        fontSize: 8,
        color: s.color || '#3b82f6',
        margin: 0,
        hideOverlap: true,
        formatter: v => String(v),
        showMinLabel: true,
        showMaxLabel: true,
      },
      name: (s.unit || ''),
      nameLocation: 'start',
      nameTextStyle: { color: s.color || '#3b82f6', fontSize: 10, fontWeight: 600 },
      nameGap: 10,
      splitNumber: 4,
      splitLine: { show: (i === 0), lineStyle: { color: '#eceff1' } },
      min: (s.min_value != null) ? s.min_value : null,
      max: (s.max_value != null) ? s.max_value : null,

      // ⬇️ label lateral del crosshair (coloreado por sensor y más grande)
      axisPointer: {
        label: {
          show: true,
          fontSize: Y_POINTER_FONT,                      // <— controla el tamaño aquí
          padding: [2, 4, 2, 4],
          color: '#fff',
          backgroundColor: hexToRgba(s.color || '#3b82f6', Y_POINTER_BG_ALPHA),
          borderRadius: 3,
          shadowBlur: 0
        }
      }
    });

    series.push({
      name: s.name,
      type: 'line',
      yAxisIndex: axisIndex,
      showSymbol: false,
      smooth: false,
      sampling: 'lttb',
      lineStyle: { width: 1.8, color: s.color || colors[i] },
      data: [],
      emphasis: { focus: 'series' },
    });
  });

  // margen izquierdo con holgura para el cuadrito lateral
  const BASE_LEFT = 30;
  const EXTRA_FOR_POINTER = 7; // súbelo si agrandas más la fuente
  const gridLeft = ((sensors.length ? (sensors.length - 1) : 0) * AXIS_STEP) + BASE_LEFT + EXTRA_FOR_POINTER;
  GRID_LEFT = gridLeft;

  const dataZoom = [
    { type: 'inside', xAxisIndex: [0] },
    { type: 'slider', xAxisIndex: [0], bottom: 2, height: 24 }
  ];

  const tooltip = {
  trigger: 'axis',
  axisPointer: { type: 'cross', snap: true, label: pointerLabelStyle },
  confine: true,
  enterable: false,
  extraCssText: 'pointer-events:none;border-radius:8px;padding:8px 10px;',
  position: function (pos, params, dom, rect, size) {
    const viewW = size.viewSize[0], boxW  = size.contentSize[0], boxH  = size.contentSize[1];
    let x = pos[0] + 18;
    let y = pos[1] - boxH - 12;
    if (x + boxW + 10 > viewW) x = pos[0] - boxW - 18;
    x = Math.max(GRID_LEFT + 8, x);
    if (y < 6) y = pos[1] + 12;
    return [x, y];
  },
  // === NUEVO: mostramos TODOS los sensores usando el histórico en memoria ===
  formatter: function(params){
    if(!params || !params.length) return '';

    // ts al que apunta el crosshair
    const tsAny   = params[0].axisValue ?? params[0].value?.[0];
    const target  = (tsAny instanceof Date) ? tsAny.getTime() : new Date(tsAny).getTime();
    const d       = new Date(target);

    // cabecera con fecha/hora
    let html = `<div style="min-width:260px">
                  <div style="font-weight:700;margin-bottom:6px">${fmtDateTime(d)}</div>`;

    // 1) primero, la serie “en foco” (la que ECharts puso arriba en params[0])
    const highlightedName = params[0].seriesName;
    const highlighted     = sensors.find(s => s.name === highlightedName);
    if (highlighted){
      const sid     = highlighted.id;
      const nearest = nearestValue(seriesBuffers[sid], target);
      const unit    = highlighted.unit || '';
      const color   = highlighted.color || params[0].color;
      const valText = (nearest.value == null) ? '--' : Number(nearest.value).toFixed(2);

      html += `<div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:6px;">
                 <span style="display:flex;align-items:center;gap:6px;">
                   <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
                   <span style="font-weight:600">${highlighted.name}</span>
                 </span>
                 <span style="font-weight:700;font-size:16px;">${valText} ${unit}</span>
               </div>`;
    }

    // 2) el resto de sensores (ordenados como en el chart)
    sensors.forEach((s) => {
      if (s.name === highlightedName) return;
      const sid     = s.id;
      const nearest = nearestValue(seriesBuffers[sid], target);
      const unit    = s.unit || '';
      const color   = s.color || '#888';
      const valText = (nearest.value == null) ? '--' : Number(nearest.value).toFixed(2);

      html += `<div style="display:flex;justify-content:space-between;gap:12px;">
                 <span style="display:flex;align-items:center;gap:6px;">
                   <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
                   ${s.name}
                 </span>
                 <span style="font-weight:600">${valText} ${unit}</span>
               </div>`;
    });

    html += `</div>`;
    return html;
  }
};


  chart.setOption({
    color: colors,
    grid: { left: gridLeft, right: 10, top: 24, bottom: 30 },
    xAxis, yAxis, series, dataZoom, tooltip,
    axisPointer: { type: 'cross', snap: true, label: pointerLabelStyle, lineStyle: { width: 1 }, crossStyle: { width: 1 } },
    animation: false,
  });

  chart.off('dataZoom');
  chart.on('dataZoom', function(){
    const opt = chart.getOption();
    const dz = (opt.dataZoom && opt.dataZoom.length > 1) ? opt.dataZoom[1] : null;
    if (!dz) return;
    const atRight = (typeof dz.end === 'number') ? (dz.end > 99) : true;
    setLiveUI(atRight);
  });

  chart.getZr().off('dblclick');
  chart.getZr().on('dblclick', () => resetHighlight());
  chart.getZr().off('click');
  chart.getZr().on('click', (e) => {
    if (!highlightedId) return;
    const pt = [e.offsetX, e.offsetY];
    if (chart.containPixel('grid', pt)) resetHighlight();
  });

  
}


function hexToRgba(hex, a = 1){
  // admite "#RRGGBB" o "#RGB"
  let c = hex.replace('#','');
  if (c.length === 3) c = c.split('').map(ch => ch+ch).join('');
  const r = parseInt(c.slice(0,2),16);
  const g = parseInt(c.slice(2,4),16);
  const b = parseInt(c.slice(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}

function applyHistory(historyData){
    // historyData: { sensorId: [ [iso,value], ... ] }
    sensors.forEach(s => {
      const arr = historyData[String(s.id)] || historyData[s.id] || [];
      const mapped = arr.map(pair => [ new Date(pair[0]), Number(pair[1]) ]);
      seriesBuffers[s.id] = mapped;
      if(mapped.length){
        lastValue[s.id] = mapped[mapped.length-1][1];
      }
    });
    flushSeriesToChart();
    renderRightPanel();
  }

  function flushSeriesToChart(){
    if(!chart) return;
    const opt = chart.getOption();
    if(!opt || !opt.series) return;

    sensors.forEach((s, i) => {
      opt.series[i].data = seriesBuffers[s.id];
    });
    chart.setOption({ series: opt.series }, { silent: true });
  }

  // ============================
  // MQTT
  // ============================
  
  function subscribeStation(stationConn) {
  // Cierra cliente previo
  try { mqttClient?.disconnect(); } catch (_) {}
  mqttClient = null;

  // Mapa topic -> sensorId según lo que devuelve tu API (sin tocar las barras)
  const topicMap = new Map();
  sensors.forEach(s => {
    const t = (s.mqtt_topic ?? s.topic) || null;
    if (t) topicMap.set(t, s.id);
  });

  // Igual que en monitor.html: proxys WSS por Nginx en /mqtt (puerto 443)
  const HOST     = window.location.hostname;            // p.ej. gasmart.ecuapulselab.com
  const PORT     = 443;
  const WS_PATH  = "/mqtt";
  const USE_SSL  = (location.protocol === "https:");
  const clientId = "montec_" + Math.random().toString(16).slice(2, 10);

  // ⬇️ Constructor de 4 argumentos (estable)
  mqttClient = new Paho.MQTT.Client(HOST, Number(PORT), WS_PATH, clientId);
  mqttClient._topicMap = topicMap;

  // Handlers
  mqttClient.onMessageArrived = onMessageArrived;
  mqttClient.onConnectionLost = (resp) => {
    console.warn("MQTT desconectado:", resp?.errorMessage || resp);
  };

  const connectOpts = {
    useSSL: USE_SSL,
    cleanSession: true,
    keepAliveInterval: 60,
    timeout: 8,
    onSuccess: () => {
      console.log(`MQTT conectado a wss://${HOST}:${PORT}${WS_PATH}`);
      // Suscripciones EXACTAS a los topics de la API
      topicMap.forEach((_, t) => {
        try {
          mqttClient.subscribe(t, { qos: 0 });
          console.log("Suscrito:", t);
        } catch (e) {
          console.error("Error suscribiendo", t, e);
        }
      });

      // (opcional) debug para ver todo lo que llega
      // try { mqttClient.subscribe('#', { qos: 0 }); console.log("DEBUG: suscrito a #"); } catch {}
    },
    onFailure: (e) => {
      console.error("MQTT conexión fallida", e);
    }
  };

  console.log("Conectando MQTT por WSS vía /mqtt …");
  mqttClient.connect(connectOpts);
}





 function onMessageArrived(message){
  const topic   = message?.destinationName || "";
  const payload = message?.payloadString;
  if (payload == null) return;

  // DEBUG (si quieres, luego lo quitas)
  console.log("MQTT ▶", topic, payload);

  // 1) Match directo por topic exacto
  const byTopicId = mqttClient?._topicMap?.get(topic);
  if (byTopicId) {
    const val = Number(payload);
    if (!Number.isNaN(val)) pushPoint(byTopicId, new Date(), val);
    return;
  }

  // 2) Fallback legado /Estacion/Sensor/...
  const parts = topic.split("/").filter(Boolean);
  if(parts.length >= 2){
    const station = parts[0];
    const sensorName = parts[1];
    if(station === currentStationName){
      const sensor = sensors.find(s => s.topic === sensorName || s.name === sensorName);
      if(sensor){
        const val = Number(payload);
        if(!Number.isNaN(val)) pushPoint(sensor.id, new Date(), val);
      }
    }
  }
}


  // ============================
  // DATA PUSH & RANGE
  // ============================
  function pushPoint(sensorId, ts, value){
    const buf = seriesBuffers[sensorId] || (seriesBuffers[sensorId] = []);
    buf.push([ts, value]);
    lastValue[sensorId] = value;

    // purga por ventana
    const windowMs = timescaleMs(currentRange);
    const cutoff = Date.now() - windowMs;
    while(buf.length && buf[0][0].getTime() < cutoff){
      buf.shift();
    }

    // expandir eje si se sale de min/max
    recalcYAxisIfOutOfRange(sensorId);

    // pintar
    flushSeriesToChart();
    // si estamos al final, mantenemos el slider en 100%
    if(isLiveMode) backToLive(false);

    // refrescar panel derecho
    renderRightPanel();
  }

  function recalcYAxisIfOutOfRange(sensorId){
    if(!chart) return;
    const s = sensorById[sensorId];
    if(!s) return;
    const opt = chart.getOption();
    const idx = sensorIdxById[sensorId];
    const y = opt.yAxis?.[idx];
    if(!y) return;

    const data = seriesBuffers[sensorId] || [];
    if(!data.length) return;
    const vals = data.map(d => d[1]);
    const dmin = Math.min.apply(null, vals);
    const dmax = Math.max.apply(null, vals);

    const baseMin = (s.min_value != null) ? Number(s.min_value) : null;
    const baseMax = (s.max_value != null) ? Number(s.max_value) : null;

    if(baseMin != null && dmin < baseMin) y.min = 'dataMin';
    if(baseMax != null && dmax > baseMax) y.max = 'dataMax';

    chart.setOption({ yAxis: opt.yAxis }, { silent: true });
  }

  // ============================
  // PANEL DERECHO
  // ============================
function renderRightPanel(){
  const panel = document.getElementById("values-panel-tech");
  if(!panel) return;
  panel.innerHTML = "";

  sensors.forEach(s => {
    const val = lastValue[s.id];
    const color = s.color || '#3b82f6';

    const item = document.createElement("div");
    item.className = "live-card" + (highlightedId === s.id ? " active" : "");
    item.innerHTML = `
      <div class="head">
        <span class="color-dot" style="background:${color}"></span>
        <span class="name-text">${s.name}</span><span class="colon">:</span>
      </div>
      <div class="reading">
        <span class="val">${val==null ? '--' : Number(val).toFixed(2)}</span>
        <span class="unit">${s.unit || ''}</span>
      </div>
    `;
    item.addEventListener("click", () => {
      // toggle: si hago click sobre el mismo, quito el resaltado
      if (highlightedId === s.id) {
        resetHighlight();
      } else {
        highlightSensor(s.id);
      }
    });
    panel.appendChild(item);
  });
}


function highlightSensor(sensorId){
  if(!chart) return;
  const s = sensorById[sensorId];
  if(!s) return;

  highlightedId = sensorId;

  const opt = chart.getOption();
  if(!opt || !opt.series || !opt.yAxis) return;

  // series
  opt.series.forEach((ser,i) => {
    const isMe = (sensors[i]?.id === sensorId);
    ser.lineStyle = ser.lineStyle || {};
    ser.lineStyle.opacity = isMe ? 1.0 : 0.20;
    ser.lineStyle.width = isMe ? 2.6 : 1.0;
  });

  // ejes
  opt.yAxis.forEach((ya,i) => {
    const baseColor = sensors[i]?.color || '#3b82f6';
    const isMe = (sensors[i]?.id === sensorId);
    ya.axisLabel = ya.axisLabel || {};
    ya.axisLine = ya.axisLine || {};
    ya.axisLabel.color = isMe ? baseColor : '#c5cbd3';
    ya.axisLine.lineStyle = ya.axisLine.lineStyle || {};
    ya.axisLine.lineStyle.color = baseColor;
    ya.axisLine.lineStyle.width = isMe ? 2.4 : 1.2;
    ya.nameTextStyle = ya.nameTextStyle || {};
    ya.nameTextStyle.color = isMe ? baseColor : '#c5cbd3';
  });

  chart.setOption({ series: opt.series, yAxis: opt.yAxis }, { silent: true });
  renderRightPanel();
}

function resetHighlight(){
  if(!chart) return;
  highlightedId = null;

  const opt = chart.getOption();
  if(!opt || !opt.series || !opt.yAxis) return;

  // restaurar estilos base
  opt.series.forEach((ser,i) => {
    const col = sensors[i]?.color || '#3b82f6';
    ser.lineStyle = ser.lineStyle || {};
    ser.lineStyle.opacity = 1.0;
    ser.lineStyle.width = 1.8;
    ser.lineStyle.color = col;
  });
  opt.yAxis.forEach((ya,i) => {
    const col = sensors[i]?.color || '#3b82f6';
    ya.axisLabel = ya.axisLabel || {};
    ya.axisLine = ya.axisLine || {};
    ya.axisLabel.color = col;
    ya.axisLine.lineStyle = ya.axisLine.lineStyle || {};
    ya.axisLine.lineStyle.color = col;
    ya.axisLine.lineStyle.width = 2;
    ya.nameTextStyle = ya.nameTextStyle || {};
    ya.nameTextStyle.color = col;
  });

  chart.setOption({ series: opt.series, yAxis: opt.yAxis }, { silent: true });
  renderRightPanel();
}

  // ============================
  // HELPERS
  // ============================
  function timeLabel(ts){
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  }

  function fmtDateTime(d){
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ` +
           `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  }

  
// Busca el punto más cercano en un buffer [ [Date, value], ... ] al timestamp targetMs
function nearestValue(buf, targetMs){
  const n = buf ? buf.length : 0;
  if (!n) return { value: null, time: null };
  // búsqueda binaria (tiempos crecientes)
  let lo = 0, hi = n - 1;
  while (lo < hi) {
    const mid   = (lo + hi) >> 1;
    const midTs = buf[mid][0].getTime();
    if (midTs < targetMs) lo = mid + 1; else hi = mid;
  }
  let idx = lo;
  if (idx > 0) {
    const t0 = buf[idx-1][0].getTime(), t1 = buf[idx][0].getTime();
    if (Math.abs(targetMs - t0) <= Math.abs(targetMs - t1)) idx = idx - 1;
  }
  return { value: buf[idx][1], time: buf[idx][0] };
}


})();
