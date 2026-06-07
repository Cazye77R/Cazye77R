import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import ErrorBoundary from './components/ErrorBoundary'
import OfflineBanner from './components/OfflineBanner'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import UserManagement from './pages/admin/UserManagement'
import ReittagebuchLayout from './pages/reittagebuch/ReittagebuchLayout'
import EntryForm from './pages/reittagebuch/EntryForm'
import Overview from './pages/reittagebuch/Overview'
import Stats from './pages/reittagebuch/Stats'
import Animals from './pages/reittagebuch/Animals'
import ExportPage from './pages/reittagebuch/ExportPage'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <OfflineBanner />
            <Routes>
              <Route path="/login" element={<Login />} />

              <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                <Route path="/dashboard" element={<Dashboard />} />

                <Route path="/admin/users" element={
                  <AdminRoute><UserManagement /></AdminRoute>
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
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
