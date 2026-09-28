import sys
import time
from collections.abc import Callable

from defines import (
    ENGINE_NAME,
    GRID_NUM,
    MSG_LENGTH,
    SEARCH_DEPTH,
    Board,
    Color,
    GameResult,
    Move,
    Position,
)
from search_engine import SearchEngine, SearchResult
from tools import (
    check_game_end,
    color_to_name,
    init_board,
    log_to_file,
    make_move,
    move2msg,
    msg2move,
    opponent,
    print_board,
)


def flush_output() -> None:
    sys.stdout.flush()


class GameEngine:
    def __init__(self, name: str = ENGINE_NAME) -> None:
        self.engine_name = "Tia.Connect6Engine"
        if name and len(name) > 0:
            if len(name) < MSG_LENGTH:
                self.engine_name = name
            else:
                print(f"Too long Engine Name: {name}, should be less than: {MSG_LENGTH}")
        self.search_depth = SEARCH_DEPTH
        self.color: Color | None = None
        self.vcf = False
        self.board: Board = [[0] * GRID_NUM for _ in range(GRID_NUM)]
        self.best_move = Move((Position(0, 0), Position(0, 0)))
        self.search_engine = SearchEngine()
        self.init_game()

    def init_game(self) -> None:
        init_board(self.board)

    def run(self) -> int:
        self.print_help()
        handlers: dict[str, Callable[[str], bool]] = {
            "name": self.cmd_name,
            "print": self.cmd_print,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
            "vcf": self.cmd_vcf,
            "unvcf": self.cmd_unvcf,
            "black": self.cmd_black,
            "white": self.cmd_white,
            "next": self.cmd_next,
            "new": self.cmd_new,
            "move": self.cmd_move,
            "depth": self.cmd_depth,
            "help": self.cmd_help,
        }
        while True:
            try:
                msg = input().strip()
            except EOFError:
                break
            log_to_file(msg)
            command, _, _ = msg.partition(" ")
            handler = handlers.get(command)
            if handler is not None and not handler(msg):
                break
        return 0

    def announce_end(self, color: Color, move: Move) -> bool:
        result = check_game_end(self.board, move)
        if result == GameResult.WIN:
            print(f"AI wins with {color_to_name(color)}!")
            return False
        if result == GameResult.DRAW:
            print("Draw!")
            return False
        return True

    def require_color(self) -> Color:
        if self.color is None:
            raise RuntimeError("no game in progress: start one with 'new black' or 'new white'")
        return self.color

    def search_and_play(self, pre_move: Move) -> bool:
        color = self.require_color()
        result = self.search_a_move(color, pre_move)
        self.best_move = result.move
        make_move(self.board, self.best_move, color)
        print(f"move {move2msg(self.best_move)}")
        flush_output()
        return self.announce_end(color, self.best_move)

    def search_a_move(self, color: Color, pre_move: Move) -> SearchResult:
        start = time.perf_counter()
        self.search_engine.before_search(self.board, color, self.search_depth)
        result = self.search_engine.min_max_search(self.search_depth, color, pre_move)
        end = time.perf_counter()

        print(f"Search Time:\t{end - start:.3f}")
        print(f"Node:\t{self.search_engine.node_count}\n")
        print(f"Score:\t{result.score:.3f}")
        return result

    def print_help(self) -> None:
        print(
            f"On help for GameEngine {self.engine_name}\n"
            " name        - print the name of the Game Engine.\n"
            " print       - print the board.\n"
            " exit/quit   - quit the game.\n"
            " black XXXX  - place the black stone on the position XXXX on the board.\n"
            " white XXXX  - place the white stone on the position XXXX on the board, X is from A to S.\n"
            " next        - the engine will search the move for the next step.\n"
            " move XXXX   - tell the engine that the opponent made the move XXXX,\n"
            "              and the engine will search the move for the next step.\n"
            " new black   - start a new game and set the engine to black player.\n"
            " new white   - start a new game and set it to white.\n"
            " depth d     - set the min-max search depth, default is 3.\n"
            " vcf         - set vcf search.\n"
            " unvcf       - set none vcf search.\n"
            " help        - print this help.\n")

    def cmd_name(self, msg: str) -> bool:
        print(f"name {self.engine_name}")
        return True

    def cmd_print(self, msg: str) -> bool:
        print_board(self.board, self.best_move)
        return True

    def cmd_exit(self, msg: str) -> bool:
        return False

    def cmd_vcf(self, msg: str) -> bool:
        self.vcf = True
        return True

    def cmd_unvcf(self, msg: str) -> bool:
        self.vcf = False
        return True

    def cmd_black(self, msg: str) -> bool:
        self.best_move = msg2move(msg[6:])
        make_move(self.board, self.best_move, Color.BLACK)
        self.color = Color.BLACK
        return True

    def cmd_white(self, msg: str) -> bool:
        self.best_move = msg2move(msg[6:])
        make_move(self.board, self.best_move, Color.WHITE)
        self.color = Color.WHITE
        return True

    def cmd_next(self, msg: str) -> bool:
        self.color = opponent(self.require_color())
        return self.search_and_play(self.best_move)

    def cmd_new(self, msg: str) -> bool:
        self.init_game()
        if msg[4:] == "black":
            self.best_move = msg2move("JJ")
            make_move(self.board, self.best_move, Color.BLACK)
            self.color = Color.BLACK
            print("move JJ")
            flush_output()
        else:
            self.color = Color.WHITE
        return True

    def cmd_move(self, msg: str) -> bool:
        color = self.require_color()
        self.best_move = msg2move(msg[5:])
        make_move(self.board, self.best_move, opponent(color))
        result = check_game_end(self.board, self.best_move)
        if result == GameResult.WIN:
            print(f"Human wins with {color_to_name(opponent(color))}!")
            return False
        if result == GameResult.DRAW:
            print("Draw!")
            return False
        return self.search_and_play(self.best_move)

    def cmd_depth(self, msg: str) -> bool:
        d = int(msg[6:])
        if 0 < d < 10:
            self.search_depth = d
        print(f"Set the search depth to {self.search_depth}.\n")
        return True

    def cmd_help(self, msg: str) -> bool:
        self.print_help()
        return True


if __name__ == "__main__":
    game_engine = GameEngine()
    game_engine.run()