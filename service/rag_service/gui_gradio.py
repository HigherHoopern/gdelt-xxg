import os
import json
import httpx
import gradio as gr

# ==========================================================
# 1. 彻底屏蔽代理 (解决 macOS + Clash 干扰)
# ==========================================================
for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(var, None)

os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# 使用 127.0.0.1 避免解析延迟
API_URL = "http://127.0.0.1:8040/chat"

# ==========================================================
# 2. 核心流式解析器
# ==========================================================
def stream_predict(message, session_id):
    """
    底层流式读取器：构造严谨的 JSON 以避免 422 错误
    """
    # 构造 Payload，确保 session_id 如果为空则设为 None
    # 这样更符合后端 Optional[str] = None 的定义
    clean_session_id = session_id if session_id and session_id.strip() else None
    payload = {
        "question": str(message), 
        "session_id": clean_session_id
    }
    
    print(f">>> 发送请求: {payload}") # 调试信息

    try:
        # 强制禁用代理
        with httpx.Client(trust_env=False, timeout=300.0) as client:
            with client.stream("POST", API_URL, json=payload) as r:
                if r.status_code == 422:
                    yield f"❌ 422 错误: 后端无法解析请求内容。Payload: {payload}", session_id
                    return
                if r.status_code != 200:
                    yield f"❌ 服务器返回错误状态码: {r.status_code}", session_id
                    return

                # 逐行读取 SSE 内容
                for line in r.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    try:
                        data_packet = json.loads(line[6:])
                        event_type = data_packet.get("type")
                        event_data = data_packet.get("data")

                        if event_type == "session_info":
                            # 获取后端生成的 session_id
                            session_id = event_data.get("session_id")
                        elif event_type == "answer_chunk":
                            # 实时返回文本碎片
                            yield event_data, session_id
                        elif event_type == "full_response":
                            # 完成后无需额外处理，由前端累加显示
                            pass 
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"❌ 连接异常: {str(e)}", session_id

# ==========================================================
# 3. 构建 UI (适配 Gradio 6.x 规范)
# ==========================================================
with gr.Blocks() as demo:
    # 状态存储建议初始化为 None
    session_id_state = gr.State(value=None)
    
    gr.Markdown("# 🚀 XterAI 强制流式版\n针对 macOS 环境优化 + 422 错误修复")

    chatbot = gr.Chatbot(label="对话记录", height=600)
    msg_input = gr.Textbox(placeholder="输入问题并按回车...", label="输入内容")
    
    # --- 逻辑 A: 显示用户消息 ---
    def user_msg(user_message, history):
        if history is None: history = []
        return "", history + [{"role": "user", "content": user_message}]

    # --- 逻辑 B: 流式生成机器人消息 ---
    def bot_msg(history, session_id):
        if not history:
            return history, session_id
            
        user_message = history[-1]["content"]
        # 追加助手空消息
        history.append({"role": "assistant", "content": ""})
        
        current_bot_text = ""
        # 遍历生成器，通过 WebSocket 将数据逐字推送到前端
        for chunk, new_session_id in stream_predict(user_message, session_id):
            current_bot_text += chunk
            history[-1]["content"] = current_bot_text
            # 这里的 yield 是触发 WebSocket 蹦字的关键
            yield history, new_session_id

    # 使用 .then() 链式调用：先显示用户消息，再开始流式
    msg_input.submit(
        user_msg, 
        [msg_input, chatbot], 
        [msg_input, chatbot], 
        queue=False
    ).then(
        bot_msg, 
        [chatbot, session_id_state], 
        [chatbot, session_id_state]
    )

    gr.Button("🗑 清空对话").click(lambda: ([], None), None, [chatbot, session_id_state])

if __name__ == "__main__":
    # 重要：启用队列开启 WebSocket 通道，绕过 macOS 代理缓存
    demo.queue() 
    demo.launch(
        server_name="127.0.0.1",
        server_port=7862,
        theme=gr.themes.Soft()
    )