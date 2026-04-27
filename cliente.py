import socket
import hashlib
import random

BUFFER_SIZE = 1024

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.settimeout(3)

def calcular_checksum(data):
    return hashlib.md5(data).hexdigest().encode()

# 1. Parse da entrada conforme requisito do trabalho
entrada = input("Digite a requisição (Ex: @127.0.0.1:5005/arquivo.ext): ")

try:
    # Remove o '@' e separa o IP:Porta do Arquivo
    entrada = entrada.lstrip('@')
    ip_porta, arquivo = entrada.split('/', 1)
    server_ip, server_porta = ip_porta.split(':')
    server_porta = int(server_porta)
except Exception:
    print("Formato inválido! Certifique-se de usar @IP:Porta/nome_do_arquivo.ext")
    exit()

server_address = (server_ip, server_porta)
mensagem_get = f"GET /{arquivo}".encode()

total_pacotes = None

# 2. Proteção contra perda do pacote TOTAL
while True:
    client_socket.sendto(mensagem_get, server_address)
    try:
        resp, _ = client_socket.recvfrom(1024)

        if resp == b"ERRO":
            print("Arquivo não encontrado no servidor.")
            exit()

        if resp.startswith(b"TOTAL"):
            total_pacotes = int(resp.decode().split("|")[1])
            print(f"Total de pacotes esperado: {total_pacotes}")
            break
            
    except socket.timeout:
        print("Timeout ao aguardar resposta do servidor. Reenviando GET...")

dados = {}
recebidos = set()

print("Recebendo dados...")

while True:
    try:
        pacote, _ = client_socket.recvfrom(BUFFER_SIZE)
    except socket.timeout:
        print("Timeout detectado (possível perda do pacote FIM). Analisando perdas...")
        break # Sai do loop para ver o que faltou

    if pacote == b"FIM":
        break
        
    if pacote.startswith(b"TOTAL"):
        continue # Ignora pacotes TOTAL duplicados que possam chegar atrasados

    try:
        # 3. Extrair o seq PRIMEIRO, para poder dizer qual foi perdido
        header, checksum, chunk = pacote.split(b"|", 2)
        seq = int(header.decode())

        # Simulação de perda (20%) - Cumprindo requisito de exibir o número
        if random.random() < 0.2:
            print(f"Pacote {seq} descartado intencionalmente (simulação)")
            continue

        if calcular_checksum(chunk) != checksum:
            print(f"Erro de checksum no pacote {seq}")
            continue

        if seq not in dados:
            dados[seq] = chunk
            recebidos.add(seq)

    except Exception as e:
        pass # Ignora pacotes que não tenham o formato esperado

# Lógica de recuperação de perdas (NACK)
faltando = set(range(total_pacotes)) - recebidos

if faltando:
    print(f"Pacotes perdidos: {len(faltando)}. Iniciando retransmissão...")

while faltando:
    for seq in faltando:
        msg = f"REQ|{seq}"
        client_socket.sendto(msg.encode(), server_address)

        try:
            # Timeout curto para não travar muito tempo esperando um pacote só
            client_socket.settimeout(0.5)
            pacote, _ = client_socket.recvfrom(BUFFER_SIZE)
            
            header, checksum, chunk = pacote.split(b"|", 2)
            seq_recv = int(header.decode())

            if calcular_checksum(chunk) == checksum:
                if seq_recv not in dados:
                    dados[seq_recv] = chunk
                    recebidos.add(seq_recv)
                    print(f"Pacote {seq_recv} recuperado!")
                    
        except socket.timeout:
            pass # Se der timeout na retransmissão, o while garante que pediremos de novo
        except Exception:
            pass 

    faltando = set(range(total_pacotes)) - recebidos

client_socket.settimeout(3) # Volta o timeout ao normal

# Salvar arquivo
print("Verificação concluída. Montando arquivo final...")
with open("recebido_" + arquivo, "wb") as f:
    for i in sorted(dados.keys()):
        f.write(dados[i])

client_socket.sendto(b"FIM_OK", server_address)
print(f"Arquivo '{arquivo}' salvo com sucesso!")