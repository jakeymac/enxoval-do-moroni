import { Navigate, Route, Routes } from 'react-router-dom'

import { tokens } from './api.js'
import { ADMIN_PATH } from './config.js'
import Login from './pages/Login.jsx'
import PublicRegistry from './pages/PublicRegistry.jsx'
import RegistryEditor from './pages/RegistryEditor.jsx'

function RequireAuth({ children }) {
  return tokens.access ? children : <Navigate to={ADMIN_PATH} replace />
}

export default function App() {
  return (
    <Routes>
      {/* A página que todo mundo acessa. */}
      <Route path="/" element={<PublicRegistry />} />

      {/* Área do dono, em um endereço separado que a página pública não divulga. */}
      <Route path={ADMIN_PATH} element={<Login />} />
      <Route
        path={`${ADMIN_PATH}/painel`}
        element={
          <RequireAuth>
            <RegistryEditor />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
