import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, tokens } from '../api.js'
import { ADMIN_PATH } from '../config.js'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      tokens.set(await api.login(username, password))
      navigate(`${ADMIN_PATH}/painel`, { replace: true })
    } catch (err) {
      setError(err.status === 401 ? 'Usuário ou senha incorretos.' : err.detail)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="center-narrow">
      <h1>Entrar</h1>
      <p className="muted">
        Área de quem administra o enxoval. Quem vai presentear não precisa de conta.
      </p>
      <form className="card stack" onSubmit={submit}>
        <div>
          <label htmlFor="username">Usuário</label>
          <input
            id="username"
            value={username}
            autoComplete="username"
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Senha</label>
          <input
            id="password"
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <div className="alert alert--error">{error}</div>}
        <button className="primary" disabled={busy}>
          {busy ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
