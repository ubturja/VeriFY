import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { QueuePage } from "./pages/Queue";
import { CasePage } from "./pages/Case";
import { DashboardPage } from "./pages/Dashboard";
import { SubmitPage } from "./pages/Submit";
import { AuditPage } from "./pages/Audit";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<QueuePage />} />
          <Route path="cases/:id" element={<CasePage />} />
          <Route path="overview" element={<DashboardPage />} />
          <Route path="submit" element={<SubmitPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
