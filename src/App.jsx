
import { useState, useEffect, useRef, useMemo } from "react";
import RESOLUCIONES from './data.json'
import { GoogleGenAI } from "@google/genai";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend, AreaChart, Area,
  Treemap, ScatterChart, Scatter, ZAxis, ReferenceLine
} from "recharts";

// ─── GOOGLE FONTS ─────────────────────────────────────────────────────────────
const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');`;




// ─── DERIVED ANALYTICS DATA (calculado dinámicamente desde RESOLUCIONES) ──────

// Evolución anual
const _evolucionMap = {};
RESOLUCIONES.forEach(r => {
  const anio = r.resolucion_metadata.fecha_emision?.slice(0, 4);
  const gravedad = r.analisis_legal.gravedad;
  if (!anio) return;
  if (!_evolucionMap[anio]) _evolucionMap[anio] = { anio, sanciones: 0, leve: 0, grave: 0, muy_grave: 0 };
  _evolucionMap[anio].sanciones++;
  if (gravedad === "Leve") _evolucionMap[anio].leve++;
  else if (gravedad === "Grave") _evolucionMap[anio].grave++;
  else if (gravedad === "Muy grave") _evolucionMap[anio].muy_grave++;
});
const evolucionAnual = Object.values(_evolucionMap).sort((a, b) => a.anio.localeCompare(b.anio));

// Sector heatmap
const _sectorMap = {};
RESOLUCIONES.forEach(r => {
  const sector = r.entidad_sancionada.sector || "Otro";
  const multa = r.resultado_final.multa_final_uit || 0;
  if (!_sectorMap[sector]) _sectorMap[sector] = { sector, sanciones: 0, _totalMulta: 0 };
  _sectorMap[sector].sanciones++;
  _sectorMap[sector]._totalMulta += multa;
});
const sectorHeatmap = Object.values(_sectorMap).map(s => ({
  sector: s.sector,
  sanciones: s.sanciones,
  multa_promedio: parseFloat((s._totalMulta / s.sanciones).toFixed(2)),
})).sort((a, b) => b.sanciones - a.sanciones);

// Top empresas por monto
const _empresaMap = {};
RESOLUCIONES.forEach(r => {
  const empresa = r.entidad_sancionada.nombre_comercial || r.entidad_sancionada.razon_social;
  const multa = r.resultado_final.multa_final_uit || 0;
  if (!_empresaMap[empresa]) _empresaMap[empresa] = { empresa, monto_total: 0, sanciones: 0 };
  _empresaMap[empresa].monto_total += multa;
  _empresaMap[empresa].sanciones++;
});
const topEmpresasMonto = Object.values(_empresaMap)
  .map(e => ({ ...e, monto_total: parseFloat(e.monto_total.toFixed(2)) }))
  .sort((a, b) => b.monto_total - a.monto_total)
  .slice(0, 10);

const treemapData = topEmpresasMonto.map(e => ({ name: e.empresa, size: e.monto_total, sanciones: e.sanciones }));

// Frecuencia de factores
const _factoresMap = {};
RESOLUCIONES.forEach(r => {
  [...r.factores_agravantes, ...r.factores_atenuantes].forEach(f => {
    const key = f.codigo || f.descripcion.slice(0, 30);
    const tipo = r.factores_agravantes.includes(f) ? "Agravante" : "Atenuante";
    if (!_factoresMap[key]) _factoresMap[key] = { factor: `${key} ${f.descripcion.slice(0, 25)}...`, tipo, frecuencia: 0, impacto_promedio: f.impacto_porcentaje * 100 };
    _factoresMap[key].frecuencia++;
  });
});
const frecuenciaFactores = Object.values(_factoresMap).sort((a, b) => b.frecuencia - a.frecuencia).slice(0, 8);

// Causa raíz
const _causaMap = {};
RESOLUCIONES.forEach(r => {
  const causa = r.control_calidad.causa_raiz || "Otro";
  const gravedad = r.analisis_legal.gravedad;
  const causaCorta = causa.length > 25 ? causa.slice(0, 25) : causa;
  if (!_causaMap[causaCorta]) _causaMap[causaCorta] = { causa: causaCorta, leve: 0, grave: 0, muy_grave: 0 };
  if (gravedad === "Leve") _causaMap[causaCorta].leve++;
  else if (gravedad === "Grave") _causaMap[causaCorta].grave++;
  else if (gravedad === "Muy grave") _causaMap[causaCorta].muy_grave++;
});
const causaRaiz = Object.values(_causaMap);

// Bubble data por sector
const SECTOR_COLORS = ["#e63946","#f4a261","#2a9d8f","#457b9d","#8338ec","#06d6a0","#ffd166","#e76f51","#264653","#a8dadc"];
const bubbleData = sectorHeatmap.map((s, i) => ({
  sector: s.sector,
  multa_promedio: s.multa_promedio,
  afectados: s.sanciones * 1500, // estimado proporcional hasta tener dato real
  sanciones: s.sanciones,
  color: SECTOR_COLORS[i % SECTOR_COLORS.length],
}));

