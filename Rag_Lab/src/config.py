from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Labs"
    ocr_languages: str = "rus+eng"
    tesseract_tessdata: str = "C:/Program Files/Tesseract-OCR/tessdata"
    ocr_dpi: int = 180
    ocr_workers: int = 4

    mssql_server: str
    mssql_database: str
    mssql_driver: str = "ODBC Driver 18 for SQL Server"
    mssql_trusted_connection: bool = True
    mssql_trust_server_certificate: bool = True
    mssql_username: str = ""
    mssql_password: str = ""

    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str = "rag_documents"

    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_device: str = "cpu"

    chunk_size: int = 1200
    chunk_overlap: int = 200

    web_crawl_max_pages: int = 60
    web_crawl_max_depth: int = 2

    llm_provider: str = "gemini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_models: str = "gemini-3.8-flash"

    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    groq_models: str = "qwen/qwen3.8-27b"

    llm_max_output_tokens: int = 1200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()