import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, job } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { JobProgress } from "./JobProgress";

const STEP = { sequence: 1, name: "create_repository", state: "succeeded", detail: "" };

describe("JobProgress", () => {
  it("polls until the job finishes", async () => {
    const api = fakeApi({ job: vi.fn().mockResolvedValueOnce(job("running")).mockResolvedValue(job("succeeded", [STEP])) });
    renderWithApi(<JobProgress jobId="job-1" pollMs={1} />, api);
    expect(await screen.findByText("Provisioning finished.")).toBeInTheDocument();
  });

  it("lists the steps", async () => {
    renderWithApi(<JobProgress jobId="job-1" pollMs={1} />, fakeApi({ job: vi.fn().mockResolvedValue(job("succeeded", [STEP])) }));
    expect(await screen.findByText("create_repository")).toBeInTheDocument();
  });

  it("shows the waiting state", async () => {
    renderWithApi(<JobProgress jobId="job-1" pollMs={60000} />, fakeApi({ job: vi.fn().mockResolvedValue(job("queued")) }));
    expect(await screen.findByText("Waiting for the worker…")).toBeInTheDocument();
  });

  it("explains a rolled-back failure", async () => {
    const api = fakeApi({ job: vi.fn().mockResolvedValue(job("failed_rolled_back", [], "boom")) });
    renderWithApi(<JobProgress jobId="job-1" pollMs={1} />, api);
    expect(await screen.findByRole("alert")).toHaveTextContent("Provisioning failed and was rolled back: boom");
  });

  it("explains a failure that needs attention", async () => {
    const api = fakeApi({ job: vi.fn().mockResolvedValue(job("failed_needs_attention", [], "boom")) });
    renderWithApi(<JobProgress jobId="job-1" pollMs={1} />, api);
    expect(await screen.findByRole("alert")).toHaveTextContent("needs attention");
  });

  it("shows polling errors", async () => {
    renderWithApi(<JobProgress jobId="job-1" pollMs={1} />, fakeApi({ job: vi.fn().mockRejectedValue(new Error("lost")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("lost");
  });
});
