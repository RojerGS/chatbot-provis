import flask
from flask import request
import json
import random

from proverbs import proverbs, difficulty_ratings
from utils import (
    load_user_data,
    save_user_data,
    get_random_string,
    create_logger,
    new_response,
    add_quick_replies,
    add_text,
    TEMPLATE_USER_DATA,
    BUFFER_SIZE_STEP,
)

# Quick replies
QR_PLAY = "Jogar 🎮"
QR_PLAY_AGAIN = "Jogar outro 🎮"
QR_HINT = "Pista 🔎"
QR_GIVE_UP = "Desistir 😢"
QR_PROGRESS = "Progresso 🥉🥈🥇"
QR_SUGGESTION = "Sugerir provérbio 👨‍🎓"
QR_GOODBYE = "Adeus! 👋"
QR_INSTRUCTIONS = "Instruções 📝"

# Replies for when the user gets the correct proverb.
CORRECT = [
    "Certo!",
    "Certíssimo!",
    "Correto!",
    "Acertaste!",
    "É isso mesmo!",
    "Mesmo na mouche!",
]

GIVE_UP = [
    "É uma pena desistires...",
    "Evita desistir ao máximo!",
    "Se for preciso, até podes pedir ajuda a amigos...",
]


def main_give_up(req):
    """Called when the user wants to give up on a given proverb."""

    resp = new_response()
    user_data = load_user_data(req)
    # If the user isn't trying to guess any proverb, the user can't give up
    if not user_data["finding_id"]:
        return add_quick_replies(
            resp,
            'Se não estás a tentar adivinhar nenhum provérbio, queres _"desistir"_ de quê?',
            [QR_PLAY, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE, QR_INSTRUCTIONS],
        )
    # If the user has found all other proverbs, don't let the user give up
    if len(user_data["found"]) == len(proverbs) - 1:
        return add_text(
            resp,
            "Só te falta mais este provérbio! Não podes desistir agora \U0001F4AA",
        )

    # Otherwise, stop signaling this proverb as the one being guessed
    seen = user_data.get("seen", [])  # Retrieve the `seen` list safely
    seen.append(user_data["finding_id"])  # as previous users may not have it
    user_data["seen"] = seen
    user_data["finding_id"] = 0
    user_data["emojis"] = ""
    save_user_data(req, user_data)

    reply = get_random_string(GIVE_UP)
    return add_quick_replies(
        resp,
        reply,
        [QR_PLAY_AGAIN, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE, QR_INSTRUCTIONS],
    )


def main_hint(req):
    """Called when the user asks for a hint on a given proverb."""

    resp = new_response()
    user_data = load_user_data(req)
    if finding_id := user_data["finding_id"]:
        hint = proverbs[finding_id]["hint"]
        if not hint:
            return add_quick_replies(
                resp,
                "Woops, para este provérbio não tenho nenhuma dica... Desculpa!",
                [
                    QR_GIVE_UP,
                    QR_PROGRESS,
                    QR_SUGGESTION,
                    QR_GOODBYE,
                    QR_INSTRUCTIONS,
                ],
            )

        if user_data["hint_given"]:
            resp = add_text(resp, f"A dica que tenho para te dar é: {hint}")
            return add_quick_replies(
                resp,
                "Mas já to tinha dito!",
                [
                    QR_GIVE_UP,
                    QR_PROGRESS,
                    QR_SUGGESTION,
                    QR_GOODBYE,
                    QR_INSTRUCTIONS,
                ],
            )
        else:
            user_data["hint_given"] = True
            user_data["hints_given"] += 1
            save_user_data(req, user_data)
            return add_quick_replies(
                resp,
                f"A dica que tenho para ti é: {hint}",
                [
                    QR_GIVE_UP,
                    QR_PROGRESS,
                    QR_SUGGESTION,
                    QR_GOODBYE,
                    QR_INSTRUCTIONS,
                ],
            )

    else:
        # The user isn't trying to guess a proverb!
        return add_quick_replies(
            resp,
            "Se não estás a adivinhar nenhum provérbio, queres uma pista de quê?",
            [QR_INSTRUCTIONS, QR_PLAY, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE],
        )


def main_progress(req):
    """Called when the user asks for its progress."""

    user_data = load_user_data(req)
    # List all the IDs that haven't been found yet
    to_be_found = [id for id in proverbs.keys() if id not in user_data["found"]]
    nfound = len(proverbs.keys()) - len(to_be_found)

    if to_be_found == 0:
        msg = f"Já acertaste todos ({nfound}) os provérbios!"
    else:
        if nfound == 0:
            msg = "Ainda não acertaste nenhum provérbio..."
        else:
            # Check if we should use an 's' for the plural
            s = "s" if nfound != 1 else ""
            msg = (
                f"Já acertaste {nfound} provérbio{s} "
                + f"e faltam-te {len(to_be_found)}!"
            )

    return add_quick_replies(
        new_response(),
        msg,
        [QR_PLAY, QR_SUGGESTION, QR_GOODBYE, QR_INSTRUCTIONS],
    )


def main_make_suggestion(req):
    """Called when the user wants to make a new suggestion."""
    # (TODO)
    return new_response()


