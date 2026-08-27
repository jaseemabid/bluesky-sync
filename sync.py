import itertools
import os
from datetime import datetime, timezone

from atproto import Client, models


def main():
    # Setup these in an `.env` file, shell env or github actions.
    LOGIN = os.environ["AT_LOGIN"]
    PASSWORD = os.environ["AT_PASSWORD"]
    CONFIG_FILE = os.environ.get("BSKY_SYNC_CONFIG_FILE", "accounts.txt")
    LISTS = [
        ("starter pack", os.environ["STARTER_PACK_URI"]),
        ("list", os.environ["LIST_URI"]),
    ]

    with open(CONFIG_FILE) as f:
        expected = set(line.strip() for line in f.readlines() if line.strip())

    client = Client()
    profile = client.login(LOGIN, PASSWORD)

    print(f"logged in as {profile.display_name}")

    for name, uri in LISTS:
        # Convert starter pack URI to sub-list URI if provided
        if "/app.bsky.graph.starterpack/" in uri:
            uri = client.app.bsky.graph.get_starter_pack({"starter_pack": uri, "limit": 100}).starter_pack.list.uri

        # List of members in the starter pack/list
        members = client.app.bsky.graph.get_list({"list": uri, "limit": 100})

        print()
        print(
            f"Found {members.list.list_item_count} users in {name}, expected {len(expected)}"
        )

        # 🔥 TODO: Paginate this, get users after first 100
        found = set(m.subject.handle for m in members.items)

        # Step 1: Log extra users
        unexpected = found - expected
        if unexpected:
            print(f"Ignoring {len(unexpected)} users not in text file: {(unexpected)}")

        # Step 2: Add missing users
        missing = expected - found
        if not missing:
            print("No new users to add, exiting")
            continue

        for batch in itertools.batched(missing, 25):
            print(f"Adding {len(batch)} users to the {name}: {batch}")

            # ✨ Neat API to get all the missing users in one request
            profiles = client.app.bsky.actor.get_profiles({"actors": list(batch)})

            # ✨ All new users are added to the list in a single API
            writes = [
                models.ComAtprotoRepoApplyWrites.Create(
                    collection="app.bsky.graph.listitem",
                    value={
                        "$type": "app.bsky.graph.listitem",
                        "subject": p["did"],
                        "list": uri,
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                    },
                )
                for p in profiles.profiles
            ]

            list_owner = members.list.creator.handle
            data = models.ComAtprotoRepoApplyWrites.Data(repo=list_owner, writes=writes)
            client.com.atproto.repo.apply_writes(data)


if __name__ == "__main__":
    main()
