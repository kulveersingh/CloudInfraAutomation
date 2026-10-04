import { createContext, useContext, type ReactNode } from "react";
import { PlatformApi } from "./PlatformApi";
import type { PlatformApiPort } from "./types";

const ApiContext = createContext<PlatformApiPort>(new PlatformApi());

export function ApiProvider({ api, children }: { api: PlatformApiPort; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): PlatformApiPort {
  return useContext(ApiContext);
}
