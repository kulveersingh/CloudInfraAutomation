import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, network, OTHER_CLOUD } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { NetworksPanel } from "./NetworksPanel";

const user = () => userEvent.setup();

async function fillForm(values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) {
    const field = screen.getByLabelText(label);
    await user().clear(field);
    await user().type(field, value);
  }
}

const NEW_NETWORK = {
  Name: "Payments VPC", "Account ID": "222222222222", Region: "us-east-2", "VPC ID": "vpc-0abc12345",
  "Private CIDR": "10.20.0.0/16", "Private subnet IDs": "subnet-0aaa1111, subnet-0bbb2222",
  "Security group IDs": "sg-0ccc3333",
};

describe("NetworksPanel", () => {
  it("lists networks per account and region", async () => {
    renderWithApi(<NetworksPanel />);
    const row = (await screen.findByText("net-prod-use1")).closest("tr")!;
    expect(within(row).getByText("vpc-0aaa1111bbbb22223")).toBeInTheDocument();
  });

  it("marks the default network", async () => {
    renderWithApi(<NetworksPanel />);
    const row = (await screen.findByText("net-prod-use1")).closest("tr")!;
    expect(within(row).getByText("Default")).toBeInTheDocument();
  });

  it("shows the attach-by-default setting", async () => {
    renderWithApi(<NetworksPanel />);
    expect(await screen.findByLabelText("Attach compute to the organization VPC by default")).toBeChecked();
  });

  it("saves the attach-by-default setting", async () => {
    const { api } = renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByLabelText("Attach compute to the organization VPC by default"));
    expect(api.updateNetworkSettings).toHaveBeenCalledWith({ attach_compute_by_default: false });
  });

  it("reflects the saved setting", async () => {
    renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByLabelText("Attach compute to the organization VPC by default"));
    expect(await screen.findByLabelText("Attach compute to the organization VPC by default")).not.toBeChecked();
  });

  it("adds a network with comma-separated ids", async () => {
    const { api } = renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByRole("button", { name: "Add network" }));
    await fillForm(NEW_NETWORK);
    await user().click(screen.getByLabelText("Default for this account and region"));
    await user().click(screen.getByRole("button", { name: "Save network" }));
    expect(api.createNetwork).toHaveBeenCalledWith({
      name: "Payments VPC", account_id: "222222222222", region: "us-east-2", network_ref: "vpc-0abc12345",
      cidr: "10.20.0.0/16", subnet_refs: ["subnet-0aaa1111", "subnet-0bbb2222"],
      firewall_refs: ["sg-0ccc3333"], is_default: true });
  });

  it("shows the added network", async () => {
    renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByRole("button", { name: "Add network" }));
    await fillForm(NEW_NETWORK);
    await user().click(screen.getByRole("button", { name: "Save network" }));
    expect(await screen.findByText("net-new")).toBeInTheDocument();
  });

  it("edits a network", async () => {
    const { api } = renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByRole("button", { name: "Edit net-prod-use1" }));
    await fillForm({ Name: "Renamed VPC" });
    await user().click(screen.getByRole("button", { name: "Save network" }));
    expect(api.updateNetwork).toHaveBeenCalledWith("net-prod-use1", expect.objectContaining({
      name: "Renamed VPC", subnet_refs: ["subnet-0a1111", "subnet-0b2222"], is_default: true }));
  });

  it("shows the edited network", async () => {
    renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByRole("button", { name: "Edit net-prod-use1" }));
    await fillForm({ Name: "Renamed VPC" });
    await user().click(screen.getByRole("button", { name: "Save network" }));
    expect(await screen.findByText("Renamed VPC")).toBeInTheDocument();
  });

  it("making a network the default clears the previous default for that account and region", async () => {
    const api = fakeApi({ networks: vi.fn().mockResolvedValue([network(), network({ id: "net-alt", is_default: false })]) });
    renderWithApi(<NetworksPanel />, api);
    await user().click(await screen.findByRole("button", { name: "Edit net-alt" }));
    await user().click(screen.getByLabelText("Default for this account and region"));
    await user().click(screen.getByRole("button", { name: "Save network" }));
    const previous = (await screen.findByText("net-prod-use1")).closest("tr")!;
    expect(within(previous).queryByText("Default")).toBeNull();
  });

  it("cancels the form", async () => {
    renderWithApi(<NetworksPanel />);
    await user().click(await screen.findByRole("button", { name: "Add network" }));
    await user().click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("VPC ID")).toBeNull();
  });

  it("shows save errors from the server", async () => {
    const api = fakeApi({ createNetwork: vi.fn().mockRejectedValue(new Error("Use at least two private subnets")) });
    renderWithApi(<NetworksPanel />, api);
    await user().click(await screen.findByRole("button", { name: "Add network" }));
    await fillForm(NEW_NETWORK);
    await user().click(screen.getByRole("button", { name: "Save network" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Use at least two private subnets");
  });

  it("shows setting errors", async () => {
    const api = fakeApi({ updateNetworkSettings: vi.fn().mockRejectedValue(new Error("forbidden")) });
    renderWithApi(<NetworksPanel />, api);
    await user().click(await screen.findByLabelText("Attach compute to the organization VPC by default"));
    expect(await screen.findByRole("alert")).toHaveTextContent("forbidden");
  });

  it("shows loading errors", async () => {
    renderWithApi(<NetworksPanel />, fakeApi({ networks: vi.fn().mockRejectedValue(new Error("down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("down");
  });

  it("names accounts, networks and firewall groups in the cloud's own words", async () => {
    renderWithApi(<NetworksPanel />, fakeApi({ providers: vi.fn().mockResolvedValue(OTHER_CLOUD) }));
    await userEvent.click(await screen.findByRole("button", { name: "Add network" }));
    expect([await screen.findByLabelText("Subscription ID"), screen.getByLabelText("VNet ID"),
      screen.getByLabelText("Network security group IDs"),
      screen.getByText("Attach compute to the organization VNet by default")]).toHaveLength(4);
  });
});
