from tools import init_board, is_board_full, is_win_by_move, check_game_end, color_to_name, opponent
from defines import Defines, StoneMove
from search_engine import SearchEngine


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def create_empty_board():
    board = [[0] * Defines.GRID_NUM for _ in range(Defines.GRID_NUM)]
    init_board(board)
    return board


def create_move(x1, y1, x2, y2):
    move = StoneMove()
    move.positions[0].x = x1
    move.positions[0].y = y1
    move.positions[1].x = x2
    move.positions[1].y = y2
    move.score = 0
    return move


def create_move_at(x, y):
    return create_move(x, y, x, y)


def fill_board_no_line(board):
    for i in range(1, Defines.GRID_NUM - 1):
        for j in range(1, Defines.GRID_NUM - 1):
            board[i][j] = Defines.BLACK if (i + 2 * j) % 5 < 2 else Defines.WHITE


# ============================================================
# BOARD TESTS
# ============================================================

def test_empty_board():
    board = create_empty_board()
    assert is_board_full(board) == False
    print("Board Test 1 - Empty board: PASS")


def test_one_stone():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    assert is_board_full(board) == False
    print("Board Test 2 - One stone: PASS")


def test_almost_full_board():
    board = create_empty_board()
    for i in range(1, Defines.GRID_NUM - 1):
        for j in range(1, Defines.GRID_NUM - 1):
            board[i][j] = Defines.BLACK
    board[10][10] = Defines.NOSTONE
    assert is_board_full(board) == False
    print("Board Test 3 - Almost full board: PASS")


def test_full_board():
    board = create_empty_board()
    for i in range(1, Defines.GRID_NUM - 1):
        for j in range(1, Defines.GRID_NUM - 1):
            board[i][j] = Defines.BLACK
    assert is_board_full(board) == True
    print("Board Test 4 - Full board: PASS")


# ============================================================
# WIN TESTS
# ============================================================

def test_horizontal_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Defines.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == Defines.WIN
    print("Win Test 1 - Horizontal 6: PASS")


def test_vertical_win():
    board = create_empty_board()
    for x in range(5, 11):
        board[x][10] = Defines.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == Defines.WIN
    print("Win Test 2 - Vertical 6: PASS")


def test_diagonal_win():
    board = create_empty_board()
    for i in range(6):
        board[5 + i][5 + i] = Defines.BLACK
    assert check_game_end(board, create_move_at(5, 5)) == Defines.WIN
    print("Win Test 3 - Diagonal 6: PASS")


def test_anti_diagonal_win():
    board = create_empty_board()
    for i in range(6):
        board[5 + i][10 - i] = Defines.BLACK
    assert check_game_end(board, create_move_at(5, 10)) == Defines.WIN
    print("Win Test 4 - Anti-diagonal 6: PASS")


def test_five_not_win():
    board = create_empty_board()
    for y in range(5, 10):
        board[10][y] = Defines.BLACK
    assert check_game_end(board, create_move_at(10, 9)) is None
    print("Win Test 5 - Five in a row: PASS")


def test_seven_win():
    board = create_empty_board()
    for y in range(4, 11):
        board[10][y] = Defines.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == Defines.WIN
    print("Win Test 6 - Seven in a row: PASS")


def test_broken_sequence():
    board = create_empty_board()
    for y in range(5, 8):
        board[10][y] = Defines.BLACK
    board[10][8] = Defines.WHITE
    for y in range(9, 11):
        board[10][y] = Defines.BLACK
    assert check_game_end(board, create_move_at(10, 10)) is None
    print("Win Test 7 - Broken sequence: PASS")


def test_white_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Defines.WHITE
    assert check_game_end(board, create_move_at(10, 10)) == Defines.WIN
    assert is_win_by_move(board, create_move_at(10, 10)) == True
    print("Win Test 8 - White win: PASS")


# ============================================================
# DRAW TESTS
# ============================================================

def test_full_board_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    assert check_game_end(board, create_move_at(10, 10)) == Defines.DRAW
    print("Draw Test 1 - Full board: PASS")


