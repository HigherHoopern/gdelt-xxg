import gradio as gr
import json
import httpx
import uuid
import requests
import docx2txt
import os
import fitz  # 新增: PyMuPDF 用于处理 PDF

# 后端配置
API_BASE = "http://localhost:8045"

# --- 核心交互逻辑 ---

async def main_chat_flow(message, history, session_id, session_titles, all_sessions):
    if not message or not message.strip():
        yield history, "", gr.update(), session_titles, all_sessions
        return

    user_msg_str = str(message).strip()
    history.append({"role": "user", "content": user_msg_str})
    
    exists = any(item[0] == session_id for item in session_titles)
    if not exists:
        title = user_msg_str[:12] + ("..." if len(user_msg_str) > 12 else "")
        session_titles.insert(0, (session_id, title))
    
    choices = [t[1] for t in session_titles]
    current_title = next((t[1] for t in session_titles if t[0] == session_id), None)

    yield history, "", gr.update(choices=choices, value=current_title), session_titles, all_sessions

    payload = {"question": user_msg_str, "session_id": str(session_id)}
    history.append({"role": "assistant", "content": ""})
    
    full_response = ""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{API_BASE}/chat", json=payload) as response:
                if response.status_code != 200:
                    err_data = await response.aread()
                    history[-1]["content"] = f"⚠️ 错误: {err_data.decode()}"
                    yield history, "", gr.update(), session_titles, all_sessions
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event_data = line[6:].strip()
                            event = json.loads(event_data)
                            if event["type"] == "answer_chunk":
                                full_response += event["data"]
                                history[-1]["content"] = full_response
                                all_sessions[session_id] = history
                                yield history, "", gr.update(), session_titles, all_sessions
                        except Exception:
                            continue
    except Exception as e:
        history[-1]["content"] = f"⚠️ 网络连接异常: {str(e)}"
        yield history, "", gr.update(), session_titles, all_sessions

def handle_upload(file):
    """上传文件并提取内容（支持 PDF, DOCX, MD, TXT）"""
    if file is None: 
        return "未选择文件", "### 暂无预览内容"
    
    file_path = file.name if hasattr(file, 'name') else str(file)
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_path)[1].lower()
    
    preview_text = ""
    try:
        # --- PDF 预览逻辑 ---
        if file_ext == ".pdf":
            with fitz.open(file_path) as doc:
                text_list = []
                for page in doc:
                    text_list.append(page.get_text())
                preview_text = "\n\n--- 第 {} 页 ---\n\n".join(text_list).format(*range(1, len(text_list)+1))
                if not preview_text.strip():
                    preview_text = "⚠️ 该 PDF 可能是扫描件或图片，未提取到可编辑文本。"
        
        # --- DOCX 预览逻辑 ---
        elif file_ext == ".docx":
            preview_text = docx2txt.process(file_path)
        
        # --- Markdown/TXT 预览逻辑 ---
        elif file_ext in [".md", ".txt"]:
            with open(file_path, 'r', encoding='utf-8') as f:
                preview_text = f.read()
        
        else:
            preview_text = f"暂不支持预览 {file_ext} 格式的详细内容。"
            
    except Exception as e:
        preview_text = f"文件解析预览失败: {str(e)}"

    # 调用后端上传
    upload_status = ""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f)}
            res = requests.post(f"{API_BASE}/upload", files=files)
            upload_status = f"✅ 上传成功: {file_name}" if res.status_code == 200 else f"❌ 失败: {res.text}"
    except Exception as e:
        upload_status = f"❌ 后端连接错误: {str(e)}"

    # 构造 Markdown 预览
    formatted_preview = f"# 📄 {file_name}\n\n{preview_text}"
    return upload_status, formatted_preview

def switch_session(selected_title, session_titles, all_sessions):
    target_id = None
    for sid, title in session_titles:
        if title == selected_title:
            target_id = sid
            break
    if target_id and target_id in all_sessions:
        return target_id, all_sessions[target_id], f"`ID: {target_id}`"
    return target_id, [], "`ID: 未知`"

def start_new_chat():
    new_id = str(uuid.uuid4())
    return new_id, [], gr.update(value=None), f"`ID: {new_id}`"

# --- UI & Theme ---

