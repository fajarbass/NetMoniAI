import React, { useState, useEffect, useRef } from "react";
import "../chatbot.css";

const SOC_QUICK_PROMPTS = [
  "🌐 Status Fleet Node",
  "🚨 Cek Anomali SOC",
  "🛡️ Rekomendasi Mitigasi",
  "❓ Bantuan SOC Copilot"
];

const GlobalChatbot = ({
  globalChatMessages,
  addGlobalChatMessage,
  sendGlobalChatMessage,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const chatHistoryRef = useRef(null);

  const toggleChatbot = () => setIsOpen(!isOpen);

  const handleSendPrompt = (promptText) => {
    const textToSend = promptText || input.trim();
    if (!textToSend || isThinking) return;

    const userMessage = { sender: "user", text: textToSend };
    addGlobalChatMessage(userMessage);
    sendGlobalChatMessage(textToSend);
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
    if (
      globalChatMessages.length > 0 &&
      globalChatMessages[globalChatMessages.length - 1].sender === "bot"
    ) {
      setIsThinking(false);
    }
  }, [globalChatMessages]);

  return (
    <div className={`chatbot ${isOpen ? "open" : ""}`}>
      <button className="chatbot-toggle soc-toggle" onClick={toggleChatbot} title="Buka SOC Copilot">
        <span>{isOpen ? "Tutup SOC Copilot" : "SOC Copilot"}</span>
        {!isOpen && <span className="chatbot-live-dot"></span>}
      </button>

      {isOpen && (
        <div className="chatbot-window">
          <div className="chatbot-header">
            <div className="chatbot-title">
              <span className="copilot-robot-icon">🛰️</span>
              <div>
                <div className="copilot-name">Central SOC Copilot</div>
                <div className="copilot-status-sub">
                  <span className="status-mini-dot"></span>
                  <span>Fleet Analytics &amp; Multi-Node Defense</span>
                </div>
              </div>
            </div>
            <button className="chatbot-close-btn" onClick={toggleChatbot} title="Tutup">
              ✕
            </button>
          </div>

          <div className="chat-history" ref={chatHistoryRef}>
            {globalChatMessages.map((msg, index) => (
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
                <span className="thinking-label">SOC Copilot sedang menganalisis seluruh fleet node...</span>
              </div>
            )}
          </div>

          {/* Quick prompt suggestion chips */}
          <div className="quick-chips-bar">
            {SOC_QUICK_PROMPTS.map((prompt, idx) => (
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
              placeholder="Tanyakan status node, serangan siber, atau rekomendasi..."
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

export default GlobalChatbot;
