import random


def generate_ticket():
    """
    Generate a standard 3 x 9 Housie ticket.

    Each row has exactly 5 numbers.
    Total numbers = 15.
    """

    column_ranges = [
        list(range(1, 10)),     # 1-9
        list(range(10, 20)),    # 10-19
        list(range(20, 30)),    # 20-29
        list(range(30, 40)),    # 30-39
        list(range(40, 50)),    # 40-49
        list(range(50, 60)),    # 50-59
        list(range(60, 70)),    # 60-69
        list(range(70, 80)),    # 70-79
        list(range(80, 91))     # 80-90
    ]

    while True:

        # Select 5 columns for every row
        row_columns = [
            random.sample(range(9), 5)
            for _ in range(3)
        ]

        # Every column must contain at least one number
        used_columns = set()

        for row in row_columns:
            used_columns.update(row)

        if len(used_columns) != 9:
            continue

        ticket = [
            [None] * 9
            for _ in range(3)
        ]

        # Fill columns
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