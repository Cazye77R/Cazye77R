import { useState, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { BrandingProvider, useBranding } from './context/BrandingContext'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import StartupAnimation from './components/StartupAnimation'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import UserManagement from './pages/admin/UserManagement'
import BrandingSettings from './pages/admin/BrandingSettings'
import ReittagebuchLayout from './pages/reittagebuch/ReittagebuchLayout'
import EntryForm from './pages/reittagebuch/EntryForm'
import Overview from './pages/reittagebuch/Overview'
import Stats from './pages/reittagebuch/Stats'
import Animals from './pages/reittagebuch/Animals'
import ExportPage from './pages/reittagebuch/ExportPage'

function AnimatedApp() {
  const { app_name, animation_theme, custom_subtitle, loading } = useBranding()
  const [showAnim, setShowAnim] = useState(
    () => !sessionStorage.getItem('startup_shown')
  )

  const handleDone = useCallback(() => {
    sessionStorage.setItem('startup_shown', 'true')
    setShowAnim(false)
  }, [])

  return (
    <>
      {showAnim && !loading && (
        <StartupAnimation
          appName={app_name}
          animationTheme={animation_theme}
          subtitle={custom_subtitle}
          onDone={handleDone}
        />
      )}
      <OfflineBanner />
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />

          <Route path="/admin/users" element={
            <AdminRoute><UserManagement /></AdminRoute>
          } />
          <Route path="/admin/branding" element={
            <AdminRoute><BrandingSettings /></AdminRoute>
          } />

          <Route path="/reittagebuch" element={<ReittagebuchLayout />}>
            <Route index element={<Navigate to="neu" replace />} />
            <Route path="neu"          element={<EntryForm />} />
            <Route path="uebersicht"   element={<Overview />} />
            <Route path="auswertungen" element={<Stats />} />
            <Route path="tiere"        element={<Animals />} />
            <Route path="export"       element={<ExportPage />} />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <BrandingProvider>
              <AnimatedApp />
            </BrandingProvider>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
