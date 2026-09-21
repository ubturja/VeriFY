import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { QueuePage } from "./pages/Queue";
import { CasePage } from "./pages/Case";
import { DashboardPage } from "./pages/Dashboard";
import { SubmitPage } from "./pages/Submit";
import { AuditPage } from "./pages/Audit";
import { PolicyPage } from "./pages/Policy";
import { WebhooksPage } from "./pages/Webhooks";
import { DeadLettersPage } from "./pages/DeadLetters";
import { ProfilePage } from "./pages/Profile";
import { LoginPage } from "./pages/Login";
import { WelcomePage } from "./pages/Welcome";
import { AuthProvider, useAuth } from "./auth";

function RequireAuth() {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function RedirectIfSignedIn() {
  const { session } = useAuth();
  if (session) return <Navigate to="/" replace />;
  return <LoginPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<RedirectIfSignedIn />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route index element={<WelcomePage />} />
              <Route path="queue" element={<QueuePage />} />
              <Route path="cases/:id" element={<CasePage />} />
              <Route path="overview" element={<DashboardPage />} />
              <Route path="submit" element={<SubmitPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="policy" element={<PolicyPage />} />
              <Route path="webhooks" element={<WebhooksPage />} />
              <Route path="dead-letters" element={<DeadLettersPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

