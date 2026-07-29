import chess
from engine import evaluate_board, PAWN_TABLE

b1 = chess.Board('4k3/8/8/8/4P3/8/8/4K3 w - - 0 1')
b2 = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 0 1')
for board in (b1, b2):
    for square in chess.SquareSet(board.pieces(chess.PAWN, chess.WHITE)):
        print(square, chess.square_name(square), PAWN_TABLE[square])
    print('board eval', evaluate_board(board))
    print('---')
print(chess.square_file(chess.E2), chess.square_rank(chess.E2))
print(chess.square_file(chess.E4), chess.square_rank(chess.E4))
