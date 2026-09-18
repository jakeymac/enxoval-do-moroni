import { useNavigate } from 'react-router-dom'

import { tokens } from '../api.js'
import { ADMIN_PATH } from '../config.js'

export default function Masthead({ children }) {
  const navigate = useNavigate()

  function signOut() {
    tokens.clear()
    navigate(ADMIN_PATH, { replace: true })
  }

  return (
    <header className="masthead">
      <div className="masthead__inner">
        <span className="masthead__title">Enxoval</span>
        <div className="spacer" />
        {children}
        <button className="ghost" onClick={signOut}>
          Sair
        </button>
      </div>
    </header>
  )
}
