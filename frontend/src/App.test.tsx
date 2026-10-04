import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { renderWithApi } from "./test/render";

describe("App", () => {
  it("opens on projects", async () => {
    renderWithApi(<App />);
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
  });

  it("navigates to the wizard", async () => {
    renderWithApi(<App />);
    await userEvent.click(within(screen.getByLabelText("Main navigation")).getByRole("button", { name: "New project" }));
    expect(await screen.findByRole("heading", { name: "New project" })).toBeInTheDocument();
  });

  it("navigates to admin", async () => {
    renderWithApi(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Admin" }));
    expect(await screen.findByRole("heading", { name: "Admin" })).toBeInTheDocument();
  });

  it("returns to projects", async () => {
    renderWithApi(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Admin" }));
    await userEvent.click(screen.getByRole("button", { name: "Projects" }));
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
  });

  it("the projects page can open the wizard", async () => {
    renderWithApi(<App />);
    const buttons = await screen.findAllByRole("button", { name: "New project" });
    await userEvent.click(buttons[buttons.length - 1]);
    expect(await screen.findByRole("heading", { name: "New project" })).toBeInTheDocument();
  });

  it("navigates to the release console", async () => {
    renderWithApi(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Release console" }));
    expect(await screen.findByRole("heading", { name: "Release console" })).toBeInTheDocument();
  });

  it("starts as a reviewer and tells the API", () => {
    const { api } = renderWithApi(<App />);
    expect(api.setActor).toHaveBeenCalledWith(expect.objectContaining({ name: "sam" }));
  });

  it("switches the acting identity", async () => {
    const { api } = renderWithApi(<App />);
    await userEvent.selectOptions(screen.getByLabelText("Viewing as"), "alex");
    expect(api.setActor).toHaveBeenLastCalledWith(expect.objectContaining({ name: "alex",
      roles: ["platform-admin", "reviewer"] }));
  });

  it("marks the current page", () => {
    renderWithApi(<App />);
    expect(screen.getByRole("button", { name: "Projects" })).toHaveAttribute("aria-current", "page");
  });

  it("navigates to the landing zone as a platform admin", async () => {
    renderWithApi(<App />);
    await userEvent.selectOptions(screen.getByLabelText("Viewing as"), "riley");
    await userEvent.click(screen.getByRole("button", { name: "Landing zone" }));
    expect(await screen.findByRole("heading", { name: "1. Organization" })).toBeInTheDocument();
  });
});
