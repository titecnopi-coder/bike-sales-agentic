import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://bike-sales-api-575202457786.us-central1.run.app'

const ETIQUETAS = {
  '1_tasa_exito_tools': 'Tasa de éxito de tools',
  '2_score_juez_promedio': 'Score del Juez (promedio)',
  '3_time_to_last_token_p95': 'Time to last token (p95)',
  '4_costo_promedio_por_consulta': 'Costo promedio por consulta',
  '5_tasa_alucinacion': 'Tasa de alucinación detectada',
  '6_latencia_rag_p95': 'Latencia del pipeline RAG (p95)',
  '7_cobertura_corpus_rag': 'Cobertura del corpus RAG',
  '8_tokens_promedio': 'Tokens promedio por conversación',
}

function TarjetaKPI({ etiqueta, dato }) {
  const { valor, unidad, umbral, cumple } = dato
  const claseEstado =
    cumple === true ? 'kpi-card--ok' : cumple === false ? 'kpi-card--bajo' : 'kpi-card--neutro'

  return (
    <div className={`kpi-card ${claseEstado}`}>
      <p className="kpi-card-label">{etiqueta}</p>
      <p className="kpi-card-valor">
        {valor === null || valor === undefined ? '—' : valor}
        <span className="kpi-card-unidad">{valor !== null ? unidad : ''}</span>
      </p>
      <p className="kpi-card-umbral">Umbral: {umbral}</p>
    </div>
  )
}

export default function Dashboard() {
  const [kpis, setKpis] = useState(null)
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/metricas`)
      .then((r) => {
        if (!r.ok) throw new Error(`Error ${r.status}`)
        return r.json()
      })
      .then(setKpis)
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }, [])

  if (cargando) return <div className="dashboard-mensaje">Cargando métricas...</div>
  if (error) return <div className="dashboard-mensaje dashboard-mensaje--error">No se pudo cargar el dashboard: {error}</div>
  if (!kpis) return null

  return (
    <div className="dashboard">
      <p className="dashboard-subtitulo">
        Basado en {kpis.total_consultas_registradas} consulta(s) registrada(s)
      </p>
      <div className="kpi-grid">
        {Object.entries(ETIQUETAS).map(([clave, etiqueta]) => (
          <TarjetaKPI key={clave} etiqueta={etiqueta} dato={kpis[clave]} />
        ))}
      </div>
    </div>
  )
}
