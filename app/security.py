from fastapi import HTTPException, Header
from .config import API_KEY

async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Dependência de segurança: Verifica se o header X-API-Key
    corresponde ao valor definido no .env.
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="X-API-Key inválida ou ausente.")
    return x_api_key