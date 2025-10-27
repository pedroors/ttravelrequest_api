def processar_resultados_voos(resultados_brutos, origin, destination):
    if 'VoosIda' not in resultados_brutos:
        print(f"Erro: Estrutura 'VoosIda' não encontrada para {origin}->{destination}.")
        return []
    try:
        dados_voos = resultados_brutos.get('VoosIda', {})
        lista_viagens = dados_voos.get('Viagens', [])
        lista_trechos = dados_voos.get('TrechosViagem', [])
        lista_assentos_map = dados_voos.get('assentos', [])
        lista_fares = dados_voos.get('assento', [])

        mapa_viagens = {v['ViagensId']: v for v in lista_viagens}
        mapa_trechos = {t['TrechosViagemId']: t for t in lista_trechos}
        mapa_assentos_trechos = {a['AssentosId']: a['TrechosViagemId'] for a in lista_assentos_map}

        voos_processados = []
        for fare in lista_fares:
            assentos_id = fare.get('AssentosId') 
            trechos_viagem_id = mapa_assentos_trechos.get(assentos_id)
            trecho = mapa_trechos.get(trechos_viagem_id)
            if not trecho: continue
            viagens_id = trecho.get('ViagensId')
            viagem = mapa_viagens.get(viagens_id)
            if not viagem: continue

            voo_info = {
                'Trecho': f"{origin}-{destination}",
                'Companhia': trecho.get('empresaAerea'),
                'Voo': trecho.get('vooCiaOperadora'),
                'Data Saída': trecho.get('dataPartida'),
                'Hora Saída': trecho.get('horaSaida'),
                'Tarifa Acordo': viagem.get('tarifaTipado'),
                'Tarifa Sem Acordo': fare.get('tarifaNet'),
                'Base Tarifária': fare.get('baseFare')
            }
            voos_processados.append(voo_info)
        return voos_processados
    except Exception as e:
        print(f"Erro ao processar dados dos voos: {e}")
        return []

def filtrar_voo_mais_cedo_por_companhia(lista_de_voos):
    def get_tarifa_float(voo):
        tarifa = voo.get('Tarifa Acordo')
        return tarifa if isinstance(tarifa, (int, float)) else float('inf')
    try:
        lista_ordenada = sorted(
            lista_de_voos, 
            key=lambda voo: (
                voo.get('Companhia'), 
                voo.get('Hora Saída'), 
                get_tarifa_float(voo)
            )
        )
    except TypeError:
        print("Erro de tipo ao ordenar 'Hora Saída'.")
        return lista_de_voos 
    voos_filtrados = []
    companhias_adicionadas = set()
    for voo in lista_ordenada:
        companhia = voo.get('Companhia')
        if companhia and companhia not in companhias_adicionadas:
            voos_filtrados.append(voo)
            companhias_adicionadas.add(companhia)
    return voos_filtrados