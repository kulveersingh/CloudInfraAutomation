import { useState, type ReactNode } from "react";
import { useApi } from "./api/ApiContext";
import type { Identity } from "./api/types";
import { AdminPage } from "./pages/admin/AdminPage";
import { LandingZonePage } from "./pages/landingZone/LandingZonePage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReleaseConsolePage } from "./pages/releases/ReleaseConsolePage";
import { ChangeProjectPage } from "./pages/wizard/ChangeProjectPage";
import { NewProjectPage } from "./pages/wizard/NewProjectPage";

type Page = "projects" | "new" | "change" | "releases" | "admin" | "landing-zone";

/** Local identities until SSO is connected; the API receives them as X-Actor / X-Roles. */
export const IDENTITIES: Identity[] = [
  { name: "jordan", label: "Jordan Lee · Developer", roles: ["developer"] },
  { name: "sam", label: "Sam Patel · Reviewer", roles: ["reviewer"] },
  { name: "alex", label: "Alex Kim · Platform admin", roles: ["platform-admin", "reviewer"] },
  { name: "riley", label: "Riley Chen · Platform admin", roles: ["platform-admin", "reviewer"] },
];
const DEFAULT_IDENTITY = IDENTITIES[1];

const NAVIGATION: Array<{ page: Page; label: string }> = [
  { page: "projects", label: "Projects" },
  { page: "new", label: "New project" },
  { page: "releases", label: "Release console" },
  { page: "admin", label: "Admin" },
  { page: "landing-zone", label: "Landing zone" },
];

type Go = (page: Page, project?: string) => void;

const PAGES: Record<Page, (go: Go, identity: Identity, project: string) => ReactNode> = {
  projects: (go) => <ProjectsPage onNewProject={() => go("new")} onChangeProject={(name) => go("change", name)} />,
  new: () => <NewProjectPage />,
  change: (_, __, project) => <ChangeProjectPage key={project} projectName={project} />,
  releases: (_, identity) => <ReleaseConsolePage key={identity.name} identity={identity} />,
  admin: () => <AdminPage />,
  "landing-zone": (_, identity) => <LandingZonePage key={identity.name} identity={identity} />,
};

export function App() {
  const api = useApi();
  const [page, setPage] = useState<Page>("projects");
  const [project, setProject] = useState("");
  const go: Go = (next, name = "") => {
    setProject(name);
    setPage(next);
  };
  const [identity, setIdentity] = useState(() => {
    api.setActor(DEFAULT_IDENTITY);
    return DEFAULT_IDENTITY;
  });
  const switchIdentity = (name: string) => {
    const next = IDENTITIES.find((item) => item.name === name)!;
    api.setActor(next);
    setIdentity(next);
  };

  return (
    <div className="app">
      <aside className="rail" aria-label="Main navigation">
        <div className="brand"><b>CloudInfra Console</b><span>Infrastructure self-service</span></div>
        <nav className="nav">
          {NAVIGATION.map((item) => (
            <button key={item.page} className={item.page === page ? "on" : undefined}
                    aria-current={item.page === page ? "page" : undefined} onClick={() => setPage(item.page)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="identity">
          <label htmlFor="identity">Viewing as</label>
          <select id="identity" value={identity.name} onChange={(event) => switchIdentity(event.target.value)}>
            {IDENTITIES.map((item) => <option key={item.name} value={item.name}>{item.label}</option>)}
          </select>
        </div>
      </aside>
      <main className="content">{PAGES[page](go, identity, project)}</main>
    </div>
  );
}
