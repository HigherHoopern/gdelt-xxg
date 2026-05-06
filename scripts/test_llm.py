import os
from openai import OpenAI
import json

def test_llm_enhanced():
    # 配置信息
    MODEL_NAME = "deepseek" # 建议确认中转站里确切的模型标识符
    BASE_URL = "http://192.168.70.108:3000/v1"
    API_KEY = "sk-e7jryiLdsXbU9HqXi72sZkBYIw4F8VdjRMn6efOe3BrCC09o"

    print(f"🚀 正在增强测试私有节点: {BASE_URL}")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    try:
        # 1. 尝试流式请求 (这是主程序使用的模式)
        print("\n📡 [测试 1] 流式请求测试...")
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "你好"}],
            stream=True
        )
        print("📥 收到流式内容: ", end="", flush=True)
        has_content = False
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
                has_content = True
        
        if not has_content:
            print(" (无任何内容流出)")
        else:
            print("\n✅ 流式测试成功！")

        # 2. 尝试非流式请求并打印原始 JSON
        print("\n📡 [测试 2] 非流式请求原始数据探测...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "1+1=?"}],
            stream=False
        )
        
        # 打印原始对象的 dict 形式，查看隐藏字段
        raw_data = response.model_dump()
        print(f"📊 原始响应结构:\n{json.dumps(raw_data, indent=2, ensure_ascii=False)}")

        content = response.choices[0].message.content
        if content:
            print(f"\n✅ 非流式回复成功: {content}")
        else:
            print("\n⚠️ 回复内容仍为 None。请检查中转站的 '渠道' 状态是否正常。")

    except Exception as e:
        print(f"\n❌ 发生异常: {str(e)}")

if __name__ == "__main__":
    test_llm_enhanced()
