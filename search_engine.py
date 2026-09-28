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

    def alpha_beta_search(self, depth, alpha, beta, ourColor, bestMove, preMove): # change for min max

        #Check game result
        score = self.evaluate(preMove)
        if score == Defines.MAXINT or score == Defines.MININT:
            return score

        alpha = 0
        if(self.check_first_move()):
            bestMove.positions[0].x = 10
            bestMove.positions[0].y = 10
            bestMove.positions[1].x = 10
            bestMove.positions[1].y = 10
        else:
            candidates = self.generate_candidate_moves(Defines.MAX_CANDIDATE_MOVES)
            if len(candidates) > 0:
                candidate = candidates[0]
                bestMove.positions[0].x = candidate.positions[0].x
                bestMove.positions[0].y = candidate.positions[0].y
                bestMove.positions[1].x = candidate.positions[1].x
                bestMove.positions[1].y = candidate.positions[1].y
                make_move(self.m_board,bestMove,ourColor)

        return alpha

    def check_first_move(self):
        for i in range(1,len(self.m_board)-1):
            for j in range(1, len(self.m_board[i])-1):
                if(self.m_board[i][j] != Defines.NOSTONE):
                    return False
        return True

    def get_empty_positions(self):
        positions = []
        for i in range(1, len(self.m_board) - 1):
            for j in range(1, len(self.m_board[i]) - 1):
                if self.m_board[i][j] == Defines.NOSTONE:
                    positions.append(StonePosition(i, j))
        positions.sort(key=self.count_neighbor_stones, reverse=True)
        return positions

    def count_neighbor_stones(self, position):
        count = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                stone = self.m_board[position.x + dx][position.y + dy]
                if stone != Defines.NOSTONE and stone != Defines.BORDER:
                    count += 1
        return count

    def generate_candidate_moves(self, limit):
        positions = self.get_empty_positions()
        moves = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                move = StoneMove()
                move.positions[0] = positions[i]
                move.positions[1] = positions[j]
                moves.append(move)
                if len(moves) >= limit:
                    return moves
        return moves

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
                    length, free = measure_line(self.m_board, position, direction)
                    if length + free >= 6:
                        value += Defines.LIVE_WEIGHTS[min(length, 5)]
        return value

def flush_output():
    import sys
    sys.stdout.flush()
