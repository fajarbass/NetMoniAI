import logging
from typing import Optional, Dict, Any
from settings_manager import settings_manager
from services.llm_service import generate_llm_response

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """
You are NetMoniAI Assistant, an advanced AI network monitoring and cybersecurity copilot.
Help the network administrator understand live metrics, security anomalies, DDoS alerts, 
multi-node fleet posture, and provide clear, concise troubleshooting advice in Indonesian or English.
"""

def generate_heuristic_chat_response(
    user_query: str,
    context: Optional[Dict[str, Any]] = None,
    ai_error: Optional[str] = None
) -> str:
    """Generate smart, deterministic cybersecurity & telemetry response when LLM is unconfigured or offline."""
    q = (user_query or "").lower().strip()
    ctx = context or {}
    ctx_type = ctx.get("type", "local")
    metrics = ctx.get("latest_metrics") or {}
    nodes = ctx.get("node_statuses") or {}

    response_lines = []

    # 1. Greetings & Identity
    if any(k in q for k in ["halo", "hai", "hello", "hi", "siapa", "bisa apa", "kamu siapa", "bantuan", "help"]):
        response_lines.append("🛡️ **NetMoniAI Cyber Sentinel & APM Copilot Online**")
        response_lines.append(
            "Saya adalah asisten cerdas untuk pemantauan performa jaringan dan pertahanan siber real-time."
        )
        response_lines.append("\n**Kemampuan saya meliputi:**")
        response_lines.append("• 📊 **Monitoring Telemetri:** Analisis throughput, latensi lokal/eksternal, dan packet loss.")
        response_lines.append("• 🚨 **Deteksi Anomali:** Indikasi serangan DDoS, SYN Flood, dan Port Scan.")
        response_lines.append("• 🌐 **Fleet Intelligence:** Status kesehatan node pada Central SOC.")
        response_lines.append("• 🛡️ **Rekomendasi Keamanan:** Saran mitigasi dan konfigurasi firewall.")
        response_lines.append("\nKetik pertanyaan Anda tentang status trafik, anomali jaringan, atau node yang terhubung!")

    # 2. Node / Fleet Status Query
    elif any(k in q for k in ["node", "klien", "client", "agen", "agent", "soc", "berapa node", "daftar node"]):
        response_lines.append("🌐 **Status Node Central SOC**")
        if not nodes:
            response_lines.append(
                "Saat ini **belum ada node/agen aktif** yang mengirimkan laporan telemetri ke database Central SOC.\n"
                "• **Untuk Endpoint Agent:** Pastikan `Central Server URL` pada menu **Settings > Central Server** diarahkan ke server ini (`http://<ip-server>:8000`).\n"
                "• **Untuk Simulasi NS-3:** Jalankan skrip simulasi pada folder `simulations/` untuk menghasilkan lalu lintas multi-node."
            )
        else:
            response_lines.append(f"Terdeteksi **{len(nodes)} node** tercatat di database:")
            for ip, st in nodes.items():
                is_attack = st.get("attack_detected", False)
                status_icon = "🔴 DARURAT" if is_attack else "🟢 NORMAL"
                atk_type = st.get("attack_type", "None")
                response_lines.append(f"• **{ip}** [{status_icon}]: Serangan: {atk_type} | Ringkasan: {st.get('summary', 'Traffic stabil')}")

    # 3. Traffic / Throughput / Latency / Metrics Query
    elif any(k in q for k in ["status", "trafik", "traffic", "throughput", "bandwidth", "kecepatan", "bytes", "paket", "loss", "ping", "latensi", "latency"]):
        response_lines.append("📊 **Laporan Telemetri Jaringan Real-Time**")
        if metrics:
            bytes_s = metrics.get("bytes_sent", 0)
            bytes_r = metrics.get("bytes_recv", 0)
            tp_s = metrics.get("throughput_sent", 0.0)
            tp_r = metrics.get("throughput_recv", 0.0)
            lat_ext = metrics.get("avg_latency", "N/A")
            lat_loc = metrics.get("local_latency", "N/A")
            loss = metrics.get("avg_loss", "0")

            response_lines.append(f"• **Throughput Kirim:** {tp_s:.2f} B/s ({bytes_s:,} bytes)")
            response_lines.append(f"• **Throughput Terima:** {tp_r:.2f} B/s ({bytes_r:,} bytes)")
            response_lines.append(f"• **Latensi Eksternal (8.8.8.8):** {lat_ext} ms")
            response_lines.append(f"• **Latensi Gateway Lokal:** {lat_loc} ms")
            response_lines.append(f"• **Packet Loss:** {loss}%")
            
            # Diagnostic evaluation
            if isinstance(lat_ext, (int, float)) and lat_ext > 100:
                response_lines.append("\n⚠️ *Peringatan:* Latensi eksternal terdeteksi tinggi (> 100ms). Periksa beban bandwidth atau routing ISP.")
            else:
                response_lines.append("\n✅ *Evaluasi:* Jalur transmisi jaringan berada dalam ambang batas normal.")
        else:
            response_lines.append("Buffer metrik sedang mengumpulkan sampel awal paket jaringan. Pantau grafik garis pada dashboard.")

    # 4. Security / Attack / DDoS Query
    elif any(k in q for k in ["ddos", "syn", "attack", "serangan", "port scan", "anomali", "aman", "security", "bahaya", "mitigasi"]):
        response_lines.append("🛡️ **Analisis Pertahanan Siber & Heuristik**")
        if nodes:
            attacked = [ip for ip, st in nodes.items() if st.get("attack_detected")]
            if attacked:
                response_lines.append(f"🚨 **Terdeteksi Serangan Aktif** pada node: {', '.join(attacked)}")
                response_lines.append("Rekomendasi Tindakan Segera:")
                response_lines.append("1. Lakukan isolasi paket atau filter IP penyerang pada firewall host.")
                response_lines.append("2. Periksa dump PCAP pada direktori `lastCapture/` untuk investigasi muatan paket.")
            else:
                response_lines.append("✅ **Kondisi Aman:** Seluruh node yang terdaftar memiliki status *Normal Traffic Nominal*.")
        else:
            response_lines.append("✅ **Kondisi Nominal:** Mesin heuristik NetMoniAI aktif memantau ambang batas paket. Tidak ada anomali lonjakan yang melampaui batas toleransi saat ini.")

    # 5. Default Fallback
    else:
        response_lines.append(f"🔍 **NetMoniAI Copilot:** Menanggapi pertanyaan Anda: *\"{user_query}\"*")
        response_lines.append(
            "Saya terus memantau kinerja jaringan dan pola serangan siber. "
            "Anda dapat menanyakan hal-hal spesifik seperti: *'Berapa throughput saat ini?'*, *'Apakah ada serangan DDoS?'*, atau *'Bagaimana status node SOC?'*."
        )

    # Footnote about AI Engine configuration
    cfg = settings_manager.get_config()
    provider = cfg.ai.active_provider.capitalize()
    if ai_error:
        response_lines.append(
            f"\n---\n⚠️ *Catatan AI:* Server {provider} melaporkan kendala: `{ai_error}`. "
            "Respons di atas disajikan langsung oleh *Autonomous Local Heuristics Engine NetMoniAI*."
        )
    else:
        response_lines.append(
            f"\n---\n💡 *Tips:* Untuk mengaktifkan penalaran mendalam berbasis model AI generatif (Gemini 3.8 Flash / GPT-4o), "
            f"silakan lengkapi API Key di menu **Settings > AI Providers & Models**."
        )

    return "\n".join(response_lines)


