import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApi } from "../test/fakes";
import { renderWithApi } from "../test/render";
import { ProjectsPage } from "./ProjectsPage";

describe("ProjectsPage", () => {
  it("lists projects", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} />);
    expect(await screen.findByText("invoice-ingest")).toBeInTheDocument();
  });

  it("shows the resilience mode", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} />);
    expect(await screen.findByText("DR · active/standby")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    renderWithApi(<ProjectsPage onNewProject={() => {}} />, fakeApi({ projects: vi.fn().mockResolvedValue([]) }));
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it("shows loading errors", async () => {
    const api = fakeApi({ projects: vi.fn().mockRejectedValue(new Error("API down")) });
    renderWithApi(<ProjectsPage onNewProject={() => {}} />, api);
    expect(await screen.findByRole("alert")).toHaveTextContent("API down");
  });

  it("starts a new project", async () => {
    const onNewProject = vi.fn();
    renderWithApi(<ProjectsPage onNewProject={onNewProject} />);
    await userEvent.click(screen.getByRole("button", { name: "New project" }));
    expect(onNewProject).toHaveBeenCalled();
  });
});
