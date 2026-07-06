from pydantic import BaseModel, Field

class BuscaRequest(BaseModel):
    """Define o corpo da requisição para /buscar-voos."""
    client_id: str = Field(..., description="ID do cliente para logar", examples=["40709"])
    origin: str = Field(..., description="Aeroporto de origem (IATA)", examples=["BSB"])
    destination: str = Field(..., description="Aeroporto de destino (IATA)", examples=["SSA"])
    date: str = Field(..., description="Data da viagem (Formato: YYYY-MM-DD)", examples=["2025-10-30"])

class BuscaFixaRequest(BaseModel):
    """Define o corpo da requisição para /buscar-trechos-fixos com suporte a múltiplos clientes."""
    cliente_indice: int | None = Field(None, description="Índice do cliente (null=padrão, 125=CNT, 183=FLYTOUR)", examples=[None, 55942, 55943])

class VooResponse(BaseModel):
    """Define a estrutura de um voo na resposta final."""
    Trecho: str | None
    Companhia: str | None
    Voo: str | None
    Data_Saida: str | None = Field(None, alias="Data Saída")
    Hora_Saida: str | None = Field(None, alias="Hora Saída")
    Tarifa_Acordo: float | None = Field(None, alias="Tarifa Acordo")
    Tarifa_Sem_Acordo: str | None = Field(None, alias="Tarifa Sem Acordo")
    Base_Tarifaria: str | None = Field(None, alias="Base Tarifária")

    class Config:
        populate_by_name = True