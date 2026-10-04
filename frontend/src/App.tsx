import { useState, type ReactNode } from "react";
import { AdminPage } from "./pages/admin/AdminPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { NewProjectPage } from "./pages/wizard/NewProjectPage";

type Page = "projects" | "new" | "admin";

const NAVIGATION: Array<{ page: Page; label: string }> = [
  { page: "projects", label: "Projects" },
  { page: "new", label: "New project" },
  { page: "admin", label: "Admin" },
];

const PAGES: Record<Page, (go: (page: Page) => void) => ReactNode> = {
  projects: (go) => <ProjectsPage onNewProject={() => go("new")} />,
  new: () => <NewProjectPage />,
  admin: () => <AdminPage />,
};

export function App() {
  const [page, setPage] = useState<Page>("projects");
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
      </aside>
      <main className="content">{PAGES[page](setPage)}</main>
    </div>
  );
}
