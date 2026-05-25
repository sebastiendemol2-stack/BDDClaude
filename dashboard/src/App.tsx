import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import Health from './pages/Health'
import SearchStats from './pages/SearchStats'
import RuntimeEvents from './pages/RuntimeEvents'
import WorktreeStatus from './pages/WorktreeStatus'
import Chat from './pages/Chat'
import Models from './pages/Models'
import Graph from './pages/Graph'
import Login from './pages/Login'
import { AuthProvider, useAuth } from './lib/auth'
import { TenantsProvider } from './lib/tenants'
import TenantSelector from './components/TenantSelector'
import './App.css'

function AuthControls() {
  const { user, isAdmin, signOut, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  if (loading) return null

  if (user) {
    return (
      <div className="auth-controls">
        <span className="muted">
          {user.email}
          {isAdmin && <strong> · admin</strong>}
        </span>
        <button
          className="btn-secondary"
          onClick={async () => {
            await signOut()
            navigate('/health', { replace: true })
          }}
        >
          Sign out
        </button>
      </div>
    )
  }

  return (
    <NavLink
      to="/login"
      state={{ from: location }}
      className={({ isActive }) => (isActive ? 'active' : '')}
    >
      Sign in
    </NavLink>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-layout">
      <nav className="sidebar">
        <h1>BDDClaude</h1>
        <NavLink to="/health" className={({ isActive }) => isActive ? 'active' : ''}>Health</NavLink>
        <NavLink to="/search-stats" className={({ isActive }) => isActive ? 'active' : ''}>Search Stats</NavLink>
        <NavLink to="/runtime-events" className={({ isActive }) => isActive ? 'active' : ''}>Runtime Events</NavLink>
        <NavLink to="/worktree-status" className={({ isActive }) => isActive ? 'active' : ''}>Worktree Status</NavLink>
        <NavLink to="/chat" className={({ isActive }) => isActive ? 'active' : ''}>Chat Vault</NavLink>
        <NavLink to="/models" className={({ isActive }) => isActive ? 'active' : ''}>Models</NavLink>
        <NavLink to="/graph" className={({ isActive }) => isActive ? 'active' : ''}>Memory Graph</NavLink>
        <TenantSelector />
        <AuthControls />
      </nav>
      <main className="content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <TenantsProvider>
          <Layout>
            <Routes>
              <Route path="/health" element={<Health />} />
              <Route path="/search-stats" element={<SearchStats />} />
              <Route path="/runtime-events" element={<RuntimeEvents />} />
              <Route path="/worktree-status" element={<WorktreeStatus />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/models" element={<Models />} />
              <Route path="/graph" element={<Graph />} />
              <Route path="/login" element={<Login />} />
              <Route path="*" element={<Navigate to="/health" replace />} />
            </Routes>
          </Layout>
        </TenantsProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
