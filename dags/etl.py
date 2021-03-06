"""
Created on Mon Jun 14 20:00:00 2022

@author: Pedro Simas Neto
"""
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine
from datetime import datetime
import pandas as pd
import utils as ut
import requests


class Jobs:

    def __init__(self, url, header, database):
        self.url_job = url
        self.header_job = header
        self.database_job = database

    def st_importar_condominios(self, table: str):
        response = requests.request("GET", self.url_job, headers=self.header_job)

        # Transformado o retorno da API em Dataframe Pandas.
        df_condominio = pd.DataFrame(response.json())

        # Obtendo a conexão cadastrada do PostgreSQL (Datalake) no Airflow.
        connection = ut.obter_conn_uri(self.database_job)

        print(f"Inserindo dados na tabela {table}")
        engine = create_engine(f'postgresql://{connection["user"]}:{connection["password"]}@{connection["host"]}:{connection["port"]}/{connection["schema"]}')
        df_condominio.to_sql(table, engine, if_exists="replace", index=False)

    def st_relatorio_receita_despesa(self, table: str, data_execucao: str, intervalo_execucao: int):
        # Obtendo a data de execução do Scheduler e diminuindo pelos numeros de meses parametrizados no Airflow.

        # Transformando a string em data
        data_execucao = datetime.strptime(data_execucao, "%Y-%m-%d")
        # Dimunuindo os números de meses para reprocessamento.
        data_inicio = data_execucao - relativedelta(months=intervalo_execucao)
        data_fim = data_execucao
        # Criando range de datas para o laço de repetição.
        data = pd.date_range(data_inicio, data_fim, freq="D")
        print(f"Reprocessando entre os dias {data_inicio.strftime('%Y-%m-%d')} a {data_fim.strftime('%Y-%m-%d')}")

        # Query que busca no banco de dados os condomínios cadastrados para buscar na API.
        dado_condominio = ut.read_pgsql(self.database_job, "select array_agg(distinct id_condominio) from dim_condominio;")[0][0]
        print(f"Será processados {len(dado_condominio)} condomínios")

        # Obtendo a conexão cadastrada do PostgreSQL (Datalake) no Airflow.
        connection = ut.obter_conn_uri(self.database_job)
        engine = create_engine(f'postgresql://{connection["user"]}:{connection["password"]}@{connection["host"]}:{connection["port"]}/{connection["schema"]}')
        # Truncate na staging
        ut.truncate_pgsql(self.database_job, table=table)

        try:
            for d2 in dado_condominio:
                print("Condomínio:", d2)
                # Criado lista que será preenchida com os dados da API por condomínio
                dado_list = list()
                for d1 in data:
                    # Alterando o formato da data por questão da API.
                    data_periodo = d1.strftime("%d/%m/%Y")
                    # Criando a URL para buscar na API por condomínio e por dia.
                    url_completa = self.url_job + f"idCondominio={d2}&dtInicio={data_periodo}&dtFim={data_periodo}&agrupadoPorMes=0"
                    response = requests.request("GET", url_completa, headers=self.header_job)
                    if response.status_code and response.status_code == 200:
                        response_json = response.json()
                        if response_json:
                            for item in response_json[0]["itens"]:
                                # Inserindo a data nos dados
                                item[0]["data"] = d1.strftime("%Y-%m-%d")
                                # Inserindo o numero do condomínio
                                item[0]["id_condominio"] = d2
                                # Adicionado o dado na lista.
                                dado_list.extend(item)
                print(f"Obteve {len(dado_list)} do condomínio {d2}")
                if len(dado_list) != 0:
                    # Transformado a lista em Dataframe Pandas.
                    df_relatorio_receita_despesa = pd.DataFrame(dado_list)
                    # Inserindo na tabela staging
                    df_relatorio_receita_despesa.to_sql(table, engine, if_exists='append', index=False)
        except Exception as ex:
            raise print(f"ERRO! Motivo: {ex}")
