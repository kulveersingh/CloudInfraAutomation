import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { ApiProvider } from "../api/ApiContext";
import type { PlatformApiPort } from "../api/types";
import { fakeApi } from "./fakes";

export function renderWithApi(ui: ReactElement, api: PlatformApiPort = fakeApi()) {
  return { api, ...render(<ApiProvider api={api}>{ui}</ApiProvider>) };
}
