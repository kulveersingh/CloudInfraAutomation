import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "../api/ApiContext";
import type { CloudProviderInfo, Vocabulary } from "../api/types";
import { useLoad } from "../hooks/useLoad";

const DEFAULT_PROVIDER = "aws";

/** AWS's words, shown until the providers have loaded (AWS is the platform's default cloud). */
const AWS_VOCABULARY: Vocabulary = {
  cloud: "AWS", isolation_unit: "account", hierarchy_node: "OU", iac_document: "CloudFormation template",
  deploy_unit: "stack", preventive_policy: "SCP", private_network: "VPC", firewall_group: "security group",
  landing_zone_service: "Control Tower", control_catalog: "Control Tower controls",
};

const ProvidersContext = createContext<CloudProviderInfo[]>([]);

/** Loads the clouds the platform supports, so every page can speak each cloud's language (§22.2). */
export function VocabularyProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const providers = useLoad(() => api.providers());
  return <ProvidersContext.Provider value={providers.data ?? []}>{children}</ProvidersContext.Provider>;
}

export function useVocabulary(provider: string = DEFAULT_PROVIDER): Vocabulary {
  const providers = useContext(ProvidersContext);
  return providers.find((item) => item.id === provider)?.vocabulary ?? AWS_VOCABULARY;
}

export const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
