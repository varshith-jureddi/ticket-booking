from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
import redis
from redis.exceptions import RedisError

app = Flask(__name__, static_folder="static", static_url_path="")

HOLD_TTL_SECONDS = 2 * 60
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)

redis_client.ping()

print(f"Connected to Redis: {REDIS_URL}")
HOLD_TTL_SECONDS = 2 * 60
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# try:
#     redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
#     redis_client.ping()
#     print(f"Connected to Redis: {REDIS_URL}")
# except RedisError as exc:
#     raise RuntimeError(
#         f"Could not connect to Redis at {REDIS_URL}. "
#         "Start Redis and try again."
#     ) from exc

MOVIES = [
    {"id": "inception", "title": "Inception", "rows": 5, "seats_per_row": 8},
    {"id": "dune", "title": "Dune: Part Two", "rows": 4, "seats_per_row": 6},
]


class SeatAlreadyBooked(Exception):
    """Raised when another session already owns a seat."""


class SessionNotFound(Exception):
    """Raised when a session or its seat no longer exists."""


class SessionNotOwned(Exception):
    """Raised when a user tries to modify another user's session."""


def seat_key(movie_id: str, seat_id: str) -> str:
    return f"seat:{movie_id}:{seat_id}"


def session_key(session_id: str) -> str:
    return f"session:{session_id}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def booking_to_json(booking: dict[str, Any]) -> dict[str, Any]:
    """Return the public representation used by the API."""
    return {
        "id": booking["id"],
        "movie_id": booking["movie_id"],
        "seat_id": booking["seat_id"],
        "user_id": booking["user_id"],
        "status": booking["status"],
    }


def hold_seat(movie_id: str, seat_id: str, user_id: str) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    expires_at = now_utc() + timedelta(seconds=HOLD_TTL_SECONDS)

    booking = {
        "id": session_id,
        "movie_id": movie_id,
        "seat_id": seat_id,
        "user_id": user_id,
        "status": "held",
    }

    key = seat_key(movie_id, seat_id)

    # NX is the important part: only one concurrent request can acquire the seat.
    acquired = redis_client.set(
        key,
        __import__("json").dumps(booking),
        nx=True,
        ex=HOLD_TTL_SECONDS,
    )

    if not acquired:
        raise SeatAlreadyBooked

    # Reverse lookup: session ID -> seat key.
    redis_client.set(
        session_key(session_id),
        key,
        ex=HOLD_TTL_SECONDS,
    )

    return {
        **booking,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }


def parse_booking(value: str) -> dict[str, Any]:
    import json

    return json.loads(value)


def list_bookings(movie_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pattern = f"seat:{movie_id}:*"

    for key in redis_client.scan_iter(match=pattern):
        value = redis_client.get(key)
        if not value:
            continue
        try:
            result.append(parse_booking(value))
        except (ValueError, TypeError):
            continue

    return result


def get_session(session_id: str, user_id: str) -> tuple[dict[str, Any], str]:
    key = redis_client.get(session_key(session_id))
    if not key:
        raise SessionNotFound

    value = redis_client.get(key)
    if not value:
        # The seat hold may have expired before the reverse lookup expired.
        redis_client.delete(session_key(session_id))
        raise SessionNotFound

    try:
        booking = parse_booking(value)
    except (ValueError, TypeError) as exc:
        raise SessionNotFound from exc

    if booking.get("user_id") != user_id:
        raise SessionNotOwned

    return booking, key


def confirm_session(session_id: str, user_id: str) -> dict[str, Any]:
    booking, key = get_session(session_id, user_id)

    # Remove expiry from both keys so the confirmed reservation is permanent.
    redis_client.persist(key)
    redis_client.persist(session_key(session_id))

    booking["status"] = "confirmed"

    import json

    redis_client.set(key, json.dumps(booking))
    return booking


def release_session(session_id: str, user_id: str) -> None:
    _booking, key = get_session(session_id, user_id)
    redis_client.delete(key, session_key(session_id))


def find_movie(movie_id: str) -> dict[str, Any] | None:
    return next((movie for movie in MOVIES if movie["id"] == movie_id), None)


def error(message: str, status: int):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/movies")
def get_movies():
    return jsonify(MOVIES)


@app.get("/movies/<movie_id>/seats")
def get_seats(movie_id: str):
    if find_movie(movie_id) is None:
        return error("movie not found", 404)

    bookings = list_bookings(movie_id)
    seats = [
        {
            "seat_id": booking["seat_id"],
            "user_id": booking["user_id"],
            "booked": True,
            "confirmed": booking.get("status") == "confirmed",
        }
        for booking in bookings
    ]
    return jsonify(seats)


@app.post("/movies/<movie_id>/seats/<seat_id>/hold")
def hold(movie_id: str, seat_id: str):
    if find_movie(movie_id) is None:
        return error("movie not found", 404)

    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id:
        return error("user_id is required", 400)

    try:
        session = hold_seat(movie_id, seat_id, user_id)
    except SeatAlreadyBooked:
        return error("seat is already taken", 409)
    except RedisError:
        app.logger.exception("Redis error while holding seat")
        return error("booking service unavailable", 503)

    return (
        jsonify(
            {
                "session_id": session["id"],
                "movie_id": session["movie_id"],
                "seat_id": session["seat_id"],
                "expires_at": session["expires_at"],
            }
        ),
        201,
    )


@app.put("/sessions/<session_id>/confirm")
def confirm(session_id: str):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id:
        return error("user_id is required", 400)

    try:
        session = confirm_session(session_id, user_id)
    except SessionNotFound:
        return error("session not found or expired", 404)
    except SessionNotOwned:
        return error("session does not belong to this user", 403)
    except RedisError:
        app.logger.exception("Redis error while confirming session")
        return error("booking service unavailable", 503)

    return jsonify(
        {
            "session_id": session["id"],
            "movie_id": session["movie_id"],
            "seat_id": session["seat_id"],
            "user_id": session["user_id"],
            "status": session["status"],
        }
    )


@app.delete("/sessions/<session_id>")
def release(session_id: str):
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id:
        return error("user_id is required", 400)

    try:
        release_session(session_id, user_id)
    except SessionNotFound:
        return error("session not found or expired", 404)
    except SessionNotOwned:
        return error("session does not belong to this user", 403)
    except RedisError:
        app.logger.exception("Redis error while releasing session")
        return error("booking service unavailable", 503)

    return ("", 204)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
