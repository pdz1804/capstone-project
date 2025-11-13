import time
from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1",
    timeout=3600
)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://ofasys-multimodal-wlcb-3-toshanghai.oss-accelerate.aliyuncs.com/wpf272043/keepme/image/receipt.png"
                }
            },
            {
                "type": "text",
                "text": "Free OCR."
            }
        ]
    }
]

start = time.time()
response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-OCR",
    messages=messages,
    max_tokens=2048,
    temperature=0.0,
    extra_body={
        "skip_special_tokens": False,
        # args used to control custom logits processor
        "vllm_xargs": {
            "ngram_size": 30,
            "window_size": 90,
            # whitelist: <td>, </td>
            "whitelist_token_ids": [128821, 128822],
        },
    },
)
print(f"Response costs: {time.time() - start:.2f}s")
print(f"Generated text: {response.choices[0].message.content}")