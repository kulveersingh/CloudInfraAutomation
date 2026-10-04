export function ErrorAlert({ message }: { message?: string }) {
  return message ? <div role="alert" className="notice crit">{message}</div> : null;
}

export interface SaveStatus {
  kind: "saved" | "error";
  message: string;
}

export function StatusMessage({ status }: { status?: SaveStatus }) {
  if (!status) return null;
  return status.kind === "saved"
    ? <div role="status" className="notice ok">{status.message}</div>
    : <ErrorAlert message={status.message} />;
}
