import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  getSettings,
  updateSettings,
  getNetworkInterfaces,
  getAIModels,
  testAIConnection,
  getIncidentReports,
  pingCentralServer,
  getStartupStatus,
  setStartupStatus,
  minimizeToTray,
} from "../apiService";
import "./SettingsDashboard.css";

const SettingsDashboard = ({ appMode = "agent" }) => {
  const navigate = useNavigate();
  const isServer = appMode === "server";
  const [activeTab, setActiveTab] = useState("ai");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Settings State
  const [settings, setSettings] = useState({
    ai: {
      active_provider: "gemini",
      gemini: {
        api_key: "",
        default_model: "gemini-3.8-flash",
        thinking_level: "medium",
        thinking_budget: 2048,
        temperature: 0.3,
      },
      openai: {
        api_key: "",
        default_model: "gpt-4o",
        reasoning_effort: "medium",
        temperature: 0.3,
      },
      opencode: {
        api_key: "opencode-token",
        base_url: "http://localhost:11434/v1",
        default_model: "opencode-deepseek-r1",
        temperature: 0.2,
      },
    },
    network: {
      interface: "auto",
      ping_target_external: "8.8.8.8",
      ping_target_local: "192.168.1.1",
      thresholds: {
        avg_latency_ms: 75.0,
        max_latency_ms: 100.0,
        avg_packet_loss_pct: 5.0,
        max_packet_loss_pct: 10.0,
      },
      sliding_window_size: 15,
    },
  });

  // Dynamic Lists
  const [interfaces, setInterfaces] = useState([]);
  const [modelsList, setModelsList] = useState([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [reports, setReports] = useState([]);
  const [startupStatus, setStartupStatusState] = useState({
    enabled: false,
    app_name: "",
    command: "",
    platform_supported: true,
  });
  const [togglingStartup, setTogglingStartup] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [settingsRes, ifaceRes, startupRes] = await Promise.allSettled([
        getSettings(),
        getNetworkInterfaces(),
        getStartupStatus(),
      ]);

      if (settingsRes.status === "fulfilled") {
        setSettings(settingsRes.value);
      }
      if (ifaceRes.status === "fulfilled") {
        setInterfaces(ifaceRes.value.interfaces || []);
      }
      if (startupRes.status === "fulfilled") {
        setStartupStatusState(startupRes.value);
      }
    } catch (err) {
      console.error("Failed to load initial settings:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStartup = async (newVal) => {
    setTogglingStartup(true);
    try {
      const res = await setStartupStatus(newVal);
      setStartupStatusState((prev) => ({ ...prev, enabled: res.enabled }));
      setFeedback({
        type: "success",
        msg: newVal
          ? "Registered in Windows Startup. NetMoniAI will launch silently to System Tray on boot."
          : "Removed from Windows Startup.",
      });
    } catch (err) {
      setFeedback({
        type: "error",
        msg: "Failed to update Windows Startup registration: " + err.message,
      });
    } finally {
      setTogglingStartup(false);
    }
  };

  const handleMinimizeToTray = async () => {
    try {
      await minimizeToTray();
      setFeedback({
        type: "success",
        msg: "Dashboard window minimized to system tray. Double-click the tray icon to restore.",
      });
    } catch (err) {
      setFeedback({
        type: "error",
        msg: "Failed to minimize to tray: " + err.message,
      });
    }
  };

  const handleFetchModels = async () => {
    setFetchingModels(true);
    setTestResult(null);
    const provider = settings.ai.active_provider;
    const providerCfg = settings.ai[provider] || {};
    try {
      const res = await getAIModels(
        provider,
        providerCfg.api_key,
        providerCfg.base_url
      );
      setModelsList(res.models || []);
      setFeedback({
        type: "success",
        text: `Loaded ${res.models?.length || 0} models from ${provider.toUpperCase()}`,
      });
    } catch (err) {
      setFeedback({
        type: "error",
        text: `Failed to fetch models: ${err.message}`,
      });
    } finally {
      setFetchingModels(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestResult(null);
    const provider = settings.ai.active_provider;
    const providerCfg = settings.ai[provider] || {};
    try {
      const res = await testAIConnection(
        provider,
        providerCfg.api_key,
        providerCfg.base_url,
        providerCfg.default_model
      );
      setTestResult(res);
    } catch (err) {
      setTestResult({ status: "error", message: err.message });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const res = await updateSettings(settings);
      setSettings(res.settings);
      setFeedback({
        type: "success",
        text: "Configuration saved to SQLite and active in real-time!",
      });
    } catch (err) {
      setFeedback({
        type: "error",
        text: `Save failed: ${err.message}`,
      });
    } finally {
      setSaving(false);
    }
  };

  const loadAuditReports = async () => {
    try {
      const res = await getIncidentReports(50);
      setReports(res.reports || []);
    } catch (err) {
      console.error("Failed to fetch audit reports:", err);
    }
  };

  useEffect(() => {
    if (activeTab === "audit") {
      loadAuditReports();
    }
  }, [activeTab]);

  if (loading) {
    return (
      <div className="settings-dashboard">
        <p style={{ color: "#94a3b8", padding: "40px 0" }}>Loading configuration from database...</p>
      </div>
    );
  }

  const activeProvider = settings.ai.active_provider;

  return (
    <div className="settings-dashboard">
      <div className="dashboard-hero">
        <div className="hero-header-flex">
          <div>
            <div className="settings-mode-badge">
              {isServer ? "🌐 Central Controller & SOC Config" : "💻 Endpoint Agent Config"}
            </div>
            <h1 className="page-title">System &amp; AI Settings</h1>
            <p className="page-subtitle">
              Konfigurasi model AI, ambang batas deteksi anomali, capture interface, dan integrasi desktop
            </p>
          </div>
          <div className="hero-actions-group">
            <button
              className="back-dashboard-btn"
              onClick={() => navigate(isServer ? "/gc" : "/")}
              title="Kembali ke Dashboard Utama"
            >
              ← Kembali ke Dashboard
            </button>
            <button
              className="save-settings-btn"
              onClick={handleSaveSettings}
              disabled={saving}
            >
              {saving ? "Menyimpan..." : "💾 Simpan Perubahan"}
            </button>
          </div>
        </div>
      </div>

      {feedback && (
        <div className={`feedback-banner ${feedback.type}`}>
          {feedback.text || feedback.msg}
        </div>
      )}

      {/* Tabs */}
      <div className="settings-controls-bar">
        <div className="settings-tab-group">
          <button
            className={`settings-tab-item ${activeTab === "ai" ? "active" : ""}`}
            onClick={() => setActiveTab("ai")}
          >
            AI Providers &amp; Models
          </button>
          <button
            className={`settings-tab-item ${activeTab === "network" ? "active" : ""}`}
            onClick={() => setActiveTab("network")}
          >
            Network &amp; Thresholds
          </button>
          <button
            className={`settings-tab-item ${activeTab === "system" ? "active" : ""}`}
            onClick={() => setActiveTab("system")}
          >
            Windows &amp; System Tray
          </button>
          <button
            className={`settings-tab-item ${activeTab === "audit" ? "active" : ""}`}
            onClick={() => setActiveTab("audit")}
          >
            Audit Reports ({reports.length})
          </button>
        </div>
      </div>

      {/* Tab 1: AI Provider Settings */}
      {activeTab === "ai" && (
        <div>
          <div className="settings-card">
            <h3>Select Active AI Engine</h3>
            <div className="provider-selector">
              <div
                className={`provider-pill ${activeProvider === "gemini" ? "active" : ""}`}
                onClick={() =>
                  setSettings({
                    ...settings,
                    ai: { ...settings.ai, active_provider: "gemini" },
                  })
                }
              >
                <h4>Google Gemini</h4>
                <small>Native SDK, Gemini 3.8 Flash & Thinking</small>
              </div>
              <div
                className={`provider-pill ${activeProvider === "openai" ? "active" : ""}`}
                onClick={() =>
                  setSettings({
                    ...settings,
                    ai: { ...settings.ai, active_provider: "openai" },
                  })
                }
              >
                <h4>OpenAI</h4>
                <small>GPT-4o, o3-mini & Reasoning</small>
              </div>
              <div
                className={`provider-pill ${activeProvider === "opencode" ? "active" : ""}`}
                onClick={() =>
                  setSettings({
                    ...settings,
                    ai: { ...settings.ai, active_provider: "opencode" },
                  })
                }
              >
                <h4>OpenCode / Local</h4>
                <small>OpenAI-Compatible (Ollama, vLLM, OpenRouter)</small>
              </div>
            </div>

            {/* Google Gemini Config */}
            {activeProvider === "gemini" && (
              <div>
                <div className="form-group">
                  <label>Google Gemini API Key</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="AIzaSy..."
                    value={settings.ai.gemini.api_key}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        ai: {
                          ...settings.ai,
                          gemini: { ...settings.ai.gemini, api_key: e.target.value },
                        },
                      })
                    }
                  />
                  <small>Stored securely in SQLite database.</small>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label>Gemini Model</label>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <input
                        type="text"
                        className="form-input"
                        value={settings.ai.gemini.default_model}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            ai: {
                              ...settings.ai,
                              gemini: {
                                ...settings.ai.gemini,
                                default_model: e.target.value,
                              },
                            },
                          })
                        }
                      />
                      <button
                        className="btn-secondary"
                        onClick={handleFetchModels}
                        disabled={fetchingModels}
                      >
                        {fetchingModels ? "..." : "Fetch"}
                      </button>
                    </div>
                    {modelsList.length > 0 && (
                      <select
                        className="form-select"
                        style={{ marginTop: "6px" }}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            ai: {
                              ...settings.ai,
                              gemini: {
                                ...settings.ai.gemini,
                                default_model: e.target.value,
                              },
                            },
                          })
                        }
                      >
                        <option value="">Select from discovered models...</option>
                        {modelsList.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name || m.id}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="form-group">
                    <label>Thinking Level (Reasoning Effort)</label>
                    <select
                      className="form-select"
                      value={settings.ai.gemini.thinking_level}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          ai: {
                            ...settings.ai,
                            gemini: {
                              ...settings.ai.gemini,
                              thinking_level: e.target.value,
                            },
                          },
                        })
                      }
                    >
                      <option value="off">Off (Fastest / Real-time)</option>
                      <option value="low">Low (Brief reasoning)</option>
                      <option value="medium">Medium (Balanced)</option>
                      <option value="high">High (Deep Root Cause Analysis)</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* OpenAI Config */}
            {activeProvider === "openai" && (
              <div>
                <div className="form-group">
                  <label>OpenAI API Key</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="sk-..."
                    value={settings.ai.openai.api_key}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        ai: {
                          ...settings.ai,
                          openai: { ...settings.ai.openai, api_key: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>OpenAI Model</label>
                  <input
                    type="text"
                    className="form-input"
                    value={settings.ai.openai.default_model}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        ai: {
                          ...settings.ai,
                          openai: {
                            ...settings.ai.openai,
                            default_model: e.target.value,
                          },
                        },
                      })
                    }
                  />
                </div>
              </div>
            )}

            {/* OpenCode Config */}
            {activeProvider === "opencode" && (
              <div>
                <div className="form-group">
                  <label>OpenCode / Local Server Base URL</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="http://localhost:11434/v1"
                    value={settings.ai.opencode.base_url}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        ai: {
                          ...settings.ai,
                          opencode: {
                            ...settings.ai.opencode,
                            base_url: e.target.value,
                          },
                        },
                      })
                    }
                  />
                  <small>Supports Ollama, vLLM, LocalAI, or OpenCode server.</small>
                </div>
                <div className="grid-2">
                  <div className="form-group">
                    <label>Auth Token (Optional)</label>
                    <input
                      type="password"
                      className="form-input"
                      value={settings.ai.opencode.api_key}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          ai: {
                            ...settings.ai,
                            opencode: {
                              ...settings.ai.opencode,
                              api_key: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label>Served Model Name</label>
                    <input
                      type="text"
                      className="form-input"
                      value={settings.ai.opencode.default_model}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          ai: {
                            ...settings.ai,
                            opencode: {
                              ...settings.ai.opencode,
                              default_model: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="btn-group" style={{ marginTop: "16px" }}>
              <button
                className="btn-secondary"
                onClick={handleTestConnection}
                disabled={testingConnection}
              >
                {testingConnection ? "Testing..." : "Test Connection"}
              </button>
            </div>

            {testResult && (
              <div
                className={`status-badge ${testResult.status === "ok" ? "success" : "error"}`}
              >
                {testResult.message} ({testResult.latency_ms} ms)
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Network & Thresholds */}
      {activeTab === "network" && (
        <div>
          <div className="settings-card">
            <h3>Network Adapter & Capture Settings</h3>
            <div className="form-group">
              <label>Capture Interface (Active Network Card)</label>
              <select
                className="form-select"
                value={settings.network.interface}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    network: { ...settings.network, interface: e.target.value },
                  })
                }
              >
                <option value="auto">Auto-detect Default Physical Interface</option>
                {interfaces.map((iface) => (
                  <option key={iface.name} value={iface.name}>
                    {iface.name} {iface.ipv4 ? `(${iface.ipv4})` : ""} - {iface.is_up ? "UP" : "DOWN"}
                  </option>
                ))}
              </select>
              <small>Auto-discovered from system hardware.</small>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label>External Ping Target (Latency Check)</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.network.ping_target_external}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      network: {
                        ...settings.network,
                        ping_target_external: e.target.value,
                      },
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>Local Gateway Target</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.network.ping_target_local}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      network: {
                        ...settings.network,
                        ping_target_local: e.target.value,
                      },
                    })
                  }
                />
              </div>
            </div>
          </div>

          <div className="settings-card">
            <h3>Anomaly Detection Thresholds</h3>
            <div className="grid-2">
              <div className="form-group">
                <label>Average Latency Threshold (ms)</label>
                <input
                  type="number"
                  className="form-input"
                  value={settings.network?.thresholds?.avg_latency_ms || 75}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      network: {
                        ...settings.network,
                        thresholds: {
                          ...settings.network.thresholds,
                          avg_latency_ms: parseFloat(e.target.value) || 0,
                        },
                      },
                    })
                  }
                />
                <small>Triggers automated PCAP capture if exceeded.</small>
              </div>

              <div className="form-group">
                <label>Packet Loss Threshold (%)</label>
                <input
                  type="number"
                  className="form-input"
                  value={settings.network?.thresholds?.avg_packet_loss_pct || 5}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      network: {
                        ...settings.network,
                        thresholds: {
                          ...settings.network.thresholds,
                          avg_packet_loss_pct: parseFloat(e.target.value) || 0,
                        },
                      },
                    })
                  }
                />
              </div>
            </div>
          </div>

          <div className="settings-card">
            <h3>Central Server Forwarding (Client Sync)</h3>
            <p style={{ fontSize: "13px", color: "#8b949e", marginTop: 0 }}>
              (Pendekatan A: Klien Mandiri) Agen ini memantau PC lokal secara independen. Aktifkan opsi ini jika ingin mengirimkan salinan laporan insiden ke Dashboard Server Pusat admin.
            </p>
            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={settings.central_server?.enabled ?? true}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      central_server: {
                        ...settings.central_server,
                        enabled: e.target.checked,
                      },
                    })
                  }
                />
                <strong>Forward incident reports to Central Server</strong>
              </label>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label>Client Device Identifier / Node Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Laptop-Finance-01"
                  value={settings.central_server?.client_node_name || "My-Client-PC"}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      central_server: {
                        ...settings.central_server,
                        client_node_name: e.target.value,
                      },
                    })
                  }
                />
                <small>Label that will appear on Central Controller dashboard.</small>
              </div>

              <div className="form-group">
                <label>Central Server URL</label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="http://192.168.1.100:8000"
                    value={settings.central_server?.server_url || "http://localhost:8000"}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        central_server: {
                          ...settings.central_server,
                          server_url: e.target.value,
                        },
                      })
                    }
                  />
                  <button
                    className="btn-secondary"
                    onClick={async () => {
                      try {
                        const targetUrl = settings.central_server?.server_url || "http://localhost:8000";
                        const res = await pingCentralServer(targetUrl);
                        setFeedback({ type: "success", text: `${res.message} (${res.latency_ms} ms)` });
                      } catch (err) {
                        setFeedback({ type: "error", text: `Central server test failed: ${err.message}` });
                      }
                    }}
                  >
                    Ping
                  </button>
                </div>
                <small>Central Controller REST endpoint.</small>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Windows Boot & System Tray */}
      {activeTab === "system" && (
        <div>
          <div className="settings-card">
            <div className="card-header-with-badge">
              <div>
                <h3>Windows Boot Startup</h3>
                <p className="card-subtitle">
                  Configure whether NetMoniAI starts automatically on Windows boot.
                </p>
              </div>
              <span className={`status-badge ${startupStatus.enabled ? "success" : "error"}`}>
                {startupStatus.enabled ? "Registered in Windows Startup" : "Disabled (Not Registered)"}
              </span>
            </div>

            <div className="system-integration-banner">
              <div className="integration-info">
                <h4>Silent Boot to System Tray</h4>
                <p>
                  When enabled, Windows launches NetMoniAI with the <code>--tray</code> argument on login. The application runs quietly in the System Tray without showing pop-up windows.
                </p>
                {startupStatus.command && (
                  <div className="registry-command-box">
                    <small>Registry Launch Target:</small>
                    <code>{startupStatus.command}</code>
                  </div>
                )}
              </div>
              <div className="integration-action">
                <button
                  type="button"
                  className={startupStatus.enabled ? "btn-danger-outline" : "btn-primary"}
                  disabled={togglingStartup}
                  onClick={() => handleToggleStartup(!startupStatus.enabled)}
                >
                  {togglingStartup
                    ? "Updating..."
                    : startupStatus.enabled
                    ? "Disable Auto-Start"
                    : "Enable Auto-Start"}
                </button>
              </div>
            </div>
          </div>

          <div className="settings-card">
            <h3>System Tray &amp; Background Minimization</h3>
            <p className="card-subtitle">
              Manage how NetMoniAI behaves when minimized or closed.
            </p>

            <div className="form-grid">
              <div className="form-group checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={settings.system?.minimize_to_tray ?? true}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        system: {
                          ...(settings.system || {}),
                          minimize_to_tray: e.target.checked,
                        },
                      })
                    }
                  />
                  <div>
                    <strong>Minimize Window to System Tray</strong>
                    <p style={{ margin: "4px 0 0 0", color: "#8b949e", fontSize: "13px" }}>
                      Hides window completely from taskbar when minimized, keeping it accessible via the system tray icon near the clock.
                    </p>
                  </div>
                </label>
              </div>

              <div className="form-group checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={settings.system?.close_to_tray ?? true}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        system: {
                          ...(settings.system || {}),
                          close_to_tray: e.target.checked,
                        },
                      })
                    }
                  />
                  <div>
                    <strong>Close Button (X) Keeps Monitoring Active</strong>
                    <p style={{ margin: "4px 0 0 0", color: "#8b949e", fontSize: "13px" }}>
                      Closing the window will not terminate the agent or server; background telemetry continues seamlessly in the tray.
                    </p>
                  </div>
                </label>
              </div>
            </div>

            <div style={{ marginTop: "20px", display: "flex", gap: "14px", alignItems: "center", flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleMinimizeToTray}
              >
                Minimize to System Tray Now
              </button>
              <small style={{ color: "#8b949e" }}>
                Test the tray minimize action. Double-click the NetMoniAI shield icon in your taskbar notification area to restore.
              </small>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: SQLite Audit Reports */}
      {activeTab === "audit" && (
        <div className="settings-card">
          <h3>Incident Reports Stored in SQLite ({reports.length})</h3>
          {reports.length === 0 ? (
            <p style={{ color: "#8b949e" }}>
              No security reports recorded in SQLite database yet.
            </p>
          ) : (
            <table className="reports-table">
              <thead>
                <tr>
                  <th>Report ID</th>
                  <th>Node IP</th>
                  <th>Time</th>
                  <th>Attack Type</th>
                  <th>Confidence</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((rep) => (
                  <tr key={rep.id}>
                    <td><code>{rep.id}</code></td>
                    <td>{rep.node_ip}</td>
                    <td>{rep.timestamp}</td>
                    <td>
                      <span className={rep.attack_detected ? "tag-attack" : "tag-normal"}>
                        {rep.attack_type || (rep.attack_detected ? "Attack" : "Normal")}
                      </span>
                    </td>
                    <td>{((rep.confidence || 0) * 100).toFixed(0)}%</td>
                    <td>{rep.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

export default SettingsDashboard;
