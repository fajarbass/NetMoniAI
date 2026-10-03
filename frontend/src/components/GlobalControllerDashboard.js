import React, { useEffect, useState, useRef } from "react";
import ApexCharts from "react-apexcharts";
import { getNodeStatuses } from "../apiService.js";
import "../GlobalControllerDashboard.css";
import NetworkVisualizer from "./NetworkVisualizer";
import GlobalChatbot from "./GlobalChatbot";

// MetricChart component with dark mode theme
const MetricChart = ({ metrics, title, yLabel, color, valueKey }) => {
  if (!Array.isArray(metrics) || metrics.length === 0) {
    return (
      <div style={{ color: "#64748b", padding: "40px 20px", textAlign: "center", fontSize: "13px" }}>
        No telemetry stream available for {title}.
      </div>
    );
  }

  const data = metrics
    .map((m) => ({ x: Number(m.time) * 1000, y: Number(m[valueKey]) }))
    .filter((d) => !isNaN(d.x) && !isNaN(d.y));

  if (data.length < 2) {
    return (
      <div style={{ color: "#64748b", padding: "40px 20px", textAlign: "center", fontSize: "13px" }}>
        Collecting telemetry points... ({data.length} sample)
      </div>
    );
  }

  const sortedData = [...data].sort((a, b) => a.x - b.x);
  const minX = sortedData[0].x;
  const maxX = sortedData[sortedData.length - 1].x;

  const options = {
    chart: {
      type: "line",
      height: 250,
      background: "transparent",
      toolbar: { show: false },
      animations: { enabled: true, easing: "linear" },
    },
    theme: { mode: "dark" },
    grid: { borderColor: "#1e293b", strokeDashArray: 3 },
    xaxis: {
      type: "datetime",
      min: minX,
      max: maxX,
      labels: {
        style: { colors: "#94a3b8", fontSize: "11px", fontFamily: "JetBrains Mono" },
        datetimeUTC: false,
      },
      axisBorder: { color: "#1e293b" },
      axisTicks: { color: "#1e293b" },
    },
    yaxis: {
      title: { text: yLabel, style: { color: "#94a3b8", fontSize: "11px" } },
      labels: {
        style: { colors: "#94a3b8", fontSize: "11px", fontFamily: "JetBrains Mono" },
        formatter: (v) => (v > 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(1)),
      },
    },
    stroke: { width: 2.2, curve: "smooth" },
    colors: [color],
    tooltip: {
      theme: "dark",
      y: { formatter: (v) => `${v.toFixed(2)} ${yLabel}` },
      x: { format: "HH:mm:ss" },
    },
  };

  return (
    <div className="chart-panel-card">
      <div className="chart-card-header">
        <span className="chart-card-title">{title}</span>
        <span className="chart-unit-badge">{yLabel}</span>
      </div>
      <ApexCharts options={options} series={[{ name: title, data: sortedData }]} type="line" height={240} />
    </div>
  );
};

