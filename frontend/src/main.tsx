import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApiProvider } from "./api/ApiContext";
import { PlatformApi } from "./api/PlatformApi";
import { App } from "./App";
import { VocabularyProvider } from "./providers/VocabularyContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ApiProvider api={new PlatformApi()}>
      <VocabularyProvider>
        <App />
      </VocabularyProvider>
    </ApiProvider>
  </StrictMode>,
);
