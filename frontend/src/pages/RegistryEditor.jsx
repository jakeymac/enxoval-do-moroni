import { useCallback, useEffect, useState } from 'react'

import { api } from '../api.js'
import Masthead from '../components/Masthead.jsx'
import ShareLink from '../components/ShareLink.jsx'

const BLANK_ITEM = {
  name: '',
  description: '',
  quantity_needed: 1,
  estimated_price: '',
  product_url: '',
  image_url: '',
}

const STATUS_LABEL = {
  pending: 'Aguardando contato',
  contacted: 'Contato feito',
  fulfilled: 'Recebido',
  cancelled: 'Cancelado',
}

export default function RegistryEditor() {
  const [registry, setRegistry] = useState(null)
  const [claims, setClaims] = useState([])
  const [error, setError] = useState('')
  const [tab, setTab] = useState('itens')

  const reload = useCallback(async () => {
    try {
      const [reg, cls] = await Promise.all([api.getRegistry(), api.listClaims()])
      setRegistry(reg)
      setClaims(cls)
    } catch (err) {
      setError(err.detail)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  if (error && !registry) {
    return (
      <div className="page">
        <div className="alert alert--error">{error}</div>
      </div>
    )
  }
  if (!registry) return <div className="page muted">Carregando…</div>

  const pending = claims.filter((c) => c.status === 'pending').length

  return (
    <>
      <Masthead />
      <main className="page page--wide">
        <h1 style={{ marginBottom: 4 }}>{registry.title}</h1>
        <p className="muted">Este é o link para enviar a quem você quiser.</p>
        <ShareLink />

        <div className="row" style={{ margin: '24px 0 14px' }}>
          {[
            ['itens', `Itens (${registry.items.length})`],
            ['reservas', `Quem vai comprar${pending ? ` (${pending})` : ''}`],
            ['ajustes', 'Ajustes'],
          ].map(([key, label]) => (
            <button
              key={key}
              className={tab === key ? 'primary small' : 'ghost small'}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {error && <div className="alert alert--error">{error}</div>}

        {tab === 'itens' && <ItemsTab registry={registry} onChange={reload} setError={setError} />}
        {tab === 'reservas' && (
          <ClaimsTab claims={claims} onChange={reload} setError={setError} />
        )}
        {tab === 'ajustes' && (
          <SettingsTab registry={registry} onChange={reload} setError={setError} />
        )}
      </main>
    </>
  )
}

function ItemsTab({ registry, onChange, setError }) {
  const [draft, setDraft] = useState(BLANK_ITEM)
  const [editingId, setEditingId] = useState(null)
  const [busy, setBusy] = useState(false)

  function field(name, value) {
    setDraft((prev) => ({ ...prev, [name]: value }))
  }

  async function save(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    // Preço vazio precisa ir como null, não como "", senão o campo decimal recusa.
    const payload = {
      ...draft,
      registry: registry.id,
      estimated_price: draft.estimated_price === '' ? null : draft.estimated_price,
      position: editingId ? draft.position : registry.items.length,
    }
    try {
      if (editingId) await api.updateItem(editingId, payload)
      else await api.createItem(payload)
      setDraft(BLANK_ITEM)
      setEditingId(null)
      await onChange()
    } catch (err) {
      setError(err.detail)
    } finally {
      setBusy(false)
    }
  }

  async function remove(item) {
    const warning =
      item.quantity_claimed > 0
        ? `${item.name} tem ${item.quantity_claimed} reserva(s). Excluir o item também exclui as reservas. Continuar?`
        : `Excluir ${item.name}?`
    if (!window.confirm(warning)) return
    try {
      await api.deleteItem(item.id)
      await onChange()
    } catch (err) {
      setError(err.detail)
    }
  }

  function startEdit(item) {
    setEditingId(item.id)
    setDraft({ ...item, estimated_price: item.estimated_price ?? '' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="stack">
      <form className="card stack" onSubmit={save}>
        <h2>{editingId ? 'Editar item' : 'Adicionar um item'}</h2>
        <div>
          <label htmlFor="name">O que é?</label>
          <input
            id="name"
            value={draft.name}
            onChange={(e) => field('name', e.target.value)}
            placeholder="Jogo de lençóis de casal"
            required
          />
        </div>
        <div>
          <label htmlFor="description">Observações (opcional)</label>
          <textarea
            id="description"
            value={draft.description}
            onChange={(e) => field('description', e.target.value)}
            placeholder="Tamanho, cor, marca — o que ajudar a pessoa a escolher certo."
          />
        </div>
        <div className="form-grid">
          <div>
            <label htmlFor="qty">Quantos precisa</label>
            <input
              id="qty"
              type="number"
              min="1"
              value={draft.quantity_needed}
              onChange={(e) => field('quantity_needed', Number(e.target.value))}
            />
          </div>
          <div>
            <label htmlFor="price">Preço aproximado (opcional)</label>
            <input
              id="price"
              type="number"
              step="0.01"
              min="0"
              value={draft.estimated_price}
              onChange={(e) => field('estimated_price', e.target.value)}
              placeholder="250,00"
            />
          </div>
        </div>
        <div className="form-grid">
          <div>
            <label htmlFor="product_url">Onde comprar (opcional)</label>
            <input
              id="product_url"
              type="url"
              value={draft.product_url}
              onChange={(e) => field('product_url', e.target.value)}
              placeholder="https://…"
            />
          </div>
          <div>
            <label htmlFor="image_url">Link da foto (opcional)</label>
            <input
              id="image_url"
              type="url"
              value={draft.image_url}
              onChange={(e) => field('image_url', e.target.value)}
              placeholder="https://…"
            />
          </div>
        </div>
        <div className="row">
          <button className="primary" disabled={busy}>
            {editingId ? 'Salvar alterações' : 'Adicionar à lista'}
          </button>
          {editingId && (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setEditingId(null)
                setDraft(BLANK_ITEM)
              }}
            >
              Cancelar
            </button>
          )}
        </div>
      </form>

      <div className="item-grid">
        {registry.items.map((item) => (
          <div
            key={item.id}
            className={`card${item.quantity_remaining === 0 ? ' card--claimed' : ''}`}
          >
            {item.image_url && <img className="item__thumb" src={item.image_url} alt="" />}
            <div className="item__name">{item.name}</div>
            <div className="item__meta">
              <span
                className={`badge ${item.quantity_remaining === 0 ? 'badge--done' : 'badge--need'}`}
              >
                {item.quantity_claimed} de {item.quantity_needed} reservado(s)
              </span>
              {item.estimated_price && <span className="faint">~R$ {item.estimated_price}</span>}
            </div>
            {item.description && (
              <p className="muted" style={{ fontSize: '0.9rem' }}>
                {item.description}
              </p>
            )}
            <div className="row">
              <button className="small ghost" onClick={() => startEdit(item)}>
                Editar
              </button>
              <button className="small ghost danger" onClick={() => remove(item)}>
                Excluir
              </button>
            </div>
          </div>
        ))}
      </div>
      {registry.items.length === 0 && (
        <p className="muted">Nenhum item ainda — adicione o primeiro acima.</p>
      )}
    </div>
  )
}

function ClaimsTab({ claims, onChange, setError }) {
  async function setStatus(claim, status) {
    try {
      await api.updateClaim(claim.id, { status })
      await onChange()
    } catch (err) {
      setError(err.detail)
    }
  }

  if (claims.length === 0) {
    return (
      <div className="card card--flat muted">
        Ninguém reservou nenhum item ainda. Quando alguém reservar, o nome e o e-mail aparecem
        aqui — e você recebe um aviso por e-mail.
      </div>
    )
  }

  return (
    <div className="card stack">
      {claims.map((claim) => (
        <div key={claim.id} className="claim-row">
          <div className="row row--between">
            <div>
              <strong>{claim.name}</strong>{' '}
              <span className="muted">
                → {claim.item_name}
                {claim.quantity > 1 && ` ×${claim.quantity}`}
              </span>
              <div className="faint">
                {claim.email} · {new Date(claim.created_at).toLocaleDateString('pt-BR')}
              </div>
              {claim.message && <p style={{ margin: '6px 0 0' }}>“{claim.message}”</p>}
            </div>
            <div className="row">
              <a
                className="btn small"
                href={`mailto:${claim.email}?subject=${encodeURIComponent(
                  `Obrigado pelo ${claim.item_name}`,
                )}`}
              >
                E-mail
              </a>
              <select
                value={claim.status}
                onChange={(e) => setStatus(claim, e.target.value)}
                style={{ width: 'auto' }}
                aria-label={`Situação da reserva de ${claim.name}`}
              >
                {Object.entries(STATUS_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function SettingsTab({ registry, onChange, setError }) {
  const [form, setForm] = useState({
    title: registry.title,
    intro: registry.intro,
    contact_note: registry.contact_note,
    notify_email: registry.notify_email,
    is_published: registry.is_published,
  })
  const [saved, setSaved] = useState(false)

  function field(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }))
    setSaved(false)
  }

  async function save(event) {
    event.preventDefault()
    setError('')
    try {
      await api.updateRegistry(form)
      setSaved(true)
      await onChange()
    } catch (err) {
      setError(err.detail)
    }
  }

  return (
    <form className="card stack" onSubmit={save}>
      <div>
        <label htmlFor="title">Nome do enxoval</label>
        <input id="title" value={form.title} onChange={(e) => field('title', e.target.value)} />
      </div>
      <div>
        <label htmlFor="intro">Texto de abertura da página pública</label>
        <textarea id="intro" value={form.intro} onChange={(e) => field('intro', e.target.value)} />
      </div>
      <div>
        <label htmlFor="contact_note">
          Agradecimento que aparece assim que alguém reserva um item
        </label>
        <input
          id="contact_note"
          value={form.contact_note}
          onChange={(e) => field('contact_note', e.target.value)}
          placeholder="Entraremos em contato com você esta semana."
        />
      </div>
      <div>
        <label htmlFor="notify_email">Enviar os avisos de reserva para</label>
        <input
          id="notify_email"
          type="email"
          value={form.notify_email}
          onChange={(e) => field('notify_email', e.target.value)}
          placeholder="o e-mail da sua conta"
        />
      </div>
      <label className="row" style={{ gap: 8 }}>
        <input
          type="checkbox"
          checked={form.is_published}
          onChange={(e) => field('is_published', e.target.checked)}
          style={{ width: 'auto' }}
        />
        <span>Página no ar (desmarque para tirar o enxoval do ar)</span>
      </label>
      <div className="row">
        <button className="primary">Salvar ajustes</button>
        {saved && <span className="alert alert--ok">Salvo</span>}
      </div>
    </form>
  )
}
