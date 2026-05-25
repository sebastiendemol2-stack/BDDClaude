import { useState, useRef, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { useTenant } from '../lib/tenants'

interface Source {
  title: string
  snippet: string
  score: number
}

interface Message {
  id: string
  question: string
  answer: string
  sources: Source[]
  llm_used: boolean
}

const FUNCTIONS_URL = import.meta.env.VITE_SUPABASE_URL?.replace(/\/$/, '') + '/functions/v1/rag-answer'

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { selectedTenant, loading: tenantLoading } = useTenant()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = input.trim()
    if (!q || loading) return

    setInput('')
    setLoading(true)

    try {
      if (tenantLoading || !selectedTenant) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          question: q,
          answer: tenantLoading ? 'Chargement du tenant en cours.' : 'Aucun tenant actif disponible.',
          sources: [],
          llm_used: false,
        }])
        return
      }

      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token
      if (!token) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          question: q,
          answer: 'Vous devez être connecté pour utiliser le chat.',
          sources: [],
          llm_used: false,
        }])
        return
      }

      const res = await fetch(FUNCTIONS_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ question: q, max_sources: 5, tenant_slug: selectedTenant.slug }),
      })

      if (!res.ok) {
        const err = await res.json()
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          question: q,
          answer: `Erreur: ${err.error || res.status}`,
          sources: [],
          llm_used: false,
        }])
        return
      }

      const data = await res.json()
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        question: q,
        answer: data.answer,
        sources: data.sources || [],
        llm_used: data.llm_used,
      }])
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        question: q,
        answer: 'Erreur de connexion au serveur.',
        sources: [],
        llm_used: false,
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <h1>Chat Vault</h1>
      <p className="chat-subtitle">Posez une question sur votre vault — recherche hybride vector + BM25</p>

      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            Posez une question pour explorer votre vault.
            <br />Ex: « architecture de Cowork App », « vecteur search », « décisions récentes »
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className="msg">
            <div className="msg-q">
              <strong>Q:</strong> {msg.question}
            </div>
            <div className="msg-a">
              <pre className="msg-text">{msg.answer}</pre>
              {msg.sources.length > 0 && (
                <details className="msg-sources">
                  <summary>Sources ({msg.sources.length})</summary>
                  {msg.sources.map((s, i) => (
                    <div key={i} className="source-item">
                      <span className="source-title">{s.title}</span>
                      <span className="source-score">{(s.score * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </details>
              )}
              {msg.llm_used && <span className="llm-badge">LLM</span>}
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg msg-loading">
            <div className="msg-a">Recherche dans le vault...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Posez une question..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? '...' : 'Envoyer'}
        </button>
      </form>
    </div>
  )
}
