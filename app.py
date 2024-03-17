#!/usr/bin/env python
import os
import signal
import asyncio
import json
import secrets

import websockets

from connect4 import PLAYER1, PLAYER2, Connect4


JOIN = {}
WATCH = {}


async def error(websocket, message):
    """
    Send an error message.

    """
    event = {"type": "error", "message": message}
    await websocket.send(json.dumps(event))


async def replay(websocket, game):
    """
    Send previous moves.

    """
    # Make a copy to avoid an exception if game.moves changes while iteration is in progress.
    # If a move is played while replay is running, moves will be sent out of order but each move
    # will be sent once and eventually the UI will be consistent.
    for player, column, row in game.moves.copy():
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row,
        }
        await websocket.send(json.dumps(event))


async def play(websocket, game: Connect4, player, connected):
    """
    Receive and process moves from a player.

    """
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
        websockets.broadcast(connected, json.dumps(event))

        # If move is winning, send a "win" event.
        if game.last_player_won:
            win_event = {"type": "win", "player": game.last_player}
            websockets.broadcast(connected, json.dumps(win_event))


async def start(websocket):
    """
    Handle a connection from the first player: start a new game.

    """
    # Initialise a Connect Four game,
    # the set of WS connections receiving moves for this game,
    # and the join / watch tokens.
    game = Connect4()
    connected = {websocket}

    join_token = secrets.token_urlsafe(12)
    JOIN[join_token] = game, connected

    watch_token = secrets.token_urlsafe(12)
    WATCH[watch_token] = game, connected

    try:
        # Send the join / watch tokens to the browser of the first player,
        # where they'll be used for building "join" and "watch" links.
        event = {
            "type": "init",
            "join": join_token,
            "watch": watch_token,
        }
        await websocket.send(json.dumps(event))

        print("Player 1 started a game with ID:", id(game))
        # Receive and process moves from the first player.
        await play(websocket, game, PLAYER1, connected)

    finally:
        del JOIN[join_token]
        del WATCH[watch_token]


async def watch(websocket, watch_token):
    """
    Handle a connection from a spectator: watch an existing game.

    """
    try:
        game, connected = WATCH[watch_token]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:
        print("Watcher joined game with ID:", id(game))
        # Send previous moves, in case the game has already started.
        await replay(websocket, game)
        # Keep the connection open, but don't receive any messages.
        await websocket.wait_closed()
    finally:
        connected.remove(websocket)


async def join(websocket, join_key):
    """
    Handle a connection from the second player: join an existing game.

    """
    # Find the Connect Four game.
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:
        print("Player 2 joined a game with ID:", id(game))
        # Send the first move, in case the first player already played it.
        await replay(websocket, game)
        # Receive and process moves from the second player.
        await play(websocket, game, PLAYER2, connected)
    finally:
        connected.remove(websocket)


async def handler(websocket):
    """
    Handle a connection and dispatch it according to who is connecting.

    """
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
    # Set the stop condition when receiving SIGTERM.
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

    port = int(os.environ.get("PORT", "8001"))
    async with websockets.serve(handler, "", port):
        await stop


if __name__ == "__main__":
    asyncio.run(main())
