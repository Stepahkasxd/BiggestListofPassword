import random
import string
import os
import time
from multiprocessing import Process, Queue, cpu_count, Value
from threading import Thread


def generate_passwords_batch(batch_size=100, length=8, characters=None, existing_passwords=None):
    """Генерирует партию уникальных паролей."""
    passwords = set()

    while len(passwords) < batch_size:
        password = ''.join(random.choices(characters, k=length))
        if existing_passwords is None or password not in existing_passwords:
            passwords.add(password)

    return list(passwords)


def worker(queue, batch_size, length, characters, existing_passwords, total_count):
    """Процесс-воркер для генерации уникальных паролей."""
    local_passwords = set(existing_passwords) if existing_passwords else set()
    while True:
        passwords = generate_passwords_batch(batch_size=batch_size, length=length, characters=characters,
                                             existing_passwords=local_passwords)
        local_passwords.update(passwords)  # Обновляем локальный список уникальных паролей
        with total_count.get_lock():
            total_count.value += len(passwords)  # Увеличиваем общий счетчик
        queue.put(passwords)  # Отправляем партию паролей в очередь
        time.sleep(0.1)  # Замедляем генерацию


def save_to_file(file_path, queue, existing_passwords):
    """Сохраняет уникальные пароли из очереди в файл."""
    with open(file_path, 'a') as file:
        while True:
            passwords = queue.get()  # Получаем партию паролей из очереди
            if passwords is None:  # Сигнал завершения работы
                break
            unique_passwords = [p for p in passwords if p not in existing_passwords]
            existing_passwords.update(unique_passwords)  # Добавляем в множество уникальные пароли
            if unique_passwords:
                file.write('\n'.join(unique_passwords) + '\n')


def progress_monitor(total_count):
    """Мониторит прогресс генерации паролей и выводит его каждые 10 секунд."""
    while True:
        time.sleep(10)
        print(f"Сгенерировано паролей: {total_count.value}")


def get_user_preferences():
    """Запрашивает настройки генерации паролей у пользователя."""
    print("Настройка генерации паролей:")

    # Запрос длины пароля
    while True:
        try:
            length = int(input("Введите длину пароля (по умолчанию 8): ") or 8)
            if length > 0:
                break
        except ValueError:
            pass
        print("Пожалуйста, введите положительное число.")

    # Включение спецсимволов
    use_special = input("Использовать специальные символы? (y/n, по умолчанию y): ").strip().lower() or 'y'
    use_special = use_special == 'y'

    # Включение цифр
    use_digits = input("Использовать цифры? (y/n, по умолчанию y): ").strip().lower() or 'y'
    use_digits = use_digits == 'y'

    # Выбор регистра
    print("Выберите регистр букв:")
    print("1. Только заглавные буквы")
    print("2. Только строчные буквы")
    print("3. Разные регистры (по умолчанию)")
    while True:
        try:
            choice = int(input("Ваш выбор (1/2/3): ") or 3)
            if choice in [1, 2, 3]:
                break
        except ValueError:
            pass
        print("Пожалуйста, выберите 1, 2 или 3.")

    if choice == 1:
        characters = string.ascii_uppercase
    elif choice == 2:
        characters = string.ascii_lowercase
    else:
        characters = string.ascii_letters

    # Добавление цифр и спецсимволов
    if use_digits:
        characters += string.digits
    if use_special:
        characters += string.punctuation

    return length, characters


if __name__ == "__main__":
    file_path = '/home/insomtripple/Рабочий стол/wifipassgenerator/pass.txt'
    batch_size = 1000  # Количество паролей в одной партии
    num_workers = max(1, cpu_count() // 2)  # Количество процессов

    # Запрос параметров у пользователя
    password_length, characters = get_user_preferences()

    # Создаем директорию, если она не существует
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Загружаем уже существующие пароли из файла, если он существует
    existing_passwords = set()
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            existing_passwords.update(file.read().splitlines())

    print(f"Генерация паролей началась. Используем {num_workers} процессов.")
    print(f"Пароли сохраняются в: {file_path}")

    # Счетчик для общего количества сгенерированных паролей
    total_count = Value('i', 0)

    try:
        queue = Queue()  # Очередь для передачи паролей между процессами

        # Запускаем процессы-воркеры для генерации паролей
        workers = []
        for _ in range(num_workers):
            p = Process(target=worker,
                        args=(queue, batch_size, password_length, characters, existing_passwords, total_count))
            p.start()
            workers.append(p)

        # Запускаем монитор прогресса в отдельном потоке
        monitor_thread = Thread(target=progress_monitor, args=(total_count,), daemon=True)
        monitor_thread.start()

        # Главный процесс отвечает за сохранение паролей в файл
        save_to_file(file_path, queue, existing_passwords)
    except KeyboardInterrupt:
        print("\nОстановка генерации паролей. Завершаем процессы...")

        # Завершаем все процессы-воркеры
        for _ in workers:
            queue.put(None)  # Отправляем сигнал завершения работы
        for p in workers:
            p.join()
        print("Все процессы завершены.")
    finally:
        print(f"\nОбщее количество сгенерированных паролей: {total_count.value}")
