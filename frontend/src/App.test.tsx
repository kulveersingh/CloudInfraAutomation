import { screen } from "@testing-library/react";
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
    await userEvent.click(screen.getByRole("button", { name: "New project" }));
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

  it("marks the current page", () => {
    renderWithApi(<App />);
    expect(screen.getByRole("button", { name: "Projects" })).toHaveAttribute("aria-current", "page");
  });
});
