import time
from typing import Optional

from defines import (
    BORDER,
    DIRECTIONS,
    GRID_NUM,
    LOG_FILE,
    NOSTONE,
    Board,
    Cell,
    Color,
    Direction,
    GameResult,
    Move,
    Position,
)


# Result of one line walk: (length, free, end_a, end_b) — the ends are the
# cells where each side's walk stopped. A plain tuple: this is the hottest
# construct in the engine, named-tuple creation costs ~18x more.
Line = tuple[int, int, Cell, Cell]


def isValidPos(x: int, y: int) -> bool:
    return x > 0 and x < GRID_NUM - 1 and y > 0 and y < GRID_NUM - 1


def init_board(board: Board) -> None:
    for i in range(GRID_NUM):
        board[i][0] = board[0][i] = board[i][GRID_NUM - 1] = board[GRID_NUM - 1][i] = BORDER
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            board[i][j] = NOSTONE


def make_move(board: Board, move: Move, color: Color) -> None:
    board[move.positions[0].x][move.positions[0].y] = color.value
    board[move.positions[1].x][move.positions[1].y] = color.value


def unmake_move(board: Board, move: Move) -> None:
    board[move.positions[0].x][move.positions[0].y] = NOSTONE
    board[move.positions[1].x][move.positions[1].y] = NOSTONE


def color_to_name(color: Color) -> str:
    if color == Color.BLACK:
        return "black"
    return "white"


def opponent(color: Color) -> Color:
    if color == Color.BLACK:
        return Color.WHITE
    return Color.BLACK


def measure_line(
    board: Board,
    x: int,
    y: int,
    direction: Direction,
    max_length: int = GRID_NUM,
    max_free: int = GRID_NUM,
) -> Line:
    stone = board[x][y]
    length = 0
    free = 0
    ends: list[Cell] = []
    for sign in (1, -1):
        step_x = direction[0] * sign
        step_y = direction[1] * sign
        px = x
        py = y
        if sign == -1:
            px += step_x
            py += step_y
        while length < max_length and board[px][py] == stone:
            px += step_x
            py += step_y
            length += 1
        while free < max_free and board[px][py] == NOSTONE:
            px += step_x
            py += step_y
            free += 1
        ends.append((px, py))
    return length, free, ends[0], ends[1]


def is_win_by_move(board: Board, pre_move: Move) -> bool:
    for direction in DIRECTIONS:
        for position in pre_move.positions:
            stone = board[position.x][position.y]
            if stone == BORDER or stone == NOSTONE:
                continue
            if measure_line(board, position.x, position.y, direction)[0] >= 6:
                return True
    return False


def is_board_full(board: Board) -> bool:
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            if board[i][j] == NOSTONE:
                return False
    return True


def check_game_end(board: Board, pre_move: Move) -> Optional[GameResult]:
    if is_win_by_move(board, pre_move):
        return GameResult.WIN
    if is_board_full(board):
        return GameResult.DRAW
    return None


def log_to_file(msg: str) -> int:
    try:
        with open(LOG_FILE, "a") as file:
            tm = time.time()
            ptr = time.ctime(tm)
            ptr = ptr[:-1]
            file.write(f"[{ptr}] - {msg}\n")
        return 0
    except Exception as e:
        print(f"Error: Can't open log file - {LOG_FILE}")
        return -1


def move2msg(move: Move) -> str:
    first = move.positions[0]
    second = move.positions[1]
    if first.x == second.x and first.y == second.y:
        return f"{chr(ord('S') - first.x + 1)}{chr(first.y + ord('A') - 1)}"
    return (
        f"{chr(first.y + ord('A') - 1)}{chr(ord('S') - first.x + 1)}"
        f"{chr(second.y + ord('A') - 1)}{chr(ord('S') - second.x + 1)}"
    )


def msg2move(msg: str) -> Move:
    if len(msg) == 2:
        x = ord('S') - ord(msg[1]) + 1
        y = ord(msg[0]) - ord('A') + 1
        return Move((Position(x, y), Position(x, y)))
    return Move(
        (
            Position(ord('S') - ord(msg[1]) + 1, ord(msg[0]) - ord('A') + 1),
            Position(ord('S') - ord(msg[3]) + 1, ord(msg[2]) - ord('A') + 1),
        )
    )


def print_board(board: Board, pre_move: Move | None = None) -> None:
    print("   " + "".join([chr(i + ord('A') - 1) + " " for i in range(1, GRID_NUM - 1)]))
    for i in range(1, GRID_NUM - 1):
        print(f"{chr(ord('A') - 1 + i)}", end=" ")
        for j in range(1, GRID_NUM - 1):
            x = GRID_NUM - 1 - j
            y = i
            stone = board[x][y]
            if stone == NOSTONE:
                print(" -", end="")
            elif stone == Color.BLACK:
                print(" O", end="")
            elif stone == Color.WHITE:
                print(" *", end="")
        print(" ", end="")
        print(f"{chr(ord('A') - 1 + i)}", end="\n")
    print("   " + "".join([chr(i + ord('A') - 1) + " " for i in range(1, GRID_NUM - 1)]))