import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "../api/ApiContext";
import type { CloudProviderInfo, Vocabulary } from "../api/types";
import { useLoad } from "../hooks/useLoad";

export const DEFAULT_PROVIDER = "aws";
const AWS_DOCUMENT_FILE = "template.yaml";

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

/** The clouds the platform supports, AWS first; empty until they have loaded. */
export function useProviders(): CloudProviderInfo[] {
  return useContext(ProvidersContext);
}

export function useVocabulary(provider: string = DEFAULT_PROVIDER): Vocabulary {
  return useProviders().find((item) => item.id === provider)?.vocabulary ?? AWS_VOCABULARY;
}

/** The main IaC file of a cloud's repositories (AWS's until the providers have loaded). */
export function useDocumentFile(provider: string = DEFAULT_PROVIDER): string {
  return useProviders().find((item) => item.id === provider)?.document_file ?? AWS_DOCUMENT_FILE;
}

export const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
