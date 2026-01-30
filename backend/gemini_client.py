import os
from typing import List, Dict
from google import genai
from dotenv import load_dotenv
from duckduckgo_search import DDGS

load_dotenv()

#using query string and duckduckgo search to get relevant context

def perform_search(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    results : List[Dict[str, str]] = []
    try:
        for result in DDGS.text(query, max_results=max_results):
                # result keys typically include: title, href, body
                if not isinstance(result, dict):
                    continue
                title = result.get('title') or ''
                href = result.get('href') or ''
                body = result.get('body') or ''
                if title and href:
                    results.append({
                        'title': title,
                        'href': href,
                        'body': body,
                    })
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
        return []
# creating client for gemini api
class GeminiClient:
    def __init__(self):
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            self.client = genai.Client(api_key=api_key)
            self.model = 'gemini-2.5-flash'
            self.chat = self.client.chats.create(
                model=self.model,
                config=genai.types.GenerateContentConfig(
                    temperature=1,
                ),
            )
        except Exception as e:
            print(f"Error configuring Gemini API: {e}")
            self.chat = None

    def generate_response(self, user_input: str) -> str:
        """Generate an AI response with optional web search when prefixed.

        To trigger web search, start your message with one of:
        - "search: <query>"
        - "/search <query>"
        Otherwise, the model responds directly using chat history.
        """
        if not self.chat:
            return "AI service is not configured correctly."

        try:
            text = user_input or ""
            lower = text.strip().lower()

            # Search trigger
            search_query = None
            if lower.startswith("search:"):
                search_query = text.split(":", 1)[1].strip()
            elif lower.startswith("/search "):
                search_query = text.split(" ", 1)[1].strip()

            if search_query:
                web_results = perform_search(search_query, max_results=6)
                if not web_results:
                    return "I could not retrieve web results right now. Please try again."

                # Build context with numbered references
                refs_lines = []
                for idx, item in enumerate(web_results, start=1):
                    refs_lines.append(f"[{idx}] {item['title']} — {item['href']}\n{item['body']}")
                refs_block = "\n\n".join(refs_lines)

                system_prompt = (
                    "You are an AI research assistant. Use the provided web search results to answer the user query. "
                    "Synthesize concisely, cite sources inline like [1], [2] where relevant, and include a brief summary."
                )
                composed = (
                    f"<system>\n{system_prompt}\n</system>\n"
                    f"<user_query>\n{search_query}\n</user_query>\n"
                    f"<web_results>\n{refs_block}\n</web_results>"
                )
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=composed
                )
                return response.text

            # Default: normal chat - use the chat instance to maintain history
            response = self.chat.send_message(text)
            return response.text
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm sorry, I encountered an error processing your request."