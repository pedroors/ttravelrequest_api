# API de Scraping de Voos TTravel

API em Python (FastAPI) para automatizar a busca de voos em portal B2B, lidando com login multi-etapa (ASP.NET) e 2FA (TOTP).

## Visão Geral

Esta API abstrai um fluxo complexo de scraping (Login -> 2FA -> Seleção de Cliente -> Busca de Token -> Busca de API) em endpoints simples e seguros.

## Instalação Local

1.  Clone o repositório:
    ```bash
    git clone [URL_DO_SEU_REPO]
    cd ttravelrequest_api
    ```
2.  Crie um ambiente virtual e ative-o:
    ```bash
    python -m venv venv
    source venv/bin/activate  # (ou .\\venv\\Scripts\\activate no Windows)
    ```
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure seus segredos:
    ```bash
    cp .env.example .env
    ```
5.  Edite o arquivo `.env` com suas credenciais reais.

## Executando a API

```bash
python -m uvicorn app.main:app --reload