// Gravedad
const gravedadData = [
  { name: "Leve", value: RESOLUCIONES.filter(r => r.analisis_legal.gravedad === "Leve").length, color: "#f4a261" },
  { name: "Grave", value: RESOLUCIONES.filter(r => r.analisis_legal.gravedad === "Grave").length, color: "#e63946" },
  { name: "Muy grave", value: RESOLUCIONES.filter(r => r.analisis_legal.gravedad === "Muy grave").length, color: "#8d0f18" },
];

// Waterfall — usa la primera resolución del JSON como ejemplo dinámico
const _ejemploRes = RESOLUCIONES[0];
const _mb = _ejemploRes.analisis_legal.monto_base_Mb_uit;
const _agravantes = _ejemploRes.factores_agravantes;
const _atenuantes = _ejemploRes.factores_atenuantes;
let _acum = _mb;
const waterfallData = [
  { name: "Monto base (Mb)", value: _mb, start: 0, type: "base" },
  ..._agravantes.map(f => {
    const val = parseFloat((_mb * f.impacto_porcentaje).toFixed(2));
    const entry = { name: `+ ${f.descripcion.slice(0, 22)}...`, value: val, start: _acum, type: "agravante" };
    _acum += val;
    return entry;
  }),
  ..._atenuantes.map(f => {
    const val = parseFloat((_mb * f.impacto_porcentaje).toFixed(2));
    const entry = { name: `− ${f.descripcion.slice(0, 22)}...`, value: val, start: _acum, type: "atenuante" };
    _acum += val;
    return entry;
  }),
  { name: "Multa final", value: _ejemploRes.resultado_final.multa_final_uit, start: 0, type: "final" },
];

// ─── COLORS ───────────────────────────────────────────────────────────────────
const C = { red: "#e63946", orange: "#f4a261", teal: "#2a9d8f", blue: "#457b9d", dark: "#0a0a0a", card: "rgba(255,255,255,0.03)", border: "rgba(255,255,255,0.08)", text: "#f0ede8", muted: "#888", dim: "#444" };

// ─── REUSABLE COMPONENTS ──────────────────────────────────────────────────────
const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#1a1a1a", border: "1px solid #2a2a2a", padding: "10px 14px", borderRadius: "4px", fontSize: "12px", color: C.text }}>
      {label && <div style={{ color: C.muted, marginBottom: "6px", fontFamily: "'IBM Plex Mono', monospace" }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || C.red, marginBottom: "2px" }}>
          {p.name}: <strong>{p.value?.toLocaleString?.() ?? p.value}</strong>
        </div>
      ))}
    </div>
  );
};

const Card = ({ children, style = {} }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: "4px", padding: "24px", ...style }}>
    {children}
  </div>
);

const SecTitle = ({ children, accent = C.red }) => (
  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
    <div style={{ width: "3px", height: "18px", background: accent, borderRadius: "2px", flexShrink: 0 }} />
    <span style={{ fontSize: "11px", letterSpacing: "3px", textTransform: "uppercase", color: C.muted, fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 500 }}>{children}</span>
  </div>
);

const KPI = ({ label, value, sub, accent = C.red }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderTop: `3px solid ${accent}`, borderRadius: "4px", padding: "22px", flex: 1, minWidth: 140 }}>
    <div style={{ fontSize: "10px", letterSpacing: "2px", color: C.dim, textTransform: "uppercase", marginBottom: "8px", fontFamily: "'IBM Plex Sans', sans-serif" }}>{label}</div>
    <div style={{ fontSize: "32px", fontFamily: "'Playfair Display', serif", color: C.text, lineHeight: 1 }}>{value}</div>
    {sub && <div style={{ fontSize: "11px", color: "#555", marginTop: "6px" }}>{sub}</div>}
  </div>
);

// ─── CHAT COMPONENT ───────────────────────────────────────────────────────────
const SYSTEM_PROMPT = `Eres un asistente especializado en las resoluciones sancionadoras de la Autoridad Nacional de Protección de Datos Personales (ANPD) del Perú.

Tienes acceso a ${RESOLUCIONES.length} resoluciones reales. Aquí están los datos clave:

RESOLUCIONES DISPONIBLES:
${RESOLUCIONES.map(r => `- ${r.resolucion_metadata.id_resolucion} | ${r.entidad_sancionada.razon_social} (${r.entidad_sancionada.sector}) | ${r.analisis_legal.gravedad} | Multa: ${r.resultado_final.multa_final_uit} UIT | Infracción: ${r.analisis_legal.infraccion} | Causa: ${r.control_calidad.causa_raiz}`).join('\n')}

TOP EMPRESAS POR MONTO:
${topEmpresasMonto.map(e => `- ${e.empresa}: ${e.monto_total} UIT en ${e.sanciones} sanción(es)`).join('\n')}

SECTORES:
${sectorHeatmap.map(s => `- ${s.sector}: ${s.sanciones} sanción(es), multa promedio ${s.multa_promedio} UIT`).join('\n')}

GRAVEDAD: ${gravedadData.map(g => `${g.name}: ${g.value}`).join(' | ')}

UIT 2019: S/4,200 | UIT 2020: S/4,300 | UIT 2021: S/4,400 | UIT 2022: S/4,600 | UIT 2023: S/4,950

Responde en español, con precisión, citando datos específicos cuando sea relevante.`;

