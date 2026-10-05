import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi } from "../test/fakes";
import { renderWithApi } from "../test/render";
import { useDocumentFile } from "./VocabularyContext";

function DocumentFile({ provider }: { provider: string }) {
  return <span>{useDocumentFile(provider)}</span>;
}

describe("useDocumentFile", () => {
  it("names the cloud's main IaC file", async () => {
    renderWithApi(<DocumentFile provider="gcp" />);
    expect(await screen.findByText("main.tf.json")).toBeInTheDocument();
  });

  it("falls back to AWS's until the clouds have loaded", () => {
    renderWithApi(<DocumentFile provider="gcp" />, fakeApi({ providers: vi.fn().mockReturnValue(new Promise(() => {})) }));
    expect(screen.getByText("template.yaml")).toBeInTheDocument();
  });
});
