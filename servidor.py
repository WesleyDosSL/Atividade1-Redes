import socket

HOST = '0.0.0.0' # De modo a escutar em todas as interfaces
PORT = 5005     # Porta (Maior que 1024)

# Criação do socket UDP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Associa o socket a um endereço e porta
server_socket.bind((HOST, PORT))

print(f"Servidor UDP escutando em {HOST}:{PORT}")

while True:
    data, addr = server_socket.recvfrom(1024) # Buffer de 1024 bytes
    print(f"Recebido de {addr}: {data.decode()}")

    resposta = "Mensagem recebida"
    server_socket.sendto(resposta.encode(), addr) # Envia resposta para o cliente