const ChatAgent = () => {
  const [msgs, setMsgs] = useState([{ role: "assistant", content: "Hola, soy el asistente ANPD. Puedo responderte sobre sanciones, empresas, sectores, causas de infracción o cómo se calculan las multas. ¿Qué deseas saber?" }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  // Carga Puter.js dinámicamente (no necesita API key)
  useEffect(() => {
    if (window.puter) return;
    const script = document.createElement("script");
    script.src = "https://js.puter.com/v2/";
    script.async = true;
    document.head.appendChild(script);
  }, []);

  const send = async (text) => {
    const q = text || input;
    if (!q.trim() || loading) return;

    const newMsgs = [...msgs, { role: "user", content: q }];
    setMsgs(newMsgs);
    setInput("");
    setLoading(true);

    try {
      // Espera a que puter esté disponible
      let attempts = 0;
      while (!window.puter && attempts < 20) {
        await new Promise(r => setTimeout(r, 300));
        attempts++;
      }
      if (!window.puter) throw new Error("Puter.js no cargó. Recarga la página.");

      // Construye el prompt completo con el contexto del sistema
      const fullPrompt = `${SYSTEM_PROMPT}\n\n---\n\nHistorial de conversación:\n${
        newMsgs.slice(0, -1).map(m => 
          `${m.role === "user" ? "Usuario" : "Asistente"}: ${m.content}`
        ).join("\n")
      }\n\nUsuario: ${q}\n\nAsistente:`;

      const response = await window.puter.ai.chat(fullPrompt, {
        model: "gemini-2.0-flash"
      });

      const botReply = typeof response === "string" ? response : response?.message?.content?.[0]?.text || response?.text || String(response);
      setMsgs(prev => [...prev, { role: "assistant", content: botReply }]);

    } catch (error) {
      console.error("Error:", error);
      setMsgs(prev => [...prev, { role: "assistant", content: "❌ Error: " + error.message }]);
    }

    setLoading(false);
  };

  const suggestions = [
    "¿Cuál es la empresa más sancionada en monto?",
    "¿Cómo se calculó la multa de Motorlink?",
    "¿Qué sector tiene la multa promedio más alta?",
    "¿Cuál fue el factor atenuante más usado?",
    "¿Cuánto creció la cantidad de sanciones entre 2022 y 2025?"
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 260px", gap: "20px", alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", height: "500px", background: C.card, border: `1px solid ${C.border}`, borderRadius: "4px" }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: C.teal, boxShadow: `0 0 8px ${C.teal}` }} />
          <span style={{ fontSize: "11px", letterSpacing: "2px", textTransform: "uppercase", color: C.muted }}>Agente ANPD · Gemini 2.0 (Puter.js)</span>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
          {msgs.map((m, i) => (
            <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
              <div style={{
                maxWidth: "78%", padding: "12px 16px", borderRadius: "4px",
                fontSize: "13px", lineHeight: 1.7, whiteSpace: "pre-wrap",
                background: m.role === "user" ? C.red : "rgba(255,255,255,0.05)",
                color: m.role === "user" ? "#fff" : "#ccc",
                border: m.role === "assistant" ? `1px solid ${C.border}` : "none"
              }}>
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: "flex", gap: "5px", padding: "12px", alignItems: "center" }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: "6px", height: "6px", borderRadius: "50%", background: C.red,
                  animation: `dot 1s ease-in-out ${i * 0.2}s infinite`
                }} />
              ))}
              <span style={{ fontSize: "11px", color: C.muted, marginLeft: "6px" }}>Analizando...</span>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div style={{ padding: "14px 20px", borderTop: `1px solid ${C.border}`, display: "flex", gap: "10px" }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Escribe tu consulta..."
            style={{
              flex: 1, background: "rgba(255,255,255,0.04)",
              border: `1px solid ${C.border}`, borderRadius: "4px",
              padding: "10px 14px", color: C.text, fontSize: "13px",
              outline: "none", fontFamily: "'IBM Plex Sans', sans-serif"
            }}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            style={{
              background: C.red, border: "none", borderRadius: "4px",
              padding: "10px 18px", color: "#fff", fontSize: "11px",
              letterSpacing: "1px",
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
              opacity: loading || !input.trim() ? 0.4 : 1,
              fontFamily: "inherit", transition: "opacity 0.15s"
            }}>
            ENVIAR
          </button>
        </div>
      </div>

      <div>
        <div style={{ fontSize: "10px", letterSpacing: "2px", color: C.dim, marginBottom: "12px", textTransform: "uppercase" }}>
          Consultas sugeridas
        </div>
        {suggestions.map((s, i) => (
          <button key={i} onClick={() => send(s)} disabled={loading}
            style={{
              width: "100%", background: C.card, border: `1px solid ${C.border}`,
              borderRadius: "4px", padding: "10px 14px", color: C.muted,
              fontSize: "12px", cursor: loading ? "not-allowed" : "pointer",
              textAlign: "left", fontFamily: "'IBM Plex Sans', sans-serif",
              lineHeight: 1.5, marginBottom: "8px", transition: "all 0.15s",
              opacity: loading ? 0.5 : 1
            }}
            onMouseEnter={e => { if (!loading) { e.currentTarget.style.borderColor = "rgba(230,57,70,0.5)"; e.currentTarget.style.color = C.text; }}}
            onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.muted; }}>
            {s}
          </button>
        ))}

        <div style={{
          marginTop: "16px", padding: "12px",
          background: "rgba(42,157,143,0.05)",
          border: `1px solid rgba(42,157,143,0.2)`, borderRadius: "4px"
        }}>
          <div style={{ fontSize: "10px", color: C.teal, letterSpacing: "1px", textTransform: "uppercase", marginBottom: "6px" }}>Motor</div>
          <div style={{ fontSize: "12px", color: "#666", fontFamily: "'IBM Plex Mono', monospace" }}>gemini-2.0-flash</div>
          <div style={{ fontSize: "11px", color: "#444", marginTop: "4px" }}>via Puter.js · sin API key · gratuito</div>
        </div>
      </div>
    </div>
  );
};