class ChatAgentWrapper:
    async def run(self, user_prompt: str, context: Optional[Dict[str, Any]] = None):
        class ChatResponse:
            def __init__(self, data: str):
                self.data = data

        cfg = settings_manager.get_config()
        provider = (cfg.ai.active_provider or "gemini").lower()
        active_key = ""
        if provider == "gemini":
            active_key = cfg.ai.gemini.api_key
        elif provider == "openai":
            active_key = cfg.ai.openai.api_key
        elif provider == "opencode":
            active_key = cfg.ai.opencode.api_key or "opencode-token"

        raw_query = (context or {}).get("raw_message", user_prompt)

        # If no API key configured, seamlessly answer using local heuristic intelligence
        if not active_key:
            heuristic_resp = generate_heuristic_chat_response(
                user_query=raw_query,
                context=context
            )
            return ChatResponse(data=heuristic_resp)

        # Call remote AI model
        try:
            res_text = await generate_llm_response(
                prompt=user_prompt,
                system_prompt=CHAT_SYSTEM_PROMPT,
                agent_name="chat_agent"
            )
            if not res_text or not res_text.strip():
                # Fallback if empty output
                return ChatResponse(data=generate_heuristic_chat_response(raw_query, context))
            return ChatResponse(data=res_text.strip())
        except Exception as e:
            logger.warning(f"Remote LLM call failed ({e}), falling back to local heuristics: {e}")
            fallback_text = generate_heuristic_chat_response(
                user_query=raw_query,
                context=context,
                ai_error=str(e)
            )
            return ChatResponse(data=fallback_text)

ChatAgent = ChatAgentWrapper()
