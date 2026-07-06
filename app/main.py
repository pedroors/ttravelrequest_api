import uvicorn
from fastapi import FastAPI, Depends
from typing import List

# Importa os modelos, segurança e serviços dos outros arquivos
from .models import BuscaRequest, BuscaFixaRequest, VooResponse
from .security import get_api_key
from .services import run_single_search, run_fixed_search
from .config import CONCURRENCY_LIMIT # Importa o semaphore

# Inicializa o aplicativo FastAPI
app = FastAPI(
    title="Busca Voos API",
    description="API para realizar scraping de voos em portal B2B.",
    version="1.0.0"
)

@app.post("/buscar-voos",
          response_model=List[VooResponse],
          dependencies=[Depends(get_api_key)])
def api_buscar_voos(request: BuscaRequest):
    """
    Endpoint principal para buscar voos (um trecho por vez).
    Recebe parâmetros de busca (requer X-API-Key) e executa o scraping.
    """
    
    # O Semaphore protege este endpoint para rodar um de cada vez
    # (ou quantos o CONCURRENCY_LIMIT permitir)
    with CONCURRENCY_LIMIT:
        return run_single_search(
            client_id=request.client_id,
            origin=request.origin,
            destination=request.destination,
            date=request.date
        )

@app.post("/buscar-trechos-fixos",
          response_model=List[VooResponse],
          dependencies=[Depends(get_api_key)])
def api_buscar_trechos_fixos(request: BuscaFixaRequest):
    """
    Busca 5 trechos pré-determinados em paralelo.
    A data da busca é sempre D+7 (7 dias a partir de hoje).
    Os resultados são retornados na ordem pré-definida.

    Opcionalmente, aceita um 'cliente_indice' para buscar dados de clientes diferentes:
    - None (padrão): Cliente ATUAL (40709)
    - 55942: Cliente CNT
    - 55943: Cliente FLYTOUR
    """
    # A lógica de concorrência já está dentro de 'run_fixed_search'
    return run_fixed_search(cliente_indice=request.cliente_indice)


@app.get("/", include_in_schema=False)
def root():
    """Endpoint raiz para verificação de status."""
    return {"status": "API de Busca de Voos está online."}

# --- Para rodar localmente ---
if __name__ == "__main__":
    print("Iniciando servidor localmente em http://127.0.0.1:8000")
    print("Acesse http://127.0.0.1:8000/docs para testar.")
    # Nota: O comando mudou para "app.main:app"
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)