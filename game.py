import random


def generate_ticket():
    """
    Generate a standard 3 x 9 Housie ticket.

    Each row has exactly 5 numbers.
    Total numbers = 15.
    """

    column_ranges = [
        list(range(1, 10)),
        list(range(10, 20)),
        list(range(20, 30)),
        list(range(30, 40)),
        list(range(40, 50)),
        list(range(50, 60)),
        list(range(60, 70)),
        list(range(70, 80)),
        list(range(80, 91))
    ]

    while True:
        row_columns = [
            random.sample(range(9), 5)
            for _ in range(3)
        ]

        used_columns = set()

        for row in row_columns:
            used_columns.update(row)

        if len(used_columns) != 9:
            continue

        ticket = [
            [None] * 9
            for _ in range(3)
        ]

        for column in range(9):
            rows = [
                row
                for row in range(3)
                if column in row_columns[row]
            ]

            numbers = random.sample(
                column_ranges[column],
                len(rows)
            )

            numbers.sort()

            for row, number in zip(rows, numbers):
                ticket[row][column] = number

        return ticket
