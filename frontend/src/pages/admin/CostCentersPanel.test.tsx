import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/PlatformApi";
import { COST_CENTERS, fakeApi } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { CostCentersPanel } from "./CostCentersPanel";

describe("CostCentersPanel", () => {
  it("shows the organization default", async () => {
    renderWithApi(<CostCentersPanel />);
    expect(await screen.findByLabelText("Organization default")).toHaveValue("CC-1000");
  });

  it("shows where a product's cost center comes from", async () => {
    renderWithApi(<CostCentersPanel />);
    expect(await screen.findByText("CC-4400 · inherited from portfolio")).toBeInTheDocument();
  });

  it("saves only changed values", async () => {
    const { api } = renderWithApi(<CostCentersPanel />);
    const product = await screen.findByLabelText("Cost center for Invoicing");
    await userEvent.type(product, "CC-4411");
    await userEvent.click(screen.getByRole("button", { name: "Save cost centers" }));
    expect(api.updateCostCenters).toHaveBeenCalledWith({ products: { "pr-invoicing": "CC-4411" } });
  });

  it("clearing a value saves null so it inherits again", async () => {
    const { api } = renderWithApi(<CostCentersPanel />);
    await userEvent.clear(await screen.findByLabelText("Cost center for Payments"));
    await userEvent.click(screen.getByRole("button", { name: "Save cost centers" }));
    expect(api.updateCostCenters).toHaveBeenCalledWith({ portfolios: { "pf-payments": null } });
  });

  it("saves a new organization default", async () => {
    const { api } = renderWithApi(<CostCentersPanel />);
    const field = await screen.findByLabelText("Organization default");
    await userEvent.clear(field);
    await userEvent.type(field, "CC-2000");
    await userEvent.click(screen.getByRole("button", { name: "Save cost centers" }));
    expect(api.updateCostCenters).toHaveBeenCalledWith({ default: "CC-2000" });
  });

  it("confirms a save", async () => {
    renderWithApi(<CostCentersPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "Save cost centers" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Saved");
  });

  it("shows server validation errors", async () => {
    const api = fakeApi({ updateCostCenters: vi.fn().mockRejectedValue(new ApiError(422, "Invalid cost center")) });
    renderWithApi(<CostCentersPanel />, api);
    await userEvent.click(await screen.findByRole("button", { name: "Save cost centers" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid cost center");
  });

  it("shows an empty field for a portfolio that inherits the organization default", async () => {
    const inheriting = { ...COST_CENTERS, portfolios: [{ ...COST_CENTERS.portfolios[0], cost_center: null,
      effective: { value: "CC-1000", source: "organization" } }] };
    renderWithApi(<CostCentersPanel />, fakeApi({ costCenters: vi.fn().mockResolvedValue(inheriting) }));
    expect(await screen.findByLabelText("Cost center for Payments")).toHaveValue("");
  });

  it("shows loading errors", async () => {
    renderWithApi(<CostCentersPanel />, fakeApi({ costCenters: vi.fn().mockRejectedValue(new Error("down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("down");
  });
});
