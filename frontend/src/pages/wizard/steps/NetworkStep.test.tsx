import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, network } from "../../../test/fakes";
import { renderWithApi } from "../../../test/render";
import { ProjectDraft } from "../../../wizard/ProjectDraft";
import { NetworkStep } from "./NetworkStep";

const draftFor = (...environments: string[]) => environments.reduce(
  (draft, environment) => draft.withEnvironment(environment, true),
  ProjectDraft.initial().withOwnership("pf-payments", "pr-invoicing").withMode("dr"));

function renderStep(draft = draftFor("dev", "prod"), api = fakeApi()) {
  const onChange = vi.fn();
  return { onChange, ...renderWithApi(<NetworkStep draft={draft} onChange={onChange} />, api) };
}

describe("NetworkStep", () => {
  it("loads the options for the chosen portfolio", async () => {
    const { api } = renderStep();
    await screen.findByLabelText("Network for prod in us-east-1");
    expect(api.networkOptions).toHaveBeenCalledWith("pf-payments", "aws");
  });

  it("offers one dropdown per environment and region the project deploys to", async () => {
    renderStep();
    await screen.findByLabelText("Network for prod in us-east-1");
    expect([screen.getByLabelText("Network for dev in us-east-1"), screen.queryByLabelText("Network for dev in us-east-2")])
      .toEqual([expect.anything(), null]);
  });

  it("pre-selects the platform default network", async () => {
    renderStep();
    expect(await screen.findByLabelText("Network for prod in us-east-1")).toHaveValue("net-prod-use1");
  });

  it("falls back to the first network when the platform has no default", async () => {
    const options = [{ environment: "prod", region: "us-east-1", account_id: "555555555555", default_network_id: null,
      networks: [network({ id: "net-a", is_default: false }), network({ id: "net-b", is_default: false })] }];
    renderStep(draftFor("prod"), fakeApi({ networkOptions: vi.fn().mockResolvedValue(options) }));
    expect(await screen.findByLabelText("Network for prod in us-east-1")).toHaveValue("net-a");
  });

  it("shows the explicit choice from the draft", async () => {
    renderStep(draftFor("prod").withNetworkSelection("prod", "us-east-1", "net-prod-alt"));
    expect(await screen.findByLabelText("Network for prod in us-east-1")).toHaveValue("net-prod-alt");
  });

  it("records a different choice", async () => {
    const { onChange } = renderStep();
    await userEvent.selectOptions(await screen.findByLabelText("Network for prod in us-east-1"), "net-prod-alt");
    expect(onChange.mock.calls[0][0].toRequest().network.selections).toEqual({ "prod:us-east-1": "net-prod-alt" });
  });

  it("labels options with name, VPC and range", async () => {
    renderStep();
    await screen.findByLabelText("Network for prod in us-east-1");
    expect(screen.getByRole("option", { name: "Isolated VPC · vpc-0aaa1111bbbb22223 · 10.9.0.0/16" })).toBeInTheDocument();
  });

  it("warns when an environment and region has no network", async () => {
    renderStep();
    expect(await screen.findByText(/No network is configured for prod in us-east-2/)).toBeInTheDocument();
  });

  it("detaches compute from the VPC", async () => {
    const { onChange } = renderStep();
    await userEvent.click(await screen.findByLabelText("Attach compute to the organization VPC"));
    expect(onChange.mock.calls[0][0].values.attachCompute).toBe(false);
  });

  it("hides the dropdowns when compute is detached", async () => {
    renderStep(draftFor("prod").withAttachCompute(false));
    await screen.findByLabelText("Attach compute to the organization VPC");
    expect(screen.queryByLabelText("Network for prod in us-east-1")).toBeNull();
  });

  it("asks for environments first", async () => {
    renderStep(draftFor());
    expect(await screen.findByText("Select environments first.")).toBeInTheDocument();
  });

  it("asks for a portfolio first", () => {
    renderStep(ProjectDraft.initial().withEnvironment("dev", true));
    expect(screen.getByText("Choose a portfolio first.")).toBeInTheDocument();
  });

  it("shows loading errors", async () => {
    renderStep(draftFor("prod"), fakeApi({ networkOptions: vi.fn().mockRejectedValue(new Error("down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("down");
  });
});
