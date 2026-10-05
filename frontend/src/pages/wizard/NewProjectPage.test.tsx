import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/PlatformApi";
import type { PlatformApiPort } from "../../api/types";
import { fakeApi } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { NewProjectPage } from "./NewProjectPage";

const user = () => userEvent.setup();

function renderWizard(api: PlatformApiPort = fakeApi()) {
  return renderWithApi(<NewProjectPage newKey={() => "key-123"} pollMs={1} />, api);
}

async function fillOwnership() {
  await user().selectOptions(await screen.findByLabelText("Portfolio"), "pf-payments");
  await user().selectOptions(screen.getByLabelText("Product / Platform"), "pr-invoicing");
  await user().type(screen.getByLabelText("Project name"), "demo-app");
}

async function goTo(step: string) {
  await user().click(screen.getByRole("button", { name: step }));
}

async function completeDraft() {
  await fillOwnership();
  await goTo("Services");
  await user().click(screen.getByRole("button", { name: "Add S3 bucket" }));
  await goTo("Environments");
  await user().click(screen.getByLabelText("DEV"));
  await goTo("Preview");
}

describe("NewProjectPage", () => {
  it("shows loading errors", async () => {
    renderWizard(fakeApi({ orgRegistry: vi.fn().mockRejectedValue(new Error("registry down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("registry down");
  });

  it("filters products by portfolio", async () => {
    renderWizard();
    await user().selectOptions(await screen.findByLabelText("Portfolio"), "pf-retail");
    expect(within(screen.getByLabelText("Product / Platform")).getAllByRole("option").map((o) => o.textContent))
      .toEqual(["Choose…", "Storefront (product)"]);
  });

  it("shows the resolved cost center", async () => {
    renderWizard();
    await fillOwnership();
    expect(screen.getByText("CC-4410 · product")).toBeInTheDocument();
  });

  it("changes the classification", async () => {
    renderWizard();
    await user().selectOptions(await screen.findByLabelText("Data classification"), "confidential");
    expect(screen.getByLabelText("Data classification")).toHaveValue("confidential");
  });

  it("moves forward and back with the buttons", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await user().click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "Resilience" })).toBeInTheDocument();
    await user().click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Ownership" })).toBeInTheDocument();
  });

  it("offers only enabled regions", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Resilience");
    expect(within(screen.getByLabelText("Primary region")).queryByText(/ap-southeast-2/)).toBeNull();
  });

  it("enables the secondary region for DR", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Resilience");
    await user().click(screen.getByLabelText(/DR · active \/ standby/));
    expect(screen.getByLabelText("Secondary region")).toBeEnabled();
  });

  it("picks regions", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Resilience");
    await user().click(screen.getByLabelText(/HA pair/));
    await user().selectOptions(screen.getByLabelText("Primary region"), "us-east-2");
    await user().selectOptions(screen.getByLabelText("Secondary region"), "us-east-1");
    expect([screen.getByLabelText("Primary region"), screen.getByLabelText("Secondary region")].map(
      (field) => (field as HTMLSelectElement).value)).toEqual(["us-east-2", "us-east-1"]);
  });

  it("adds and removes curated services", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Add S3 bucket" }));
    await user().click(screen.getByRole("button", { name: "Remove bucket" }));
    expect(screen.getByText("Nothing selected yet.")).toBeInTheDocument();
  });

  it("searches and adds any CloudFormation type", async () => {
    const { api } = renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().type(screen.getByLabelText("Search all CloudFormation types"), "sns");
    await user().click(screen.getByRole("button", { name: "Search" }));
    await user().click(await screen.findByRole("button", { name: "Add AWS::SNS::Topic" }));
    expect([api.searchCloudFormation, screen.getByText("topic")]).toBeTruthy();
  });

  it("shows required properties of a CloudFormation type", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Required: Protocol, TopicArn")).toBeInTheDocument();
  });

  it("shows search errors", async () => {
    renderWizard(fakeApi({ searchCloudFormation: vi.fn().mockRejectedValue(new Error("search failed")) }));
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("search failed");
  });

  it("accepts JSON properties for CloudFormation types", async () => {
    const { api } = renderWizard();
    await fillOwnership();
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Search" }));
    await user().click(await screen.findByRole("button", { name: "Add AWS::SNS::Topic" }));
    await user().click(screen.getByLabelText("Properties for topic"));
    await user().paste('{"DisplayName":"Alerts"}');
    await goTo("Environments");
    await user().click(screen.getByLabelText("DEV"));
    await goTo("Preview");
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(vi.mocked(api.preview).mock.calls[0][0].resources[0]).toEqual({
      id: "topic", type: "AWS::SNS::Topic", config: { properties: { DisplayName: "Alerts" } } });
  });

  it("flags invalid JSON properties", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Search" }));
    await user().click(await screen.findByRole("button", { name: "Add AWS::SNS::Topic" }));
    await user().click(screen.getByLabelText("Properties for topic"));
    await user().paste("{not json");
    expect(screen.getByText("Properties must be a JSON object.")).toBeInTheDocument();
  });

  describe("service settings", () => {
    async function addService(name: string) {
      await screen.findByLabelText("Portfolio");
      await goTo("Services");
      await user().click(screen.getByRole("button", { name: `Add ${name}` }));
    }

    async function previewedResource(api: PlatformApiPort) {
      await user().click(screen.getByRole("button", { name: "Generate preview" }));
      return vi.mocked(api.preview).mock.calls[0][0].resources[0];
    }

    async function toPreview() {
      await goTo("Ownership");
      await fillOwnership();
      await goTo("Environments");
      await user().click(screen.getByLabelText("DEV"));
      await goTo("Preview");
    }

    it("shows each setting of a curated service with its default", async () => {
      renderWizard();
      await addService("Lambda function");
      expect([(screen.getByLabelText("Runtime for function") as HTMLSelectElement).value,
        (screen.getByLabelText("Handler for function") as HTMLInputElement).value,
        (screen.getByLabelText("Memory for function (MB)") as HTMLInputElement).value]).toEqual(
        ["python3.13", "lambda_function.lambda_handler", "256"]);
    });

    it("sends only the settings the user changed", async () => {
      const { api } = renderWizard();
      await addService("Lambda function");
      await user().selectOptions(screen.getByLabelText("Runtime for function"), "java21");
      await user().clear(screen.getByLabelText("Memory for function (MB)"));
      await user().type(screen.getByLabelText("Memory for function (MB)"), "1024");
      await toPreview();
      expect(await previewedResource(api)).toEqual({ id: "function", type: "lambda.function",
        config: { runtime: "java21", memory_mb: 1024 } });
    });

    it("choosing the default again sends nothing", async () => {
      const { api } = renderWizard();
      await addService("Lambda function");
      await user().selectOptions(screen.getByLabelText("Runtime for function"), "java21");
      await user().selectOptions(screen.getByLabelText("Runtime for function"), "python3.13");
      await toPreview();
      expect((await previewedResource(api)).config).toBeUndefined();
    });

    it("flags numbers out of range and keeps the last valid value", async () => {
      const { api } = renderWizard();
      await addService("Lambda function");
      await user().clear(screen.getByLabelText("Memory for function (MB)"));
      await user().type(screen.getByLabelText("Memory for function (MB)"), "64");
      expect(screen.getByText("Memory must be a whole number from 128 to 10240 MB.")).toBeInTheDocument();
      await toPreview();
      expect((await previewedResource(api)).config).toBeUndefined();
    });

    it("flags text that does not fit the rule", async () => {
      renderWizard();
      await addService("Lambda function");
      await user().clear(screen.getByLabelText("Handler for function"));
      await user().type(screen.getByLabelText("Handler for function"), "bad handler");
      expect(screen.getByText("Handler must be 1 to 128 characters of letters, digits and _ . : / $ -.")).toBeInTheDocument();
    });

    it("sets and clears an optional setting", async () => {
      const { api } = renderWizard();
      await addService("DynamoDB table");
      await user().type(screen.getByLabelText("Sort key for table (optional)"), "created");
      await toPreview();
      expect((await previewedResource(api)).config).toEqual({ sort_key: "created" });
    });

    it("an empty optional setting is not sent", async () => {
      const { api } = renderWizard();
      await addService("DynamoDB table");
      await user().type(screen.getByLabelText("Sort key for table (optional)"), "created");
      await user().clear(screen.getByLabelText("Sort key for table (optional)"));
      await toPreview();
      expect((await previewedResource(api)).config).toBeUndefined();
    });

    it("services without settings show no fields", async () => {
      renderWizard();
      await addService("S3 bucket");
      expect(screen.queryByLabelText(/for bucket/)).toBeNull();
    });
  });

  it("adds and removes connections", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Add S3 bucket" }));
    await user().click(screen.getByRole("button", { name: "Add Lambda function" }));
    await goTo("Connections");
    await user().selectOptions(screen.getByLabelText("Kind"), "iam.access");
    await user().selectOptions(screen.getByLabelText("From"), "function");
    await user().selectOptions(screen.getByLabelText("To"), "bucket");
    await user().selectOptions(screen.getByLabelText("Access"), "write");
    await user().type(screen.getByLabelText("Prefix"), "processed/");
    await user().click(screen.getByRole("button", { name: "Add connection" }));
    expect(screen.getByText("function → bucket")).toBeInTheDocument();
    await user().click(screen.getByRole("button", { name: "Remove connection 1" }));
    expect(screen.queryByText("function → bucket")).toBeNull();
  });

  it("needs two services before connecting", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Connections");
    expect(screen.getByRole("button", { name: "Add connection" })).toBeDisabled();
  });

  it("lists draft problems on the preview step", async () => {
    renderWizard();
    await screen.findByLabelText("Portfolio");
    await goTo("Preview");
    expect(screen.getByText("Add at least one service.")).toBeInTheDocument();
  });

  it("shows the preview", async () => {
    renderWizard();
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText("555555555555")).toBeInTheDocument();
  });

  it("shows the generated template", async () => {
    renderWizard();
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText(/UploadsBucket/)).toBeInTheDocument();
  });

  it("shows lint findings", async () => {
    const preview = { files: { "template.yaml": "" }, tags: {}, targets: {}, lint: ["R: wildcard action '*'."] };
    renderWizard(fakeApi({ preview: vi.fn().mockResolvedValue(preview) }));
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText("R: wildcard action '*'.")).toBeInTheDocument();
  });

  it("shows server validation errors", async () => {
    renderWizard(fakeApi({ preview: vi.fn().mockRejectedValue(new ApiError(422, "Region ap-southeast-2 is not enabled.")) }));
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Region ap-southeast-2 is not enabled.");
  });

  it("creates the project with the idempotency key and tracks the job", async () => {
    const { api } = renderWizard();
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Create repository and deploy" }));
    expect(await screen.findByText("Provisioning finished.")).toBeInTheDocument();
    expect(vi.mocked(api.createProject).mock.calls[0][1]).toBe("key-123");
  });

  it("shows creation errors", async () => {
    renderWizard(fakeApi({ createProject: vi.fn().mockRejectedValue(new ApiError(409, "Project 'demo-app' already exists.")) }));
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Create repository and deploy" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
  });

  it("uses a random idempotency key by default", async () => {
    const api = fakeApi();
    renderWithApi(<NewProjectPage pollMs={1} />, api);
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Create repository and deploy" }));
    await screen.findByText("Provisioning finished.");
    expect(vi.mocked(api.createProject).mock.calls[0][1]).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("starts with the organization's attach-by-default setting", async () => {
    renderWizard(fakeApi({ networkSettings: vi.fn().mockResolvedValue({ attach_compute_by_default: false }) }));
    await fillOwnership();
    await goTo("Network");
    expect(screen.getByLabelText("Attach compute to the organization VPC")).not.toBeChecked();
  });

  it("sends the network choice with the request", async () => {
    const api = fakeApi();
    renderWizard(api);
    await fillOwnership();
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Add S3 bucket" }));
    await goTo("Environments");
    await user().click(screen.getByLabelText("PROD"));
    await goTo("Network");
    await user().selectOptions(await screen.findByLabelText("Network for prod in us-east-1"), "net-prod-alt");
    await goTo("Preview");
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(vi.mocked(api.preview).mock.calls[0][0].network).toEqual({
      attach_compute: true, selections: { "prod:us-east-1": "net-prod-alt" } });
  });

  it("shows the VPC per environment and region in the preview", async () => {
    renderWizard();
    await completeDraft();
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect(await screen.findByText("us-east-1: vpc-0aaa1111bbbb22223")).toBeInTheDocument();
  });
});
