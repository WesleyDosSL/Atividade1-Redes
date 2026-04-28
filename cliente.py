import socket
import hashlib
import random

BUFFER_SIZE = 1024 # Tamanho do buffer para receber mensagens (pode ser ajustado conforme necessário)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Cria um socket UDP
client_socket.settimeout(3) # Define um timeout de 3 segundos para as operações de recepção. Isso é importante para detectar perdas de pacotes e evitar que o cliente fique preso esperando indefinidamente por uma resposta do servidor.

def calcular_checksum(data): # Função para calcular o checksum usando MD5. O MD5 é uma função de hash rápida que gera um valor de 128 bits (16 bytes) a partir dos dados de entrada. Embora o MD5 não seja recomendado para segurança criptográfica, ele é adequado para detectar erros de transmissão.
    return hashlib.md5(data).hexdigest().encode() # A função hexdigest() retorna o hash como uma string hexadecimal, que é então codificada em bytes para ser enviada junto com os dados.

# Parse da entrada conforme requisito do trabalho
entrada = input("Digite a requisição (Ex: @127.0.0.1:5005/arquivo.ext): ")

try:
    # Remove o '@' e separa o IP:Porta do Arquivo
    entrada = entrada.lstrip('@')
    ip_porta, arquivo = entrada.split('/', 1)
    server_ip, server_porta = ip_porta.split(':')
    server_porta = int(server_porta)
except Exception: # Se a entrada não estiver no formato esperado, o programa exibirá uma mensagem de erro e encerrará. Isso é importante para garantir que o cliente forneça as informações corretas para se conectar ao servidor e solicitar o arquivo desejado.
    print("Formato inválido! Certifique-se de usar @IP:Porta/nome_do_arquivo.ext")
    exit()

server_address = (server_ip, server_porta) # O endereço do servidor é construído como uma tupla contendo o IP e a porta. Isso é necessário para que o cliente possa enviar mensagens para o servidor usando o método sendto() do socket, que requer o endereço de destino em formato de tupla (IP, porta).
mensagem_get = f"GET /{arquivo}".encode() # A mensagem de requisição é construída no formato "GET /nome_do_arquivo.ext" e codificada em bytes para ser enviada ao servidor.

total_pacotes = None

# Proteção contra perda do pacote TOTAL
while True:
    client_socket.sendto(mensagem_get, server_address)
    try:
        resp, _ = client_socket.recvfrom(1024)

        if resp == b"ERRO": # Se o servidor responder com "ERRO", isso indica que o arquivo solicitado não foi encontrado. O cliente exibirá uma mensagem informando que o arquivo não foi encontrado no servidor e encerrará o programa.
            print("Arquivo não encontrado no servidor.")
            exit()

        if resp.startswith(b"TOTAL"): # Se a resposta do servidor começar com "TOTAL", isso indica que o servidor está informando o número total de pacotes que serão enviados. O cliente extrairá esse número da resposta, exibirá uma mensagem indicando quantos pacotes são esperados e sairá do loop para começar a receber os pacotes de dados.
            total_pacotes = int(resp.decode().split("|")[1])
            print(f"Total de pacotes esperado: {total_pacotes}")
            break
            
    except socket.timeout: # Se ocorrer um timeout ao aguardar a resposta do servidor, isso pode indicar que o pacote "TOTAL" foi perdido. O cliente exibirá uma mensagem informando que houve um timeout e que a requisição GET será reenviada. O loop continuará, permitindo que o cliente tente novamente até receber a resposta correta do servidor.
        print("Timeout ao aguardar resposta do servidor. Reenviando GET...")

dados = {}
recebidos = set() # O conjunto "recebidos" é usado para rastrear quais pacotes foram recebidos com sucesso. Ele armazena os números de sequência dos pacotes que foram processados corretamente, permitindo que o cliente identifique quais pacotes estão faltando e precisam ser solicitados novamente ao servidor durante a fase de recuperação de perdas (NACK).

print("Recebendo dados...")

