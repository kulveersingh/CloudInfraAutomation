import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApi } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { RegionsPanel } from "./RegionsPanel";

describe("RegionsPanel", () => {
  it("lists regions with their state", async () => {
    renderWithApi(<RegionsPanel />);
    expect(await screen.findByLabelText("Enable ap-southeast-2")).not.toBeChecked();
  });

  it("enables a region", async () => {
    const { api } = renderWithApi(<RegionsPanel />);
    await userEvent.click(await screen.findByLabelText("Enable ap-southeast-2"));
    expect(api.setRegionEnabled).toHaveBeenCalledWith("aws", "ap-southeast-2", true);
  });

  it("reflects the saved state", async () => {
    renderWithApi(<RegionsPanel />);
    await userEvent.click(await screen.findByLabelText("Enable ap-southeast-2"));
    expect(await screen.findByLabelText("Enable ap-southeast-2")).toBeChecked();
  });

  it("shows update errors", async () => {
    const api = fakeApi({ setRegionEnabled: vi.fn().mockRejectedValue(new Error("not allowed")) });
    renderWithApi(<RegionsPanel />, api);
    await userEvent.click(await screen.findByLabelText("Enable us-east-2"));
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed");
  });

  it("shows loading errors", async () => {
    renderWithApi(<RegionsPanel />, fakeApi({ regions: vi.fn().mockRejectedValue(new Error("down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("down");
  });

  it("shows one cloud's regions at a time", async () => {
    const { api } = renderWithApi(<RegionsPanel />);
    await userEvent.selectOptions(await screen.findByLabelText("Cloud"), "gcp");
    await userEvent.click(await screen.findByLabelText("Enable asia-southeast1"));
    expect([screen.queryByLabelText("Enable ap-southeast-2"), vi.mocked(api.setRegionEnabled).mock.calls[0]]).toEqual(
      [null, ["gcp", "asia-southeast1", true]]);
  });
});
