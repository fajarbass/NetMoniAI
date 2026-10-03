import React, { useState, useEffect, useRef } from "react";
import "../chatbot.css";

const QUICK_PROMPTS = [
  "📊 Status Trafik",
  "🚨 Cek Anomali",
  "🛡️ Info Keamanan",
  "❓ Siapa Kamu?"
];

const Chatbot = ({ chatMessages, addChatMessage, sendChatMessage }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const chatHistoryRef = useRef(null);

  const toggleChatbot = () => setIsOpen(!isOpen);

  const handleSendPrompt = (promptText) => {
    const textToSend = promptText || input.trim();
    if (!textToSend || isThinking) return;

    const userMessage = { sender: "user", text: textToSend };
    addChatMessage(userMessage);
    sendChatMessage(textToSend);
    setInput("");
    setIsThinking(true);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendPrompt();
    }
  };

  useEffect(() => {
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTop = chatHistoryRef.current.scrollHeight;
    }
    // If the last message is from bot, stop thinking indicator
    if (chatMessages.length > 0 && chatMessages[chatMessages.length - 1].sender === "bot") {
      setIsThinking(false);
    }
  }, [chatMessages]);

  return (
    <div className={`chatbot ${isOpen ? "open" : ""}`}>
      <button className="chatbot-toggle" onClick={toggleChatbot} title="Buka NetMoniAI Copilot">
        <span>{isOpen ? "Tutup Copilot" : "Copilot"}</span>
        {!isOpen && <span className="chatbot-live-dot"></span>}
      </button>

      {isOpen && (
        <div className="chatbot-window">
          <div className="chatbot-header">
            <div className="chatbot-title">
              <span className="copilot-robot-icon">🤖</span>
              <div>
                <div className="copilot-name">NetMoniAI Endpoint Copilot</div>
                <div className="copilot-status-sub">
                  <span className="status-mini-dot"></span>
                  <span>Autonomous Sentinel &amp; APM</span>
                </div>
              </div>
            </div>
            <button className="chatbot-close-btn" onClick={toggleChatbot} title="Tutup">
              ✕
            </button>
          </div>

          <div className="chat-history" ref={chatHistoryRef}>
            {chatMessages.map((msg, index) => (
              <div key={index} className={`message ${msg.sender}`}>
                <div className="message-content">{msg.text}</div>
              </div>
            ))}

            {isThinking && (
              <div className="message bot thinking-bubble">
                <span className="thinking-dots">
                  <span className="dot"></span>
                  <span className="dot"></span>
                  <span className="dot"></span>
                </span>
                <span className="thinking-label">NetMoniAI sedang menganalisis telemetri...</span>
              </div>
            )}
          </div>

          {/* Quick prompt suggestion chips */}
          <div className="quick-chips-bar">
            {QUICK_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                className="quick-chip-btn"
                onClick={() => handleSendPrompt(prompt)}
                disabled={isThinking}
              >
                {prompt}
              </button>
            ))}
          </div>

          <div className="chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Tanyakan status trafik, anomali, latensi..."
              disabled={isThinking}
            />
            <button
              onClick={() => handleSendPrompt()}
              disabled={!input.trim() || isThinking}
              className="chat-send-btn"
            >
              {isThinking ? "..." : "Kirim"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chatbot;