// ─── WATERFALL CHART CUSTOM ───────────────────────────────────────────────────
const WaterfallChart = ({ data }) => {
  const barH = 44, gap = 8, w = 480, labelW = 190, chartW = 200;
  const maxVal = 25;
  const scale = (v) => (Math.abs(v) / maxVal) * chartW;
  const getX = (d) => {
    if (d.type === "final") return labelW;
    return labelW + (d.start / maxVal) * chartW;
  };
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${data.length * (barH + gap) + 20}`} style={{ overflow: "hidden" }}>
      {data.map((d, i) => {
        const y = i * (barH + gap);
        const x = getX(d);
        const bw = scale(d.value);
        const color = d.type === "base" ? C.blue : d.type === "agravante" ? C.red : d.type === "atenuante" ? C.teal : "#f0ede8";
        const label = d.type === "agravante" ? `+${d.value.toFixed(2)}` : d.type === "atenuante" ? `${d.value.toFixed(2)}` : `${Math.abs(d.value).toFixed(2)}`;
        const barX = d.type === "atenuante" ? x + bw : x;
        const labelX = labelW + chartW + 10;
        return (
          <g key={i}>
            <text x={labelW - 10} y={y + barH / 2 + 5} textAnchor="end" fill={C.muted} fontSize="11" fontFamily="IBM Plex Sans">{d.name}</text>
            <rect x={barX} y={y} width={Math.abs(bw)} height={barH} fill={color} opacity={0.85} rx="2" />
            <text x={labelX} y={y + barH / 2 + 5} textAnchor="start" fill={color} fontSize="12" fontFamily="IBM Plex Mono" fontWeight="500">{label} UIT</text>
            {i < data.length - 1 && d.type !== "atenuante" && (
              <line x1={barX + Math.abs(bw)} y1={y + barH} x2={barX + Math.abs(bw)} y2={y + barH + gap} stroke="#333" strokeDasharray="3,3" />
            )}
          </g>
        );
      })}
    </svg>
  );
};

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("macro");
  const [mounted, setMounted] = useState(false);

  // Filters for resoluciones
  const [search, setSearch] = useState("");
  const [filterSector, setFilterSector] = useState("Todos");
  const [filterGravedad, setFilterGravedad] = useState("Todos");
  const [filterAnio, setFilterAnio] = useState("Todos");

  // Dashboard filters
  const [dashFilterAnio, setDashFilterAnio] = useState("Todos");
  const [dashFilterSector, setDashFilterSector] = useState("Todos");

  useEffect(() => { setTimeout(() => setMounted(true), 80); }, []);

  const sectores = ["Todos", ...Array.from(new Set(RESOLUCIONES.map(r => r.entidad_sancionada.sector)))];
  const gravedades = ["Todos", "Leve", "Grave", "Muy grave"];
  const anios = ["Todos", "2025", "2024", "2023", "2022", "2021"];

  const filtradas = useMemo(() => RESOLUCIONES.filter(r => {
    const q = search.toLowerCase();
    const matchSearch = !q ||
      r.entidad_sancionada.razon_social.toLowerCase().includes(q) ||
      r.entidad_sancionada.nombre_comercial.toLowerCase().includes(q) ||
      r.entidad_sancionada.sector.toLowerCase().includes(q) ||
      r.analisis_legal.infraccion.toLowerCase().includes(q) ||
      r.resolucion_metadata.id_resolucion.toLowerCase().includes(q);
    const matchSector = filterSector === "Todos" || r.entidad_sancionada.sector === filterSector;
    const matchGravedad = filterGravedad === "Todos" || r.analisis_legal.gravedad === filterGravedad;
    const matchAnio = filterAnio === "Todos" || r.resolucion_metadata.fecha_emision.startsWith(filterAnio);
    return matchSearch && matchSector && matchGravedad && matchAnio;
  }), [search, filterSector, filterGravedad, filterAnio]);

  const tabs = [
    { id: "macro", label: "Vista Macro" },
    { id: "entidades", label: "Entidades" },
    { id: "legal", label: "Laboratorio Legal" },
    { id: "causas", label: "Causas y Afectados" },
    { id: "resoluciones", label: "Resoluciones" },
    { id: "agente", label: "Agente IA" },
  ];

  const SelectFilter = ({ value, onChange, options, label }) => (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <label style={{ fontSize: "10px", letterSpacing: "1px", textTransform: "uppercase", color: C.dim }}>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} style={{ background: "#111", border: `1px solid ${C.border}`, borderRadius: "4px", padding: "8px 12px", color: C.muted, fontSize: "12px", fontFamily: "'IBM Plex Sans', sans-serif", cursor: "pointer", outline: "none" }}>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );

  const gravedadColor = { Leve: C.orange, Grave: C.red, "Muy grave": "#8d0f18" };

  return (
    <div style={{ minHeight: "100vh", background: C.dark, color: C.text, fontFamily: "'IBM Plex Sans', sans-serif", opacity: mounted ? 1 : 0, transition: "opacity 0.3s" }}>
      <style>{`
        ${FONTS}
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #2a2a2a; }
        input::placeholder, textarea::placeholder { color: #555; }
        select option { background: #111; }
        @keyframes dot { 0%,100%{opacity:.2;transform:scale(.8)} 50%{opacity:1;transform:scale(1)} }
      `}</style>

      {/* ── HEADER ── */}
      <header style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(10,10,10,0.97)", borderBottom: `1px solid ${C.border}`, backdropFilter: "blur(12px)" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 32px", display: "flex", alignItems: "center", justifyContent: "space-between", height: 60 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ width: 30, height: 30, background: C.red, borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, fontWeight: 700, color: "#fff" }}>A</span>
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, letterSpacing: 1 }}>ANPD Analytics</div>
              <div style={{ fontSize: 10, color: "#555", letterSpacing: 2, textTransform: "uppercase" }}>Protección de Datos · Perú</div>
            </div>
          </div>
          <nav style={{ display: "flex", gap: 2 }}>
            {tabs.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{ background: tab === t.id ? "rgba(230,57,70,0.12)" : "transparent", border: tab === t.id ? `1px solid rgba(230,57,70,0.35)` : "1px solid transparent", borderRadius: 3, padding: "5px 14px", color: tab === t.id ? C.red : "#555", fontSize: 11, letterSpacing: 1.5, textTransform: "uppercase", cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s" }}>
                {t.label}
              </button>
            ))}
          </nav>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: C.dim }}>850 resoluciones · mock data</span>
        </div>
      </header>

      <main style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 32px" }}>

        {/* ════════════ VISTA MACRO ════════════ */}
        {tab === "macro" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                ¿Cómo va el Perú en<br /><em style={{ color: C.red }}>Protección de Datos?</em>
              </h1>
              <p style={{ marginTop: 10, color: "#666", fontSize: 13 }}>Panorama general de resoluciones sancionadoras 2017–2024</p>
            </div>

            {/* KPIs */}
            {(() => {
              const total = RESOLUCIONES.length;
              const gravesPlus = RESOLUCIONES.filter(r => r.analisis_legal.gravedad === "Grave" || r.analisis_legal.gravedad === "Muy grave").length;
              const pctGraves = Math.round((gravesPlus / total) * 100);
              const multaPromedio = parseFloat((RESOLUCIONES.reduce((s, r) => s + (r.resultado_final.multa_final_uit || 0), 0) / total).toFixed(1));
              const sectorLider = sectorHeatmap[0];
              const anios = [...new Set(RESOLUCIONES.map(r => r.resolucion_metadata.fecha_emision?.slice(0,4)))].filter(Boolean).sort();
              return (
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <KPI label="Resoluciones totales" value={total} sub={`${anios[0]} – ${anios[anios.length-1]}`} accent={C.red} />
                  <KPI label="Infracciones graves+" value={gravesPlus} sub={`${pctGraves}% del total`} accent="#8d0f18" />
                  <KPI label="Multa promedio" value={`${multaPromedio} UIT`} sub={`≈ S/ ${(multaPromedio * 4950).toLocaleString()}`} accent={C.orange} />
                  <KPI label="Sector líder" value={sectorLider?.sector} sub={`${sectorLider?.sanciones} sanciones`} accent={C.teal} />
                  <KPI label="Empresas únicas" value={Object.keys(_empresaMap).length} sub="con al menos 1 sanción" accent={C.blue} />
                </div>
              );
            })()}

            {/* Evolución + Gravedad */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
              <Card>
                <SecTitle>Evolución temporal de sanciones</SecTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={evolucionAnual}>
                    <defs>
                      <linearGradient id="gLeve" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={C.orange} stopOpacity={0.3}/><stop offset="95%" stopColor={C.orange} stopOpacity={0}/></linearGradient>
                      <linearGradient id="gGrave" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={C.red} stopOpacity={0.3}/><stop offset="95%" stopColor={C.red} stopOpacity={0}/></linearGradient>
                      <linearGradient id="gMuyGrave" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8d0f18" stopOpacity={0.4}/><stop offset="95%" stopColor="#8d0f18" stopOpacity={0}/></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="anio" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<Tip />} />
                    <Legend formatter={v => <span style={{ color: "#777", fontSize: 11 }}>{v}</span>} />
                    <Area type="monotone" dataKey="leve" name="Leve" stroke={C.orange} fill="url(#gLeve)" strokeWidth={2} stackId="1" />
                    <Area type="monotone" dataKey="grave" name="Grave" stroke={C.red} fill="url(#gGrave)" strokeWidth={2} stackId="1" />
                    <Area type="monotone" dataKey="muy_grave" name="Muy grave" stroke="#8d0f18" fill="url(#gMuyGrave)" strokeWidth={2} stackId="1" />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
              <Card>
                <SecTitle accent={C.orange}>Distribución por gravedad</SecTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={gravedadData} dataKey="value" cx="50%" cy="50%" outerRadius={95} innerRadius={50} paddingAngle={3}>
                      {gravedadData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip formatter={(v, n) => [`${v} resoluciones`, n]} contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 4, fontSize: 12 }} />
                    <Legend formatter={(v, e) => <span style={{ color: "#888", fontSize: 11 }}>{v}: {e.payload.value}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </div>

            {/* Sector heatmap como barras de calor */}
            <Card>
              <SecTitle accent={C.teal}>Mapa de calor por sector económico</SecTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
                {sectorHeatmap.sort((a,b) => b.sanciones - a.sanciones).map((s, i) => {
                  const intensity = s.sanciones / 198;
                  return (
                    <div key={i} style={{ background: `rgba(230,57,70,${0.08 + intensity * 0.55})`, border: `1px solid rgba(230,57,70,${0.1 + intensity * 0.4})`, borderRadius: 4, padding: "14px 16px", cursor: "default", transition: "transform 0.15s" }}
                      onMouseEnter={e => e.currentTarget.style.transform = "scale(1.03)"}
                      onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}>
                      <div style={{ fontSize: 11, color: "#ccc", marginBottom: 6, fontWeight: 500 }}>{s.sector}</div>
                      <div style={{ fontSize: 22, fontFamily: "'Playfair Display', serif", color: C.text }}>{s.sanciones}</div>
                      <div style={{ fontSize: 10, color: "#888", marginTop: 4 }}>Ø {s.multa_promedio} UIT</div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        )}

        {/* ════════════ ENTIDADES ════════════ */}
        {tab === "entidades" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                ¿Quiénes son los<br /><em style={{ color: C.red }}>Infractores Recurrentes?</em>
              </h1>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <Card>
                <SecTitle>Top 10 empresas por cantidad de sanciones</SecTitle>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={topEmpresasMonto.map(e => ({ ...e })).sort((a,b) => b.sanciones - a.sanciones)} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="empresa" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
                    <Tooltip content={<Tip />} />
                    <Bar dataKey="sanciones" name="Sanciones" fill={C.red} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
              <Card>
                <SecTitle accent={C.orange}>Top 10 empresas por monto acumulado (UIT)</SecTitle>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={topEmpresasMonto} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="empresa" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={110} />
                    <Tooltip content={<Tip />} />
                    <Bar dataKey="monto_total" name="UIT acumuladas" fill={C.orange} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>

            {/* Treemap */}
            <Card>
              <SecTitle accent={C.blue}>Ranking de multas récord — Treemap</SecTitle>
              <p style={{ fontSize: 12, color: "#555", marginBottom: 16 }}>El tamaño de cada bloque representa el monto total acumulado en UIT</p>
              <ResponsiveContainer width="100%" height={300}>
                <Treemap data={treemapData} dataKey="size" aspectRatio={4 / 3} stroke="#0a0a0a"
                  content={({ x, y, width, height, name, size }) => {
                    if (width < 30 || height < 20) return null;
                    const colors = [C.red, C.orange, "#8d0f18", C.teal, C.blue, "#8338ec", "#06d6a0", "#ffd166", "#e76f51", "#264653"];
                    const idx = treemapData.findIndex(d => d.name === name);
                    return (
                      <g>
                        <rect x={x} y={y} width={width} height={height} fill={colors[idx % colors.length]} opacity={0.85} stroke="#0a0a0a" strokeWidth={2} rx={2} />
                        {width > 60 && <text x={x + 10} y={y + 20} fill="#fff" fontSize={Math.min(13, width / 8)} fontFamily="IBM Plex Sans" fontWeight={500}>{name}</text>}
                        {width > 60 && height > 35 && <text x={x + 10} y={y + 36} fill="rgba(255,255,255,0.7)" fontSize={11} fontFamily="IBM Plex Mono">{size} UIT</text>}
                      </g>
                    );
                  }}
                />
              </ResponsiveContainer>
            </Card>
          </div>
        )}

        {/* ════════════ LABORATORIO LEGAL ════════════ */}
        {tab === "legal" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                El <em style={{ color: C.red }}>Laboratorio Legal</em><br />
                <span style={{ fontSize: 28, color: "#666" }}>¿Cómo se calculan las multas?</span>
              </h1>
            </div>

            {/* Waterfall */}
            <Card>
              <SecTitle>Caso Motorlink (Tracklink) — Camino de la multa</SecTitle>
              <p style={{ fontSize: 12, color: "#555", marginBottom: 20 }}>
                Resolución 0662-2025 · Infracción Grave · Fórmula: Multa = Mb × (1 + ΣFactores)
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "center" }}>
                <WaterfallChart data={waterfallData} />
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {[
                    { label: "Monto base (Mb)", value: "22.50 UIT", color: C.blue, desc: "Grado relativo 3, infracción grave" },
                    { label: "Agravante f3.1 (+10%)", value: "+2.25 UIT", color: C.red, desc: "Riesgo o daño a una persona" },
                    { label: "Atenuante f3.7 (−30%)", value: "−6.75 UIT", color: C.teal, desc: "Reconocimiento de responsabilidad" },
                    { label: "Multa final", value: "18.00 UIT", color: C.text, desc: "≈ S/ 89,100 (UIT 2023: S/4,950)" },
                  ].map((r, i) => (
                    <div key={i} style={{ background: "rgba(255,255,255,0.03)", border: `1px solid ${C.border}`, borderLeft: `3px solid ${r.color}`, borderRadius: 4, padding: "12px 16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 12, color: "#aaa" }}>{r.label}</span>
                        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, color: r.color, fontWeight: 500 }}>{r.value}</span>
                      </div>
                      <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>{r.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            {/* Frecuencia factores */}
            <Card>
              <SecTitle accent={C.orange}>Frecuencia de factores agravantes y atenuantes</SecTitle>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={frecuenciaFactores} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="factor" tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} width={190} />
                  <Tooltip content={<Tip />} />
                  <Bar dataKey="frecuencia" name="Frecuencia" radius={[0, 3, 3, 0]}
                    fill={C.red}
                    label={false}>
                    {frecuenciaFactores.map((f, i) => (
                      <Cell key={i} fill={f.tipo === "Atenuante" ? C.teal : C.red} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", gap: 20, marginTop: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 12, height: 12, background: C.red, borderRadius: 2 }} /><span style={{ fontSize: 11, color: C.muted }}>Agravante</span></div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 12, height: 12, background: C.teal, borderRadius: 2 }} /><span style={{ fontSize: 11, color: C.muted }}>Atenuante</span></div>
              </div>
            </Card>
          </div>
        )}

        {/* ════════════ CAUSAS Y AFECTADOS ════════════ */}
        {tab === "causas" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                Análisis de <em style={{ color: C.red }}>Causas y Afectados</em>
              </h1>
            </div>
            <Card>
              <SecTitle>Causa raíz por gravedad de infracción</SecTitle>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={causaRaiz}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="causa" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<Tip />} />
                  <Legend formatter={v => <span style={{ color: "#888", fontSize: 11 }}>{v}</span>} />
                  <Bar dataKey="leve" name="Leve" stackId="a" fill={C.orange} />
                  <Bar dataKey="grave" name="Grave" stackId="a" fill={C.red} />
                  <Bar dataKey="muy_grave" name="Muy grave" stackId="a" fill="#8d0f18" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <SecTitle accent={C.teal}>Multa promedio vs. personas afectadas por sector</SecTitle>
              <p style={{ fontSize: 12, color: "#555", marginBottom: 16 }}>El tamaño de la burbuja representa el número de resoluciones del sector</p>
              <ResponsiveContainer width="100%" height={320}>
                <ScatterChart margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis type="number" dataKey="multa_promedio" name="Multa promedio (UIT)" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} label={{ value: "Multa promedio (UIT)", position: "insideBottom", fill: "#555", fontSize: 11, offset: -2 }} />
                  <YAxis type="number" dataKey="afectados" name="Personas afectadas" tick={{ fill: "#555", fontSize: 11 }} axisLine={false} tickLine={false} label={{ value: "Afectados", angle: -90, position: "insideLeft", fill: "#555", fontSize: 11 }} />
                  <ZAxis type="number" dataKey="sanciones" range={[400, 3000]} />
                  <Tooltip cursor={{ strokeDasharray: "3 3", stroke: "#333" }} content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    return <div style={{ background: "#1a1a1a", border: "1px solid #2a2a2a", padding: "10px 14px", borderRadius: 4, fontSize: 12 }}>
                      <div style={{ color: d.color, fontWeight: 600, marginBottom: 6 }}>{d.sector}</div>
                      <div style={{ color: "#aaa" }}>Multa promedio: <strong style={{ color: C.text }}>{d.multa_promedio} UIT</strong></div>
                      <div style={{ color: "#aaa" }}>Afectados: <strong style={{ color: C.text }}>{d.afectados.toLocaleString()}</strong></div>
                      <div style={{ color: "#aaa" }}>Sanciones: <strong style={{ color: C.text }}>{d.sanciones}</strong></div>
                    </div>;
                  }} />
                  <Scatter data={bubbleData} shape={(props) => {
                    const { cx, cy, payload } = props;
                    const r = Math.sqrt(payload.sanciones) * 2.5;
                    return <circle cx={cx} cy={cy} r={r} fill={payload.color} opacity={0.75} stroke={payload.color} strokeWidth={1} />;
                  }} />
                  {bubbleData.map((d, i) => null)}
                </ScatterChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16 }}>
                {bubbleData.map((d, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 10, height: 10, borderRadius: "50%", background: d.color }} />
                    <span style={{ fontSize: 11, color: C.muted }}>{d.sector}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* ════════════ RESOLUCIONES ════════════ */}
        {tab === "resoluciones" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                Resoluciones <em style={{ color: C.red }}>Sancionadoras</em>
              </h1>
              <p style={{ color: "#666", fontSize: 13, marginTop: 8 }}>Mostrando datos de muestra — se conectará con la base de datos real</p>
            </div>

            {/* Filters */}
            <Card style={{ padding: "18px 24px" }}>
              <div style={{ display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
                <div style={{ flex: 2, minWidth: 200 }}>
                  <label style={{ fontSize: "10px", letterSpacing: "1px", textTransform: "uppercase", color: C.dim, display: "block", marginBottom: 4 }}>Buscar</label>
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Empresa, sector, infracción, N° resolución..." style={{ width: "100%", background: "#111", border: `1px solid ${C.border}`, borderRadius: 4, padding: "8px 14px", color: C.text, fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", outline: "none" }} />
                </div>
                <SelectFilter label="Sector" value={filterSector} onChange={setFilterSector} options={sectores} />
                <SelectFilter label="Gravedad" value={filterGravedad} onChange={setFilterGravedad} options={gravedades} />
                <SelectFilter label="Año" value={filterAnio} onChange={setFilterAnio} options={anios} />
                <button onClick={() => { setSearch(""); setFilterSector("Todos"); setFilterGravedad("Todos"); setFilterAnio("Todos"); }} style={{ background: "rgba(255,255,255,0.04)", border: `1px solid ${C.border}`, borderRadius: 4, padding: "8px 16px", color: C.muted, fontSize: 11, letterSpacing: 1, cursor: "pointer", fontFamily: "inherit", alignSelf: "flex-end" }}>Limpiar</button>
              </div>
            </Card>

            <div style={{ fontSize: 12, color: "#555" }}>
              {filtradas.length} resultado{filtradas.length !== 1 ? "s" : ""} encontrado{filtradas.length !== 1 ? "s" : ""}
            </div>

            {filtradas.length === 0 ? (
              <Card style={{ textAlign: "center", padding: "40px", color: "#555" }}>
                No se encontraron resoluciones con los filtros seleccionados.
              </Card>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {filtradas.map((r, i) => (
                  <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderLeft: `3px solid ${gravedadColor[r.analisis_legal.gravedad] || C.red}`, borderRadius: 4, padding: "18px 22px", display: "grid", gridTemplateColumns: "160px 1fr 120px 130px 120px", gap: 16, alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 10, color: "#555", letterSpacing: 1, textTransform: "uppercase", marginBottom: 3 }}>N° Resolución</div>
                      <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: C.red, lineHeight: 1.4 }}>{r.resolucion_metadata.id_resolucion.split("/")[0]}</div>
                      <div style={{ fontSize: 10, color: "#444", marginTop: 3 }}>{r.resolucion_metadata.fecha_emision}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: C.text, marginBottom: 4 }}>
                        {r.entidad_sancionada.razon_social}
                        {r.entidad_sancionada.nombre_comercial !== r.entidad_sancionada.razon_social && (
                          <span style={{ fontSize: 11, color: "#666", marginLeft: 8 }}>({r.entidad_sancionada.nombre_comercial})</span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: "#666", lineHeight: 1.4 }}>{r.analisis_legal.infraccion}</div>
                      <div style={{ fontSize: 11, color: "#444", marginTop: 4, fontFamily: "'IBM Plex Mono', monospace" }}>{r.analisis_legal.base_legal}</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 10, color: "#555", letterSpacing: 1, textTransform: "uppercase", marginBottom: 3 }}>Multa final</div>
                      <div style={{ fontSize: 16, color: C.orange, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 500 }}>{r.resultado_final.multa_final_uit} UIT</div>
                      <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>Base: {r.analisis_legal.monto_base_Mb_uit} UIT</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <span style={{ display: "inline-block", background: `${gravedadColor[r.analisis_legal.gravedad]}22`, border: `1px solid ${gravedadColor[r.analisis_legal.gravedad]}55`, borderRadius: 3, padding: "3px 10px", fontSize: 11, color: gravedadColor[r.analisis_legal.gravedad], letterSpacing: 1 }}>
                        {r.analisis_legal.gravedad.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ display: "inline-block", background: "rgba(42,157,143,0.1)", border: "1px solid rgba(42,157,143,0.3)", borderRadius: 3, padding: "3px 10px", fontSize: 11, color: C.teal, letterSpacing: 1 }}>
                        {r.entidad_sancionada.sector}
                      </div>
                      <div style={{ fontSize: 10, color: "#444", marginTop: 6 }}>{r.control_calidad.causa_raiz}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ textAlign: "center", padding: "20px", border: `1px dashed ${C.border}`, borderRadius: 4 }}>
              <span style={{ fontSize: 12, color: "#444", letterSpacing: 1 }}>Mostrando {Math.min(filtradas.length, RESOLUCIONES.length)} de 850 resoluciones reales · Los datos completos se cargarán desde la BD</span>
            </div>
          </div>
        )}

        {/* ════════════ AGENTE ════════════ */}
        {tab === "agente" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div>
              <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 400, lineHeight: 1.1 }}>
                Agente <em style={{ color: C.red }}>Inteligente</em>
              </h1>
              <p style={{ color: "#666", fontSize: 13, marginTop: 8 }}>Consulta los datos de las resoluciones en lenguaje natural</p>
            </div>
            <ChatAgent />
          </div>
        )}

      </main>

      <footer style={{ borderTop: `1px solid ${C.border}`, padding: "20px 32px", marginTop: 60 }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: C.dim, letterSpacing: 1 }}>ANPD Analytics · Universidad · Tesis 2025 · Datos de prueba</span>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: C.dim }}>v0.2.0-mock</span>
        </div>
      </footer>
    </div>
  );
}