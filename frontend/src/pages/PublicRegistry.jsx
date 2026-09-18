import { useEffect, useRef, useState } from 'react'

import { api } from '../api.js'

const STORAGE_KEY = 'enxoval.visitante'
const BLANK = { first_name: '', last_name: '', email: '' }

/** Quem já preencheu os dados não precisa digitar de novo a cada item. */
function loadVisitor() {
  try {
    return { ...BLANK, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
  } catch {
    return { ...BLANK }
  }
}

const LOOKS_LIKE_EMAIL = /^\S+@\S+\.\S+$/

/** Campos que faltam, na ordem em que aparecem na tela. */
function missingFields(visitor) {
  const missing = []
  if (!visitor.first_name.trim()) missing.push('first_name')
  if (!visitor.last_name.trim()) missing.push('last_name')
  if (!LOOKS_LIKE_EMAIL.test(visitor.email.trim())) missing.push('email')
  return missing
}

export default function PublicRegistry() {
  const [registry, setRegistry] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [visitor, setVisitor] = useState(loadVisitor)
  const [flagged, setFlagged] = useState([])
  const [thanks, setThanks] = useState(null)
  const [error, setError] = useState('')
  const [claimingId, setClaimingId] = useState(null)

  const identityRef = useRef(null)

  useEffect(() => {
    api
      .publicRegistry()
      .then(setRegistry)
      .catch(() => setNotFound(true))
  }, [])

  function field(name, value) {
    const next = { ...visitor, [name]: value }
    setVisitor(next)
    setFlagged((prev) => prev.filter((f) => f !== name))
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      // Navegador sem armazenamento local: só perde a comodidade de não redigitar.
    }
  }

  async function claim(item, quantity) {
    setError('')
    const missing = missingFields(visitor)
    if (missing.length > 0) {
      // Sem nome, sobrenome e e-mail não dá para reservar: é como o contato acontece depois.
      setFlagged(missing)
      const section = identityRef.current
      section?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      section?.querySelector(`#${missing[0]}`)?.focus({ preventScroll: true })
      return
    }

    setClaimingId(item.id)
    try {
      const result = await api.claimItem(item.id, {
        first_name: visitor.first_name.trim(),
        last_name: visitor.last_name.trim(),
        email: visitor.email.trim(),
        quantity,
      })
      setThanks(result.contact_note || 'Entraremos em contato em breve.')
      setRegistry(await api.publicRegistry())
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err.detail)
    } finally {
      setClaimingId(null)
    }
  }

  if (notFound) {
    return (
      <main className="page">
        <h1>Esta página não está disponível</h1>
        <p className="muted">
          O enxoval pode ter saído do ar. Fale com quem enviou o link para você.
        </p>
      </main>
    )
  }

  if (!registry) return <main className="page muted">Carregando…</main>

  const available = registry.items.filter((i) => !i.is_fully_claimed)
  const taken = registry.items.filter((i) => i.is_fully_claimed)
  const ready = missingFields(visitor).length === 0

  return (
    <main className="page">
      <h1>{registry.title}</h1>
      {registry.intro && (
        <p className="muted" style={{ fontSize: '1.05rem' }}>
          {registry.intro}
        </p>
      )}

      {thanks && (
        <div className="alert alert--ok" style={{ margin: '16px 0' }}>
          <strong>Obrigado!</strong> {thanks}
        </div>
      )}

      <VisitorFields
        innerRef={identityRef}
        visitor={visitor}
        flagged={flagged}
        ready={ready}
        onChange={field}
      />

      {error && (
        <div className="alert alert--error" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {available.length === 0 && (
        <div className="card card--flat muted">
          Todos os itens já foram escolhidos. Obrigado a todo mundo que ajudou!
        </div>
      )}

      <div className="item-grid">
        {available.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            busy={claimingId === item.id}
            onClaim={(quantity) => claim(item, quantity)}
          />
        ))}
      </div>

      {taken.length > 0 && (
        <>
          <h2 style={{ marginTop: 32 }}>Já escolhidos</h2>
          <div className="item-grid">
            {taken.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </>
      )}
    </main>
  )
}

function VisitorFields({ innerRef, visitor, flagged, ready, onChange }) {
  return (
    <section
      ref={innerRef}
      className="card stack"
      style={{ margin: '20px 0 24px', scrollMarginTop: 16 }}
      aria-labelledby="seus-dados"
    >
      <div>
        <h2 id="seus-dados" style={{ marginBottom: 2 }}>
          Seus dados
        </h2>
        <p className="muted" style={{ margin: 0, fontSize: '0.92rem' }}>
          Preencha antes de escolher um item — é assim que entramos em contato com você. Nada é
          pago nem comprado aqui.
        </p>
      </div>

      <div className="form-grid">
        <div>
          <label htmlFor="first_name">Nome</label>
          <input
            id="first_name"
            value={visitor.first_name}
            onChange={(e) => onChange('first_name', e.target.value)}
            aria-invalid={flagged.includes('first_name')}
            autoComplete="given-name"
          />
        </div>
        <div>
          <label htmlFor="last_name">Sobrenome</label>
          <input
            id="last_name"
            value={visitor.last_name}
            onChange={(e) => onChange('last_name', e.target.value)}
            aria-invalid={flagged.includes('last_name')}
            autoComplete="family-name"
          />
        </div>
        <div>
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            value={visitor.email}
            onChange={(e) => onChange('email', e.target.value)}
            aria-invalid={flagged.includes('email')}
            autoComplete="email"
          />
        </div>
      </div>

      {flagged.length > 0 ? (
        <div className="alert alert--error" role="alert">
          Preencha nome, sobrenome e um e-mail válido para poder escolher um item.
        </div>
      ) : (
        ready && (
          <p className="faint" style={{ margin: 0 }}>
            Tudo certo, {visitor.first_name.trim()} — agora é só escolher um item abaixo.
          </p>
        )
      )}
    </section>
  )
}

function ItemCard({ item, busy, onClaim }) {
  const [quantity, setQuantity] = useState(1)
  const claimed = item.is_fully_claimed

  return (
    <div className={`card${claimed ? ' card--claimed' : ''}`}>
      {item.image_url && <img className="item__thumb" src={item.image_url} alt="" />}
      <div className="item__name">{item.name}</div>
      <div className="item__meta">
        {claimed ? (
          <span className="badge badge--done">Escolhido</span>
        ) : (
          <span className="badge badge--need">
            {item.quantity_remaining === 1
              ? 'falta 1'
              : `faltam ${item.quantity_remaining}`}
          </span>
        )}
        {item.estimated_price && (
          <span className="faint">cerca de R$ {item.estimated_price}</span>
        )}
      </div>
      {item.description && (
        <p className="muted" style={{ fontSize: '0.9rem' }}>
          {item.description}
        </p>
      )}
      {item.product_url && (
        <p style={{ fontSize: '0.9rem' }}>
          <a href={item.product_url} target="_blank" rel="noreferrer">
            Ver um exemplo →
          </a>
        </p>
      )}
      {!claimed && (
        <>
          {item.quantity_remaining > 1 && (
            <div style={{ marginBottom: 10 }}>
              <label htmlFor={`qtd-${item.id}`}>Quantos você vai comprar?</label>
              <select
                id={`qtd-${item.id}`}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              >
                {Array.from({ length: item.quantity_remaining }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button
            className="primary"
            style={{ width: '100%' }}
            disabled={busy}
            onClick={() => onClaim(quantity)}
          >
            {busy ? 'Reservando…' : 'Vou comprar este'}
          </button>
        </>
      )}
    </div>
  )
}
