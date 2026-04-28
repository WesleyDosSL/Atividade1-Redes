import socket
import os
import hashlib
import time

HOST = '0.0.0.0' # Escuta em todas as interfaces de rede disponíveis
PORT = 5005 # Porta para o servidor UDP
BUFFER_SIZE = 1024 # Tamanho do buffer para receber mensagens (pode ser ajustado conforme necessário)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Cria um socket UDP
server_socket.bind((HOST, PORT)) # Associa o socket ao endereço e porta especificados

print(f"Servidor UDP aguardando na porta {PORT}...")

def calcular_checksum(data): # Função para calcular o checksum usando MD5
    return hashlib.md5(data).hexdigest().encode() # MD5 é rápido e suficiente para detectar erros de transmissão, mesmo que não seja criptograficamente seguro.

while True:
    data, addr = server_socket.recvfrom(1024) # Recebe uma mensagem do cliente
    msg = data.decode() # Decodifica a mensagem recebida para string

    if msg.startswith("GET"): # Verifica se a mensagem é um comando GET
        nome_arquivo = msg.split(" ")[1].replace("/", "") # Pega o nome do arquivo solicitado

        if not os.path.exists(nome_arquivo): # Verifica se o arquivo existe
            server_socket.sendto(b"ERRO", addr) # Envia uma mensagem de erro para o cliente se o arquivo não existir
            continue

        pacotes = {}

        with open(nome_arquivo, "rb") as f: # Abre o arquivo em modo binário para leitura
            seq = 0 # Número de sequência para cada pacote, começando em 0
            while True:
                chunk = f.read(800) # O arquivo é lido em blocos(chunks). Foram escolhidos 800 bytes para que, somado ao cabeçalho e ao MD5, o pacote final fique abaixo de 1500 bytes (MTU padrão da Ethernet), evitando fragmentação na camada IP.
                if not chunk: # Se não houver mais dados para ler
                    break

                checksum = calcular_checksum(chunk) # Calcula o checksum do chunk usando a função definida anteriormente
                pacote = f"{seq}|".encode() + checksum + b"|" + chunk # O pacote é construído com o formato: SEQ|CHECKSUM|DADOS. O número de sequência é convertido para string e codificado em bytes, seguido pelo checksum e pelos dados do chunk.

                pacotes[seq] = pacote # Armazena o pacote em um dicionário usando o número de sequência como chave. Isso facilita a retransmissão de pacotes específicos caso o cliente solicite.
                seq += 1 

        total_pacotes = len(pacotes) # O total de pacotes é calculado como o número de entradas no dicionário de pacotes. Isso é importante para que o cliente saiba quantos pacotes esperar e possa detectar se algum pacote está faltando.
        server_socket.sendto(f"TOTAL|{total_pacotes}".encode(), addr) # Envia uma mensagem para o cliente informando o total de pacotes que serão enviados.

        print(f"Iniciando envio de {total_pacotes} pacotes...")
        
        for seq in sorted(pacotes.keys()): # Envia os pacotes em ordem de sequência. O método sorted() é usado para garantir que os pacotes sejam enviados na ordem correta, mesmo que o dicionário de pacotes não esteja ordenado.
            server_socket.sendto(pacotes[seq], addr) # Envia o pacote para o cliente usando o método sendto() do socket. O pacote é recuperado do dicionário de pacotes usando o número de sequência como chave.
            time.sleep(0.005) # Delay para evitar estouro de buffer

        server_socket.sendto(b"FIM", addr)

        # Modo retransmissão (com timeout)
        server_socket.settimeout(5) # Define um timeout de 5 segundos para a sessão de retransmissão. Isso significa que o servidor aguardará por mensagens do cliente por até 5 segundos antes de considerar a sessão como encerrada. O timeout é importante para evitar que o servidor fique preso.

        while True:
            try:
                req, addr = server_socket.recvfrom(1024)

                if req.startswith(b"REQ"): # Se o cliente solicitar um pacote específico (REQ|SEQ), verificamos se o pacote existe e o reenviamos. Isso é útil para lidar com pacotes perdidos durante a transmissão.
                    seq_req = int(req.decode().split("|")[1]) # O número de sequência solicitado é extraído da mensagem recebida. A mensagem é decodificada para string, dividida pelo caractere "|" e o segundo elemento (índice 1) é convertido para inteiro para obter o número de sequência solicitado.
                    if seq_req in pacotes:
                        #print(f"Reenviando pacote {seq_req}") # Comentado para não poluir a tela
                        server_socket.sendto(pacotes[seq_req], addr)
                
                elif req.startswith(b"GET"): # Se o cliente solicitar o total de pacotes novamente (GET TOTAL), reenviamos a informação do total. Isso é útil para o cliente verificar se perdeu a mensagem inicial que informava o total de pacotes ou para confirmar o total caso haja dúvidas.
                    server_socket.sendto(f"TOTAL|{total_pacotes}".encode(), addr)

                elif req == b"FIM_OK": # Se o cliente confirmar que recebeu todos os pacotes (FIM_OK), encerramos a sessão de retransmissão. Isso indica que a transferência foi concluída com sucesso e o servidor pode voltar a aguardar por novos clientes.
                    print("Transferência concluída com sucesso.\n---")
                    break

            except socket.timeout: # Se o timeout for atingido, consideramos a sessão encerrada e voltamos a aguardar por novos clientes.
                print("Timeout da sessão. Aguardando novos clientes...\n---")
                break

        server_socket.settimeout(None) # Remove o timeout para a próxima sessão. Isso é importante para garantir que o servidor volte a funcionar normalmente para o próximo cliente, sem um timeout indesejado.