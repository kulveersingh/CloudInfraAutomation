import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ProjectSummary } from "../api/types";
import { fakeApi, PROJECTS } from "../test/fakes";
import { renderWithApi } from "../test/render";
import { ProjectsPage } from "./ProjectsPage";

describe("ProjectsPage", () => {
  it("lists projects", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />);
    expect(await screen.findByText("invoice-ingest")).toBeInTheDocument();
  });

  it("shows the resilience mode", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />);
    expect(await screen.findByText("DR · active/standby")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />, fakeApi({ projects: vi.fn().mockResolvedValue([]) }));
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it("shows loading errors", async () => {
    const api = fakeApi({ projects: vi.fn().mockRejectedValue(new Error("API down")) });
    renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />, api);
    expect(await screen.findByRole("alert")).toHaveTextContent("API down");
  });

  describe("changes", () => {
    const OPEN_CHANGE = { id: "chg-1", revision: 2, state: "open" as const,
      pull_request: { number: 1, url: "https://github.com/acme-platform/invoice-ingest-infra/pull/1" } };
    const OPEN: ProjectSummary = { ...PROJECTS[0], open_change: OPEN_CHANGE };
    const withProjects = (projects = [OPEN]) => fakeApi({ projects: vi.fn().mockResolvedValue(projects) });

    it("offers Change infrastructure for active projects", async () => {
      const onChange = vi.fn();
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={onChange} />);
      await userEvent.click(await screen.findByRole("button", { name: "Change infrastructure for invoice-ingest" }));
      expect(onChange).toHaveBeenCalledWith("invoice-ingest");
    });

    it("does not offer changes while a project is provisioning", async () => {
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />,
        withProjects([{ ...PROJECTS[0], status: "provisioning" }]));
      await screen.findByText("invoice-ingest");
      expect(screen.queryByRole("button", { name: /Change infrastructure/ })).toBeNull();
    });

    it("shows the revision", async () => {
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />);
      expect(await screen.findByText("r1")).toBeInTheDocument();
    });

    it("links the open change's pull request instead of offering another change", async () => {
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />, withProjects());
      const link = await screen.findByRole("link", { name: "Revision 2 · pull request #1" });
      expect([link.getAttribute("href"), screen.queryByRole("button", { name: /Change infrastructure/ })]).toEqual(
        ["https://github.com/acme-platform/invoice-ingest-infra/pull/1", null]);
    });

    it("shows a queued change without a link", async () => {
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />,
        withProjects([{ ...OPEN, open_change: { ...OPEN_CHANGE, state: "queued", pull_request: null } }]));
      expect(await screen.findByText("Revision 2 · queued")).toBeInTheDocument();
    });

    it.each([["Simulate merge", "mergeChange"], ["Close", "closeChange"]] as const)(
      "%s records the outcome and reloads", async (label, method) => {
        const api = withProjects();
        renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />, api);
        await userEvent.click(await screen.findByRole("button", { name: `${label} revision 2 of invoice-ingest` }));
        expect([vi.mocked(api[method]).mock.calls[0], vi.mocked(api.projects).mock.calls.length]).toEqual(
          [["invoice-ingest", "chg-1"], 2]);
      });

    it("shows merge errors", async () => {
      const api = fakeApi({ projects: vi.fn().mockResolvedValue([OPEN]),
        mergeChange: vi.fn().mockRejectedValue(new Error("main moved")) });
      renderWithApi(<ProjectsPage onNewProject={() => {}} onChangeProject={() => {}} />, api);
      await userEvent.click(await screen.findByRole("button", { name: "Simulate merge revision 2 of invoice-ingest" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("main moved");
    });
  });

  it("starts a new project", async () => {
    const onNewProject = vi.fn();
    renderWithApi(<ProjectsPage onNewProject={onNewProject} onChangeProject={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "New project" }));
    expect(onNewProject).toHaveBeenCalled();
  });
});
