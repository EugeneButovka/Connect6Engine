from tools import init_board, is_board_full, is_win_by_move, check_game_end, color_to_name, opponent, measure_line, make_move
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

def create_search_engine(board, color=Defines.WHITE):
    engine = SearchEngine()
    engine.before_search(board, color, Defines.SEARCH_DEPTH)
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
# EVALUATION TESTS
# ============================================================

def test_evaluate_black_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Defines.BLACK
    engine = create_search_engine(board)
    assert engine.evaluate(create_move_at(10, 10)) == Defines.MAXINT
    print("Eval Test 1 - Black win returns MAXINT: PASS")


def test_evaluate_white_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Defines.WHITE
    engine = create_search_engine(board)
    assert engine.evaluate(create_move_at(10, 10)) == Defines.MININT
    print("Eval Test 2 - White win returns MININT: PASS")


def test_evaluate_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    engine = create_search_engine(board)
    assert engine.evaluate(create_move_at(10, 10)) == 0
    print("Eval Test 3 - Draw returns 0: PASS")


def test_evaluate_empty_board():
    board = create_empty_board()
    engine = create_search_engine(board)
    assert engine.evaluate(create_move_at(10, 10)) == 0
    print("Eval Test 4 - Empty board is balanced: PASS")


def test_evaluate_black_advantage():
    board = create_empty_board()
    for y in range(3, 7):
        board[10][y] = Defines.BLACK
    for y in range(3, 5):
        board[15][y] = Defines.WHITE
    engine = create_search_engine(board)
    score = engine.evaluate(create_move_at(10, 10))
    assert score > 0
    assert score > Defines.LIVE_WEIGHTS[3]
    print("Eval Test 5 - Black advantage is positive: PASS")


def test_evaluate_white_advantage():
    board = create_empty_board()
    for y in range(3, 7):
        board[10][y] = Defines.WHITE
    for y in range(3, 5):
        board[15][y] = Defines.BLACK
    engine = create_search_engine(board)
    score = engine.evaluate(create_move_at(10, 10))
    assert score < 0
    assert score < -Defines.LIVE_WEIGHTS[3]
    print("Eval Test 6 - White advantage is negative: PASS")


def test_evaluate_mirrored_board():
    board = create_empty_board()
    for y in range(3, 6):
        board[5][y] = Defines.BLACK
        board[15][y] = Defines.WHITE
    engine = create_search_engine(board)
    assert engine.evaluate(create_move_at(10, 10)) == 0
    print("Eval Test 7 - Mirrored board is balanced: PASS")


def test_dead_set_is_worthless():
    dead = create_empty_board()
    for y in range(8, 12):
        dead[10][y] = Defines.BLACK
    dead[10][7] = Defines.WHITE
    dead[10][12] = Defines.WHITE
    open_board = create_empty_board()
    for y in range(8, 12):
        open_board[10][y] = Defines.BLACK
    d = create_search_engine(dead)
    o = create_search_engine(open_board)
    assert o.count_live_sets(Defines.BLACK) - d.count_live_sets(Defines.BLACK) == Defines.LIVE_WEIGHTS[4]
    print("Eval Test 8 - Dead set contributes nothing: PASS")


def test_diagonal_equals_horizontal():
    horizontal = create_empty_board()
    for y in range(3, 6):
        horizontal[10][y] = Defines.BLACK
    diagonal = create_empty_board()
    for i in range(3):
        diagonal[10 + i][4 + i] = Defines.BLACK
    h = create_search_engine(horizontal)
    d = create_search_engine(diagonal)
    assert h.count_live_sets(Defines.BLACK) == d.count_live_sets(Defines.BLACK)
    assert h.count_live_sets(Defines.BLACK) > Defines.LIVE_WEIGHTS[3]
    print("Eval Test 9 - All line axes are covered equally: PASS")


def test_longer_set_worth_more():
    three = create_empty_board()
    for y in range(3, 6):
        three[10][y] = Defines.BLACK
    two_pairs = create_empty_board()
    for y in range(3, 5):
        two_pairs[10][y] = Defines.BLACK
        two_pairs[15][y] = Defines.BLACK
    t = create_search_engine(three)
    p = create_search_engine(two_pairs)
    assert t.count_live_sets(Defines.BLACK) > p.count_live_sets(Defines.BLACK)
    print("Eval Test 10 - Longer sets outweigh more shorter ones: PASS")


# ============================================================
# MIN-MAX SEARCH TESTS
# ============================================================

def create_winnable_board():
    board = create_empty_board()
    for y in range(3, 8):
        board[10][y] = Defines.BLACK
    board[9][7] = Defines.BLACK
    board[11][7] = Defines.BLACK
    board[9][8] = Defines.BLACK
    board[11][8] = Defines.BLACK
    return board


