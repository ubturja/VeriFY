import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { AuthProvider } from "../auth";
import "../i18n";
import { AppShell } from "./AppShell";

vi.mock("../api", () => ({
  api: {
    login: vi.fn(),
    me: vi.fn().mockRejectedValue(new Error("offline")),
    logout: vi.fn(),
    setRole: vi.fn(),
  },
}));

function renderShell() {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/queue"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="queue" element={<div>Queue body</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

test("a supervisor sees policy and an auditor does not", () => {
  localStorage.setItem(
    "verify.session.v1",
    JSON.stringify({ token: "t", email: "owner@example.com", role: "supervisor" }),
  );
  renderShell();
  fireEvent.click(screen.getByRole("button", { name: "Toggle navigation" }));
  expect(screen.getByText("Policy")).toBeTruthy();
  expect(screen.getByText("Queue body")).toBeTruthy();
  cleanup();

  localStorage.setItem(
    "verify.session.v1",
    JSON.stringify({ token: "t", email: "owner@example.com", role: "auditor" }),
  );
  renderShell();
  fireEvent.click(screen.getByRole("button", { name: "Toggle navigation" }));
  expect(screen.queryByText("Policy")).toBeNull();
});