def test_win_beats_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    for y in range(2, 8):
        board[5][y] = Defines.BLACK
    assert check_game_end(board, create_move_at(5, 7)) == Defines.WIN
    print("Draw Test 2 - Win beats draw: PASS")


# ============================================================
# COLOR TESTS
# ============================================================

def test_color_names():
    assert color_to_name(Defines.BLACK) == "black"
    assert color_to_name(Defines.WHITE) == "white"
    print("Color Test 1 - Names: PASS")


def test_opponent():
    assert opponent(Defines.BLACK) == Defines.WHITE
    assert opponent(Defines.WHITE) == Defines.BLACK
    print("Color Test 2 - Opponent: PASS")


# ============================================================
# MOVE GENERATION TESTS
# ============================================================

def create_search_engine(board):
    engine = SearchEngine()
    engine.before_search(board, Defines.WHITE, 6)
    return engine


def candidates_are_valid(board, candidates):
    for move in candidates:
        for p in move.positions:
            assert 0 < p.x < Defines.GRID_NUM - 1
            assert 0 < p.y < Defines.GRID_NUM - 1
            assert board[p.x][p.y] == Defines.NOSTONE
        assert move.positions[0].x != move.positions[1].x or move.positions[0].y != move.positions[1].y
    return True


def test_candidate_limit():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    engine = create_search_engine(board)
    candidates = engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
    assert len(candidates) == Defines.MAX_CANDIDATE_MOVES
    assert candidates_are_valid(board, candidates)
    print("Search Test 1 - Fixed limit of candidates: PASS")


def test_candidates_skip_occupied():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    engine = create_search_engine(board)
    candidates = engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
    for move in candidates:
        assert board[move.positions[0].x][move.positions[0].y] == Defines.NOSTONE
        assert board[move.positions[1].x][move.positions[1].y] == Defines.NOSTONE
    print("Search Test 2 - Skip occupied positions: PASS")


def test_candidates_near_stones():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    engine = create_search_engine(board)
    candidates = engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
    first = candidates[0]
    assert abs(first.positions[0].x - 10) <= 1 and abs(first.positions[0].y - 10) <= 1
    print("Search Test 3 - Candidates ordered near stones: PASS")


def test_candidates_few_empties():
    board = create_empty_board()
    fill_board_no_line(board)
    board[5][2] = Defines.NOSTONE
    board[5][3] = Defines.NOSTONE
    board[5][4] = Defines.NOSTONE
    engine = create_search_engine(board)
    candidates = engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
    assert len(candidates) == 3
    print("Search Test 4 - Few empties produce all pairs: PASS")


def test_candidates_full_board():
    board = create_empty_board()
    fill_board_no_line(board)
    engine = create_search_engine(board)
    assert engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES) == []
    print("Search Test 5 - No candidates on full board: PASS")


def test_candidates_custom_limit():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    engine = create_search_engine(board)
    assert len(engine.generate_candidate_moves(5)) == 5
    print("Search Test 6 - Custom limit: PASS")


# ============================================================
# RUN ALL TESTS
# ============================================================

if __name__ == "__main__":
    print("\n========== BOARD TESTS ==========\n")
    test_empty_board()
    test_one_stone()
    test_almost_full_board()
    test_full_board()

    print("\n========== WIN TESTS ==========\n")
    test_horizontal_win()
    test_vertical_win()
    test_diagonal_win()
    test_anti_diagonal_win()
    test_five_not_win()
    test_seven_win()
    test_broken_sequence()
    test_white_win()

    print("\n========== DRAW TESTS ==========\n")
    test_full_board_draw()
    test_win_beats_draw()

    print("\n========== COLOR TESTS ==========\n")
    test_color_names()
    test_opponent()

    print("\n========== MOVE GENERATION TESTS ==========\n")
    test_candidate_limit()
    test_candidates_skip_occupied()
    test_candidates_near_stones()
    test_candidates_few_empties()
    test_candidates_full_board()
    test_candidates_custom_limit()

    print("\n========== ALL TESTS PASSED ==========\n")