# ticket-booking
# Cinema Ticket Booking System

A lightweight cinema ticket booking application built with **Python, Flask, and Redis**. It demonstrates real-time seat availability, temporary seat reservations, automatic reservation expiration, and concurrency control to prevent double booking.

## Features

- **Movie Selection:** Browse available movies and their seating layouts.
- **Interactive Seat Selection:** View occupied and available seats.
- **Temporary Reservations:** Hold a seat for 2 minutes.
- **Concurrency Control:** Prevent multiple users from reserving the same seat using Redis atomic operations.
- **Automatic Expiration:** Release unconfirmed reservations automatically.
- **Booking Confirmation:** Convert temporary reservations into confirmed bookings.
- **Reservation Release:** Allow users to release their reservations.
- **Live Seat Updates:** Periodically refresh seat availability.
- **Countdown Timer:** Display the remaining reservation time.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | REST API |
| Redis | Reservation storage and concurrency control |
| HTML, CSS, JavaScript | Frontend |
| Docker Compose | Redis service management |
| Pytest | Testing |

## Architecture

```text
        User / Browser
              |
              v
      Frontend (HTML/CSS/JS)
              |
          HTTP / JSON
              |
              v
        Flask Backend
         (REST API)
              |
         Redis Client
              |
              v
            Redis
    (Seat Locks & Sessions)
```

## Booking Workflow

```text
       Available Seat
              |
              v
       Temporary Hold
         (120 sec)
              |
        +-----+------+
        |            |
        v            v
     Confirm       Release
        |            |
        v            v
    Confirmed     Available

Unconfirmed reservations automatically expire.
```

## Project Structure

```text
ticket-booking/
│
├── app.py
├── static/
│   └── index.html
├── tests/
├── .env.example
├── docker-compose.yaml
├── requirements.txt
├── LICENSE
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/varshith-jureddi/ticket-booking.git
cd ticket-booking
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows**
```bash
venv\Scripts\activate
```

**Linux / macOS**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```env
REDIS_URL=redis://localhost:6379/0
```

Note: The application reads environment variables from the process environment; `.env` loading is not automatic.

### 5. Start Redis

```bash
docker compose up -d
```

Verify Redis:

```bash
docker exec cinema-redis redis-cli ping
```

Expected output:

```text
PONG
```

### 6. Run the Application

```bash
python app.py
```

Open the application:

**http://127.0.0.1:8080**

Redis Commander is available at:

**http://localhost:8081**

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/movies` | Retrieve available movies |
| GET | `/movies/{movie_id}/seats` | Get occupied seats |
| POST | `/movies/{movie_id}/seats/{seat_id}/hold` | Temporarily reserve a seat |
| PUT | `/sessions/{session_id}/confirm` | Confirm a reservation |
| DELETE | `/sessions/{session_id}` | Release a reservation |

The API uses JSON for request and response bodies.

## How Double Booking Is Prevented

The application uses Redis atomic operations to ensure that only one user can acquire a particular seat.

```python
redis_client.set(
    key,
    booking_data,
    nx=True,
    ex=120
)
```

- `NX`: Creates the key only if it does not already exist.
- `EX`: Sets an expiration time of 120 seconds.

Redis executes this operation atomically, preventing competing requests from successfully reserving the same seat.

Confirmed reservations have their expiration removed.

## Running Tests

Run the test suite using Pytest:

```bash
python -m pytest -v
```

Ensure Redis is running before executing tests that require Redis.

## Future Improvements

- User authentication and authorization.
- Payment gateway integration.
- Persistent booking history using a database.
- Support for multiple cinemas and showtimes.
- Improved atomicity for multi-key Redis operations.
- WebSocket-based real-time seat updates.
- Automated CI/CD pipeline.

## License

This project is licensed under the [MIT License](LICENSE).

## Author

**Varshith Jureddi**

- GitHub: [@varshith-jureddi](https://github.com/varshith-jureddi)
- Repository: [Cinema Ticket Booking System](https://github.com/varshith-jureddi/ticket-booking)
