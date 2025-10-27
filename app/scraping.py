import requests
import pyotp
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from fastapi import HTTPException
from typing import Dict, Any

from .config import (
    MFA_SECRET_KEY, LOGIN_PROCESS_URL, FRAME_URL,
    USERNAME_FIELD, PASSWORD_FIELD, LOGIN_BUTTON_FIELD,
    MFA_FIELD, MFA_BUTTON_FIELD, CLIENT_SELECT_PAGE_IDENTIFIER,
    FLIGHT_SEARCH_PAGE_IDENTIFIER, API_SEARCH_URL
)

def _extract_aspnet_fields(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    viewstate = soup.find('input', {'id': '__VIEWSTATE'})
    generator = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
    validation = soup.find('input', {'id': '__EVENTVALIDATION'})
    if not all([viewstate, generator, validation]):
        print("ERRO: Não foi possível encontrar os campos ASP.NET (VIEWSTATE, etc.).")
        return None
    return {
        '__VIEWSTATE': viewstate['value'],
        '__VIEWSTATEGENERATOR': generator['value'],
        '__EVENTVALIDATION': validation['value'],
    }

def _extract_frame_fields(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    aspnet_fields = _extract_aspnet_fields(html_text)
    if not aspnet_fields: return None
    hid_info = soup.find('input', {'name': 'hidInfo'})
    btn_continua = soup.find('input', {'name': 'btnContinua'})
    if not hid_info or not btn_continua:
        print("ERRO: Não foi possível encontrar 'hidInfo' ou 'btnContinua'.")
        return None
    aspnet_fields['hidInfo'] = hid_info['value']
    aspnet_fields['btnContinua'] = btn_continua.get('value', '.')
    return aspnet_fields

def perform_login_com_mfa(session, username, password):
    """Etapas 1-3: Login -> 2FA -> Frame."""
    try:
        print(f"[{username}] Acessando {LOGIN_PROCESS_URL} para obter campos...")
        response_get = session.get(LOGIN_PROCESS_URL)
        response_get.raise_for_status()
        aspnet_fields_1 = _extract_aspnet_fields(response_get.text)
        if not aspnet_fields_1: 
            raise ValueError("Campos ASP.NET (Etapa 1) não encontrados.")
    except Exception as e:
        print(f"Erro no GET Inicial: {e}")
        raise HTTPException(status_code=503, detail=f"Erro no GET Inicial: {e}")

    payload_step1 = {
        USERNAME_FIELD: username,
        PASSWORD_FIELD: password,
        LOGIN_BUTTON_FIELD: 'Entrar',
        '__EVENTTARGET': LOGIN_BUTTON_FIELD,
        '__EVENTARGUMENT': '',
    }
    payload_step1.update(aspnet_fields_1)
    
    try:
        print(f"[{username}] Enviando Passo 1 (Usuário/Senha)...")
        response_step1 = session.post(LOGIN_PROCESS_URL, data=payload_step1)
        response_step1.raise_for_status()
    except Exception as e:
        print(f"Erro no Passo 1 (Usuário/Senha): {e}")
        raise HTTPException(status_code=401, detail="Falha no Passo 1 (Usuário/Senha). Credenciais inválidas?")

    try:
        totp = pyotp.TOTP(MFA_SECRET_KEY)
        mfa_code = totp.now()
        print(f"[{username}] Gerando código 2FA: {mfa_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar código TOTP: {e}")
        
    aspnet_fields_2 = _extract_aspnet_fields(response_step1.text)
    if not aspnet_fields_2:
        raise HTTPException(status_code=503, detail="Campos ASP.NET (Etapa 2) não encontrados.")

    payload_step2 = {
        MFA_FIELD: mfa_code,
        MFA_BUTTON_FIELD: 'Entrar',
        '__EVENTTARGET': MFA_BUTTON_FIELD, 
        '__EVENTARGUMENT': '',
    }
    payload_step2.update(aspnet_fields_2)
    
    try:
        print(f"[{username}] Enviando Passo 2 (2FA)...")
        response_step2 = session.post(LOGIN_PROCESS_URL, data=payload_step2, allow_redirects=True) 
        response_step2.raise_for_status()
        if "frmnovoframeui.aspx" not in response_step2.url:
            raise ValueError(f"Resposta inesperada. URL: {response_step2.url}")
        print(f"[{username}] Passo 2 (2FA) OK. Redirecionado para o frame.")
    except Exception as e:
        print(f"Erro no Passo 2 (2FA): {e}")
        raise HTTPException(status_code=401, detail=f"Falha no Passo 2 (2FA). Chave MFA correta? {e}")

    frame_fields = _extract_frame_fields(response_step2.text)
    if not frame_fields:
        raise HTTPException(status_code=503, detail="Campos do Frame (Etapa 3) não encontrados.")

    payload_step3 = {
        'hidInfo': frame_fields['hidInfo'],
        'btnContinua': frame_fields['btnContinua'],
        '__VIEWSTATE': frame_fields['__VIEWSTATE'],
        '__VIEWSTATEGENERATOR': frame_fields['__VIEWSTATEGENERATOR'],
        '__EVENTVALIDATION': frame_fields['__EVENTVALIDATION'],
    }
    
    try:
        print(f"[{username}] Enviando Passo 3 (Frame Intermediário)...")
        response_step3 = session.post(FRAME_URL, data=payload_step3, allow_redirects=True)
        response_step3.raise_for_status()
        if CLIENT_SELECT_PAGE_IDENTIFIER not in response_step3.url:
            raise ValueError(f"Redirecionamento inesperado. URL: {response_step3.url}")
        
        print(f"[{username}] Autenticação OK. Na página de seleção de cliente.")
        return response_step3
            
    except Exception as e:
        print(f"Erro no Passo 3 (Frame): {e}")
        raise HTTPException(status_code=503, detail=f"Falha no Passo 3 (Frame): {e}")

def select_client(session, response_login, client_id):
    html_pagina_cliente = response_login.text
    pagina_cliente_url = response_login.url 
    soup = BeautifulSoup(html_pagina_cliente, 'html.parser')
    
    form_data = {}
    inputs = soup.find_all('input')
    for input_tag in inputs:
        name = input_tag.get('name')
        if name: form_data[name] = input_tag.get('value', '')
            
    selects = soup.find_all('select')
    for select_tag in selects:
        name = select_tag.get('name')
        if name:
            selected_option = select_tag.find('option', {'selected': True})
            form_data[name] = selected_option.get('value', '') if selected_option else \
                              (select_tag.find('option').get('value', '') if select_tag.find('option') else '')

    form_data['ctl00$ContentPlaceHolder1$dpdEmpresa'] = client_id 
    form_data['ctl00$ContentPlaceHolder1$btnAcessar'] = 'Logar'
    form_data['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$btnAcessar'
    form_data.pop('ctl00$btnCancelar', None)

    try:
        print(f"[{session.cookies.get('svcCookie_usr')}] Enviando Passo 4 (Selecionando Cliente {client_id})...")
        response = session.post(pagina_cliente_url, data=form_data, allow_redirects=True)
        response.raise_for_status()

        if FLIGHT_SEARCH_PAGE_IDENTIFIER in response.url:
            print(f"[{session.cookies.get('svcCookie_usr')}] Passo 4 (Seleção de Cliente) OK. Acesso final concedido.")
            return response
        else:
            raise ValueError(f"Redirecionamento inesperado. URL: {response.url}")

    except Exception as e:
        print(f"Erro no Passo 4 (Seleção de Cliente): {e}")
        raise HTTPException(status_code=503, detail=f"Falha no Passo 4 (Seleção de Cliente): {e}")

def execute_flight_search(session: requests.Session, 
                            response_select: requests.Response, 
                            origin: str, 
                            destination: str, 
                            date: str) -> dict:
    """
    Etapa 5: Executa a chamada final da API de busca de voos.
    
    Esta função "raspa" os tokens de busca (Chave, Acesso) da página
    de busca de voos, monta o payload JSON complexo e faz o POST final
    para a API /BuscarDisponibilidade.
    
    Args:
        session: A sessão 'requests' já autenticada (após o Passo 4).
        response_select: O objeto de resposta do Passo 4, que contém
                         o HTML da página de busca com os tokens.
        origin: O código IATA de origem (ex: "BSB").
        destination: O código IATA de destino (ex: "SSA").
        date: A data da busca no formato "YYYY-MM-DD".

    Raises:
        HTTPException(503): Se os tokens de busca (hidDados) não forem encontrados.
        HTTPException(400): Se o formato da data for inválido.
        HTTPException(500): Se a API da TTravel falhar.

    Returns:
        dict: O JSON bruto da resposta da API de voos.
    """
    html_pagina_busca = response_select.text
    pagina_busca_url = response_select.url
    soup = BeautifulSoup(html_pagina_busca, 'html.parser')
    
    # Seletores para o <input> que contém o JSON com os tokens de busca.
    # O site usa 'name' em alguns ambientes e 'id' em outros; tentamos os dois.
    SELETOR_ID_INPUT_JSON = 'hidDados'
    SELETOR_NAME_INPUT_JSON = 'ctl00$ContentPlaceHolder1$hidDados'
    
    try:
        json_input = soup.find('input', {'id': SELETOR_ID_INPUT_JSON})
        if not json_input:
            json_input = soup.find('input', {'name': SELETOR_NAME_INPUT_JSON})
        if not json_input:
            raise AttributeError("Input JSON 'hidDados' não encontrado.")
            
        json_string = json_input.get('value')
        data = json.loads(json_string)
        api_token = data.get('Chave')
        chave_busca = data.get('Acesso')
        if not api_token or not chave_busca:
            raise ValueError("JSON 'Chave' ou 'Acesso' não encontrado.")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Falha ao processar JSON de busca: {e}")

    try:
        data_obj = datetime.strptime(date, '%Y-%m-%d')
        data_formatada = data_obj.strftime('%d/%m/%Y')
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD.")

    payload = {
        "Token": api_token,
        "BuscarDisponibilidade": {
            "OrigemIata": origin.lower(),
            "DestinoIata": destination.lower(),
            "DataIda": data_formatada,
            "QuantidadePassageirosAdultos": "1",
            "QuantidadePassageirosCriancas": "0",
            "QuantidadePassageirosBebes": "0",
            "ApenasvoosDiretos": True,
            "ApenasTarifasComBagagem": False,
            "ApenasTarifasMaisBaratas": True,
            "ChaveBuscaSeparada": chave_busca,
            "RemoverVoosRoundTrip": False,
            "AdicionandoTrechos": False,
            "AzulB2BToken": None,
            "CiasSelecionadasWooba": [],
            "Sistemas": ["GOLGWS", "AZUL", "LATAM"],
            "MultiplosDestinos": False,
            "Indice": 0
        }
    }

    api_headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'pt-BR,pt;q=0.9',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://www.ttravel.com.br',
        'priority': 'u=1, i',
        # O 'Referer' é o header mais crítico. Sem ele, a API retorna 500.
        'referer': pagina_busca_url,
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        # O 'X-Requested-With' simula uma chamada AJAX (JS) do navegador.
        'x-requested-with': 'XMLHttpRequest'
    }

    try:
        print(f"[{session.cookies.get('svcCookie_usr')}] Enviando busca de voos {origin}->{destination} para {API_SEARCH_URL}...")
        response = session.post(API_SEARCH_URL, headers=api_headers, json=payload)
        response.raise_for_status() 
        
        # --- VERIFICAÇÃO DE ROBUSTEZ ---
        data = response.json()
        if "VoosIda" not in data:
            print(f"[{origin}->{destination}] API retornou 200 OK mas sem 'VoosIda'. Resposta: {data}")
            return {}
        
        print(f"[{session.cookies.get('svcCookie_usr')}] Busca {origin}->{destination} bem-sucedida.")
        return data

    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar API de busca de voos: {e}")
        if 'response' in locals() and response:
            print(f"Resposta do servidor: {response.text}")
        raise HTTPException(status_code=500, detail=f"Erro 500 da API de voos: {e}")