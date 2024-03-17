#!/usr/bin/env python

import asyncio
import json
import secrets

import websockets

from connect4 import PLAYER1, PLAYER2, Connect4


JOIN = {}
WATCH = {}


async def play(websocket, game: Connect4, player, connected):
    async for message in websocket:
        # Parse a "play" event from the UI.
        event = json.loads(message)
        assert event["type"] == "play"

        if game.last_player == player:
            # Send an "error" event if it's not our player's turn.
            event = {"type": "error", "message": "It's not your turn!"}
            await websocket.send(json.dumps(event))
            continue

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

        websockets.broadcast(connected, json.dumps(event))

        # If move is winning, send a "win" event.
        if game.last_player_won:
            win_event = {"type": "win", "player": game.last_player}
            websockets.broadcast(connected, json.dumps(win_event))


async def error(websocket, message):
    event = {"type": "error", "message": message}
    await websocket.send(json.dumps(event))


async def start(websocket):
    # Initialise a Connect Four game,
    # the set of WS connections receiving moves for this game,
    # and the join token.
    game = Connect4()
    connected = {websocket}

    join_token = secrets.token_urlsafe(12)
    JOIN[join_token] = game, connected

    watch_token = secrets.token_urlsafe(12)
    WATCH[watch_token] = game, connected

    try:
        # Send the join token to the browser of the first player,
        # where it'll be used for building a "join" link.
        event = {
            "type": "init",
            "join": join_token,
            "watch": watch_token,
        }
        await websocket.send(json.dumps(event))

        print("first player started game", id(game))
        await play(websocket, game, PLAYER1, connected)

    finally:
        del JOIN[join_token]


async def watch(websocket, watch_token):
    try:
        game, connected = WATCH[watch_token]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)

    # Catch up with game state
    for player, column, row in game.moves:
        # Send a "play" event to update the UI.
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row,
        }
        await websocket.send(json.dumps(event))

    try:
        print("watcher joined game", id(game))
        await websocket.wait_closed()
    finally:
        connected.remove(websocket)


async def join(websocket, join_key):
    # Find the Connect Four game.
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:
        print("second player joined game", id(game))
        await play(websocket, game, PLAYER2, connected)

    finally:
        connected.remove(websocket)


async def handler(websocket):
    # Receive and parse the "init" event from the UI.
    message = await websocket.recv()
    event = json.loads(message)
    assert event["type"] == "init"

    if "join" in event:
        # Second player joins an existing game.
        await join(websocket, event["join"])
    elif "watch" in event:
        # Spectators watch an existing game.
        await watch(websocket, event["watch"])
    else:
        # First player starts a new game.
        await start(websocket)


async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
