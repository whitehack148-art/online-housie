import random
import string
import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from game import generate_ticket


app = FastAPI(
    title="Online Housie",
    description="Online Multiplayer Housie Game",
    version="5.0.0"
)


# =====================================================
# STATIC FILES
# =====================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


templates = Jinja2Templates(
    directory="templates"
)


# =====================================================
# ROOMS
# =====================================================

rooms = {}


# =====================================================
# GENERATE 6 CHARACTER ROOM CODE
# =====================================================

def generate_room_code():

    characters = string.ascii_uppercase + string.digits

    while True:

        code = "".join(
            random.choices(
                characters,
                k=6
            )
        )

        if code not in rooms:
            return code


# =====================================================
# HOME PAGE
# =====================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# =====================================================
# CREATE ROOM
# =====================================================

@app.post("/create-room")
async def create_room():

    code = generate_room_code()

    rooms[code] = {

        "host": None,

        "players": [],

        "called_numbers": [],

        "current_number": None,

        "started": False,

        "auto_calling": False,

        "auto_call_task": None,

        "winners": {

            "early5": None,

            "row1": None,

            "row2": None,

            "row3": None,

            "fullhouse": None

        }

    }

    return {
        "room_code": code
    }


# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
async def health():

    return {
        "status": "online",
        "game": "Online Housie"
    }


# =====================================================
# AUTOMATIC NUMBER CALLER
# =====================================================

async def automatic_number_caller(room_code):

    while room_code in rooms:

        room = rooms[room_code]

        if not room.get(
            "auto_calling",
            False
        ):

            break

        available_numbers = [

            number

            for number in range(1, 91)

            if number not in room["called_numbers"]

        ]

        if not available_numbers:

            room["auto_calling"] = False

            await broadcast(
                room_code,
                {
                    "type": "game_finished"
                }
            )

            break

        number = random.choice(
            available_numbers
        )

        room["called_numbers"].append(
            number
        )

        room["current_number"] = number

        await broadcast(
            room_code,
            {
                "type": "number_called",

                "number": number,

                "called_numbers":
                    room["called_numbers"]
            }
        )

        await asyncio.sleep(5)


# =====================================================
# WEBSOCKET
# =====================================================

