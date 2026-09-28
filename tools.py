from defines import *
import time


# Point (x, y) if in the valid position of the board.
def isValidPos(x, y):
    return x > 0 and x < Defines.GRID_NUM - 1 and y > 0 and y < Defines.GRID_NUM - 1


def init_board(board):
    for i in range(21):
        board[i][0] = board[0][i] = board[i][Defines.GRID_NUM - 1] = board[Defines.GRID_NUM - 1][i] = Defines.BORDER
    for i in range(1, Defines.GRID_NUM - 1):
        for j in range(1, Defines.GRID_NUM - 1):
            board[i][j] = Defines.NOSTONE


def make_move(board, move, color):
    board[move.positions[0].x][move.positions[0].y] = color
    board[move.positions[1].x][move.positions[1].y] = color


def color_to_name(color):
    if color == Defines.BLACK:
        return "black"
    return "white"


def opponent(color):
    if color == Defines.BLACK:
        return Defines.WHITE
    return Defines.BLACK


def unmake_move(board, move):
    board[move.positions[0].x][move.positions[0].y] = Defines.NOSTONE
    board[move.positions[1].x][move.positions[1].y] = Defines.NOSTONE


def measure_line(board, position, direction, max_length=Defines.GRID_NUM, max_free=Defines.GRID_NUM):
    stone = board[position.x][position.y]
    length = 0
    free = 0
    ends = []
    for sign in (1, -1):
        step_x = direction[0] * sign
        step_y = direction[1] * sign
        x = position.x
        y = position.y
        if sign == -1:
            x += step_x
            y += step_y
        while length < max_length and board[x][y] == stone:
            x += step_x
            y += step_y
            length += 1
        while free < max_free and board[x][y] == Defines.NOSTONE:
            x += step_x
            y += step_y
            free += 1
        ends.append((x, y))
    return length, free, ends[0], ends[1]


def is_win_by_move(board, preMove):
    for direction in Defines.DIRECTIONS:
        for position in preMove.positions:
            stone = board[position.x][position.y]
            if stone == Defines.BORDER or stone == Defines.NOSTONE:
                continue
            if measure_line(board, position, direction)[0] >= 6:
                return True
    return False


def is_board_full(board):
    for i in range(1, Defines.GRID_NUM - 1):
        for j in range(1, Defines.GRID_NUM - 1):
            if board[i][j] == Defines.NOSTONE:
                return False
    return True


def check_game_end(board, preMove):
    if is_win_by_move(board, preMove):
        return Defines.WIN
    if is_board_full(board):
        return Defines.DRAW
    return None


def get_msg(max_len):
    buf = input().strip()
    return buf[:max_len]


def log_to_file(msg):
    g_log_file_name = Defines.LOG_FILE
    try:
        with open(g_log_file_name, "a") as file:
            tm = time.time()
            ptr = time.ctime(tm)
            ptr = ptr[:-1]
            file.write(f"[{ptr}] - {msg}\n")
        return 0
    except Exception as e:
        print(f"Error: Can't open log file - {g_log_file_name}")
        return -1


def move2msg(move):
    if move.positions[0].x == move.positions[1].x and move.positions[0].y == move.positions[1].y:
        msg = f"{chr(ord('S') - move.positions[0].x + 1)}{chr(move.positions[0].y + ord('A') - 1)}"
        return msg
    else:
        msg = f"{chr(move.positions[0].y + ord('A') - 1)}{chr(ord('S') - move.positions[0].x + 1)}" \
              f"{chr(move.positions[1].y + ord('A') - 1)}{chr(ord('S') - move.positions[1].x + 1)}"
        return msg


def msg2move(msg):
    move = StoneMove()
    if len(msg) == 2:
        move.positions[0].x = move.positions[1].x = ord('S') - ord(msg[1]) + 1
        move.positions[0].y = move.positions[1].y = ord(msg[0]) - ord('A') + 1
        move.score = 0
        return move
    else:
        move.positions[0].x = ord('S') - ord(msg[1]) + 1
        move.positions[0].y = ord(msg[0]) - ord('A') + 1
        move.positions[1].x = ord('S') - ord(msg[3]) + 1
        move.positions[1].y = ord(msg[2]) - ord('A') + 1
        move.score = 0
        return move


def print_board(board, preMove=None):
    print("   " + "".join([chr(i + ord('A') - 1) + " " for i in range(1, Defines.GRID_NUM - 1)]))
    for i in range(1, Defines.GRID_NUM - 1):
        print(f"{chr(ord('A') - 1 + i)}", end=" ")
        for j in range(1, Defines.GRID_NUM - 1):
            x = Defines.GRID_NUM - 1 - j
            y = i
            stone = board[x][y]
            if stone == Defines.NOSTONE:
                print(" -", end="")
            elif stone == Defines.BLACK:
                print(" O", end="")
            elif stone == Defines.WHITE:
                print(" *", end="")
        print(" ", end="")
        print(f"{chr(ord('A') - 1 + i)}", end="\n")
    print("   " + "".join([chr(i + ord('A') - 1) + " " for i in range(1, Defines.GRID_NUM - 1)]))


def print_score(move_list, n):
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    for move in move_list:
        board[move.x][move.y] = move.score

    print("  " + "".join([f"{i:4}" for i in range(1, Defines.GRID_NUM - 1)]))
    for i in range(1, Defines.GRID_NUM - 1):
        print(f"{i:2}", end="")
        for j in range(1, Defines.GRID_NUM - 1):
            score = board[i][j]
            if score == 0:
                print("   -", end="")
            else:
                print(f"{score:4}", end="")
        print()
