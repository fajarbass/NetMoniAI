import React, { useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
  Navigate,
} from "react-router-dom";
import LocalControllerDashboard from "./components/LocalControllerDashboard";
import GlobalControllerDashboard from "./components/GlobalControllerDashboard";
import SettingsDashboard from "./components/SettingsDashboard";
import { getAppMode, getSettings } from "./apiService";
import "./App.css";

const NavigationBar = ({ modeInfo, hasApiKey }) => {
  const [currentTime, setCurrentTime] = useState("");

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const mode = (modeInfo && modeInfo.mode) ? modeInfo.mode.toLowerCase() : "agent";
  const isAgent = mode === "agent";
  const isServer = mode === "server";

  return (
    <header className="main-header">
      <div className="header-left">
        <NavLink to={isServer ? "/gc" : "/"} className="brand-badge">
          <img src="/shield-radar.svg" alt="NetMoniAI Logo" className="brand-logo" />
          <div className="brand-text">
            <span className="brand-title">NetMoniAI</span>
            <span className="brand-tagline">Cyber Sentinel &amp; APM</span>
          </div>
        </NavLink>
      </div>


      {/* Right Controls */}
      <div className="header-right">
        <div className="status-pill mode-pill">
          <span className="pulse-dot"></span>
          <span className="mode-label">
            {isAgent
              ? "ENDPOINT AGENT"
              : isServer
              ? "CENTRAL SERVER"
              : "ALL-IN-ONE"}
          </span>
        </div>

        {currentTime && <div className="time-badge">{currentTime}</div>}

        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="api-docs-link"
          title="FastAPI Swagger Documentation"
        >
          API Docs
        </a>

        {/* Dedicated Modern Settings Button with SVG Gear Icon (Icon Only) */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            isActive ? "settings-nav-btn active" : "settings-nav-btn"
          }
          title="Settings - System, AI Provider & Network Configuration"
          aria-label="Settings"
        >
          <svg
            className="settings-gear-svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          {!hasApiKey && (
            <span
              className="settings-hint-dot"
              title="Kunci AI belum disetel - berjalan dalam mode heuristik lokal"
            ></span>
          )}
        </NavLink>
      </div>
    </header>
  );
};

const AppContent = () => {
  const [modeInfo, setModeInfo] = useState(() => {
    const port =
      typeof window !== "undefined" && window.location
        ? window.location.port
        : "8001";
    if (port === "8000") {
      return { mode: "server", title: "Central Server", is_server: true, is_agent: false, port: 8000 };
    }
    return { mode: "agent", title: "Endpoint Agent", is_server: false, is_agent: true, port: 8001 };
  });

  const [hasApiKey, setHasApiKey] = useState(true);

  useEffect(() => {
    let isMounted = true;

    getAppMode()
      .then((data) => {
        if (!isMounted || !data) return;
        setModeInfo(data);
        if (data.mode === "agent") {
          document.title = "NetMoniAI - Endpoint Agent Dashboard";
        } else if (data.mode === "server") {
          document.title = "NetMoniAI - Central Controller SOC";
        } else {
          document.title = "NetMoniAI - All-in-One Dashboard";
        }
      })
      .catch((err) => {
        console.warn("Could not query /api/mode, using port fallback:", err);
      });

    getSettings()
      .then((cfg) => {
        if (!isMounted || !cfg) return;
        const provider = cfg.ai?.active_provider || "gemini";
        const key = cfg.ai?.[provider]?.api_key;
        setHasApiKey(Boolean(key && key.trim()));
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  const isServer = modeInfo.mode === "server";
  const isAgent = modeInfo.mode === "agent";

  return (
    <div className="app-layout">
      <NavigationBar modeInfo={modeInfo} hasApiKey={hasApiKey} />
      <main className="main-content">
        <Routes>
          {isServer ? (
            <>
              {/* Central Server: Redirect root to Central SOC */}
              <Route path="/" element={<Navigate to="/gc" replace />} />
              <Route path="/gc" element={<GlobalControllerDashboard />} />
              <Route
                path="/settings"
                element={<SettingsDashboard appMode={modeInfo.mode} />}
              />
              <Route path="*" element={<Navigate to="/gc" replace />} />
            </>
          ) : isAgent ? (
            <>
              {/* Endpoint Agent: Root is Local Agent, redirect /gc to root */}
              <Route path="/" element={<LocalControllerDashboard />} />
              <Route path="/gc" element={<Navigate to="/" replace />} />
              <Route
                path="/settings"
                element={<SettingsDashboard appMode={modeInfo.mode} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          ) : (
            <>
              {/* All-in-One Development Mode */}
              <Route path="/" element={<LocalControllerDashboard />} />
              <Route path="/gc" element={<GlobalControllerDashboard />} />
              <Route
                path="/settings"
                element={<SettingsDashboard appMode={modeInfo.mode} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          )}
        </Routes>
      </main>
    </div>
  );
};

const App = () => (
  <Router>
    <AppContent />
  </Router>
);

export default App;
