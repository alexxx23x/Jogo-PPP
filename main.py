import redis
import random
import time
import string



def generate_room_id(length=6):
    """Gera um ID aleatório para a sala."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def normalize_room_key(room_input):
    """Normaliza o nome da sala (com ou sem prefixo 'room:')."""
    if room_input.startswith("room:"):
        return room_input
    return f"room:{room_input}"

def create_room(r, room_ttl_seconds=300):
    """Cria uma nova sala vazia."""
    room_id = generate_room_id()
    room_key = f"room:{room_id}"
    r.hset(room_key, "player1", "")
    r.hset(room_key, "player2", "")
    r.hset(room_key, "ready1", "0")
    r.hset(room_key, "ready2", "0")
    r.expire(room_key, room_ttl_seconds)
    return room_key

def join_room(r, room_input):
    """Player 2 entra em uma sala existente."""
    room_key = normalize_room_key(room_input)
    if not r.exists(room_key):
        return False, "Sala inexistente", None
    p2 = r.hget(room_key, "player2")
    if p2 and p2 != "":
        return False, "A sala já possui dois jogadores.", None
    return True, "Conectado com sucesso!", room_key

def wait_for_both_ready(r, room_key, poll_interval=1, timeout_seconds=120):
    """Aguarda até que os dois jogadores estejam prontos (mensagem única)."""
    waited = 0
    print("\nAguardando jogador entrar na sala...")

    while waited < timeout_seconds:
        ready1 = r.hget(room_key, "ready1")
        ready2 = r.hget(room_key, "ready2")
        if ready1 == b"1" and ready2 == b"1":
            print("Ambos os jogadores estão prontos!")
            return True
        time.sleep(poll_interval)
        waited += poll_interval

    print("Tempo esgotado. Sala encerrada.")
    return False

def wait_for_moves(r, room_key, poll_interval=1, timeout_seconds=120):
    """Aguarda até que ambos façam suas jogadas (mensagem única)."""
    waited = 0
    print("\nAguardando o outro jogador jogar...")

    while waited < timeout_seconds:
        p1 = r.hget(room_key, "player1")
        p2 = r.hget(room_key, "player2")
        if p1 and p1 != b"" and p2 and p2 != b"":
            return int(p1), int(p2)
        time.sleep(poll_interval)
        waited += poll_interval

    print("Tempo esgotado. Sala encerrada.")
    return None, None

# Interface textual e lógica do jogo

def front():
    print("\nEscolha sua jogada:")
    print("1 - 👊  Pedra")
    print("2 - 🖐  Papel")
    print("3 - ✌  Tesoura")

def anime(p1_choice, p2_choice, is_player1):
    choi = ["👊", "🖐", "✌"]

    print("\nJo...")
    time.sleep(0.4)
    print("Ken...")
    time.sleep(0.4)
    print("Po!\n")
    time.sleep(0.3)

    print(f"Player 1: {choi[p1_choice - 1]}  |  Player 2: {choi[p2_choice - 1]}")
    print("-----------------------------------------")

    if p1_choice == p2_choice:
        print("Empate!")
    elif (p1_choice == 1 and p2_choice == 3) or (p1_choice == 2 and p2_choice == 1) or (p1_choice == 3 and p2_choice == 2):
        if is_player1:
            print("Você venceu!")
        else:
            print("Você perdeu!")
    else:
        if is_player1:
            print("Você perdeu!")
        else:
            print("Você venceu!")

# Função principal

def main():
    print("==============================================")
    print("   ✊ PEDRA  🖐 PAPEL  ✌ TESOURA - Multiplayer ")
    print("==============================================")

    # Conecta ao Redis local
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)
        r.ping()
        print("Conectado ao Redis!\n")
    except Exception as e:
        print("Erro ao conectar ao Redis:", e)
        return

    print("1 - Criar sala (Player 1)")
    print("2 - Entrar em sala (Player 2)")
    try:
        select = int(input("Escolha: "))
    except:
        print("Entrada inválida.")
        return
    
    # PLAYER 1 - Cria a sala

    if select == 1:
        room_key = create_room(r)
        print(f"\nSala criada: {room_key}")
        print("Aguardando outro jogador entrar...\n")

        # Aguarda até que o Player 2 entre e marque "pronto"
        joined = wait_for_both_ready(r, room_key, poll_interval=1, timeout_seconds=300)
        if not joined:
            r.delete(room_key)
            return

        # Ambos conectados → jogar
        front()
        try:
            p1_choice = int(input("Sua jogada: "))
        except:
            print("Jogada inválida.")
            r.delete(room_key)
            return
        r.hset(room_key, "player1", p1_choice)

        print("Jogada enviada.")
        p1, p2 = wait_for_moves(r, room_key)
        if not p1 or not p2:
            r.delete(room_key)
            return

        anime(p1, p2, True)
        print("\nPartida encerrada. Sala removida.")
        r.delete(room_key)

    # PLAYER 2 - Entra na sala

    elif select == 2:
        room_input = input("Digite o ID da sala (ex: ab12cd ou room:ab12cd): ").strip()
        ok, msg, room_key = join_room(r, room_input)
        if not ok:
            print("Erro:", msg)
            return

        print("\nConectado à sala!")
        r.hset(room_key, "ready2", "1")

        # Marca Player 1 como pronto
        r.hset(room_key, "ready1", "1")

        # Aguarda confirmação de ambos
        both_ready = wait_for_both_ready(r, room_key, poll_interval=1, timeout_seconds=300)
        if not both_ready:
            r.delete(room_key)
            return

        # Agora joga
        front()
        try:
            p2_choice = int(input("Sua jogada: "))
        except:
            print("Jogada inválida.")
            return
        r.hset(room_key, "player2", p2_choice)

        print("Jogada enviada.")
        p1, p2 = wait_for_moves(r, room_key)
        if not p1 or not p2:
            r.delete(room_key)
            return

        anime(p1, p2, False)
        print("\nPartida encerrada. Sala removida.")
        r.delete(room_key)

    else:
        print("Opção inválida.")



if __name__ == "__main__":
    main()
