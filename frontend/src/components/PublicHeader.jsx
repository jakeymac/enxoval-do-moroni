import { Link } from 'react-router-dom'

import { tokens } from '../api.js'
import { ADMIN_PATH } from '../config.js'

/**
 * Barra no topo da página pública, só com o acesso do dono.
 *
 * Sem título: a página já mostra o nome do enxoval no h1 logo abaixo, e ele
 * vem do banco — repetir aqui significaria uma cópia desatualizada no dia em
 * que o nome mudar nos ajustes. Quem veio presentear não precisa de conta, por
 * isso o link fica discreto, à direita.
 */
export default function PublicHeader() {
  const signedIn = Boolean(tokens.access)

  return (
    <header className="masthead">
      <div className="masthead__inner">
        <div className="spacer" />
        {signedIn ? (
          <Link className="btn small" to={`${ADMIN_PATH}/painel`}>
            Editar enxoval
          </Link>
        ) : (
          <Link className="btn small" to={ADMIN_PATH}>
            Entrar
          </Link>
        )}
      </div>
    </header>
  )
}
