from dataclasses import dataclass

from defines import (
    BORDER,
    Cell,
    CellPair,
    CompletionPair,
    DIRECTIONS,
    GRID_NUM,
    LIVE_WEIGHTS,
    MAXINT,
    MAX_CANDIDATE_CELLS,
    MAX_CANDIDATE_MOVES,
    MININT,
    NOSTONE,
    ScoredCell,
    Board,
    Color,
    GameResult,
    Move,
    Position,
)
from tools import check_game_end, make_move, measure_line, opponent, unmake_move


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Move
    score: int


class SearchEngine:
    def __init__(self) -> None:
        self.board: Board = []
        self.color: Color = Color.BLACK
        self.depth: int = 0
        self.node_count: int = 0

    def before_search(self, board: Board, color: Color, depth: int) -> None:
        self.board = [row[:] for row in board]
        self.color = color
        self.depth = depth
        self.node_count = 0

    def min_max_search(self, depth: int, our_color: Color, pre_move: Move) -> SearchResult:
        self.node_count += 1
        if self.is_first_move():
            center = Move((Position(10, 10), Position(10, 10)))
            return SearchResult(center, 0)

        candidates = self.generate_candidate_moves(MAX_CANDIDATE_MOVES)
        if len(candidates) == 0:
            return SearchResult(pre_move, self.evaluate(pre_move))

        maximizing = our_color == Color.BLACK
        best_score = MININT if maximizing else MAXINT
        best_candidate = candidates[0]
        for candidate in candidates:
            make_move(self.board, candidate, our_color)
            score = self.min_max(depth - 1, opponent(our_color), candidate)
            unmake_move(self.board, candidate)
            if maximizing:
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            else:
                if score < best_score:
                    best_score = score
                    best_candidate = candidate

        return SearchResult(best_candidate, best_score)

    def min_max(self, depth: int, our_color: Color, pre_move: Move) -> int:
        self.node_count += 1
        score = self.evaluate(pre_move)
        if score == MAXINT or score == MININT:
            return score
        if depth <= 0:
            return score

        candidates = self.generate_candidate_moves(MAX_CANDIDATE_MOVES)
        if len(candidates) == 0:
            return score

        maximizing = our_color == Color.BLACK
        best_score = MININT if maximizing else MAXINT
        for candidate in candidates:
            make_move(self.board, candidate, our_color)
            child = self.min_max(depth - 1, opponent(our_color), candidate)
            unmake_move(self.board, candidate)
            if maximizing:
                if child > best_score:
                    best_score = child
            else:
                if child < best_score:
                    best_score = child
        return best_score

    def is_first_move(self) -> bool:
        for i in range(1, GRID_NUM - 1):
            for j in range(1, GRID_NUM - 1):
                if self.board[i][j] != NOSTONE:
                    return False
        return True

    def get_scored_cells(self) -> list[ScoredCell]:
        scored: list[ScoredCell] = []
        fillers: list[ScoredCell] = []
        for i in range(1, GRID_NUM - 1):
            for j in range(1, GRID_NUM - 1):
                if self.board[i][j] != NOSTONE:
                    continue
                if self.count_neighbor_stones(i, j):
                    scored.append((self.score_position(i, j), i, j))
                else:
                    fillers.append((0, i, j))
        scored.sort(reverse=True)
        return scored + fillers

    def count_neighbor_stones(self, x: int, y: int) -> int:
        count = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                stone = self.board[x + dx][y + dy]
                if stone != NOSTONE and stone != BORDER:
                    count += 1
        return count

    def score_position(self, x: int, y: int) -> int:
        board = self.board
        total = 0
        for color in (Color.BLACK, Color.WHITE):
            board[x][y] = color.value
            value = 0
            for direction in DIRECTIONS:
                length, free, _, _ = measure_line(board, x, y, direction, 6, 6)
                if length + free >= 6:
                    value += LIVE_WEIGHTS[min(length, 5)]
            board[x][y] = NOSTONE
            total += value
        return total

    def generate_candidate_moves(self, limit: int) -> list[Move]:
        cells = self.get_scored_cells()[:MAX_CANDIDATE_CELLS]
        moves: list[Move] = []
        seen: set[CellPair] = set()
        for x1, y1, x2, y2 in self.find_completion_pairs(cells):
            self.try_add_candidate(moves, seen, limit, x1, y1, x2, y2)
        pairs: list[tuple[int, int, int]] = []
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                pairs.append((cells[i][0] + cells[j][0], i, j))
        pairs.sort(reverse=True)
        for _, i, j in pairs:
            if len(moves) >= limit:
                return moves
            self.try_add_candidate(moves, seen, limit, cells[i][1], cells[i][2], cells[j][1], cells[j][2])
        return moves

    def try_add_candidate(
        self,
        moves: list[Move],
        seen: set[CellPair],
        limit: int,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        if len(moves) >= limit:
            return
        a = (x1, y1)
        b = (x2, y2)
        key = (a, b) if a <= b else (b, a)
        if key in seen:
            return
        seen.add(key)
        moves.append(Move((Position(x1, y1), Position(x2, y2))))

    def find_completion_pairs(self, cells: list[ScoredCell]) -> list[CompletionPair]:
        board = self.board
        results: list[CompletionPair] = []
        for score, x, y in cells:
            if score < LIVE_WEIGHTS[5]:
                continue
            for color in (Color.BLACK, Color.WHITE):
                board[x][y] = color.value
                for direction in DIRECTIONS:
                    length, _, end_a, end_b = measure_line(board, x, y, direction, 6, 0)
                    if length == 5:
                        for end_x, end_y in (end_a, end_b):
                            if board[end_x][end_y] == NOSTONE:
                                results.append((x, y, end_x, end_y))
                board[x][y] = NOSTONE
        return results

    def evaluate(self, pre_move: Move) -> int:
        result = check_game_end(self.board, pre_move)
        if result == GameResult.WIN:
            winner = self.board[pre_move.positions[0].x][pre_move.positions[0].y]
            if winner == Color.BLACK:
                return MAXINT
            return MININT
        if result == GameResult.DRAW:
            return 0
        return self.count_live_sets(Color.BLACK) - self.count_live_sets(Color.WHITE)

    def count_live_sets(self, color: Color) -> int:
        value = 0
        for x in range(1, GRID_NUM - 1):
            for y in range(1, GRID_NUM - 1):
                if self.board[x][y] != color:
                    continue
                for direction in DIRECTIONS:
                    if self.board[x - direction[0]][y - direction[1]] == color.value:
                        continue
                    length, free, _, _ = measure_line(self.board, x, y, direction)
                    if length + free >= 6:
                        value += LIVE_WEIGHTS[min(length, 5)]
        return value