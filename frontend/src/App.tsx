import { Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import Layout from "./components/Layout";
import { RequireAdmin, RequireUser } from "./components/ProtectedRoute";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Directory from "./pages/Directory";
import BusinessDetail from "./pages/BusinessDetail";
import Profile from "./pages/Profile";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";
import AdminBusinesses from "./pages/AdminBusinesses";
import AdminUsers from "./pages/AdminUsers";
import AdminTransactions from "./pages/AdminTransactions";

export default function App() {
  return (
    <AuthProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/directory" element={<Directory />} />
          <Route path="/businesses/:id" element={<BusinessDetail />} />
          <Route
            path="/profile"
            element={
              <RequireUser>
                <Profile />
              </RequireUser>
            }
          />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminDashboard />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/users"
            element={
              <RequireAdmin>
                <AdminUsers />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/businesses"
            element={
              <RequireAdmin>
                <AdminBusinesses />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/transactions"
            element={
              <RequireAdmin>
                <AdminTransactions />
              </RequireAdmin>
            }
          />
          <Route path="*" element={<Landing />} />
        </Routes>
      </Layout>
    </AuthProvider>
  );
}