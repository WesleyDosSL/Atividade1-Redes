import socket

server_ip = "127.0.0.1"
port = 5005

cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

msg = "Olá, servidor!"
cliente_socket.sendto(msg.encode(), (server_ip, port))

data, _ = cliente_socket.recvfrom(1024)
print(f"Resposta do servidor: {data.decode()}")