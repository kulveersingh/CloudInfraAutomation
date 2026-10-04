import { useApi } from "../api/ApiContext";
import type { ProjectSummary, ResilienceMode } from "../api/types";
import { ErrorAlert } from "../components/Notices";
import { useLoad } from "../hooks/useLoad";

export const MODE_LABELS: Record<ResilienceMode, string> = {
  single: "Single region",
  dr: "DR · active/standby",
  ha: "HA · active/active",
};

export function ProjectsPage({ onNewProject }: { onNewProject: () => void }) {
  const api = useApi();
  const projects = useLoad(() => api.projects());
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Projects</h1>
          <p className="sub">Every project is one infrastructure repository deployed through your environments.</p>
        </div>
        <button className="btn pri" onClick={onNewProject}>New project</button>
      </header>
      <ErrorAlert message={projects.error} />
      {projects.data && <ProjectTable projects={projects.data} />}
    </section>
  );
}

function ProjectTable({ projects }: { projects: ProjectSummary[] }) {
  if (projects.length === 0) {
    return <p className="empty">No projects yet. Create one with New project.</p>;
  }
  return (
    <div className="panel tbl-wrap">
      <table>
        <thead><tr><th>Project</th><th>Portfolio</th><th>Product</th><th>Resilience</th><th>Status</th></tr></thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.name}>
              <td><b>{project.name}</b></td>
              <td className="mono">{project.portfolio_id}</td>
              <td className="mono">{project.product_id}</td>
              <td>{MODE_LABELS[project.resilience_mode]}</td>
              <td><span className={`chip ${project.status}`}>{project.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
