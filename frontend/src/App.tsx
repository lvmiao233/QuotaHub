import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminAuthProvider } from "@/contexts/AdminAuthContext";
import { QuotaProvider } from "@/contexts/QuotaContext";
import { AdminLayout } from "@/layouts/AdminLayout";
import { AppLayout } from "@/layouts/AppLayout";
import AccountDetailPage from "@/pages/AccountDetailPage";
import AccountsPage from "@/pages/AccountsPage";
import AllUsagePage from "@/pages/AllUsagePage";
import DashboardPage from "@/pages/DashboardPage";
import OverviewPage from "@/pages/OverviewPage";
import SettingsPage from "@/pages/SettingsPage";
import AdminLoginPage from "@/pages/AdminLoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <AdminAuthProvider>
        <QuotaProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<OverviewPage />} />
              <Route path="overview" element={<Navigate to="/" replace />} />
              <Route path="quota" element={<DashboardPage />} />
            </Route>
            <Route path="/admin/login" element={<AdminLoginPage />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="accounts" replace />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="accounts/opencode/:id" element={<AccountDetailPage />} />
              <Route path="usage" element={<AllUsagePage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </QuotaProvider>
      </AdminAuthProvider>
    </BrowserRouter>
  );
}