def main_play(req):
    """Called when the user wants to play."""

    resp = new_response()
    user_data = load_user_data(req)
    finding_id = user_data.get("finding_id", 0)

    if finding_id:
        emojis = user_data["emojis"]
        resp = add_text(resp, emojis)
        return add_quick_replies(
            resp,
            "Se estiver a ficar difícil podes desistir ou pedir uma pista!",
            [
                QR_HINT,
                QR_GIVE_UP,
                QR_PROGRESS,
                QR_SUGGESTION,
                QR_GOODBYE,
                QR_INSTRUCTIONS,
            ],
        )

    buff_size = user_data.get("buffer_size", TEMPLATE_USER_DATA["buffer_size"])
    # Retrieve as many proverbs as the user can see, as defined by the buffer.
    found = user_data.get("found", [])
    to_be_found = [id for id in difficulty_ratings if id not in found]
    rotation = to_be_found[:buff_size]
    # Then check what is the next unseen proverb that is available
    seen = user_data.get("seen", [])
    to_be_seen = [id for id in rotation if id not in seen]

    if not to_be_found:
        return add_quick_replies(
            resp,
            "Já descobriste todos os provérbios!",
            [QR_SUGGESTION, QR_GOODBYE],
        )

    # Determine if we will start another cycle over some proverbs
    elif not to_be_seen:
        # Increase the buffer size only if it is not already too large;
        # give some extra room in case new proverbs are added to the game later.
        if buff_size <= len(to_be_found):
            buff_size += BUFFER_SIZE_STEP
            user_data["buffer_size"] = buff_size
        to_be_seen = to_be_found[:buff_size]  # no need to redefine `rotation`
        user_data["seen"] = []

        resp = add_text(
            resp,
            "Já te mostrei alguns provérbios diferentes, agora vou começar "
            "a repeti-los, ok? Se estiveres mesmo com dificuldades, pede "
            "ajuda a alguém que esteja por perto \U0001F60E... "
            "Ou pede-me uma pista!",
        )
        # Tell the player if there are other proverbs the player won't see yet
        if len(to_be_found) > len(to_be_seen):
            resp = add_text(
                resp,
                "Assim que fizeres mais algum progresso posso começar "
                "a mostrar outros provérbios ainda mais difíceis!",
            )

    proverb_id = to_be_seen[0]
    proverb = proverbs[proverb_id]
    user_data["emojis"] = proverb["emojis"]
    user_data["finding_id"] = proverb_id
    user_data["hint_given"] = False
    save_user_data(req, user_data)

    return add_quick_replies(
        resp,
        proverb["emojis"],
        [QR_GIVE_UP, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE, QR_INSTRUCTIONS],
    )


def check_proverb(req):
    """Check if the proverb the user said is correct or not."""

    resp = new_response()
    user_data = load_user_data(req)
    finding_id = user_data.setdefault("finding_id", 0)

    if not finding_id:
        resp = add_text(
            resp, "Para tentares adivinhar um provérbio, escreve 'jogar'!"
        )
        return add_quick_replies(
            resp,
            "Ou escolhe qualquer uma das outras opções...",
            [QR_PLAY, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE, QR_INSTRUCTIONS],
        )

    intent_name = req["queryResult"]["intent"]["displayName"]

    # Get the proverb the player is trying to guess and check for correct guess
    proverb = proverbs[finding_id]
    # If the intents match, the player got it right!
    if intent_name == proverb["intent"]:
        found = user_data.setdefault("found", [])
        found.append(finding_id)
        user_data["found"] = found
        user_data["finding_id"] = None
        user_data["emojis"] = ""
        user_data["hint_given"] = False
        save_user_data(req, user_data)

        return add_quick_replies(
            resp,
            get_random_string(CORRECT),
            [QR_PLAY_AGAIN, QR_PROGRESS, QR_SUGGESTION, QR_GOODBYE],
        )

    else:
        resp = add_text(resp, "Woops, erraste...")
        return add_quick_replies(
            resp,
            "Tenta outra vez!",
            [
                QR_HINT,
                QR_GIVE_UP,
                QR_PROGRESS,
                QR_SUGGESTION,
                QR_GOODBYE,
                QR_INSTRUCTIONS,
            ],
        )


logger = create_logger("proverbs", "proverbios.log")


def webhook():
    """Entry point from the main flask server."""

    req_json = request.json

    # Log the request
    logger.debug(json.dumps(req_json))

    # Fetch the intent name
    intent_name = req_json["queryResult"]["intent"]["displayName"]
    logger.debug(f"Got intent '{intent_name}'")

    # Map some intents to some handlers
    intent_mapping = {
        "main_play": main_play,
        "main_give_up": main_give_up,
        "main_hint": main_hint,
        "main_progress": main_progress,
        "main_make_suggestion": main_make_suggestion,
    }

    if intent_name in intent_mapping:
        func = intent_mapping[intent_name]
        req_json = func(req_json)
    elif intent_name.startswith("proverb_"):
        req_json = check_proverb(req_json)

    return flask.jsonify(req_json)
