import React, { useState, useEffect, useRef } from "react";
import ApexCharts from "react-apexcharts";
import "../App.css";
import Chatbot from "./chatbot";

const colors = [
  "#38bdf8", // Cyan
  "#10b981", // Emerald
  "#6366f1", // Indigo
  "#ec4899", // Pink
  "#f59e0b", // Amber
  "#06b6d4", // Sky
  "#a855f7", // Purple
];

const metricBins = {
  "Bytes Sent": [100, 500],
  "Bytes Received": [100, 500],
  "Throughput Sent": [100, 500],
  "Throughput Received": [100, 500],
  "External Latency": [50, 100],
  "Local Latency": [50, 100],
};

const thresholds = {
  "External Latency": { avg: 75, max: 100 },
  "Local Latency": { avg: 75, max: 100 },
  "External Packet Loss": { avg: 0.05, max: 0.1 },
};

const LocalControllerDashboard = () => {
  const [metricsData, setMetricsData] = useState({
    bytesSentData: [],
    bytesRecvData: [],
    throughputSentData: [],
    throughputRecvData: [],
    externalLatencyData: [],
    externalPacketLossData: [],
    localLatencyData: [],
  });

  const [attackDetection, setAttackDetection] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("Connecting...");
  const [activeTab, setActiveTab] = useState("line");
  const [chatMessages, setChatMessages] = useState([
    {
      sender: "bot",
      text: "NetMoniAI Copilot online. Ready to inspect local endpoint traffic and metrics.",
    },
  ]);

  const wsRef = useRef(null);
  const retryCountRef = useRef(0);
  const isMountedRef = useRef(true);
  const reconnectTimeoutRef = useRef(null);

  const addChatMessage = (message) => {
    setChatMessages((prev) => [...prev, message]);
  };

  const sendChatMessage = (text) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "chat", message: text }));
    } else {
      addChatMessage({
        sender: "bot",
        text: "Error: WebSocket connection to NetMoniAI agent is not open.",
      });
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
      setConnectionStatus("Connected");
      retryCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const message = JSON.parse(event.data);
        if (message.type === "metrics") {
          const newMetric = message.data;
          const maxPoints = 60;
          const ts = new Date(newMetric.timestamp).getTime();

          setMetricsData((prevData) => ({
            bytesSentData: [
              ...prevData.bytesSentData,
              { x: ts, y: newMetric.bytes_sent },
            ].slice(-maxPoints),
            bytesRecvData: [
              ...prevData.bytesRecvData,
              { x: ts, y: newMetric.bytes_recv },
            ].slice(-maxPoints),
            throughputSentData: [
              ...prevData.throughputSentData,
              { x: ts, y: newMetric.throughput_sent },
            ].slice(-maxPoints),
            throughputRecvData: [
              ...prevData.throughputRecvData,
              { x: ts, y: newMetric.throughput_recv },
            ].slice(-maxPoints),
            externalLatencyData: [
              ...prevData.externalLatencyData,
              { x: ts, y: newMetric.external_ping?.avg_latency ?? 0 },
            ].slice(-maxPoints),
            externalPacketLossData: [
              ...prevData.externalPacketLossData,
              { x: ts, y: newMetric.external_ping?.packet_loss ?? 0 },
            ].slice(-maxPoints),
            localLatencyData: [
              ...prevData.localLatencyData,
              { x: ts, y: newMetric.local_ping?.avg_latency ?? 0 },
            ].slice(-maxPoints),
          }));
        } else if (message.type === "attack_detection") {
          setAttackDetection(message.data);
        } else if (message.type === "chat_response") {
          addChatMessage({ sender: "bot", text: message.data });
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setConnectionStatus("Disconnected");
      const retryDelay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          retryCountRef.current += 1;
          connectWebSocket();
        }
      }, retryDelay);
    };

    ws.onerror = (error) => {
      console.warn("WebSocket error:", error);
      if (isMountedRef.current) setConnectionStatus("Disconnected");
    };
  };

  useEffect(() => {
    isMountedRef.current = true;
    connectWebSocket();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect timer on unmount
        wsRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const metrics = [
    { name: "Bytes Sent", data: metricsData.bytesSentData, unit: "bytes" },
    { name: "Bytes Received", data: metricsData.bytesRecvData, unit: "bytes" },
    { name: "Throughput Sent", data: metricsData.throughputSentData, unit: "B/s" },
    { name: "Throughput Received", data: metricsData.throughputRecvData, unit: "B/s" },
    { name: "External Latency", data: metricsData.externalLatencyData, unit: "ms" },
    { name: "External Packet Loss", data: metricsData.externalPacketLossData, unit: "%" },
    { name: "Local Latency", data: metricsData.localLatencyData, unit: "ms" },
  ];

  const aggregateData = (data, intervalMinutes = 5) => {
    if (data.length === 0) return [];
    const intervalMs = intervalMinutes * 60 * 1000;
    const aggregated = {};
    data.forEach((point) => {
      const intervalStart = Math.floor(point.x / intervalMs) * intervalMs;
      if (!aggregated[intervalStart]) {
        aggregated[intervalStart] = { sum: 0, count: 0 };
      }
      aggregated[intervalStart].sum += point.y;
      aggregated[intervalStart].count += 1;
    });
    return Object.entries(aggregated).map(([time, { sum, count }]) => ({
      x: Number(time),
      y: sum / count,
    }));
  };

  const getPieChartData = (metricName, data) => {
    if (data.length === 0) return { series: [], labels: [], exceeded: false };
    if (metricName === "External Packet Loss") {
      const noLoss = data.filter((d) => d.y === 0).length;
      const loss = data.length - noLoss;
      const latestValue = data[data.length - 1]?.y || 0;
      const threshold = thresholds[metricName];
      const exceeded =
        threshold &&
        (latestValue > threshold.avg || latestValue > threshold.max);
      return {
        series: [(noLoss / data.length) * 100, (loss / data.length) * 100],
        labels: ["No Loss", "Packet Loss"],
        exceeded,
      };
    } else {
      const bins = metricBins[metricName] || [100, 500];
      const low = data.filter((d) => d.y < bins[0]).length;
      const medium = data.filter((d) => d.y >= bins[0] && d.y < bins[1]).length;
      const high = data.filter((d) => d.y >= bins[1]).length;
      const total = data.length;
      const latestValue = data[data.length - 1]?.y || 0;
      const threshold = thresholds[metricName];
      const exceeded =
        threshold &&
        (latestValue > threshold.avg || latestValue > threshold.max);
      return {
        series: [
          (low / total) * 100,
          (medium / total) * 100,
          (high / total) * 100,
        ],
        labels: [
          `Low (<${bins[0]})`,
          `Medium (${bins[0]}-${bins[1]})`,
          `High (>${bins[1]})`,
        ],
        exceeded,
      };
    }
  };

  const lineChartOptions = (title, yAxisLabel, color, threshold) => {
    const options = {
      chart: {
        type: "line",
        height: 260,
        background: "transparent",
        toolbar: { show: false },
        animations: { enabled: true, easing: "linear", dynamicAnimation: { speed: 1000 } },
      },
      theme: { mode: "dark" },
      grid: {
        borderColor: "#1e293b",
        strokeDashArray: 3,
      },
      xaxis: {
        type: "datetime",
        labels: {
          style: { colors: "#94a3b8", fontSize: "11px", fontFamily: "JetBrains Mono" },
          datetimeUTC: false,
        },
        axisBorder: { color: "#1e293b" },
        axisTicks: { color: "#1e293b" },
      },
      yaxis: {
        title: { text: yAxisLabel, style: { color: "#94a3b8", fontSize: "11px" } },
        labels: {
          style: { colors: "#94a3b8", fontSize: "11px", fontFamily: "JetBrains Mono" },
          formatter: (value) =>
            title === "External Packet Loss"
              ? `${(value * 100).toFixed(1)}%`
              : value > 1000
              ? `${(value / 1000).toFixed(1)}k`
              : value.toFixed(1),
        },
        ...(title === "External Packet Loss" ? { min: 0, max: 1 } : {}),
      },
      stroke: { width: 2.5, curve: "smooth" },
      colors: [color],
      tooltip: {
        theme: "dark",
        x: { format: "HH:mm:ss" },
        y: { formatter: (v) => `${v.toFixed(2)} ${yAxisLabel}` },
      },
    };

    if (threshold) {
      options.annotations = {
        yaxis: [
          {
            y: threshold.avg,
            borderColor: "#f59e0b",
            strokeDashArray: 4,
            label: {
              borderColor: "#f59e0b",
              style: { color: "#000", background: "#f59e0b", fontSize: "10px" },
              text: `Warn: ${threshold.avg}`,
            },
          },
          {
            y: threshold.max,
            borderColor: "#ef4444",
            strokeDashArray: 4,
            label: {
              borderColor: "#ef4444",
              style: { color: "#fff", background: "#ef4444", fontSize: "10px" },
              text: `Crit: ${threshold.max}`,
            },
          },
        ],
      };
    }
    return options;
  };

  const barChartOptions = (title, yAxisLabel, threshold) => {
    return {
      chart: {
        type: "bar",
        height: 260,
        background: "transparent",
        toolbar: { show: false },
      },
      theme: { mode: "dark" },
      grid: { borderColor: "#1e293b" },
      xaxis: {
        type: "datetime",
        labels: { style: { colors: "#94a3b8", fontSize: "11px" }, datetimeUTC: false },
      },
      yaxis: {
        title: { text: yAxisLabel, style: { color: "#94a3b8", fontSize: "11px" } },
        labels: { style: { colors: "#94a3b8", fontSize: "11px" } },
      },
      plotOptions: { bar: { borderRadius: 4, columnWidth: "55%" } },
      colors: ["#38bdf8"],
      tooltip: { theme: "dark", x: { format: "HH:mm:ss" } },
    };
  };

  const pieChartOptions = (title, labels) => ({
    chart: { type: "donut", height: 260, background: "transparent" },
    theme: { mode: "dark" },
    labels,
    colors: colors.slice(0, labels.length),
    legend: { labels: { colors: "#94a3b8" }, position: "bottom" },
    dataLabels: { enabled: true, style: { fontSize: "11px" } },
  });

  const isConnected = connectionStatus === "Connected";
  const isAttack = attackDetection?.attack_detected;

  return (
    <div className="local-dashboard">
      <div className="dashboard-hero">
        <h1 className="page-title">Local Endpoint Monitoring</h1>
        <p className="page-subtitle">
          Real-time packet sniffing, sliding-window throughput APM &amp; on-device attack heuristics
        </p>
      </div>

      {/* SOC Radar Status Row */}
      <div className="soc-status-grid">
        <div className="soc-status-card">
          <div className="status-meta">
            <span className="status-label">Endpoint Telemetry Status</span>
            <span className="status-value">
              {isConnected ? "Live Socket Active (ws://)" : "Reconnecting to Agent..."}
            </span>
          </div>
          <div className={`status-pill ${isConnected ? "badge-connected" : "badge-disconnected"}`}>
            <span className="pulse-dot"></span>
            {connectionStatus}
          </div>
        </div>

        <div className="soc-status-card">
          <div className="status-meta">
            <span className="status-label">Autonomous Heuristics Engine</span>
            <span className="status-value">
              {isAttack
                ? (attackDetection.details || "Degradation / Threat Detected")
                : "Normal - Traffic Nominal"}
            </span>
          </div>
          <div className={`status-pill ${isAttack ? "badge-attack" : "badge-normal"}`}>
            {isAttack ? "THREAT DETECTED" : "DEFENSE ACTIVE"}
          </div>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="dashboard-controls-bar">
        <div className="chart-type-tabs">
          <button
            className={`chart-tab-btn ${activeTab === "line" ? "active" : ""}`}
            onClick={() => setActiveTab("line")}
          >
            Line Charts
          </button>
          <button
            className={`chart-tab-btn ${activeTab === "bar" ? "active" : ""}`}
            onClick={() => setActiveTab("bar")}
          >
            Bar Graphs
          </button>
          <button
            className={`chart-tab-btn ${activeTab === "pie" ? "active" : ""}`}
            onClick={() => setActiveTab("pie")}
          >
            Distribution
          </button>
        </div>

        <div className="sim-btn-wrapper">
          <span style={{ fontSize: "12px", color: "#64748b" }}>
            Live Buffer: {metricsData.bytesSentData.length} samples
          </span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid-4">
        {activeTab === "line" &&
          metrics.map((metric, index) => {
            const threshold = thresholds[metric.name];
            const latestValue =
              metric.data.length > 0
                ? metric.data[metric.data.length - 1].y
                : null;
            const exceeded =
              threshold &&
              latestValue !== null &&
              (latestValue > threshold.avg || latestValue > threshold.max);
            return (
              <div
                key={index}
                className={`chart-panel-card ${exceeded ? "exceeded-threshold" : ""}`}
              >
                <div className="chart-card-header">
                  <span className="chart-card-title">{metric.name}</span>
                  <span className="chart-unit-badge">{metric.unit}</span>
                </div>
                <ApexCharts
                  options={lineChartOptions(
                    metric.name,
                    metric.unit,
                    colors[index % colors.length],
                    threshold
                  )}
                  series={[{ name: metric.name, data: metric.data }]}
                  type="line"
                  height={260}
                />
                {exceeded && (
                  <div className="threshold-badge-alert">Threshold Limit Exceeded</div>
                )}
              </div>
            );
          })}

        {activeTab === "bar" &&
          metrics.map((metric, index) => {
            const aggregatedData = aggregateData(metric.data);
            const threshold = thresholds[metric.name];
            const latestBarValue =
              aggregatedData.length > 0
                ? aggregatedData[aggregatedData.length - 1].y
                : null;
            const exceeded =
              threshold &&
              latestBarValue !== null &&
              (latestBarValue > threshold.avg || latestBarValue > threshold.max);
            return (
              <div
                key={index}
                className={`chart-panel-card ${exceeded ? "exceeded-threshold" : ""}`}
              >
                <div className="chart-card-header">
                  <span className="chart-card-title">{metric.name}</span>
                  <span className="chart-unit-badge">5-min avg</span>
                </div>
                <ApexCharts
                  options={barChartOptions(metric.name, metric.unit, threshold)}
                  series={[{ name: metric.name, data: aggregatedData }]}
                  type="bar"
                  height={260}
                />
                {exceeded && (
                  <div className="threshold-badge-alert">Threshold Limit Exceeded</div>
                )}
              </div>
            );
          })}

        {activeTab === "pie" &&
          metrics.map((metric, index) => {
            const { series, labels, exceeded } = getPieChartData(
              metric.name,
              metric.data
            );
            if (series.length === 0) return null;
            return (
              <div
                key={index}
                className={`chart-panel-card ${exceeded ? "exceeded-threshold" : ""}`}
              >
                <div className="chart-card-header">
                  <span className="chart-card-title">{metric.name}</span>
                  <span className="chart-unit-badge">Binned %</span>
                </div>
                <ApexCharts
                  options={pieChartOptions(`${metric.name} Distribution`, labels)}
                  series={series}
                  type="donut"
                  height={260}
                />
                {exceeded && (
                  <div className="threshold-badge-alert">Threshold Limit Exceeded</div>
                )}
              </div>
            );
          })}
      </div>

      <Chatbot
        chatMessages={chatMessages}
        addChatMessage={addChatMessage}
        sendChatMessage={sendChatMessage}
      />
    </div>
  );
};

export default LocalControllerDashboard;
