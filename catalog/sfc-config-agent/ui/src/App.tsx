import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import ConfigBrowser from "./pages/ConfigBrowser";
import ConfigEditor from "./pages/ConfigEditor";
import PackageList from "./pages/PackageList";
import PackageDetail from "./pages/PackageDetail";
import LogViewer from "./pages/LogViewer";
import FocusBanner from "./components/FocusBanner";
import LoginGate from "./components/LoginGate";
import { logout, getUser } from "./auth";

export default function App() {
  const user = getUser();
  const displayName = user?.email ?? user?.username ?? user?.sub ?? "";
  return (
    <LoginGate>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="min-h-screen flex flex-col">
        {/* Top nav */}
        <header className="border-b border-[#252d3d] bg-[#0d1117] px-6 flex items-center gap-8 h-14 shrink-0">
          {/* Logo / wordmark */}
          <div className="flex items-center gap-2.5 select-none">
            <svg viewBox="0 0 24 24" className="w-7 h-7 text-sky-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              {/* Main summit ridgeline */}
              <polyline points="2,20 9,7 13,13 16,9 22,20" />
              {/* Snow cap accent */}
              <polyline points="14.3,11 16,9 17.7,11.4" />
            </svg>
            <span className="font-mono text-sky-400 font-semibold text-sm tracking-widest uppercase">
              SFC Control Plane
            </span>
          </div>

          {/* Divider */}
          <div className="h-5 w-px bg-[#252d3d]" />

          <nav className="flex gap-0.5">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3.5 py-1.5 rounded-md text-sm font-medium tracking-wide transition-all duration-150 ${
                  isActive
                    ? "bg-sky-950/60 text-sky-300 ring-1 ring-sky-700/50"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                }`
              }
            >
              Configs
            </NavLink>
            <NavLink
              to="/packages"
              className={({ isActive }) =>
                `px-3.5 py-1.5 rounded-md text-sm font-medium tracking-wide transition-all duration-150 ${
                  isActive
                    ? "bg-sky-950/60 text-sky-300 ring-1 ring-sky-700/50"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                }`
              }
            >
              Launch Packages
            </NavLink>
          </nav>

          {/* Spacer + user info + sign-out */}
          <div className="ml-auto flex items-center gap-3">
            {displayName && (
              <span className="flex items-center gap-1.5 text-xs text-slate-400 select-none">
                {/* User icon */}
                <svg
                  viewBox="0 0 24 24"
                  className="w-3.5 h-3.5 text-slate-500 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                </svg>
                {displayName}
              </span>
            )}
            <div className="h-4 w-px bg-[#252d3d]" />
            <button
              onClick={logout}
              className="text-xs text-slate-500 hover:text-slate-200 transition-colors"
              title="Sign out"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Focus banner */}
        <FocusBanner />

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<ConfigBrowser />} />
            <Route path="/configs/:configId" element={<ConfigEditor />} />
            <Route path="/packages" element={<PackageList />} />
            <Route path="/packages/:packageId" element={<PackageDetail />} />
            <Route path="/packages/:packageId/logs" element={<LogViewer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
    </LoginGate>
  );
}
