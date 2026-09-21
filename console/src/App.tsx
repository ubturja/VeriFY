import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { WelcomePage } from "./pages/Welcome";
import { QueuePage } from "./pages/Queue";
import { CasePage } from "./pages/Case";
import { DashboardPage } from "./pages/Dashboard";
import { SubmitPage } from "./pages/Submit";
import { AuditPage } from "./pages/Audit";
import { ProfilePage } from "./pages/Profile";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<WelcomePage />} />
          <Route path="queue" element={<QueuePage />} />
          <Route path="cases/:id" element={<CasePage />} />
          <Route path="overview" element={<DashboardPage />} />
          <Route path="submit" element={<SubmitPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
