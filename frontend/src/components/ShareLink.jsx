import { useState } from 'react'

/** Mostra o endereço público com um clique para copiar — é o link que vai para todo mundo. */
export default function ShareLink() {
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/`

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      return // Área de transferência bloqueada (ex.: fora de HTTPS); dá para copiar à mão.
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="sharebar">
      <code>{url}</code>
      <button className="small" onClick={copy}>
        {copied ? 'Copiado' : 'Copiar link'}
      </button>
      <a className="btn small" href="/" target="_blank" rel="noreferrer">
        Ver página
      </a>
    </div>
  )
}
