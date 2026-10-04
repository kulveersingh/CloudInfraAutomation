import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApiProvider } from "./api/ApiContext";
import { PlatformApi } from "./api/PlatformApi";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ApiProvider api={new PlatformApi()}>
      <App />
    </ApiProvider>
  </StrictMode>,
);
