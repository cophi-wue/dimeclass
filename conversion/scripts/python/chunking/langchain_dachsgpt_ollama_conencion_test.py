## Braucht es Uni WUE VPN?
#das hat funktioniert. wie kann ich thinking nicht im ooutput haben,sondern nur die antwort?
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("OLLAMA_MODEL", "qwen3:32b"),                               # as shown in OpenWebUI/Ollama
    base_url=os.getenv("OLLAMA_BASE_URL","https://dachsgpt.kallimachos.de/api"),  # NOTE: base_url="https://dachsgpt.kallimachos.de:11434/v1", # if using ollama port
    api_key=os.getenv("OLLAMA_API_KEY"),
)


#print(llm.invoke("Say hi in 10 words.").content)

print("Starte Anfrage...")
resp = llm.invoke("Say hi in 10 words.")
print("Antwort bekommen")
print(resp.content)
