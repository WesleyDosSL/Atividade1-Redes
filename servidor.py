import socket
import os
import hashlib
import time

HOST = '0.0.0.0'
PORT = 5005
BUFFER_SIZE = 1024

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((HOST, PORT))

print(f"Servidor UDP aguardando na porta {PORT}...")

def calcular_checksum(data):
    return hashlib.md5(data).hexdigest().encode()

while True:
    data, addr = server_socket.recvfrom(1024)
    msg = data.decode()

    if msg.startswith("GET"):
        nome_arquivo = msg.split(" ")[1].replace("/", "")

        if not os.path.exists(nome_arquivo):
            server_socket.sendto(b"ERRO", addr)
            continue

        pacotes = {}

        with open(nome_arquivo, "rb") as f:
            seq = 0
            while True:
                chunk = f.read(800)
                if not chunk:
                    break

                checksum = calcular_checksum(chunk)
                pacote = f"{seq}|".encode() + checksum + b"|" + chunk

                pacotes[seq] = pacote
                seq += 1

        total_pacotes = len(pacotes)
        server_socket.sendto(f"TOTAL|{total_pacotes}".encode(), addr)

        print(f"Iniciando envio de {total_pacotes} pacotes...")
        
        for seq in sorted(pacotes.keys()):
            server_socket.sendto(pacotes[seq], addr)
            # DELAY CRUCIAL: Evita o Buffer Overflow (Rajada)
            time.sleep(0.002) 

        server_socket.sendto(b"FIM", addr)

        # Modo retransmissão (com timeout)
        server_socket.settimeout(5)

        while True:
            try:
                req, addr = server_socket.recvfrom(1024)

                if req.startswith(b"REQ"):
                    seq_req = int(req.decode().split("|")[1])
                    if seq_req in pacotes:
                        #print(f"Reenviando pacote {seq_req}") # Comentado para não poluir a tela
                        server_socket.sendto(pacotes[seq_req], addr)
                
                elif req.startswith(b"GET"):
                    # Se o cliente perdeu o TOTAL e mandou GET de novo, reenviamos o TOTAL
                    server_socket.sendto(f"TOTAL|{total_pacotes}".encode(), addr)

                elif req == b"FIM_OK":
                    print("Transferência concluída com sucesso.\n---")
                    break

            except socket.timeout:
                print("Timeout da sessão. Aguardando novos clientes...\n---")
                break

        server_socket.settimeout(None)