def placed_cells(move):
    return {
        (move.positions[0].x, move.positions[0].y),
        (move.positions[1].x, move.positions[1].y),
    }


def test_search_finds_winning_move():
    board = create_winnable_board()
    engine = create_search_engine(board, Defines.BLACK)
    best = StoneMove()
    score = engine.min_max_search(2, Defines.BLACK, best, create_move_at(10, 7))
    assert score == Defines.MAXINT
    assert (10, 8) in placed_cells(best)
    print("Search Test 7 - Min-max finds the winning move: PASS")


def test_search_blocks_threat():
    board = create_winnable_board()
    engine = create_search_engine(board, Defines.WHITE)
    best = StoneMove()
    score = engine.min_max_search(2, Defines.WHITE, best, create_move_at(10, 7))
    assert score < Defines.MAXINT
    assert (10, 8) in placed_cells(best)
    print("Search Test 8 - Min-max blocks the opponent's winning move: PASS")


def test_search_depth_grows_nodes():
    board = create_empty_board()
    board[10][10] = Defines.BLACK
    counts = []
    for depth in (1, 2, 3):
        engine = create_search_engine(board, Defines.WHITE)
        best = StoneMove()
        engine.min_max_search(depth, Defines.WHITE, best, create_move_at(10, 10))
        counts.append(engine.m_total_nodes)
    assert counts[0] < counts[1] < counts[2]
    print("Search Test 9 - Deeper searches explore more nodes: PASS")


def create_threat_board(run_length):
    board = create_empty_board()
    for y in range(9, 9 + run_length):
        board[9][y] = Defines.WHITE
    board[12][12] = Defines.BLACK
    board[12][13] = Defines.BLACK
    return board


def color_can_complete_six(board, color):
    for x in range(1, Defines.GRID_NUM - 6):
        for y in range(1, Defines.GRID_NUM - 6):
            for dx, dy in Defines.DIRECTIONS:
                if not (1 <= x + 5 * dx <= Defines.GRID_NUM - 2 and 1 <= y + 5 * dy <= Defines.GRID_NUM - 2):
                    continue
                stones = empties = 0
                blocked = False
                for k in range(6):
                    cell = board[x + k * dx][y + k * dy]
                    if cell == color:
                        stones += 1
                    elif cell == Defines.NOSTONE:
                        empties += 1
                    else:
                        blocked = True
                        break
                if not blocked and stones >= 4 and stones + empties == 6:
                    return True
    return False


def test_candidates_include_completion_pairs():
    board = create_threat_board(4)
    engine = create_search_engine(board, Defines.WHITE)
    candidates = engine.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
    pairs = {frozenset(placed_cells(move)) for move in candidates}
    assert frozenset({(9, 13), (9, 14)}) in pairs
    print("Search Test 10 - Two-stone completion pairs are generated: PASS")


def test_search_blocks_double_threat():
    board = create_threat_board(5)
    engine = create_search_engine(board, Defines.BLACK)
    best = StoneMove()
    engine.min_max_search(2, Defines.BLACK, best, create_move_at(9, 13))
    make_move(board, best, Defines.BLACK)
    assert not color_can_complete_six(board, Defines.WHITE)
    print("Search Test 11 - Min-max blocks a live five on both ends: PASS")


def test_search_blocks_two_stone_threat():
    board = create_threat_board(4)
    engine = create_search_engine(board, Defines.BLACK)
    best = StoneMove()
    engine.min_max_search(2, Defines.BLACK, best, create_move_at(9, 12))
    make_move(board, best, Defines.BLACK)
    assert not color_can_complete_six(board, Defines.WHITE)
    print("Search Test 12 - Min-max blocks a live four: PASS")


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

    print("\n========== EVALUATION TESTS ==========\n")
    test_evaluate_black_win()
    test_evaluate_white_win()
    test_evaluate_draw()
    test_evaluate_empty_board()
    test_evaluate_black_advantage()
    test_evaluate_white_advantage()
    test_evaluate_mirrored_board()
    test_dead_set_is_worthless()
    test_diagonal_equals_horizontal()
    test_longer_set_worth_more()

    print("\n========== MIN-MAX SEARCH TESTS ==========\n")
    test_search_finds_winning_move()
    test_search_blocks_threat()
    test_search_depth_grows_nodes()
    test_candidates_include_completion_pairs()
    test_search_blocks_double_threat()
    test_search_blocks_two_stone_threat()

    print("\n========== MOVE GENERATION TESTS ==========\n")
    test_candidate_limit()
    test_candidates_skip_occupied()
    test_candidates_near_stones()
    test_candidates_few_empties()
    test_candidates_full_board()
    test_candidates_custom_limit()

    print("\n========== ALL TESTS PASSED ==========\n")