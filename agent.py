"""
@uthor :kamlesh gujrati
@date: 01/07/2025
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json

class Files:
    def loadfile(self, filename):
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    def savefile(self, filename, data):
        with open(filename, "w") as file:
            json.dump(data, file)

class googlebot(Files):
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.ai_model = self.create_model()
        self.bot = self.prepare_chat()

    def create_model(self):
        """
      This function configures and creates the ai model.
      """
        genai.configure(api_key=self.api_key)

        generation_config = {
            "temperature":1,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens" : 8192,
        }

        safety_settings = [

        ]
        instructions="instructions_to_agent.txt"
        with open(instructions, "r", encoding="utf-8") as file:
            instruction = file.read()

        system_instruction = instruction

        for agent_name in ["gemini-2.0-flash-lite", "gemini-1.5-pro-001"]:

            try:
                model = genai.GenerativeModel(model_name=agent_name,
                                              generation_config = generation_config,
                                              system_instruction=system_instruction,
                                              safety_settings=safety_settings)
                break
            except Exception as e:
                print(f"Error creating model {agent_name}: {e}")
                continue


        return model


    def prepare_chat(self):
        chat_history =self.loadfile("chat_history.json")
        # starting chat...
        ai_bot= self.ai_model.start_chat(history=chat_history)
        return ai_bot

    # pases text and return the response from the bot

    def get_message_from_bot(self, chat_text):
        print(chat_text)
        response = self.bot.send_message(chat_text)
        # Update chat history with the new interaction
        chat_history = self.loadfile("chat_history.json")
        chat_history.append({"role": "user", "parts": [{"text": chat_text}]})
        clean_json_str = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json_str)
        chat_history.append({"role": "model", "parts": [{"text": response.text}]})
        self.savefile("chat_history.json", chat_history)

        print(data)

        return data
