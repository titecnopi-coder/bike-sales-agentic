import { useState, useRef, useEffect } from 'react'
import logoCityBike from './assets/logo.jpg'
import './App.css'

const API_URL = 'http://localhost:8000'

const PATRONES = [
  { id: 'orchestrator', label: 'Orquestador' },
  { id: 'tools', label: 'Tools' },
  { id: 'rag', label: 'RAG' },
  { id: 'rerank', label: 'Reranking' },
  { id: 'judge', label: 'Juez' },
]

function InsigniaCityBike() {
  return <img src={logoCityBike} alt="City Bike" className="insignia" />
}

function Insignia5Patrones({ activos }) {
  return (
    <div className="patrones-fila">
      {PATRONES.map((p) => (
        <span
          key={p.id}
          className={`patron-chip ${activos.includes(p.id) ? 'patron-chip--activo' : ''}`}
        >
          {p.label}
        </span>
      ))}
    </div>
  )
}

function detectarPatronesUsados(resultado) {
  // Heurística simple solo para mostrar visualmente qué se usó en
  // esta respuesta específica -- el Orquestador y el Juez siempre
  // participan; Tools/RAG/Reranking dependen de si hubo tool_call.
  const activos = ['orchestrator', 'judge']
  if (resultado.tool_usada) {
    activos.push('tools')
    if (resultado.tool_usada === 'buscar_en_documentos') {
      activos.push('rag', 'rerank')
    }
  }
  return activos
}

function BurbujaMensaje({ mensaje }) {
  if (mensaje.autor === 'usuario') {
    return (
      <div className="fila-mensaje fila-mensaje--usuario">
        <div className="burbuja burbuja--usuario">{mensaje.texto}</div>
      </div>
    )
  }

  return (
    <div className="fila-mensaje fila-mensaje--sistema">
      <div className="burbuja burbuja--sistema">
        <p className="burbuja-texto">{mensaje.texto}</p>
        {mensaje.resultado && (
          <div className="burbuja-meta">
            <Insignia5Patrones activos={detectarPatronesUsados(mensaje.resultado)} />
            <div className="score-linea">
              <span className="score-label">SCORE JUEZ</span>
              <span className={`score-valor ${mensaje.resultado.aprobado ? 'score-valor--ok' : 'score-valor--bajo'}`}>
                {mensaje.resultado.score_juez.toFixed(1)}/10
              </span>
              {mensaje.resultado.intentos_refinamiento > 0 && (
                <span className="score-refinado">refinado x{mensaje.resultado.intentos_refinamiento}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [mensajes, setMensajes] = useState([
    {
      autor: 'sistema',
      texto: 'Hola, soy el asistente de City Bike. Pregúntame sobre ventas, métricas de negocio, o mantenimiento y uso de bicicletas.',
    },
  ])
  const [pregunta, setPregunta] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)
  const finalRef = useRef(null)

  useEffect(() => {
    finalRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  async function enviarPregunta(e) {
    e.preventDefault()
    const texto = pregunta.trim()
    if (!texto || cargando) return

    setMensajes((prev) => [...prev, { autor: 'usuario', texto }])
    setPregunta('')
    setCargando(true)
    setError(null)

    try {
      const resp = await fetch(`${API_URL}/preguntar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta: texto }),
      })

      if (!resp.ok) {
        throw new Error(`La API respondió con error ${resp.status}`)
      }

      const resultado = await resp.json()
      setMensajes((prev) => [
        ...prev,
        { autor: 'sistema', texto: resultado.respuesta, resultado },
      ])
    } catch (err) {
      setError(
        'No se pudo conectar con la API. Confirma que uvicorn esté corriendo en http://localhost:8000'
      )
      console.error(err)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="encabezado">
        <InsigniaCityBike />
        <div className="encabezado-texto">
          <h1>CITY BIKE</h1>
          <p>Asistente de analítica &mdash; Bicicletas · Taller · Accesorios</p>
        </div>
      </header>

      <main className="chat-ventana">
        {mensajes.map((m, i) => (
          <BurbujaMensaje key={i} mensaje={m} />
        ))}
        {cargando && (
          <div className="fila-mensaje fila-mensaje--sistema">
            <div className="burbuja burbuja--sistema burbuja--cargando">
              Procesando<span className="puntos-carga">...</span>
            </div>
          </div>
        )}
        {error && <div className="aviso-error">{error}</div>}
        <div ref={finalRef} />
      </main>

      <form className="barra-entrada" onSubmit={enviarPregunta}>
        <input
          type="text"
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          placeholder="Pregunta sobre ventas, métricas o bicicletas..."
          disabled={cargando}
        />
        <button type="submit" disabled={cargando || !pregunta.trim()}>
          Enviar
        </button>
      </form>
    </div>
  )
}
