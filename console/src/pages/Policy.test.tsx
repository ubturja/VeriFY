import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { api } from "../api";
import "../i18n";
import { PolicyPage } from "./Policy";

vi.mock("../api", () => ({
  COMPARE_FIELDS: ["shipper"],
  api: {
    policy: vi.fn().mockResolvedValue({
      weight_tolerance_kg: 0,
      mandatory_fields: ["shipper"],
      fields_may_differ: [],
    }),
    savePolicy: vi.fn(),
  },
}));

test("a failed policy save shows the error and does not claim success", async () => {
  vi.mocked(api.savePolicy).mockRejectedValue(new Error("Auditors cannot edit policy"));
  const user = userEvent.setup();
  render(<PolicyPage />);
  await user.click(await screen.findByRole("button", { name: "Save policy" }));
  expect(await screen.findByText("Auditors cannot edit policy")).toBeTruthy();
  expect(screen.queryByText("Saved.")).toBeNull();
});
