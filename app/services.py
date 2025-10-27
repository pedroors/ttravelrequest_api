import requests
import concurrent.futures
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import List

# Importa as constantes e limites
from .config import (
    BASE_HEADERS, LOGIN_USER, LOGIN_PASS, FIXED_CLIENT_ID,
    TRECHOS_FIXOS, CONCURRENCY_LIMIT, MAX_CONCURRENT_JOBS
)

# Importa as funções de lógica
from .scraping import (
    perform_login_com_mfa, select_client, execute_flight_search
)
from .processing import (
    processar_resultados_voos, filtrar_voo_mais_cedo_por_companhia
)
# Importa os modelos de dados
from .models import VooResponse


def run_single_search(client_id: str, origin: str, destination: str, date: str) -> List[VooResponse]:
    """
    Função "trabalhadora" que executa o fluxo completo de scraping para um trecho.
    É isolada e levanta exceções em caso de falha.
    """
    
    # Cria uma sessão NOVA E ISOLADA para esta execução.
    with requests.Session() as session:
        session.headers.update(BASE_HEADERS)
        try:
            # ETAPAS 1-3: Login, 2FA, Frame
            response_login = perform_login_com_mfa(session, LOGIN_USER, LOGIN_PASS)
            
            # ETAPA 4: Seleção de Cliente
            response_select = select_client(session, response_login, client_id)
            
            # ETAPA 5: Busca de Voo
            resultados_brutos = execute_flight_search(
                session, response_select, origin, destination, date
            )

            # ETAPA 6: Processamento
            lista_de_voos_limpa = processar_resultados_voos(resultados_brutos, origin, destination)
            
            # ETAPA 7: Filtragem Final
            voos_finais_filtrados = filtrar_voo_mais_cedo_por_companhia(lista_de_voos_limpa)

            return voos_finais_filtrados

        except HTTPException:
            raise # Repassa o erro
        except Exception as e:
            print(f"Erro inesperado no fluxo {origin}->{destination}: {e}")
            raise HTTPException(status_code=500, detail=f"Erro interno inesperado no fluxo: {str(e)}")


def run_fixed_search() -> List[VooResponse]:
    """
    Busca 5 trechos pré-determinados em paralelo.
    Faz o LOGIN UMA VEZ e depois busca tokens novos para cada busca paralela.
    """
    
    data_busca = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    print(f"Iniciando busca de trechos fixos (Login Único + Tokens Novos) para a data: {data_busca}")
    
    resultados_por_trecho = {}

    # Cria uma sessão única que será compartilhada pelas threads
    with requests.Session() as session:
        session.headers.update(BASE_HEADERS)
        
        try:
            # --- ETAPA DE LOGIN (EXECUTADA SÓ UMA VEZ) ---
            print("[Fluxo Fixo] Executando Login Único...")
            response_login = perform_login_com_mfa(session, LOGIN_USER, LOGIN_PASS)
            response_select = select_client(session, response_login, FIXED_CLIENT_ID)
            
            pagina_busca_url = response_select.url
            print(f"[Fluxo Fixo] Login Único bem-sucedido. Página de busca: {pagina_busca_url}")

        except Exception as e:
            print(f"[Fluxo Fixo] Falha no processo de Login Único: {e}")
            raise HTTPException(status_code=503, detail=f"Falha ao estabelecer sessão de login única: {e}")

        
        # --- FUNÇÃO TRABALHADORA INTERNA (para paralelização) ---
        def search_route_worker(origin, dest, date):
            with CONCURRENCY_LIMIT: # Controla a concorrência
                try:
                    print(f"[{origin}->{dest}] Buscando tokens novos em {pagina_busca_url}...")
                    fresh_response_select = session.get(pagina_busca_url)
                    fresh_response_select.raise_for_status()

                    resultados_brutos = execute_flight_search(
                        session, fresh_response_select, origin, dest, date
                    )
                    lista_limpa = processar_resultados_voos(resultados_brutos, origin, dest)
                    voos_filtrados = filtrar_voo_mais_cedo_por_companhia(lista_limpa)
                    
                    if voos_filtrados:
                        print(f"Sucesso no trecho {origin}->{dest}. {len(voos_filtrados)} voos encontrados.")
                    else:
                        print(f"Trecho {origin}->{dest} não retornou voos.")
                    
                    return (origin, dest), voos_filtrados
                
                except Exception as e:
                    print(f"ERRO INESPERADO no worker {origin}->{dest}: {e}")
                    return (origin, dest), None

        # --- FIM DA FUNÇÃO TRABALHADORA ---

        # --- ETAPA DE BUSCA (EXECUTADA EM PARALELO) ---
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as executor:
            futures = [
                executor.submit(search_route_worker, origin, dest, data_busca)
                for (origin, dest) in TRECHOS_FIXOS
            ]
            
            for future in concurrent.futures.as_completed(futures):
                route_key, voos_do_trecho = future.result()
                if voos_do_trecho:
                    resultados_por_trecho[route_key] = voos_do_trecho

    # --- ETAPA DE ORDENAÇÃO (Final) ---
    print("Busca de trechos fixos concluída. Ordenando resultados...")
    resultados_finais_ordenados = []
    
    for trecho_key in TRECHOS_FIXOS:
        voos = resultados_por_trecho.get(trecho_key)
        if voos:
            resultados_finais_ordenados.extend(voos)
            
    return resultados_finais_ordenados