import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { KeyRound, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useAdminAuth } from "@/contexts/AdminAuthContext";

export default function AdminLoginPage() {
  const { authenticated, checking, login } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [token, setToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const from = (location.state as { from?: string } | null)?.from || "/admin/accounts";

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        <RefreshCw className="mr-2 h-5 w-5 animate-spin" />
        正在检查管理员会话…
      </div>
    );
  }
  if (authenticated) return <Navigate to={from} replace />;

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      await login(token);
      navigate(from, { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <KeyRound className="h-5 w-5" />
          </div>
          <CardTitle>管理员登录</CardTitle>
          <p className="text-sm text-muted-foreground">请输入服务端配置的管理令牌。</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="admin-token">管理令牌</Label>
            <Input
              id="admin-token"
              type="password"
              autoComplete="current-password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && token) void submit();
              }}
            />
          </div>
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <Button className="w-full" disabled={!token || submitting} onClick={() => void submit()}>
            {submitting ? "登录中…" : "登录"}
          </Button>
          <Button variant="outline" className="w-full" onClick={() => navigate("/")}>
            返回公开页面
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
