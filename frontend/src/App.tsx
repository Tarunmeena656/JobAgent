import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth } from './auth';
import Layout from './components/Layout';
import Admin from './pages/Admin';
import ApplicationDetail from './pages/ApplicationDetail';
import Applications from './pages/Applications';
import Dashboard from './pages/Dashboard';
import JobDetail from './pages/JobDetail';
import Jobs from './pages/Jobs';
import Login from './pages/Login';
import Profile from './pages/Profile';
import Runs from './pages/Runs';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/reset-password" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="applications" element={<Applications />} />
        <Route path="applications/:id" element={<ApplicationDetail />} />
        <Route path="profile" element={<Profile />} />
        <Route path="activity" element={<Runs />} />
        <Route path="agent-runs" element={<Navigate to="/activity" replace />} />
        <Route
          path="admin"
          element={
            <RequireAuth admin>
              <Admin />
            </RequireAuth>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
