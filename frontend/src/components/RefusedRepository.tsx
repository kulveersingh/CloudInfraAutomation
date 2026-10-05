import { useId } from "react";
import type { RepositoryReadBack } from "../api/types";

/** Why a repository was not loaded back (§21.3): each finding, with the files and hand edits it is about. */
export function RefusedRepository({ title, readBack }: { title: string; readBack: RepositoryReadBack<unknown> }) {
  const headingId = useId();
  return (
    <section className="notice crit" aria-labelledby={headingId}>
      <b id={headingId}>{title}</b>
      {readBack.findings.map((finding) => (
        <div key={finding.check}>
          <p>{finding.message}</p>
          {finding.files.map((file) => (
            <div key={file.path}>
              <code>{file.path}</code>
              {file.diff && <pre className="file">{file.diff}</pre>}
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
