import { Checkbox } from "../controls";
import type { StepProps } from "./StepProps";

const ACCOUNTS: Array<{ id: string; label: string; hint: string }> = [
  { id: "network", label: "Network", hint: "Transit Gateway, IPAM, central egress and inspection" },
  { id: "shared_services", label: "Shared Services", hint: "DNS resolver, artifact buckets, directory, the CloudInfra platform" },
  { id: "identity", label: "Identity", hint: "Directory integration for IAM Identity Center" },
  { id: "backup", label: "Backup", hint: "Central backup vaults with cross-region copy" },
  { id: "monitoring", label: "Monitoring", hint: "Cross-account CloudWatch dashboards and alarms" },
  { id: "cicd", label: "CI/CD Automations", hint: "Only if you run build agents in AWS; GitHub Actions with OIDC doesn't need it" },
];

export function InfrastructureStep({ draft, onChange }: StepProps) {
  const { infrastructure } = draft.toAnswers();
  return (
    <>
      <p className="sub">These accounts go in the Infrastructure OU. Environment accounts reach them only through the
        routes on the Network step.</p>
      {ACCOUNTS.map((account) => (
        <Checkbox key={account.id} label={account.label} hint={account.hint} checked={infrastructure.includes(account.id)}
                  onChange={(checked) => onChange(draft.withListItem("infrastructure", account.id, checked))} />
      ))}
    </>
  );
}
