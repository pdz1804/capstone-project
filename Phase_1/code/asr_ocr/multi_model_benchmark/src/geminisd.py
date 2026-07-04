from google import genai
import os


api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

uploaded_file = client.files.upload("experiment/icmptable.png")


response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["Write the table into markdown", uploaded_file]
)

print("Response:", response.text)
