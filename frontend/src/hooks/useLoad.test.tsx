import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useLoad } from "./useLoad";

function Probe({ load }: { load: () => Promise<string> }) {
  const state = useLoad(load);
  return (
    <div>
      <span>{state.loading ? "loading" : "idle"}</span>
      <span>{state.data ?? "no data"}</span>
      <span>{state.error ?? "no error"}</span>
      <button onClick={state.reload}>reload</button>
    </div>
  );
}

describe("useLoad", () => {
  it("shows loading first", () => {
    render(<Probe load={() => new Promise(() => {})} />);
    expect(screen.getByText("loading")).toBeInTheDocument();
  });

  it("provides data when loaded", async () => {
    render(<Probe load={async () => "hello"} />);
    expect(await screen.findByText("hello")).toBeInTheDocument();
  });

  it("provides the error message when loading fails", async () => {
    render(<Probe load={async () => { throw new Error("boom"); }} />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("reloads on request", async () => {
    const load = vi.fn().mockResolvedValueOnce("first").mockResolvedValueOnce("second");
    render(<Probe load={load} />);
    await screen.findByText("first");
    await act(async () => screen.getByText("reload").click());
    expect(await screen.findByText("second")).toBeInTheDocument();
  });

  it("ignores results after unmount", async () => {
    let resolve: (value: string) => void = () => {};
    const { unmount } = render(<Probe load={() => new Promise((done) => { resolve = done; })} />);
    unmount();
    await act(async () => resolve("late"));
    expect(screen.queryByText("late")).not.toBeInTheDocument();
  });

  it("ignores errors after unmount", async () => {
    let reject: (error: Error) => void = () => {};
    const { unmount } = render(<Probe load={() => new Promise((_, fail) => { reject = fail; })} />);
    unmount();
    await act(async () => reject(new Error("late")));
    expect(screen.queryByText("late")).not.toBeInTheDocument();
  });
});
