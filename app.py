#!/usr/bin/env python

import asyncio
import itertools
import json

import websockets

from connect4 import PLAYER1, PLAYER2, Connect4


async def handler(websocket):
    # Initalise a Connect Four game.
    game = Connect4()

    # Players take alternating turns, using the same browser.
    turns = itertools.cycle([PLAYER1, PLAYER2])
    player = next(turns)

    async for message in websocket:
        # Parse a "play" event from the UI.
        event = json.loads(message)
        assert event["type"] == "play"
        column = event["column"]

        try:
            # Play the move.
            row = game.play(player, column)
        except RuntimeError as err:
            # Send an "error" event if the move was illegal.
            error_event = {"type": "error", "message": str(err)}
            await websocket.send(json.dumps(error_event))
            continue

        # Send a "play" event to update the UI.
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row,
        }
        await websocket.send(json.dumps(event))

        # If move is winning, send a "win" event.
        if game.last_player_won:
            win_event = {"type": "win", "player": game.last_player}
            await websocket.send(json.dumps(win_event))

        # Alternate turns.
        player = next(turns)


async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