@app.websocket("/ws/{room_code}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_code: str
):

    await websocket.accept()

    room_code = room_code.upper().strip()

    # =================================================
    # CHECK ROOM
    # =================================================

    if room_code not in rooms:

        await websocket.send_json({

            "type": "error",

            "message":
                "Room does not exist."

        })

        await websocket.close()

        return

    room = rooms[room_code]

    player = None

    try:

        # =============================================
        # RECEIVE PLAYER NAME
        # =============================================

        player_data = await websocket.receive_json()

        player_name = str(
            player_data.get(
                "name",
                "Player"
            )
        ).strip()

        if not player_name:

            player_name = "Player"

        if len(player_name) > 20:

            player_name = player_name[:20]

        # =============================================
        # CREATE PLAYER
        # =============================================

        player = {

            "websocket":
                websocket,

            "name":
                player_name,

            "ticket":
                generate_ticket(),

            "is_host":
                False,

            # NEW:
            # Unique ID for this player.
            # Used to identify the sender of chat.
            "player_id":
                "".join(
                    random.choices(
                        string.ascii_letters +
                        string.digits,
                        k=16
                    )
                )

        }

        # =============================================
        # FIRST PLAYER = HOST
        # =============================================

        if room["host"] is None:

            room["host"] = player

            player["is_host"] = True

        room["players"].append(player)

        # =============================================
        # SEND JOINED
        # =============================================

        await websocket.send_json({

            "type":
                "joined",

            "room":
                room_code,

            "name":
                player_name,

            "is_host":
                player["is_host"],

            "ticket":
                player["ticket"],

            # NEW:
            "player_id":
                player["player_id"]

        })

        # =============================================
        # SEND CURRENT GAME STATE
        # =============================================

        await websocket.send_json({

            "type":
                "game_state",

            "started":
                room["started"],

            "current_number":
                room["current_number"],

            "called_numbers":
                room["called_numbers"],

            "winners":
                room["winners"]

        })

        # =============================================
        # UPDATE PLAYER LIST
        # =============================================

        await broadcast_players(
            room_code
        )

        # =============================================
        # MAIN WEBSOCKET LOOP
        # =============================================

        while True:

            data = await websocket.receive_json()

            action = data.get("action")

            # =========================================
            # START GAME
            # =========================================

            if action == "start":

                if player != room["host"]:

                    await websocket.send_json({

                        "type":
                            "error",

                        "message":
                            "Only the host can start the game."

                    })

                    continue

                # -------------------------------------
                # GAME ALREADY STARTED
                # -------------------------------------

                if room["started"]:

                    if not room.get(
                        "auto_calling",
                        False
                    ):

                        room["auto_calling"] = True

                        room["auto_call_task"] = (
                            asyncio.create_task(
                                automatic_number_caller(
                                    room_code
                                )
                            )
                        )

                        await broadcast(
                            room_code,
                            {
                                "type":
                                    "auto_calling_started"
                            }
                        )

                    continue

                # -------------------------------------
                # START GAME
                # -------------------------------------

                room["started"] = True

                room["auto_calling"] = True

                await broadcast(
                    room_code,
                    {
                        "type":
                            "game_started"
                    }
                )

                # -------------------------------------
                # START AUTOMATIC CALLING
                # -------------------------------------

                room["auto_call_task"] = (
                    asyncio.create_task(
                        automatic_number_caller(
                            room_code
                        )
                    )
                )

                await broadcast(
                    room_code,
                    {
                        "type":
                            "auto_calling_started"
                    }
                )

            # =========================================
            # STOP AUTOMATIC CALLING
            # =========================================

            elif action == "stop_calling":

                if player != room["host"]:

                    await websocket.send_json({

                        "type":
                            "error",

                        "message":
                            "Only the host can stop automatic calling."

                    })

                    continue

                room["auto_calling"] = False

                task = room.get(
                    "auto_call_task"
                )

                if task and not task.done():

                    task.cancel()

                room["auto_call_task"] = None

                await broadcast(
                    room_code,
                    {
                        "type":
                            "auto_calling_stopped"
                    }
                )

            # =========================================
            # CALL NUMBER
            # =========================================

            elif action == "call_number":

                if player != room["host"]:

                    await websocket.send_json({

                        "type":
                            "error",

                        "message":
                            "Only the host can call numbers."

                    })

                    continue

                if not room["started"]:

                    continue

                available_numbers = [

                    number

                    for number in range(1, 91)

                    if number not in room["called_numbers"]

                ]

                if not available_numbers:

                    await broadcast(
                        room_code,
                        {
                            "type":
                                "game_finished"
                        }
                    )

                    continue

                number = random.choice(
                    available_numbers
                )

                room["called_numbers"].append(
                    number
                )

                room["current_number"] = number

                await broadcast(
                    room_code,
                    {

                        "type":
                            "number_called",

                        "number":
                            number,

                        "called_numbers":
                            room["called_numbers"]

                    }
                )

           # =========================================
# CHAT
# =========================================

elif action == "chat":

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    if not message:
        continue

    if len(message) > 150:
        message = message[:150]

    # Send chat to every player in the room
    # including the sender.
    await broadcast(
        room_code,
        {
            "type": "chat",

            "name": player["name"],

            "message": message,

            # IMPORTANT:
            # This identifies who actually sent it.
            "sender": player["name"]
        }
    )
            # =========================================
            # CLAIM WIN
            # =========================================

            elif action == "claim_win":

                win_type = data.get(
                    "win_type"
                )

                marked_numbers = data.get(
                    "marked_numbers",
                    []
                )

                if room["winners"].get(
                    win_type
                ) is not None:

                    await websocket.send_json({

                        "type":
                            "win_error",

                        "message":
                            "This winning option has already been claimed."

                    })

                    continue

                result = validate_win(

                    player,

                    room,

                    win_type,

                    marked_numbers

                )

                if result["valid"]:

                    room["winners"][
                        win_type
                    ] = player["name"]

                    await broadcast(
                        room_code,
                        {

                            "type":
                                "win_claimed",

                            "name":
                                player["name"],

                            "win_type":
                                win_type,

                            "message":
                                result["message"],

                            "winners":
                                room["winners"]

                        }
                    )

                else:

                    await websocket.send_json({

                        "type":
                            "win_error",

                        "message":
                            result["message"]

                    })

    # =================================================
    # PLAYER DISCONNECTED
    # =================================================

    except WebSocketDisconnect:

        if player and player in room["players"]:

            room["players"].remove(player)

        # =============================================
        # HOST TRANSFER
        # =============================================

        if player == room["host"]:

            room["auto_calling"] = False

            task = room.get(
                "auto_call_task"
            )

            if task and not task.done():

                task.cancel()

            room["auto_call_task"] = None

            if room["players"]:

                room["host"] = room["players"][0]

                room["host"]["is_host"] = True

                await broadcast(
                    room_code,
                    {

                        "type":
                            "host_changed",

                        "name":
                            room["host"]["name"]

                    }
                )

            else:

                del rooms[room_code]

                return

        await broadcast_players(
            room_code
        )


