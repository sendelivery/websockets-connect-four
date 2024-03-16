#!/usr/bin/env python

import asyncio

import websockets

import json

from connect4 import PLAYER1, PLAYER2, Connect4


async def handler(websocket):
    # Initalise a Connect Four game.
    game = Connect4()

    async for message in websocket:
        try:
            event = json.loads(message)

            player = PLAYER2 if len(game.moves) % 2 else PLAYER1
            column = event["column"]
            row = game.play(player, column)

            event = {
                "type": "play",
                "player": player,
                "column": column,
                "row": row,
            }
            await websocket.send(json.dumps(event))
        except RuntimeError:
            error_event = {"type": "error", "message": "Move is illegal."}
            await websocket.send(json.dumps(error_event))

        if game.last_player_won:
            win_event = {"type": "win", "player": game.last_player}
            await websocket.send(json.dumps(win_event))


async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