const GlobalControllerDashboard = () => {
  const [nodes, setNodes] = useState({});
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selectedNode, setSelectedNode] = useState("192.168.1.1");
  const [activePanel, setActivePanel] = useState("Analytics");
  const [simulationMode, setSimulationMode] = useState(true);
  const [isResetting, setIsResetting] = useState(false);
  const [isCheckingAgents, setIsCheckingAgents] = useState(false);
  const [checkFeedback, setCheckFeedback] = useState(null);

  const [globalChatMessages, setGlobalChatMessages] = useState([
    {
      sender: "bot",
      text: "Central SOC Intelligence online. Ready to analyze system-wide telemetry and node statuses.",
    },
  ]);

  const wsRef = useRef(null);
  const retryCountRef = useRef(0);
  const isMountedRef = useRef(true);
  const reconnectTimeoutRef = useRef(null);

  const colors = [
    "#38bdf8", // Cyan
    "#10b981", // Emerald
    "#6366f1", // Indigo
    "#ec4899", // Pink
    "#f59e0b", // Amber
    "#06b6d4", // Sky
    "#a855f7", // Purple
  ];

  // Fetch real node statuses from SQLite API
  const fetchStatuses = async () => {
    try {
      const data = await getNodeStatuses();
      const normalized = Object.fromEntries(
        Object.entries(data || {}).map(([k, v]) => [
          k,
          {
            ...v,
            time_series_metrics: Array.isArray(v.time_series_metrics) ? v.time_series_metrics : [],
            packet_details: Array.isArray(v.packet_details) ? v.packet_details : [],
          },
        ])
      );
      setNodes(normalized);
      setLastUpdated(new Date().toLocaleTimeString());
      if (Object.keys(normalized).length > 0) {
        setSimulationMode(false);
      }
      return normalized;
    } catch (e) {
      console.warn("Could not fetch remote node statuses:", e);
      return {};
    }
  };

  // Real action to verify agent connectivity immediately
  const handleCheckConnection = async () => {
    setIsCheckingAgents(true);
    setCheckFeedback(null);
    try {
      const normalized = await fetchStatuses();
      const count = Object.keys(normalized || {}).length;
      if (count === 0) {
        setCheckFeedback({
          type: "warning",
          message: "Belum ada endpoint agent terdeteksi di port 8000. Pastikan NetMoniAI-Agent.exe telah berjalan dan mengarah ke http://localhost:8000.",
        });
      } else {
        setCheckFeedback({
          type: "success",
          message: `Berhasil terhubung! Terdeteksi ${count} agent aktif mengirimkan telemetri.`,
        });
      }
    } catch (err) {
      setCheckFeedback({
        type: "error",
        message: "Gagal menghubungi Central Receiver API: " + err.message,
      });
    } finally {
      setIsCheckingAgents(false);
      setTimeout(() => {
        setCheckFeedback(null);
      }, 7000);
    }
  };

  // Reset all SOC data for a fresh simulation run
  const handleResetSOC = async () => {
    if (!window.confirm("Reset semua status node dan laporan di Central SOC?\nData simulasi sebelumnya akan dihapus.")) return;
    setIsResetting(true);
    try {
      const res = await fetch("/gcreset", { method: "DELETE" });
      const json = await res.json();
      console.log("SOC Reset:", json);
      setNodes({});
      setLastUpdated(null);
      setSelectedNode("192.168.1.1");
      setSimulationMode(true);
    } catch (e) {
      console.error("Reset failed:", e);
      alert("Reset gagal: " + e.message);
    } finally {
      setIsResetting(false);
    }
  };


  // Safe WebSocket connection without zombie reconnect loops
  const addGlobalChatMessage = (msg) => setGlobalChatMessages((m) => [...m, msg]);

  const sendGlobalChatMessage = (text) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "global_chat", message: text }));
    } else {
      addGlobalChatMessage({ sender: "bot", text: "Error: Not connected to Central Server." });
    }
  };

  const connectWebSocket = () => {
    if (!isMountedRef.current) return;
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = window.location.host || "localhost:8000";
    const ws = new WebSocket(`${wsProto}//${wsHost}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) {
        ws.close();
        return;
      }
      retryCountRef.current = 0;
    };

    ws.onmessage = (ev) => {
      if (!isMountedRef.current) return;
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "global_chat_response") {
          addGlobalChatMessage({ sender: "bot", text: msg.data });
        }
      } catch (err) {
        console.error("Failed to parse global chat message:", err);
      }
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          retryCountRef.current++;
          connectWebSocket();
        }
      }, delay);
    };

    ws.onerror = (err) => {
      console.warn("Central Controller WS error:", err);
    };
  };

  useEffect(() => {
    isMountedRef.current = true;
    fetchStatuses();
    const id = setInterval(fetchStatuses, 30000);
    connectWebSocket();

    return () => {
      isMountedRef.current = false;
      clearInterval(id);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-select node
  useEffect(() => {
    const keys = Object.keys(nodes);
    if (keys.length > 0 && !nodes[selectedNode]) {
      setSelectedNode(keys[0]);
    }
  }, [nodes, selectedNode]);

  // Telemetry calculation helpers
  const calculateRate = (m, key) => {
    if (!Array.isArray(m) || m.length < 2) return [];
    const sorted = m
      .map((x) => ({ t: +x.time, v: +x[key] || 0 }))
      .filter((x) => !isNaN(x.t) && !isNaN(x.v))
      .sort((a, b) => a.t - b.t);
    const out = [];
    for (let i = 1; i < sorted.length; i++) {
      const dt = sorted[i].t - sorted[i - 1].t;
      if (dt > 0) {
        const rate = (sorted[i].v - sorted[i - 1].v) / dt;
        out.push({ time: sorted[i].t, rate: rate >= 0 ? rate : 0 });
      }
    }
    return out;
  };

  const calculateAveragePacketSize = (m) =>
    Array.isArray(m) && m.length > 1
      ? m
          .map((x) => {
            const t = +x.time;
            const pk = +x.packets || 0;
            const bt = +x.bytes || 0;
            const avg = pk > 0 ? bt / pk : 0;
            return { time: t, x: t * 1000, y: avg, avg_size: avg };
          })
          .filter((d) => !isNaN(d.x) && !isNaN(d.y))
      : [];

  const getMetaData = (nd, ip) => {
    const m = nd?.time_series_metrics ?? [];
    const totalPk = m.reduce((s, x) => s + (x.packets || 0), 0);
    const totalBy = m.reduce((s, x) => s + (x.bytes || 0), 0);
    return {
      Node_IP: ip,
      Role: nd?.role || "Edge Workstation / Server",
      Status: nd?.attack_detected ? "Under Threat / Attack" : "Nominal Security State",
      Anomalies: nd?.anomalies_detected ?? 0,
      Packets_Sent: Math.floor(totalPk / 2),
      Packets_Received: totalPk - Math.floor(totalPk / 2),
      Bytes_Transferred: totalBy,
      Attack_Type: nd?.attack_type || "None Detected",
      Summary: nd?.summary || "Heuristic baseline monitoring active.",
    };
  };

  const liveNodeCount = Object.keys(nodes).length;
  const underAttackCount = Object.values(nodes).filter((n) => n.attack_detected).length;
  const current = nodes[selectedNode] || null;

  return (
    <div className="global-controller-dashboard">
      <div className="soc-hero">
        <h1 className="page-title">Central Security Operations Center (SOC)</h1>
        <p className="page-subtitle">
          Enterprise Multi-Node Telemetry Collector, Distributed Threat Heuristics &amp; Packet Flow Topology
        </p>
      </div>

      {/* Fleet Stats Overview */}
      <div className="soc-fleet-metrics">
        <div className="fleet-stat-card">
          <div className="fleet-stat-info">
            <span className="fleet-stat-label">Active Agents</span>
            <span className="fleet-stat-val">{liveNodeCount > 0 ? liveNodeCount : "8 (Topology Preview)"}</span>
          </div>
        </div>

        <div className="fleet-stat-card" style={{ borderColor: underAttackCount > 0 ? "#ef4444" : "#232a3b" }}>
          <div className="fleet-stat-info">
            <span className="fleet-stat-label">Fleet Threat Status</span>
            <span className="fleet-stat-val" style={{ color: underAttackCount > 0 ? "#ef4444" : "#10b981" }}>
              {underAttackCount > 0 ? `${underAttackCount} Under Attack` : "0 Threats Active"}
            </span>
          </div>
        </div>

        <div className="fleet-stat-card">
          <div className="fleet-stat-info">
            <span className="fleet-stat-label">Receiver Ingress</span>
            <span className="fleet-stat-val" style={{ fontSize: "14px", fontFamily: "JetBrains Mono" }}>
              :8000/gcreport
            </span>
          </div>
        </div>

        <div className="fleet-stat-card">
          <div className="fleet-stat-info">
            <span className="fleet-stat-label">Last Database Sync</span>
            <span className="fleet-stat-val" style={{ fontSize: "14px" }}>
              {lastUpdated || "Live Connected"}
            </span>
          </div>
        </div>
      </div>

      {/* Agent Connect Banner (shown when 0 live reporting nodes) */}
      {liveNodeCount === 0 && (
        <div className="agent-connect-banner">
          <div className="banner-content">
            <div>
              <div className="banner-title">Central Receiver Active: Waiting for Endpoint Telemetry</div>
              <p className="banner-desc">
                The Central Controller is listening on port <code>8000</code>. To stream real-time packet data from client machines, install and run <code>NetMoniAI-Agent.exe</code> with Server URL pointing to <code>http://{window.location.hostname || "localhost"}:8000</code>.
              </p>
              {checkFeedback && (
                <div className={`banner-feedback-msg ${checkFeedback.type}`}>
                  {checkFeedback.type === "success" ? "✅ " : checkFeedback.type === "warning" ? "⚠️ " : "❌ "}
                  {checkFeedback.message}
                </div>
              )}
            </div>
          </div>
          <div className="banner-actions">
            <button
              className="check-conn-btn"
              onClick={handleCheckConnection}
              disabled={isCheckingAgents}
              title="Periksa apakah ada agen endpoint yang sudah terhubung ke port 8000"
            >
              <span className={`btn-icon ${isCheckingAgents ? "spinning" : ""}`}>🔄</span>
              {isCheckingAgents ? "Memeriksa Agen..." : "Periksa Koneksi Agen"}
            </button>
            <button
              className={`sim-toggle-btn ${simulationMode ? "active-mode" : "inactive-mode"}`}
              onClick={() => setSimulationMode(!simulationMode)}
              title={simulationMode ? "Klik untuk menyembunyikan peta topologi simulasi" : "Klik untuk memuat peta topologi simulasi"}
            >
              {simulationMode ? "👁️ Sembunyikan Peta Topologi" : "🗺️ Muat Peta Topologi"}
            </button>
          </div>
        </div>
      )}

      {/* SOC Controls Bar */}
      <div className="soc-controls-bar">
        <div className="panel-tab-group">
          <button
            className={`panel-tab-btn ${activePanel === "Analytics" ? "active" : ""}`}
            onClick={() => setActivePanel("Analytics")}
          >
            Analytics &amp; Rates
          </button>
          <button
            className={`panel-tab-btn ${activePanel === "Statistics" ? "active" : ""}`}
            onClick={() => setActivePanel("Statistics")}
          >
            Packet Inspector (DPI)
          </button>
          <button
            className={`panel-tab-btn ${activePanel === "Meta Data" ? "active" : ""}`}
            onClick={() => setActivePanel("Meta Data")}
          >
            Node Metadata
          </button>
        </div>

        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <button className="refresh-soc-btn" onClick={fetchStatuses} title="Query SQLite Node Statuses">
            Refresh Statuses
          </button>
          <button
            className="refresh-soc-btn"
            onClick={handleResetSOC}
            disabled={isResetting}
            title="Hapus semua data simulasi dan mulai dari awal"
            style={{
              background: isResetting ? "#374151" : "rgba(239,68,68,0.15)",
              border: "1px solid rgba(239,68,68,0.4)",
              color: isResetting ? "#6b7280" : "#ef4444",
              cursor: isResetting ? "not-allowed" : "pointer",
            }}
          >
            {isResetting ? "Mereset..." : "🗑 Reset SOC"}
          </button>
        </div>
      </div>

      {/* Topology Map + Side Inspector */}
      <div className="topology-section-grid">
        <div className="topology-card">
          <div className="topology-card-header">
            <span className="topology-title">
              Network Mesh &amp; Packet Flow Topology
            </span>
            <span className="node-selection-badge">
              {liveNodeCount > 0
                ? `Selected Node: ${selectedNode}`
                : simulationMode
                ? `Simulasi (Selected: ${selectedNode})`
                : "Topologi Dinonaktifkan"}
            </span>
          </div>

          {liveNodeCount > 0 || simulationMode ? (
            <NetworkVisualizer
              nodes={nodes}
              selectedNode={selectedNode}
              onSelectNode={(nodeId) => setSelectedNode(nodeId)}
            />
          ) : (
            <div className="topology-empty-placeholder">
              <div className="placeholder-radar-pulse">📡</div>
              <div className="placeholder-title">Peta Topologi Simulasi Disembunyikan</div>
              <p className="placeholder-desc">
                Central Receiver sedang aktif mendengarkan di port <code>8000</code>. Belum ada agen riil yang mengirimkan telemetri. Anda dapat memuat topologi simulasi untuk menguji visualisasi interaktif.
              </p>
              <button
                className="sim-toggle-btn inactive-mode"
                onClick={() => setSimulationMode(true)}
              >
                🗺️ Muat Peta Topologi (Simulasi)
              </button>
            </div>
          )}
        </div>

        {/* Side Panel Inspector */}
        <div className="side-inspect-card">
          <div className="side-inspect-header">
            <span>Node Inspector: {selectedNode}</span>
          </div>

          {activePanel === "Statistics" && (
            <div style={{ overflowX: "auto" }}>
              {current?.packet_details?.length ? (
                <table className="soc-data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Src IP</th>
                      <th>Dst IP</th>
                      <th>Proto</th>
                      <th>Len</th>
                    </tr>
                  </thead>
                  <tbody>
                    {current.packet_details.slice(0, 10).map((pkt, i) => (
                      <tr key={i}>
                        <td>{new Date(pkt.timestamp * 1000).toLocaleTimeString()}</td>
                        <td>{pkt.src_ip}</td>
                        <td>{pkt.dst_ip}</td>
                        <td>{pkt.protocol}</td>
                        <td>{pkt.length}B</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ color: "#64748b", padding: "20px 0", fontSize: "12px", lineHeight: "1.6" }}>
                  <p>No raw packet logs currently ingested for node <strong>{selectedNode}</strong>.</p>
                  <p>Packets captured via Npcap will appear here automatically with deep protocol analysis.</p>
                </div>
              )}
            </div>
          )}

          {activePanel === "Meta Data" && (
            <div style={{ overflowX: "auto" }}>
              <table className="soc-data-table">
                <tbody>
                  {Object.entries(getMetaData(current, selectedNode)).map(([label, val]) => (
                    <tr key={label}>
                      <td style={{ color: "#94a3b8", fontWeight: "600", width: "40%" }}>
                        {label.replace(/_/g, " ")}:
                      </td>
                      <td style={{ color: label === "Status" && String(val).includes("Threat") ? "#ef4444" : "#f1f5f9" }}>
                        {String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activePanel === "Analytics" && (
            <div style={{ fontSize: "13px", lineHeight: "1.6", color: "#cbd5e1" }}>
              <div style={{ background: "#0f172a", padding: "12px", borderRadius: "8px", border: "1px solid #1e293b", marginBottom: "14px" }}>
                <div style={{ fontSize: "11px", textTransform: "uppercase", color: "#64748b", marginBottom: "4px" }}>
                  Current Node Defense Status
                </div>
                <div style={{ fontSize: "16px", fontWeight: "bold", color: current?.attack_detected ? "#ef4444" : "#10b981" }}>
                  {current?.attack_detected ? "ACTIVE ATTACK DETECTED" : "ALL SYSTEMS NOMINAL"}
                </div>
              </div>
              <p>
                <strong>Role:</strong> {current?.role || "Host / Workstation Node"}
              </p>
              <p>
                <strong>Anomalies Detected:</strong> {current?.anomalies_detected ?? 0}
              </p>
              <p>
                <strong>Attack Classification:</strong> {current?.attack_type || "None"}
              </p>
              <p>
                <strong>Threat Intelligence Summary:</strong>{" "}
                {current?.summary || "Traffic flow conforms to expected baseline behavior."}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Telemetry Charts */}
      {current && current.time_series_metrics && current.time_series_metrics.length > 0 && (
        <div className="bottom-analytics-card">
          <div className="analytics-header">
            <span className="analytics-title">
              Telemetry Stream for Node: {selectedNode}
            </span>
          </div>

          <div className="charts-grid-4">
            <MetricChart
              metrics={current.time_series_metrics}
              title="Packet Count"
              yLabel="Packets"
              color={colors[0]}
              valueKey="packets"
            />
            <MetricChart
              metrics={current.time_series_metrics}
              title="Byte Volume"
              yLabel="Bytes"
              color={colors[1]}
              valueKey="bytes"
            />
            <MetricChart
              metrics={calculateRate(current.time_series_metrics, "packets")}
              title="Packet Rate"
              yLabel="Packets/s"
              color={colors[2]}
              valueKey="rate"
            />
            <MetricChart
              metrics={calculateRate(current.time_series_metrics, "bytes")}
              title="Throughput"
              yLabel="Bytes/s"
              color={colors[3]}
              valueKey="rate"
            />
            <MetricChart
              metrics={calculateAveragePacketSize(current.time_series_metrics)}
              title="Average Packet Size"
              yLabel="B/packet"
              color={colors[4]}
              valueKey="avg_size"
            />
            <MetricChart
              metrics={current.time_series_metrics}
              title="Latency Stream"
              yLabel="ms"
              color={colors[5]}
              valueKey="latency_ms"
            />
            <MetricChart
              metrics={current.time_series_metrics}
              title="Jitter Variance"
              yLabel="ms"
              color={colors[6]}
              valueKey="jitter_ms"
            />
          </div>
        </div>
      )}

      {/* Global AI Copilot Drawer */}
      <GlobalChatbot
        globalChatMessages={globalChatMessages}
        addGlobalChatMessage={addGlobalChatMessage}
        sendGlobalChatMessage={sendGlobalChatMessage}
      />
    </div>
  );
};

export default GlobalControllerDashboard;
