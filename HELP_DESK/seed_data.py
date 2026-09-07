from HELP_DESK.models import Ticket
from HELP_DESK.services import create_ticket


def seed_helpdesk(app) -> None:
    """Sample tickets. Accounts are seeded once by the root app for the whole system."""
    seed_sample_tickets()


def seed_sample_tickets() -> None:
    if Ticket.query.count() > 0:
        return

    create_ticket(
        {
            "category_key": "printer",
            "subject": "Finance printer will not print payment vouchers",
            "description": (
                "The shared printer shows documents queued but nothing prints. "
                "Restarting the printer did not help."
            ),
            "reporter_name": "Sample Officer Two",
            "reporter_email": "finance.officer@example.org",
            "department": "Finance Office",
            "location": "2nd Floor, Finance",
            "computer_name": "NGOB-PC-002",
        }
    )

    create_ticket(
        {
            "category_key": "no_internet",
            "subject": "No network connection after this morning's power cut",
            "description": (
                "The network icon shows no connection. The cable is plugged in and "
                "the colleague next to me has the same problem."
            ),
            "reporter_name": "Sample Officer One",
            "reporter_email": "ict.officer@example.org",
            "department": "ICT Department",
            "location": "1st Floor, ICT",
            "computer_name": "NGOB-PC-001",
        }
    )