xterai_theme = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="emerald",
).set(
    button_primary_background_fill="#003C3D",
    button_primary_text_color="#00DEA5",
    body_background_fill="#F7F9F9",
)

custom_css = """
footer:not(.footer) { display: none !important; }
.chatbot-container { height: 75vh !important; border-radius: 0 0 12px 12px !important; border: 1px solid #eee !important; border-top: none !important; }
.preview-container { height: 75vh !important; overflow-y: auto !important; padding: 30px; background: white; border: 1px solid #eee; border-radius: 0 0 12px 12px; }
.side-panel { padding: 20px !important; border-right: 1px solid #eee; background: #fff; }
.footer { text-align: center; color: #003C3D !important; font-size: 10px; margin-top: 20px; display: block !important; }
.tabs-header { border: 1px solid #eee; border-bottom: none; border-radius: 12px 12px 0 0; background: #fafafa; }
"""

with gr.Blocks(css=custom_css, theme=xterai_theme) as demo:
    session_id_state = gr.State(str(uuid.uuid4()))
    all_sessions_state = gr.State({})      
    session_titles_state = gr.State([])    

    with gr.Row():
        # 左侧边栏
        with gr.Column(scale=1, variant="panel", elem_classes="side-panel"):
            gr.HTML("""
                <div style='text-align: center; margin-bottom: 24px;'>
                    <h1 style='color: #003C3D; font-size: 26px; margin: 0; font-weight: 800;'>Xter<span style='color: #00DEA5;'>AI</span></h1>
                    <p style='color: #888; font-size: 10px; letter-spacing: 1.5px;'>RAG 智能问答系统</p>
                </div>
            """)
            
            new_btn = gr.Button("➕ 开启新会话", variant="secondary")
            gr.Markdown("### 📜 历史对话")
            history_list = gr.Radio(choices=[], label=None, interactive=True, show_label=False)
            
            gr.Markdown("---")
            gr.Markdown("### 📂 知识库管理")
            upload_btn = gr.UploadButton("📁 上传文档", file_types=[".pdf", ".docx", ".txt", ".md"], variant="primary")
            status_msg = gr.Label(label=None, value="服务准备就绪", container=False)
            
            gr.Markdown("---")
            session_display = gr.Markdown("`ID: 初始化...`")

        # 右侧主内容区
        with gr.Column(scale=4):
            with gr.Tabs(elem_classes="tabs-header") as main_tabs:
                
                with gr.Tab("💬 智能对话", id=0):
                    chatbot = gr.Chatbot(elem_classes="chatbot-container")
                    with gr.Row():
                        msg_input = gr.Textbox(placeholder="输入您的问题...", container=False, scale=10, autofocus=True)
                        send_btn = gr.Button("发送", variant="primary", scale=1)
                
                with gr.Tab("📄 文档预览", id=1):
                    preview_area = gr.Markdown(
                        value="### 💡 提示\n上传 PDF, Word 或 Markdown 后，此处将显示提取的文本内容。",
                        elem_classes="preview-container"
                    )

    gr.HTML("""<footer class="footer">© 2026 XterAI. All Rights Reserved.</footer>""")

    # 逻辑绑定
    send_btn.click(fn=main_chat_flow, inputs=[msg_input, chatbot, session_id_state, session_titles_state, all_sessions_state], outputs=[chatbot, msg_input, history_list, session_titles_state, all_sessions_state])
    msg_input.submit(fn=main_chat_flow, inputs=[msg_input, chatbot, session_id_state, session_titles_state, all_sessions_state], outputs=[chatbot, msg_input, history_list, session_titles_state, all_sessions_state])
    
    history_list.change(fn=switch_session, inputs=[history_list, session_titles_state, all_sessions_state], outputs=[session_id_state, chatbot, session_display])
    new_btn.click(fn=start_new_chat, outputs=[session_id_state, chatbot, history_list, session_display])

    upload_btn.upload(
        fn=handle_upload,
        inputs=[upload_btn],
        outputs=[status_msg, preview_area]
    )

    demo.load(lambda sid: f"`ID: {sid}`", inputs=[session_id_state], outputs=[session_display])

if __name__ == "__main__":
    demo.launch(server_port=8065, show_error=True)