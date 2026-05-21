import sqlite3
from werkzeug.security import generate_password_hash

def reset_password(email, new_password):
    conn = sqlite3.connect('gestao.db')
    cursor = conn.cursor()
    
    hash_senha = generate_password_hash(new_password)
    
    cursor.execute("UPDATE usuarios SET senha_hash = ? WHERE email = ?", (hash_senha, email))
    
    if cursor.rowcount > 0:
        print(f"Senha de {email} redefinida com sucesso para: {new_password}")
    else:
        print(f"Usuario {email} nao encontrado.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    reset_password('viniciuslukas353@gmail.com', '12345678')
