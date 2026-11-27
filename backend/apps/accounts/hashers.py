"""Como a senha e guardada.

O padrao do Django 6 (PBKDF2 com 1,2 milhao de iteracoes) protege gastando
CPU. No plano free do Render, com um decimo de CPU, isso levava cerca de 3 s
para conferir a senha: o login demorava 3,4 s, e 3 deles eram so isso.

O Argon2 protege gastando memoria em vez de CPU e e o algoritmo que a OWASP
recomenda em primeiro lugar. Aqui com a configuracao minima recomendada por
ela (19 MiB, 2 passadas, 1 linha de execucao): localmente, 35 ms contra 228 ms
do PBKDF2. O padrao do Argon2 no Django usa 100 MiB por conferencia, o que
pesa num servidor de 512 MB com varios logins ao mesmo tempo.

O nome do algoritmo continua "argon2", e os parametros ficam gravados em cada
hash. Senha antiga (PBKDF2) continua valendo: no primeiro login certo o Django
grava de novo com o Argon2.
"""
from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2OWASPPasswordHasher(Argon2PasswordHasher):
    time_cost = 2
    memory_cost = 19 * 1024  # KiB
    parallelism = 1
