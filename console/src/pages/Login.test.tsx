import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { api } from "../api";
import { AuthProvider } from "../auth";
import "../i18n";
import { LoginPage } from "./Login";

vi.mock("../api", () => ({
  api: {
    login: vi.fn(),
    me: vi.fn().mockRejectedValue(new Error("offline")),
    logout: vi.fn(),
    setRole: vi.fn(),
  },
}));

test("login sends the app password with spaces removed", async () => {
  vi.mocked(api.login).mockResolvedValue({
    token: "token",
    email: "a@b.com",
  });
  const user = userEvent.setup();
  render(
    <AuthProvider>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </AuthProvider>,
  );
  await user.type(screen.getByLabelText("Email address"), "a@b.com");
  await user.type(screen.getByLabelText("Gmail app password"), "abcd efgh ijkl mnop");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(api.login).toHaveBeenCalledWith({
    email: "a@b.com",
    app_password: "abcdefghijklmnop",
  });
});
