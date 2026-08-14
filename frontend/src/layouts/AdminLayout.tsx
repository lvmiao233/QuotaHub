import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, List, LogOut, RefreshCw, Settings, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/admin/accounts", label: "账号管理", icon: Users },
  { to: "/admin/usage", label: "调用日志", icon: List },
  { to: "/admin/settings", label: "设置", icon: Settings },
];

export function AdminLayout() {
  const { authenticated, checking, logout } = useAdminAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        <RefreshCw className="mr-2 h-5 w-5 animate-spin" />
        正在检查管理员会话…
      </div>
    );
  }
  if (!authenticated) {
    return <Navigate to="/admin/login" state={{ from: location.pathname }} replace />;
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-6 md:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-800">QuotaHub 管理后台</h1>
          <p className="text-sm text-muted-foreground">凭证、渠道与采集设置仅管理员可见</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <nav className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                    isActive ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <Button variant="outline" size="sm" onClick={() => navigate("/")}>
            <ArrowLeft className="h-4 w-4" />
            公开页
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void logout().then(() => navigate("/admin/login", { replace: true }))}
          >
            <LogOut className="h-4 w-4" />
            退出
          </Button>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
