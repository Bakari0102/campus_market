"""Admin helper. Usage:
    python manage.py pending-vendors
    python manage.py verify-vendor business@example.com
Check the business's CAC record (CAC public search) BEFORE verifying."""
import sys

from data.database import init_db
from data.repositories import UserRepository, VendorRepository


def main(argv):
    init_db()
    vendors = VendorRepository()
    if argv[:1] == ["pending-vendors"]:
        for v in vendors.list_pending():
            print(f'{v["email"]:30} {v["business_name"]:25} CAC={v["cac_number"] or "-"} tel={v["phone"]}')
        return 0
    if len(argv) == 2 and argv[0] == "verify-vendor":
        user = UserRepository().get_by_email(argv[1].strip().lower())
        if not user or not vendors.set_verified(user["id"], True):
            print("No business account with that email.")
            return 1
        print(f'Verified: {argv[1]}')
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
