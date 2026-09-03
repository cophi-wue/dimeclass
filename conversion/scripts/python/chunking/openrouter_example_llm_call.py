from dotenv import load_dotenv
import os
from langchain.chat_models import init_chat_model

load_dotenv()

llm = init_chat_model(
    #model="openai/gpt-oss-20b:free",
    #cannot use this model bc of open router limitations - I would have to "allow the provider to publish my prompts and completions to public datasets"
    model="mistralai/devstral-2512:free",
    model_provider="mistralai",
    base_url=os.getenv("OPEN_ROUTER_BASE_URL"),
    api_key=os.getenv("OPEN_ROUTER_API_KEY"),
)
print("Starte Anfrage...")
resp = llm.invoke("Say hi in 10 words.")
print("Antwort bekommen")
print(resp.content)

"""messages = [
    SystemMessage(content="You are a concise assistant."),
    HumanMessage(content="Give me 3 bullet points on the band Muse.'")
]
resp = llm.invoke(messages)
print("second answer", resp.content)"""