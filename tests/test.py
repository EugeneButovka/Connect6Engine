import io
import os
import select
import subprocess
import sys
from contextlib import redirect_stdout

from connect6.board import init_board, _is_board_full, _is_win_by_move, check_game_end, copy_board, opponent, make_move
from connect6.game_engine import GameEngine
from connect6.protocol import color_to_name, move2msg, msg2move
from connect6.evaluation import evaluate, _score_living_sets
from connect6.candidates import generate_candidate_moves
from connect6.search import search_alpha_beta, search_min_max
from connect6.defines import (
    ENGINE_NAME,
    GRID_NUM,
    SetWeight,
    MAXINT,
    MAX_CANDIDATE_MOVES,
    MININT,
    NOSTONE,
    Color,
    DIRECTIONS,
    GameResult,
    Move,
    Position,
    SearchStats,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def create_empty_board():
    board = [[0] * GRID_NUM for _ in range(GRID_NUM)]
    init_board(board)
    return board


def create_move(x1, y1, x2, y2):
    return Move((Position(x1, y1), Position(x2, y2)))


def create_move_at(x, y):
    return create_move(x, y, x, y)


def fill_board_no_line(board):
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            board[i][j] = Color.BLACK if (i + 2 * j) % 5 < 2 else Color.WHITE


# ============================================================
# BOARD TESTS
# ============================================================

def test_empty_board():
    board = create_empty_board()
    assert _is_board_full(board) == False
    print("Board Test 1 - Empty board: PASS")


def test_one_stone():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    assert _is_board_full(board) == False
    print("Board Test 2 - One stone: PASS")


def test_almost_full_board():
    board = create_empty_board()
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            board[i][j] = Color.BLACK
    board[10][10] = NOSTONE
    assert _is_board_full(board) == False
    print("Board Test 3 - Almost full board: PASS")


def test_full_board():
    board = create_empty_board()
    for i in range(1, GRID_NUM - 1):
        for j in range(1, GRID_NUM - 1):
            board[i][j] = Color.BLACK
    assert _is_board_full(board) == True
    print("Board Test 4 - Full board: PASS")


# ============================================================
# WIN TESTS
# ============================================================

def test_horizontal_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Color.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == GameResult.WIN
    print("Win Test 1 - Horizontal 6: PASS")


def test_vertical_win():
    board = create_empty_board()
    for x in range(5, 11):
        board[x][10] = Color.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == GameResult.WIN
    print("Win Test 2 - Vertical 6: PASS")


def test_diagonal_win():
    board = create_empty_board()
    for i in range(6):
        board[5 + i][5 + i] = Color.BLACK
    assert check_game_end(board, create_move_at(5, 5)) == GameResult.WIN
    print("Win Test 3 - Diagonal 6: PASS")


def test_anti_diagonal_win():
    board = create_empty_board()
    for i in range(6):
        board[5 + i][10 - i] = Color.BLACK
    assert check_game_end(board, create_move_at(5, 10)) == GameResult.WIN
    print("Win Test 4 - Anti-diagonal 6: PASS")


def test_five_not_win():
    board = create_empty_board()
    for y in range(5, 10):
        board[10][y] = Color.BLACK
    assert check_game_end(board, create_move_at(10, 9)) is None
    print("Win Test 5 - Five in a row: PASS")


def test_seven_win():
    board = create_empty_board()
    for y in range(4, 11):
        board[10][y] = Color.BLACK
    assert check_game_end(board, create_move_at(10, 10)) == GameResult.WIN
    print("Win Test 6 - Seven in a row: PASS")


def test_broken_sequence():
    board = create_empty_board()
    for y in range(5, 8):
        board[10][y] = Color.BLACK
    board[10][8] = Color.WHITE
    for y in range(9, 11):
        board[10][y] = Color.BLACK
    assert check_game_end(board, create_move_at(10, 10)) is None
    print("Win Test 7 - Broken sequence: PASS")


def test_white_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Color.WHITE
    assert check_game_end(board, create_move_at(10, 10)) == GameResult.WIN
    assert _is_win_by_move(board, create_move_at(10, 10)) == True
    print("Win Test 8 - White win: PASS")


# ============================================================
# DRAW TESTS
# ============================================================

def test_full_board_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    assert check_game_end(board, create_move_at(10, 10)) == GameResult.DRAW
    print("Draw Test 1 - Full board: PASS")


def test_win_beats_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    for y in range(2, 8):
        board[5][y] = Color.BLACK
    assert check_game_end(board, create_move_at(5, 7)) == GameResult.WIN
    print("Draw Test 2 - Win beats draw: PASS")


# ============================================================
# COLOR TESTS
# ============================================================

def test_color_names():
    assert color_to_name(Color.BLACK) == "black"
    assert color_to_name(Color.WHITE) == "white"
    print("Color Test 1 - Names: PASS")


def test_opponent():
    assert opponent(Color.BLACK) == Color.WHITE
    assert opponent(Color.WHITE) == Color.BLACK
    print("Color Test 2 - Opponent: PASS")


# ============================================================
# MOVE GENERATION TESTS
# ============================================================

def candidates_are_valid(board, candidates):
    for move in candidates:
        for p in move.positions:
            assert 0 < p.x < GRID_NUM - 1
            assert 0 < p.y < GRID_NUM - 1
            assert board[p.x][p.y] == NOSTONE
        assert move.positions[0].x != move.positions[1].x or move.positions[0].y != move.positions[1].y
    return True


def test_candidate_limit():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    assert len(candidates) == MAX_CANDIDATE_MOVES
    assert candidates_are_valid(board, candidates)
    print("Search Test 1 - Fixed limit of candidates: PASS")


def test_candidates_skip_occupied():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    for move in candidates:
        assert board[move.positions[0].x][move.positions[0].y] == NOSTONE
        assert board[move.positions[1].x][move.positions[1].y] == NOSTONE
    print("Search Test 2 - Skip occupied positions: PASS")


def test_candidates_near_stones():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    first = candidates[0]
    assert abs(first.positions[0].x - 10) <= 1 and abs(first.positions[0].y - 10) <= 1
    print("Search Test 3 - Candidates ordered near stones: PASS")


def test_candidates_few_empties():
    board = create_empty_board()
    fill_board_no_line(board)
    board[5][2] = NOSTONE
    board[5][3] = NOSTONE
    board[5][4] = NOSTONE
    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    assert len(candidates) == 3
    print("Search Test 4 - Few empties produce all pairs: PASS")


def test_candidates_full_board():
    board = create_empty_board()
    fill_board_no_line(board)
    assert generate_candidate_moves(board, MAX_CANDIDATE_MOVES) == []
    print("Search Test 5 - No candidates on full board: PASS")


def test_candidates_custom_limit():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    assert len(generate_candidate_moves(board, 5)) == 5
    print("Search Test 6 - Custom limit: PASS")


# ============================================================
# EVALUATION TESTS
# ============================================================

def test_evaluate_black_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Color.BLACK
    assert evaluate(board, create_move_at(10, 10)) == MAXINT
    print("Eval Test 1 - Black win returns MAXINT: PASS")


def test_evaluate_white_win():
    board = create_empty_board()
    for y in range(5, 11):
        board[10][y] = Color.WHITE
    assert evaluate(board, create_move_at(10, 10)) == MININT
    print("Eval Test 2 - White win returns MININT: PASS")


def test_evaluate_draw():
    board = create_empty_board()
    fill_board_no_line(board)
    assert evaluate(board, create_move_at(10, 10)) == 0
    print("Eval Test 3 - Draw returns 0: PASS")


def test_evaluate_empty_board():
    board = create_empty_board()
    assert evaluate(board, create_move_at(10, 10)) == 0
    print("Eval Test 4 - Empty board is balanced: PASS")


def test_evaluate_black_advantage():
    board = create_empty_board()
    for y in range(3, 7):
        board[10][y] = Color.BLACK
    for y in range(3, 5):
        board[15][y] = Color.WHITE
    score = evaluate(board, create_move_at(10, 10))
    assert score > 0
    assert score > SetWeight.TRIPLE
    print("Eval Test 5 - Black advantage is positive: PASS")


def test_evaluate_white_advantage():
    board = create_empty_board()
    for y in range(3, 7):
        board[10][y] = Color.WHITE
    for y in range(3, 5):
        board[15][y] = Color.BLACK
    score = evaluate(board, create_move_at(10, 10))
    assert score < 0
    assert score < -SetWeight.TRIPLE
    print("Eval Test 6 - White advantage is negative: PASS")


def test_evaluate_mirrored_board():
    board = create_empty_board()
    for y in range(3, 6):
        board[5][y] = Color.BLACK
        board[15][y] = Color.WHITE
    assert evaluate(board, create_move_at(10, 10)) == 0
    print("Eval Test 7 - Mirrored board is balanced: PASS")


def test_dead_set_is_worthless():
    dead = create_empty_board()
    for y in range(8, 12):
        dead[10][y] = Color.BLACK
    dead[10][7] = Color.WHITE
    dead[10][12] = Color.WHITE
    open_board = create_empty_board()
    for y in range(8, 12):
        open_board[10][y] = Color.BLACK
    assert _score_living_sets(open_board, Color.BLACK) - _score_living_sets(dead, Color.BLACK) == SetWeight.LIVE_FOUR
    print("Eval Test 8 - Dead set contributes nothing: PASS")


def test_diagonal_equals_horizontal():
    horizontal = create_empty_board()
    for y in range(3, 6):
        horizontal[10][y] = Color.BLACK
    diagonal = create_empty_board()
    for i in range(3):
        diagonal[10 + i][4 + i] = Color.BLACK
    assert _score_living_sets(horizontal, Color.BLACK) == _score_living_sets(diagonal, Color.BLACK)
    assert _score_living_sets(horizontal, Color.BLACK) > SetWeight.TRIPLE
    print("Eval Test 9 - All line axes are covered equally: PASS")


def test_longer_set_worth_more():
    three = create_empty_board()
    for y in range(3, 6):
        three[10][y] = Color.BLACK
    two_pairs = create_empty_board()
    for y in range(3, 5):
        two_pairs[10][y] = Color.BLACK
        two_pairs[15][y] = Color.BLACK
    assert _score_living_sets(three, Color.BLACK) > _score_living_sets(two_pairs, Color.BLACK)
    print("Eval Test 10 - Longer sets outweigh more shorter ones: PASS")


# ============================================================
# MIN-MAX SEARCH TESTS
# ============================================================

def create_winnable_board():
    board = create_empty_board()
    for y in range(3, 8):
        board[10][y] = Color.BLACK
    board[9][7] = Color.BLACK
    board[11][7] = Color.BLACK
    board[9][8] = Color.BLACK
    board[11][8] = Color.BLACK
    return board


def placed_cells(move):
    return {
        (move.positions[0].x, move.positions[0].y),
        (move.positions[1].x, move.positions[1].y),
    }


def test_search_finds_winning_move():
    board = create_winnable_board()
    result = search_min_max(board, Color.BLACK, 2, create_move_at(10, 7), SearchStats())
    assert result.score == MAXINT
    assert (10, 8) in placed_cells(result.move)
    print("Search Test 7 - Min-max finds the winning move: PASS")


def test_search_blocks_threat():
    board = create_winnable_board()
    result = search_min_max(board, Color.WHITE, 2, create_move_at(10, 7), SearchStats())
    assert result.score < MAXINT
    assert (10, 8) in placed_cells(result.move)
    print("Search Test 8 - Min-max blocks the opponent's winning move: PASS")


def test_search_depth_grows_nodes():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    counts = []
    for depth in (1, 2, 3):
        stats = SearchStats()
        search_min_max(board, Color.WHITE, depth, create_move_at(10, 10), stats)
        counts.append(stats.node_count)
    assert counts[0] < counts[1] < counts[2]
    print("Search Test 9 - Deeper searches explore more nodes: PASS")


def create_threat_board(run_length):
    board = create_empty_board()
    for y in range(9, 9 + run_length):
        board[9][y] = Color.WHITE
    board[12][12] = Color.BLACK
    board[12][13] = Color.BLACK
    return board


def color_can_complete_six(board, color):
    for x in range(1, GRID_NUM - 6):
        for y in range(1, GRID_NUM - 6):
            for dx, dy in DIRECTIONS:
                if not (1 <= x + 5 * dx <= GRID_NUM - 2 and 1 <= y + 5 * dy <= GRID_NUM - 2):
                    continue
                stones = empties = 0
                blocked = False
                for k in range(6):
                    cell = board[x + k * dx][y + k * dy]
                    if cell == color:
                        stones += 1
                    elif cell == NOSTONE:
                        empties += 1
                    else:
                        blocked = True
                        break
                if not blocked and stones >= 4 and stones + empties == 6:
                    return True
    return False


def test_candidates_include_completion_pairs():
    board = create_threat_board(4)
    candidates = generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    pairs = {frozenset(placed_cells(move)) for move in candidates}
    assert frozenset({(9, 13), (9, 14)}) in pairs
    print("Search Test 10 - Two-stone completion pairs are generated: PASS")


def test_search_blocks_double_threat():
    board = create_threat_board(5)
    result = search_min_max(board, Color.BLACK, 2, create_move_at(9, 13), SearchStats())
    make_move(board, result.move, Color.BLACK)
    assert not color_can_complete_six(board, Color.WHITE)
    print("Search Test 11 - Min-max blocks a live five on both ends: PASS")


def test_search_blocks_two_stone_threat():
    board = create_threat_board(4)
    result = search_min_max(board, Color.BLACK, 2, create_move_at(9, 12), SearchStats())
    make_move(board, result.move, Color.BLACK)
    assert not color_can_complete_six(board, Color.WHITE)
    print("Search Test 12 - Min-max blocks a live four: PASS")


def test_search_and_candidates_do_not_mutate_board():
    board = create_threat_board(4)
    snapshot = copy_board(board)
    generate_candidate_moves(board, MAX_CANDIDATE_MOVES)
    assert board == snapshot
    search_min_max(board, Color.BLACK, 2, create_move_at(9, 13), SearchStats())
    assert board == snapshot
    print("Search Test 13 - Search and candidates leave the input board untouched: PASS")


def test_alpha_beta_finds_winning_move():
    board = create_winnable_board()
    result = search_alpha_beta(board, Color.BLACK, 2, create_move_at(10, 7), SearchStats())
    assert result.score == MAXINT
    assert (10, 8) in placed_cells(result.move)
    print("Search Test 14 - Alpha-beta finds the winning move: PASS")


def test_alpha_beta_matches_min_max():
    for threat, pre in ((4, (9, 12)), (5, (9, 13))):
        board = create_threat_board(threat)
        pre_move = create_move_at(*pre)
        naive = search_min_max(board, Color.BLACK, 2, pre_move, SearchStats())
        pruned = search_alpha_beta(board, Color.BLACK, 2, pre_move, SearchStats())
        assert pruned.score == naive.score
        make_move(board, pruned.move, Color.BLACK)
        assert not color_can_complete_six(board, Color.WHITE)
    print("Search Test 15 - Alpha-beta matches min-max on score and forced blocks: PASS")


def test_alpha_beta_visits_fewer_nodes():
    board = create_empty_board()
    board[10][10] = Color.BLACK
    pre_move = create_move_at(10, 10)
    naive_stats = SearchStats()
    pruned_stats = SearchStats()
    search_min_max(board, Color.WHITE, 3, pre_move, naive_stats)
    search_alpha_beta(board, Color.WHITE, 3, pre_move, pruned_stats)
    assert pruned_stats.node_count < naive_stats.node_count
    print("Search Test 16 - Alpha-beta visits fewer nodes: PASS")


# ============================================================
# PROTOCOL TESTS (GUI CONTRACT, Connect6GUI/engine.py)
# ============================================================

class ProtocolEngine:
    """Drives the engine binary the same way the GUI does: raw pipes,
    line-based commands, replies found by prefix scanning."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "main.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=PROJECT_ROOT,
        )
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        self.stdin = self.proc.stdin
        self.stdout = self.proc.stdout
        self.stderr = self.proc.stderr
        self.lines = []
        self.sent = []

    def send(self, cmd):
        self.sent.append(cmd)
        self.stdin.write((cmd + "\n").encode())

    def next_line(self):
        ready, _, _ = select.select([self.stdout], [], [], 15.0)
        assert ready, f"no engine output within 15s after commands: {self.sent[-3:]}"
        line = self.stdout.readline().decode()
        assert line, "engine exited unexpectedly"
        line = line.rstrip("\n")
        self.lines.append(line)
        return line

    def read_until(self, prefix):
        while True:
            line = self.next_line()
            if line.startswith(prefix):
                return line

    def drain_startup(self):
        self.send("name")
        return self.read_until("name ")

    def close(self):
        self.stdin.close()
        self.proc.terminate()
        self.proc.wait(timeout=10)
        return self.stderr.read().decode()


def capture_output(fn):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = fn()
    return result, buffer.getvalue()


def test_protocol_name_handshake():
    engine = ProtocolEngine()
    engine.send("name")
    reply = engine.read_until("name ")
    assert reply == f"name {ENGINE_NAME}"
    assert all(
        not line.startswith("name ") and not line.startswith("move ")
        for line in engine.lines[:-1]
    )
    engine.close()
    print("Protocol Test 1 - name handshake replies without prefix collisions: PASS")


def test_protocol_depth_configuration():
    engine = ProtocolEngine()
    engine.send("depth 2")
    assert engine.read_until("Set the search depth") == "Set the search depth to 2."
    engine.send("depth 0")
    assert engine.read_until("Set the search depth") == "Set the search depth to 2."
    engine.send("depth 99")
    assert engine.read_until("Set the search depth") == "Set the search depth to 2."
    engine.send("depth 1")
    assert engine.read_until("Set the search depth") == "Set the search depth to 1."
    engine.close()
    print("Protocol Test 2 - depth command configures the search depth: PASS")


def test_protocol_vcf_commands_are_silent():
    engine = ProtocolEngine()
    engine.drain_startup()
    engine.send("vcf")
    engine.send("unvcf")
    engine.send("name")
    assert engine.next_line() == f"name {ENGINE_NAME}"
    engine.close()
    print("Protocol Test 3 - vcf/unvcf are accepted without any output: PASS")


def test_protocol_gui_replay_flow():
    engine = ProtocolEngine()
    engine.send("depth 1")
    engine.read_until("Set the search depth")
    engine.send("new xxx")
    engine.send("black JIJK")
    engine.send("white KJKJ")
    engine.send("next")
    reply = engine.read_until("move ")
    coords = reply[5:]
    assert len(coords) == 4
    assert all("A" <= c <= "S" for c in coords)
    assert all(not line.startswith("move ") for line in engine.lines[:-1])
    engine.close()
    print("Protocol Test 4 - GUI replay (new xxx + places + next) gets a move: PASS")


def test_protocol_engine_first_center_opening():
    engine = ProtocolEngine()
    engine.send("new xxx")
    engine.send("next")
    assert engine.read_until("move ") == "move JJ"
    engine.close()
    print("Protocol Test 5 - engine-first game opens with 2-char 'move JJ': PASS")


def test_protocol_move_command_loop():
    engine = ProtocolEngine()
    engine.send("depth 1")
    engine.read_until("Set the search depth")
    engine.send("new white")
    engine.send("move JILL")
    first = engine.read_until("move ")
    assert all("A" <= c <= "S" for c in first[5:])
    engine.send("move ABAF")
    second = engine.read_until("move ")
    assert all("A" <= c <= "S" for c in second[5:])
    engine.close()
    print("Protocol Test 6 - move command loop keeps the game going: PASS")


def test_protocol_announces_human_win():
    engine = GameEngine()
    engine._cmd_new("new white")
    for y in range(5, 10):
        engine.board[10][y] = Color.BLACK.value
    human = move2msg(Move((Position(10, 4), Position(15, 15))))
    result, output = capture_output(lambda: engine._cmd_move(f"move {human}"))
    assert result is False
    assert "Human wins with black!" in output
    print("Protocol Test 7 - human win ends the game with announcement: PASS")


def test_protocol_announces_ai_win():
    engine = GameEngine()
    human = move2msg(Move((Position(15, 15), Position(16, 16))))

    def scenario():
        engine._cmd_new("new black")
        engine._cmd_depth("depth 1")
        for y in range(5, 9):
            engine.board[5][y] = Color.BLACK.value
        return engine._cmd_move(f"move {human}")

    result, output = capture_output(scenario)
    assert result is False
    assert "AI wins with black!" in output
    print("Protocol Test 8 - AI win ends the game with announcement: PASS")


def test_msg2move_rejects_invalid_messages():
    assert msg2move("JJ").positions[0] == Position(10, 10)
    assert msg2move("JILL").positions[1] == Position(8, 12)
    for bad in ("", "X", "XYZ", "JJJ", "ZJ", "JT", "AAAAA"):
        try:
            msg2move(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"msg2move accepted {bad!r}")
    print("Protocol Test 9 - msg2move validates message format and coordinates: PASS")


def test_protocol_malformed_commands_do_not_kill_engine():
    log_path = os.path.join(PROJECT_ROOT, "tia-engine.log")
    log_size_before = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    engine = ProtocolEngine()
    engine.send("depth 1")
    engine.read_until("Set the search depth")
    assert engine.next_line() == ""
    engine.send("new white")
    for bad in ("depth abc", "move XYZ", "move ZZZZ", "move", "black", "nonsense"):
        engine.send(bad)
    engine.send("name")
    assert engine.next_line() == f"name {ENGINE_NAME}"
    engine.send("move JILL")
    reply = engine.read_until("move ")
    assert all("A" <= c <= "S" for c in reply[5:])
    errors = engine.close()
    for bad in ("depth abc", "move XYZ", "move ZZZZ", "move", "black"):
        assert f"Error processing '{bad}'" in errors
    assert "nonsense" not in errors
    with open(log_path) as log_file:
        log_file.seek(log_size_before)
        session_log = log_file.read()
    for bad in ("depth abc", "move XYZ", "move ZZZZ", "move", "black"):
        assert f"ERROR: Error processing '{bad}'" in session_log
    assert "- move JILL" in session_log
    print("Protocol Test 10 - malformed commands never kill the engine: PASS")


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
    test_search_and_candidates_do_not_mutate_board()
    test_alpha_beta_finds_winning_move()
    test_alpha_beta_matches_min_max()
    test_alpha_beta_visits_fewer_nodes()

    print("\n========== MOVE GENERATION TESTS ==========\n")
    test_candidate_limit()
    test_candidates_skip_occupied()
    test_candidates_near_stones()
    test_candidates_few_empties()
    test_candidates_full_board()
    test_candidates_custom_limit()

    print("\n========== PROTOCOL TESTS (GUI CONTRACT) ==========\n")
    test_protocol_name_handshake()
    test_protocol_depth_configuration()
    test_protocol_vcf_commands_are_silent()
    test_protocol_gui_replay_flow()
    test_protocol_engine_first_center_opening()
    test_protocol_move_command_loop()
    test_protocol_announces_human_win()
    test_protocol_announces_ai_win()
    test_msg2move_rejects_invalid_messages()
    test_protocol_malformed_commands_do_not_kill_engine()

    print("\n========== ALL TESTS PASSED ==========\n")