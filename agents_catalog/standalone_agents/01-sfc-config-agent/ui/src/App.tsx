import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import ConfigBrowser from "./pages/ConfigBrowser";
import ConfigEditor from "./pages/ConfigEditor";
import PackageList from "./pages/PackageList";
import PackageDetail from "./pages/PackageDetail";
import LogViewer from "./pages/LogViewer";
import FocusBanner from "./components/FocusBanner";

export default function App() {
  return (
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="min-h-screen flex flex-col">
        {/* Top nav */}
        <header className="border-b border-[#2a3044] bg-[#181c27] px-4 flex items-center gap-6 h-12 shrink-0">
          <span className="font-mono text-sky-400 font-semibold text-sm tracking-wide">
            SFC Control Plane
          </span>
          <nav className="flex gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3 py-1.5 rounded text-sm transition-colors ${
                  isActive
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`
              }
            >
              Configs
            </NavLink>
            <NavLink
              to="/packages"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded text-sm transition-colors ${
                  isActive
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`
              }
            >
              Launch Packages
            </NavLink>
          </nav>
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
  );
}