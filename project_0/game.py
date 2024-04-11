""" Игра угадай число.
Компьютер сам загадывает число и пытается его отгадать.
"""

import numpy as np


def random_predict(number: int = np.random.randint(1, 101)) -> int:
    """Рандомно загадываем число
    Args:
        number (int, optional): Hidden number. Defaults to 1.
    Returns:
        int: Number of attempts
    """
    # Создадим основные переменные
    count = 0
    max_number = 100
    min_number = 0
    predict_number = np.random.randint(1, 101)  # Число, которое создает компьютер случайно в промежутке от 1 до 100

    # Воспользуемся методом бинарного поиска
    while True:
        count += 1

        if predict_number > number:
            max_number = predict_number - 1 # Верхняя граница
            predict_number = (max_number + min_number) // 2


        elif predict_number < number:
            min_number = predict_number + 1 # Нижняя граница
            predict_number = (max_number + min_number) // 2

        else:
            break  # Игра закончилась, завершаем цикл
        #print(predict_number, number) # Выводим для отслеживания процесса

    return count


def score_game(random_predict) -> int:
    """Сколько в среднем попыток тратится, чтобы отгадать число
    Args:
        random_predict ([type]): guess function
    Returns:
        int: среднее число попыток
    """

    count_ls = []  # Список для сохранения количетсва попыток
    np.random.seed(1)  # Создаем сид для воспроизводимости рандома
    random_array = np.random.randint(1, 101, size=(250))  # Создадим рандомный массив чисел от 1 до 100

    i=0
    for number in random_array:
        i+=1
        count_ls.append(random_predict(number))

    score = int(np.mean(count_ls))  # Найдем среднее количество попыток угадать число

    print('Среднее число попыток, за которое программа отгадывает число равно:', score)
    return (score)

score_game(random_predict)