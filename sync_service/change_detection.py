"""Diff computation between Nexudus snapshots and stored state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from sync_service.db.models import Member, Membership, Team


@dataclass
class MemberChange:
    member: Member
    change_type: str
    reason: str
    memberships: List[Membership]


class ChangeDetector:
    def __init__(self, existing_members: Dict[int, Member], existing_memberships: Dict[int, List[Membership]]):
        self.existing_members = existing_members
        self.existing_memberships = existing_memberships

    def detect(self, new_members: Iterable[Member], new_memberships: Dict[int, List[Membership]]) -> List[MemberChange]:
        changes: List[MemberChange] = []
        new_member_map = {member.id: member for member in new_members}

        for member_id, new_member in new_member_map.items():
            previous = self.existing_members.get(member_id)
            memberships = new_memberships.get(member_id, [])
            if not previous:
                changes.append(
                    MemberChange(
                        member=new_member,
                        change_type="create",
                        reason="new member discovered",
                        memberships=memberships,
                    )
                )
                continue
            if previous.payload_hash != new_member.payload_hash:
                changes.append(
                    MemberChange(
                        member=new_member,
                        change_type="update",
                        reason="member details changed",
                        memberships=memberships,
                    )
                )
                continue
            if previous.active and not new_member.active:
                changes.append(
                    MemberChange(
                        member=new_member,
                        change_type="deactivate",
                        reason="member cancelled",
                        memberships=memberships,
                    )
                )

        for member_id, member in self.existing_members.items():
            if member_id not in new_member_map:
                changes.append(
                    MemberChange(
                        member=member,
                        change_type="deactivate",
                        reason="member missing from latest snapshot",
                        memberships=self.existing_memberships.get(member_id, []),
                    )
                )

        return changes