while True:
    try:
        pacote, _ = client_socket.recvfrom(BUFFER_SIZE) 
    except socket.timeout: # Se ocorrer um timeout durante a recepção de pacotes, isso pode indicar que o pacote "FIM" foi perdido, o que significa que o servidor terminou de enviar os pacotes, mas o cliente não recebeu a confirmação final. O cliente exibirá uma mensagem informando que um timeout foi detectado e que isso pode indicar a perda do pacote "FIM". O loop será interrompido para permitir que o cliente analise quais pacotes foram recebidos e quais estão faltando, iniciando a fase de recuperação de perdas (NACK) se necessário.
        print("Timeout detectado (possível perda do pacote FIM). Analisando perdas...")
        break # Sai do loop para ver o que faltou

    if pacote == b"FIM": # Se o cliente receber o pacote "FIM", isso indica que o servidor terminou de enviar os pacotes de dados.
        break
        
    if pacote.startswith(b"TOTAL"):
        continue # Ignora pacotes TOTAL duplicados que possam chegar atrasados

    try:
        # Extrair o seq primeiro, para poder dizer qual foi perdido
        header, checksum, chunk = pacote.split(b"|", 2) 
        seq = int(header.decode()) # O número de sequência do pacote é extraído do cabeçalho da mensagem. O pacote é dividido usando o caractere "|" como delimitador, e o primeiro elemento (índice 0) é decodificado para obter o número de sequência em formato inteiro.

        # Simulação de perda (20%) - Cumprindo requisito de exibir o número
        if random.random() < 0.2:
            print(f"Pacote {seq} descartado intencionalmente (simulação)")
            continue

        if calcular_checksum(chunk) != checksum: # O cliente calcula o checksum do chunk de dados recebido e o compara com o checksum enviado pelo servidor. Se os checksums não corresponderem, isso indica que houve um erro de transmissão e o pacote foi corrompido. O cliente exibirá uma mensagem informando que houve um erro de checksum no pacote específico e continuará para o próximo pacote, ignorando o pacote corrompido.
            print(f"Erro de checksum no pacote {seq}")
            continue

        if seq not in dados: # Se o número de sequência do pacote recebido ainda não estiver presente no dicionário "dados", isso significa que o pacote é novo e pode ser armazenado.
            dados[seq] = chunk
            recebidos.add(seq) # O número de sequência do pacote recebido é adicionado ao conjunto "recebidos" para rastrear que esse pacote foi processado com sucesso. Isso é importante para a fase de recuperação de perdas (NACK), onde o cliente verificará quais pacotes estão faltando e solicitará retransmissões ao servidor.

    except Exception as e:
        pass # Ignora pacotes que não tenham o formato esperado

# Lógica de recuperação de perdas (NACK)
faltando = set(range(total_pacotes)) - recebidos

if faltando:
    print(f"Pacotes perdidos: {len(faltando)}. Iniciando retransmissão...")

while faltando:
    for seq in faltando: # Para cada número de sequência que está faltando, o cliente enviará uma solicitação de retransmissão ao servidor. A mensagem de solicitação é construída no formato "REQ|SEQ", onde SEQ é o número de sequência do pacote que está faltando. O cliente usará o método sendto() do socket para enviar essa mensagem ao servidor, solicitando que o pacote específico seja reenviado.
        msg = f"REQ|{seq}"
        client_socket.sendto(msg.encode(), server_address)

        try:
            # Timeout curto para não travar muito tempo esperando um pacote só
            client_socket.settimeout(0.5)
            pacote, _ = client_socket.recvfrom(BUFFER_SIZE)
            
            header, checksum, chunk = pacote.split(b"|", 2) # O cliente tentará receber o pacote retransmitido pelo servidor. Se um pacote for recebido, ele será processado da mesma forma que os pacotes recebidos inicialmente: o número de sequência será extraído do cabeçalho, o checksum será verificado e, se estiver correto, o chunk de dados será armazenado no dicionário "dados" e o número de sequência será adicionado ao conjunto "recebidos". O cliente exibirá uma mensagem indicando que o pacote específico foi recuperado com sucesso.
            seq_recv = int(header.decode())

            if calcular_checksum(chunk) == checksum:
                if seq_recv not in dados: # Se o pacote recuperado ainda não estiver presente no dicionário "dados", ele será armazenado e o número de sequência será adicionado ao conjunto "recebidos". Isso é importante para garantir que o cliente mantenha um registro preciso dos pacotes que foram processados com sucesso, mesmo durante a fase de recuperação de perdas (NACK).
                    dados[seq_recv] = chunk
                    recebidos.add(seq_recv)
                    print(f"Pacote {seq_recv} recuperado!")
                    
        except socket.timeout:
            pass # Se der timeout na retransmissão, o while garante que pediremos de novo
        except Exception:
            pass 

    faltando = set(range(total_pacotes)) - recebidos # Após tentar recuperar os pacotes perdidos, o cliente recalculará quais pacotes ainda estão faltando. O loop continuará até que todos os pacotes tenham sido recuperados com sucesso, garantindo que o cliente tenha todos os dados necessários para montar o arquivo final.

client_socket.settimeout(3) # Volta o timeout ao normal

# Salvar arquivo
print("Verificação concluída. Montando arquivo final...")
with open("recebido_" + arquivo, "wb") as f:
    for i in sorted(dados.keys()): # Os pacotes são escritos no arquivo final em ordem de sequência. O método sorted() é usado para garantir que os pacotes sejam escritos na ordem correta, mesmo que tenham sido recebidos fora de ordem devido a retransmissões ou atrasos na rede.
        f.write(dados[i])

client_socket.sendto(b"FIM_OK", server_address) # Após montar o arquivo final, o cliente enviará uma mensagem de confirmação "FIM_OK" para o servidor. Isso indica que o cliente recebeu e processou todos os pacotes com sucesso, permitindo que o servidor encerre a sessão de retransmissão e volte a aguardar por novos clientes.
print(f"Arquivo '{arquivo}' salvo com sucesso!")