from tools import *


class SearchEngine():
    def __init__(self):
        self.m_board = None
        self.m_chess_type = None
        self.m_alphabeta_depth = None
        self.m_total_nodes = 0

    def before_search(self, board, color, alphabeta_depth):
        self.m_board = [row[:] for row in board]
        self.m_chess_type = color
        self.m_alphabeta_depth = alphabeta_depth
        self.m_total_nodes = 0

    def alpha_beta_search(self, depth, alpha, beta, ourColor, bestMove, preMove):

        self.m_total_nodes += 1
        if self.check_first_move():
            bestMove.positions[0].x = 10
            bestMove.positions[0].y = 10
            bestMove.positions[1].x = 10
            bestMove.positions[1].y = 10
            return 0

        candidates = self.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
        if len(candidates) == 0:
            return self.evaluate(preMove)

        maximizing = ourColor == Defines.BLACK
        best_score = Defines.MININT if maximizing else Defines.MAXINT
        best_candidate = candidates[0]
        for candidate in candidates:
            make_move(self.m_board, candidate, ourColor)
            score = self.min_max(depth - 1, opponent(ourColor), candidate)
            unmake_move(self.m_board, candidate)
            if maximizing:
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            else:
                if score < best_score:
                    best_score = score
                    best_candidate = candidate

        bestMove.positions[0].x = best_candidate.positions[0].x
        bestMove.positions[0].y = best_candidate.positions[0].y
        bestMove.positions[1].x = best_candidate.positions[1].x
        bestMove.positions[1].y = best_candidate.positions[1].y
        return best_score

    def min_max(self, depth, ourColor, preMove):
        self.m_total_nodes += 1
        score = self.evaluate(preMove)
        if score == Defines.MAXINT or score == Defines.MININT:
            return score
        if depth <= 0:
            return score

        candidates = self.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
        if len(candidates) == 0:
            return score

        maximizing = ourColor == Defines.BLACK
        best_score = Defines.MININT if maximizing else Defines.MAXINT
        for candidate in candidates:
            make_move(self.m_board, candidate, ourColor)
            child = self.min_max(depth - 1, opponent(ourColor), candidate)
            unmake_move(self.m_board, candidate)
            if maximizing:
                if child > best_score:
                    best_score = child
            else:
                if child < best_score:
                    best_score = child
        return best_score

    def check_first_move(self):
        for i in range(1, len(self.m_board) - 1):
            for j in range(1, len(self.m_board[i]) - 1):
                if (self.m_board[i][j] != Defines.NOSTONE):
                    return False
        return True

    def get_empty_positions(self):
        scored = []
        fillers = []
        for i in range(1, len(self.m_board) - 1):
            for j in range(1, len(self.m_board[i]) - 1):
                if self.m_board[i][j] != Defines.NOSTONE:
                    continue
                if self.count_neighbor_stones(i, j):
                    scored.append((self.score_position(i, j), i, j))
                else:
                    fillers.append((0, i, j))
        scored.sort(reverse=True)
        return scored + fillers

    def count_neighbor_stones(self, x, y):
        count = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                stone = self.m_board[x + dx][y + dy]
                if stone != Defines.NOSTONE and stone != Defines.BORDER:
                    count += 1
        return count

    def score_position(self, x, y):
        board = self.m_board
        total = 0
        position = StonePosition(x, y)
        total = 0
        for color in (Defines.BLACK, Defines.WHITE):
            board[x][y] = color
            value = 0
            for direction in Defines.DIRECTIONS:
                length, free, _, _ = measure_line(board, position, direction, 6, 6)
                if length + free >= 6:
                    value += Defines.LIVE_WEIGHTS[min(length, 5)]
            board[x][y] = Defines.NOSTONE
            total += value
        return total

    def generate_candidate_moves(self, limit):
        cells = self.get_empty_positions()[:Defines.MAX_CANDIDATE_CELLS]
        moves = []
        seen = set()
        for x1, y1, x2, y2 in self.find_completion_pairs(cells):
            self.add_candidate(moves, seen, limit, x1, y1, x2, y2)
        pairs = []
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                pairs.append((cells[i][0] + cells[j][0], i, j))
        pairs.sort(reverse=True)
        for _, i, j in pairs:
            if len(moves) >= limit:
                return moves
            self.add_candidate(moves, seen, limit, cells[i][1], cells[i][2], cells[j][1], cells[j][2])
        return moves

    def add_candidate(self, moves, seen, limit, x1, y1, x2, y2):
        if len(moves) >= limit:
            return
        key = tuple(sorted(((x1, y1), (x2, y2))))
        if key in seen:
            return
        seen.add(key)
        move = StoneMove()
        move.positions[0] = StonePosition(x1, y1)
        move.positions[1] = StonePosition(x2, y2)
        moves.append(move)

    def find_completion_pairs(self, cells):
        board = self.m_board
        results = []
        for score, x, y in cells:
            if score < Defines.LIVE_WEIGHTS[5]:
                continue
            position = StonePosition(x, y)
            for color in (Defines.BLACK, Defines.WHITE):
                board[x][y] = color
                for direction in Defines.DIRECTIONS:
                    length, _, end_a, end_b = measure_line(board, position, direction, 6, 0)
                    if length == 5:
                        for end_x, end_y in (end_a, end_b):
                            if board[end_x][end_y] == Defines.NOSTONE:
                                results.append((x, y, end_x, end_y))
                board[x][y] = Defines.NOSTONE
        return results

    def evaluate(self, preMove):
        result = check_game_end(self.m_board, preMove)
        if result == Defines.WIN:
            winner = self.m_board[preMove.positions[0].x][preMove.positions[0].y]
            if winner == Defines.BLACK:
                return Defines.MAXINT
            return Defines.MININT
        if result == Defines.DRAW:
            return 0
        return self.count_live_sets(Defines.BLACK) - self.count_live_sets(Defines.WHITE)

    def count_live_sets(self, color):
        value = 0
        for x in range(1, Defines.GRID_NUM - 1):
            for y in range(1, Defines.GRID_NUM - 1):
                if self.m_board[x][y] != color:
                    continue
                position = StonePosition(x, y)
                for direction in Defines.DIRECTIONS:
                    if self.m_board[x - direction[0]][y - direction[1]] == color:
                        continue
                    position = StonePosition(x, y)
                    length, free, _, _ = measure_line(self.m_board, position, direction)
                    if length + free >= 6:
                        value += Defines.LIVE_WEIGHTS[min(length, 5)]
        return value


def flush_output():
    import sys
    sys.stdout.flush()
