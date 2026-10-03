import axios from "axios";

const API_URL = process.env.REACT_APP_API_URL || (typeof window !== "undefined" && window.location && window.location.origin ? window.location.origin : "http://localhost:8000");

// --- App Mode Discovery ---
export const getAppMode = async () => {
  try {
    const response = await axios.get(`${API_URL}/api/mode`);
    return response.data;
  } catch (error) {
    const port = (typeof window !== "undefined" && window.location && window.location.port) || "8001";
    if (port === "8001") {
      return { mode: "agent", title: "Endpoint Agent", is_agent: true, is_server: false, port: 8001 };
    } else if (port === "8000") {
      return { mode: "server", title: "Central Server", is_agent: false, is_server: true, port: 8000 };
    }
    return { mode: "agent", title: "Endpoint Agent", is_agent: true, is_server: false, port: 8001 };
  }
};

// --- Node Statuses ---
export const getNodeStatuses = async () => {
  try {
    const response = await axios.get(`${API_URL}/gcstatuses`);
    return response.data;
  } catch (error) {
    console.error("Error fetching node statuses:", error);
    throw error;
  }
};

// --- Settings API ---
export const getSettings = async () => {
  const response = await axios.get(`${API_URL}/api/settings`);
  return response.data;
};

export const updateSettings = async (settingsData) => {
  const response = await axios.put(`${API_URL}/api/settings`, settingsData);
  return response.data;
};

// --- System & Network Interfaces ---
export const getNetworkInterfaces = async () => {
  const response = await axios.get(`${API_URL}/api/system/interfaces`);
  return response.data;
};

// --- AI Models & Testing ---
export const getAIModels = async (provider, apiKey, baseUrl) => {
  const response = await axios.post(`${API_URL}/api/ai/models`, {
    provider,
    api_key: apiKey,
    base_url: baseUrl,
  });
  return response.data;
};

export const testAIConnection = async (provider, apiKey, baseUrl, model) => {
  const response = await axios.post(`${API_URL}/api/ai/test`, {
    provider,
    api_key: apiKey,
    base_url: baseUrl,
    model,
  });
  return response.data;
};

export const pingCentralServer = async (serverUrl) => {
  const response = await axios.post(`${API_URL}/api/central-server/ping`, {
    server_url: serverUrl,
  });
  return response.data;
};

// --- Persistent Reports History (SQLite) ---
export const getIncidentReports = async (limit = 50, nodeIp = null, attackType = null) => {
  const params = { limit };
  if (nodeIp) params.node_ip = nodeIp;
  if (attackType) params.attack_type = attackType;
  const response = await axios.get(`${API_URL}/api/reports`, { params });
  return response.data;
};

// --- Windows Integration & System Tray ---
export const getStartupStatus = async () => {
  const response = await axios.get(`${API_URL}/api/system/startup`);
  return response.data;
};

export const setStartupStatus = async (enabled) => {
  const response = await axios.post(`${API_URL}/api/system/startup`, { enabled });
  return response.data;
};

export const minimizeToTray = async () => {
  const response = await axios.post(`${API_URL}/api/system/tray/minimize`);
  return response.data;
};

export const restoreFromTray = async () => {
  const response = await axios.post(`${API_URL}/api/system/tray/restore`);
  return response.data;
};
