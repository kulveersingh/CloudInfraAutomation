import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithApi } from "../../test/render";
import { AdminPage } from "./AdminPage";

describe("AdminPage", () => {
  it("opens on cost centers", async () => {
    renderWithApi(<AdminPage />);
    expect(await screen.findByLabelText("Organization default")).toBeInTheDocument();
  });

  it("switches to regions", async () => {
    renderWithApi(<AdminPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Regions" }));
    expect(await screen.findByLabelText("Enable us-east-1")).toBeInTheDocument();
  });

  it("marks the selected tab", async () => {
    renderWithApi(<AdminPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Regions" }));
    expect(screen.getByRole("tab", { name: "Regions" })).toHaveAttribute("aria-selected", "true");
  });

  it("switches to networks", async () => {
    renderWithApi(<AdminPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Networks" }));
    expect(await screen.findByLabelText("Attach compute to the organization VPC by default")).toBeInTheDocument();
  });
});
