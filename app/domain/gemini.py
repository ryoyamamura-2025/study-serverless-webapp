import os
from google import genai
from google.genai import types

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# Geminiクライアント初期化
_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=LOCATION,
)

class geminiApiCaller():
    """
    Gemini API を呼び出すクラス。セーフティセッティング等は共通化する
    """
    def __init__(self, model_name, thinking_budget, response_schema=None, input_media=None):
        self.model_name = model_name
        self.thinking_budget = thinking_budget
        self.response_schema = response_schema
        if input_media:
            self.input_media = self.set_media(input_media)
        else:
            self.input_media = None
        self.media_resolution = input_media.get("resolution", "") if input_media else None

    def set_media(self, input_media):
        """
        example:
        input_media = {
            "blob_name": "xxxx.mp4",
            "start_offset": "0s",
            "end_offset": "1000s"
        }
        """
        blob_name = input_media["blob_name"]
        so, eo = input_media["start_offset"], input_media["end_offset"]

        # 動画のinput
        gs_url = f"gs://{BUCKET_NAME}/{blob_name}"
        _, ext = os.path.splitext(blob_name)
        ext = ext.lower()
               
        if so and eo:
            input_video = types.Part(
                file_data = types.FileData(file_uri=gs_url, mime_type = f"video/{ext}"),
                video_metadata = types.VideoMetadata(
                            start_offset=so,
                            end_offset=eo
                )
            )
            return input_video
        else:
            input_video = types.Part(
                file_data = types.FileData(file_uri=gs_url, mime_type = f"video/{ext}"),
            )
            return input_video

    def set_generate_content_config(self):
        base = dict(
            temperature=0, top_p=1, seed=0, max_output_tokens=65535,
            response_modalities=["TEXT"],
            safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
                )
            ],
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget),  # SDKに合わせる
        )
        if self.response_schema:
            base.update(response_mime_type="application/json", response_schema=self.response_schema)
        if self.media_resolution:
            base.update(mediaResolution="MEDIA_RESOLUTION_LOW")
        return types.GenerateContentConfig(**base)

    def text2text(self, prompt):
        print("model: ", self.model_name)
        print("thinking budget: ", self.thinking_budget)
        input_prompt = types.Part.from_text(text=prompt.strip())
        contents = [
            types.Content(
                role = "user",
                parts = [
                    input_prompt
                ]
            ),
        ]

        self.generate_content_config = self.set_generate_content_config()

        response = _client.models.generate_content(
            model = self.model_name,
            contents = contents,
            config = self.generate_content_config
        )            
        
        if self.response_schema:
            return response.parsed, response
        else:
            return response.text, response

    async def atext2text(self, prompt):
        print("model: ", self.model_name)
        print("thinking budget: ", self.thinking_budget)
        input_prompt = types.Part.from_text(text=prompt.strip())
        contents = [
            types.Content(
                role = "user",
                parts = [
                    input_prompt
                ]
            ),
        ]

        self.generate_content_config = self.set_generate_content_config()

        response = await _client.aio.models.generate_content(
            model = self.model_name,
            contents = contents,
            config = self.generate_content_config
        )            
        
        if self.response_schema:
            return response.parsed, response
        else:
            return response.text, response

    def video2text(self, prompt):
        if self.input_media:
            print("model: ", self.model_name)
            print("thinking budget: ", self.thinking_budget)
            input_prompt = types.Part.from_text(text=prompt.strip())
            contents = [
                types.Content(
                    role = "user",
                    parts = [
                        self.input_media,
                        input_prompt
                    ]
                ),
            ]

            self.generate_content_config = self.set_generate_content_config()

            response = _client.models.generate_content(
                model = self.model_name,
                contents = contents,
                config = self.generate_content_config
            )

            if self.response_schema:
                return response.parsed, response
            else:
                return response.text, response
        else:
            return "input media is not set", None

    async def avideo2text(self, prompt):
        if self.input_media:
            print("model: ", self.model_name)
            print("thinking budget: ", self.thinking_budget)
            input_prompt = types.Part.from_text(text=prompt.strip())
            contents = [
                types.Content(
                    role = "user",
                    parts = [
                        self.input_media,
                        input_prompt
                    ]
                ),
            ]

            self.generate_content_config = self.set_generate_content_config()

            response = await _client.aio.models.generate_content(
                model = self.model_name,
                contents = contents,
                config = self.generate_content_config
            )
                        
            if self.response_schema:
                return response.parsed, response
            else:
                return response.text, response        
        else:
            return "input media is not set", None
        
class geminiApiCallerWithTool(geminiApiCaller):
    """
    Search Tool 付きで Gemini API を呼び出すクラス。geminiApiCallerを継承
    """
    def __init__(self, model_name, thinking_budget, response_schema=None, input_media=None):
        super().__init__(
            model_name = model_name, 
            thinking_budget=thinking_budget, 
            response_schema=response_schema, 
            input_media=input_media
        )

    # オーバーライド
    def set_generate_content_config(self):
        # Define the grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        base = dict(
            temperature=0, top_p=1, seed=0, max_output_tokens=65535,
            response_modalities=["TEXT"],
            safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
                )
            ],
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget),  # SDKに合わせる
            tools=[grounding_tool]
        )
        if self.response_schema:
            base.update(response_mime_type="application/json", response_schema=self.response_schema)
        if self.media_resolution:
            base.update(mediaResolution="MEDIA_RESOLUTION_LOW")
        return types.GenerateContentConfig(**base)

async def simple_chat(prompt):

    api_caller = geminiApiCaller(
        model_name = "gemini-2.5-flash-lite",
        thinking_budget = 0
    )

    response_text, response = api_caller.atext2text(prompt)
    return response_text, response