# =====================================================
# VALIDATE WIN
# =====================================================

def validate_win(
    player,
    room,
    win_type,
    marked_numbers
):

    # =================================================
    # GAME START CHECK
    # =================================================

    if not room["started"]:

        return {

            "valid":
                False,

            "message":
                "Game has not started."

        }

    # =================================================
    # VALID TYPES
    # =================================================

    valid_types = [

        "early5",

        "row1",

        "row2",

        "row3",

        "fullhouse"

    ]

    if win_type not in valid_types:

        return {

            "valid":
                False,

            "message":
                "Invalid winning option."

        }

    # =================================================
    # CONVERT MARKED NUMBERS
    # =================================================

    try:

        marked = set(

            int(number)

            for number in marked_numbers

        )

    except Exception:

        return {

            "valid":
                False,

            "message":
                "Invalid marked numbers."

        }

    # =================================================
    # GET ALL TICKET NUMBERS
    # =================================================

    ticket_numbers = []

    for row in player["ticket"]:

        for number in row:

            if number is not None:

                ticket_numbers.append(
                    number
                )

    ticket_numbers = set(
        ticket_numbers
    )

    # =================================================
    # ONLY TICKET NUMBERS
    # =================================================

    if not marked.issubset(
        ticket_numbers
    ):

        return {

            "valid":
                False,

            "message":
                "Invalid ticket numbers."

        }

    # =================================================
    # ONLY CALLED NUMBERS
    # =================================================

    called = set(
        room["called_numbers"]
    )

    if not marked.issubset(
        called
    ):

        return {

            "valid":
                False,

            "message":
                "You marked a number that has not been called."

        }

    # =================================================
    # EARLY 5
    # =================================================

    if win_type == "early5":

        if len(marked) >= 5:

            return {

                "valid":
                    True,

                "message":
                    f"{player['name']} completed Early 5! 🎉"

            }

        return {

            "valid":
                False,

            "message":
                "You need at least 5 marked numbers."

        }

    # =================================================
    # ROW
    # =================================================

    if win_type in [

        "row1",

        "row2",

        "row3"

    ]:

        row_index = {

            "row1": 0,

            "row2": 1,

            "row3": 2

        }[win_type]

        row_numbers = {

            number

            for number in player[
                "ticket"
            ][row_index]

            if number is not None

        }

        if row_numbers.issubset(
            marked
        ):

            row_name = {

                "row1":
                    "First Row",

                "row2":
                    "Second Row",

                "row3":
                    "Third Row"

            }[win_type]

            return {

                "valid":
                    True,

                "message":
                    f"{player['name']} completed {row_name}! 🏆"

            }

        return {

            "valid":
                False,

            "message":
                "You have not completed this row."

        }

    # =================================================
    # FULL HOUSE
    # =================================================

    if win_type == "fullhouse":

        if ticket_numbers.issubset(
            marked
        ):

            return {

                "valid":
                    True,

                "message":
                    f"{player['name']} completed Full Housie! 🏆🎉"

            }

        return {

            "valid":
                False,

            "message":
                "You have not completed your Full Housie."

        }

    return {

        "valid":
            False,

        "message":
            "Invalid claim."

    }


# =====================================================
# PLAYER LIST
# =====================================================

async def broadcast_players(
    room_code
):

    if room_code not in rooms:

        return

    room = rooms[room_code]

    players = [

        {

            "name":
                player["name"],

            "is_host":
                player["is_host"]

        }

        for player in room["players"]

    ]

    await broadcast(
        room_code,
        {

            "type":
                "players",

            "players":
                players

        }
    )


# =====================================================
# BROADCAST
# =====================================================

async def broadcast(
    room_code,
    message
):

    if room_code not in rooms:

        return

    room = rooms[room_code]

    disconnected = []

    # IMPORTANT:
    # Send the SAME message to every connected
    # player in this room.

    for player in list(room["players"]):

        try:

            await player[
                "websocket"
            ].send_json(message)

        except Exception:

            disconnected.append(
                player
            )

    # Remove disconnected players

    for player in disconnected:

        if player in room["players"]:

            room["players"].remove(
                player
            )
